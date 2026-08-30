"""Sponsored King-of-the-Wall contests.

This router is intentionally isolated from the legacy paid wall. Sponsored events and
direct takeovers can coexist without sharing state machines or payment records.
"""
import asyncio
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import socket
import ipaddress
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import httpx

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from core import ai, payments, providers
from core.db import get_db
from core.money import fmt

router = APIRouter(prefix="/api")
ROUND_REVEAL, ROUND_VOTE, ROUND_PANEL, ROUND_RESULT = 45, 90, 25, 20
ROUND_SECONDS = ROUND_REVEAL + ROUND_VOTE + ROUND_PANEL + ROUND_RESULT
CONSTRAINTS = [
    "Sell it without saying what it is.", "Make it sound almost illegal.",
    "Use exactly seven words in the headline.", "Sell it to someone from 1890.",
    "Turn its weakest feature into the reason to buy.", "Sell it as a breakup recovery device.",
    "Write the ad using a customer objection.", "Make the product the villain.",
    "Sell it to someone who hates advertising.", "Make one honest promise and nothing else.",
]
TEMPLATES = ["type_monument", "product_evidence", "classified_panic"]
INKS = ["tomato", "mustard", "teal"]
ARCHETYPES = [
    "budget skeptic", "early adopter", "busy parent", "privacy-conscious buyer",
    "brand loyalist", "impulse shopper", "accessibility advocate", "technical evaluator",
    "sustainability-focused buyer", "advertising cynic",
]


def now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else value


def admin_required(password):
    if not os.environ.get("ADMIN_PASSWORD") or password != os.environ.get("ADMIN_PASSWORD"):
        raise HTTPException(401, "Wrong password. The wall does not know you.")


def slugify(value):
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")[:48] or "campaign"
    return base + "-" + uuid.uuid4().hex[:5]


def safe_url(value):
    parsed = urlparse(value or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or host in ("localhost", "127.0.0.1", "::1"):
        raise HTTPException(400, "Use a public HTTPS product address.")
    if host.endswith(".local") or re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", host):
        raise HTTPException(400, "Private network addresses cannot be advertised.")
    return value.strip()


async def verify_destination(value):
    url = safe_url(value)
    host = urlparse(url).hostname
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
        for item in addresses:
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                raise HTTPException(400, "Product addresses must resolve to the public internet.")
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.head(url, headers={"User-Agent": "TheLastBillboard-LinkVerifier/1.0"})
        if 300 <= response.status_code < 400:
            raise HTTPException(400, "Product links may not redirect. Submit the final destination.")
        if response.status_code >= 400 and response.status_code not in (403, 405):
            raise HTTPException(400, "The product link could not be verified.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "The product link could not be verified.")
    return url


def session_token(request: Request):
    raw = request.cookies.get("lb_audience", "")
    secret = os.environ.get("SESSION_SECRET") or os.environ.get("ADMIN_PASSWORD") or "billboard-dev-session"
    if "." in raw:
        sid, signature = raw.rsplit(".", 1)
        expected = hmac.new(secret.encode(), sid.encode(), hashlib.sha256).hexdigest()[:24]
        if hmac.compare_digest(signature, expected):
            return raw, sid, False
    sid = secrets.token_urlsafe(18)
    signature = hmac.new(secret.encode(), sid.encode(), hashlib.sha256).hexdigest()[:24]
    return sid + "." + signature, sid, True


def set_session(response, token, fresh):
    if fresh:
        response.set_cookie("lb_audience", token, max_age=60 * 60 * 24 * 30,
                            httponly=True, samesite="lax", secure=os.environ.get("COOKIE_SECURE", "1") == "1")
    return response


def clean_doc(doc, private=False):
    if not doc:
        return None
    hidden = {"_id", "sponsor_email", "creator_email", "session_hash", "ip_hash",
              "razorpay_order_id", "razorpay_payment_id", "billing"}
    out = {}
    for key, value in doc.items():
        if key == "_id" or (not private and key in hidden):
            continue
        if isinstance(value, datetime):
            value = iso(value)
        out[key] = value
    return out


def round_phase(doc):
    if doc.get("status") == "complete":
        return "complete", 0
    started = doc.get("started_at")
    if not started:
        return "waiting", ROUND_SECONDS
    elapsed = max(0, int((now() - started).total_seconds()))
    if elapsed < ROUND_REVEAL:
        return "reveal", ROUND_REVEAL - elapsed
    if elapsed < ROUND_REVEAL + ROUND_VOTE:
        return "voting", ROUND_REVEAL + ROUND_VOTE - elapsed
    if elapsed < ROUND_REVEAL + ROUND_VOTE + ROUND_PANEL:
        return "panel", ROUND_REVEAL + ROUND_VOTE + ROUND_PANEL - elapsed
    if elapsed < ROUND_SECONDS:
        return "result", ROUND_SECONDS - elapsed
    return "expired", 0


def compute_score(king_votes, challenger_votes, king_clicks, challenger_clicks):
    votes = king_votes + challenger_votes
    vote_king = king_votes / votes if votes else 0.5
    clicks = king_clicks + challenger_clicks
    click_king = king_clicks / clicks if clicks else 0.5
    king = round(100 * (0.7 * vote_king + 0.3 * click_king), 2)
    challenger = round(100 - king, 2)
    return {"king": king, "challenger": challenger,
            "vote_share": {"king": round(vote_king * 100, 2), "challenger": round((1 - vote_king) * 100, 2)},
            "click_share": {"king": round(click_king * 100, 2), "challenger": round((1 - click_king) * 100, 2)}}


async def round_counts(db, round_id):
    pipeline = [{"$match": {"round_id": round_id}}, {"$group": {"_id": "$side", "count": {"$sum": 1}}}]
    votes = {r["_id"]: r["count"] async for r in db.votes.aggregate(pipeline)}
    clicks = {r["_id"]: r["count"] async for r in db.tracked_clicks.aggregate(pipeline)}
    return votes, clicks


async def finish_round(db, doc):
    if not doc or doc.get("status") == "complete":
        return doc
    votes, clicks = await round_counts(db, doc["id"])
    kv, cv = votes.get("king", 0), votes.get("challenger", 0)
    kc, cc = clicks.get("king", 0), clicks.get("challenger", 0)
    score = compute_score(kv, cv, kc, cc)
    challenger_wins = score["challenger"] > score["king"] or (
        score["challenger"] == score["king"] and cv > kv
    )
    winner_id = doc["challenger_id"] if challenger_wins else doc["king_id"]
    loser_id = doc["king_id"] if challenger_wins else doc["challenger_id"]
    update = {"status": "complete", "finished_at": now(), "winner_id": winner_id,
              "loser_id": loser_id, "scores": score,
              "counts": {"votes": {"king": kv, "challenger": cv}, "clicks": {"king": kc, "challenger": cc}}}
    result = await db.rounds.find_one_and_update({"id": doc["id"], "status": {"$ne": "complete"}}, {"$set": update})
    if result is None:
        return await db.rounds.find_one({"id": doc["id"]})
    await db.submissions.update_one({"id": loser_id}, {"$set": {"status": "lost"}})
    await db.submissions.update_one({"id": winner_id}, {"$set": {"status": "won"}})
    event = await db.events.find_one({"id": doc["event_id"]})
    queue = list(event.get("queue") or [])
    next_index = int(event.get("queue_index", 1)) + 1
    if next_index < len(queue):
        challenger = queue[next_index]
        next_round = {"id": "rnd_" + uuid.uuid4().hex[:12], "event_id": event["id"],
                      "campaign_id": event["campaign_id"], "number": int(doc.get("number", 1)) + 1,
                      "king_id": winner_id, "challenger_id": challenger, "status": "live",
                      "started_at": now(), "created_at": now()}
        await db.rounds.insert_one(next_round)
        await db.events.update_one({"id": event["id"]}, {"$set": {"current_round_id": next_round["id"],
            "king_id": winner_id, "queue_index": next_index}})
        await db.submissions.update_one({"id": challenger}, {"$set": {"status": "competing"}})
    else:
        await db.events.update_one({"id": event["id"]}, {"$set": {"status": "completed", "king_id": winner_id,
            "completed_at": now()}})
        await db.campaigns.update_one({"id": event["campaign_id"]}, {"$set": {"status": "completed", "winner_id": winner_id}})
        await db.prize_payouts.update_one({"campaign_id": event["campaign_id"]}, {"$set": {"winner_id": winner_id}}, upsert=True)
    return await db.rounds.find_one({"id": doc["id"]})


async def event_payload(db, slug):
    event = await db.events.find_one({"slug": slug})
    if not event:
        raise HTTPException(404, "No such event.")
    campaign = await db.campaigns.find_one({"id": event["campaign_id"]})
    current = await db.rounds.find_one({"id": event.get("current_round_id")}) if event.get("current_round_id") else None
    if current and round_phase(current)[0] == "expired":
        await finish_round(db, current)
        event = await db.events.find_one({"id": event["id"]})
        current = await db.rounds.find_one({"id": event.get("current_round_id")}) if event.get("current_round_id") else current
    ads = {}
    if current:
        for ident in (current.get("king_id"), current.get("challenger_id")):
            sub = await db.submissions.find_one({"id": ident})
            if sub:
                ads[ident] = clean_doc(sub)
    phase, remaining = round_phase(current or {})
    public_round = clean_doc(current)
    if public_round:
        public_round["phase"] = phase
        public_round["remaining_seconds"] = remaining
        if phase not in ("result", "complete"):
            public_round.pop("scores", None)
            public_round.pop("counts", None)
    return {"event": clean_doc(event), "campaign": clean_doc(campaign), "round": public_round,
            "ads": ads, "server_now": iso(now())}


class CampaignIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=80)
    product_name: str = Field(min_length=2, max_length=80)
    product_description: str = Field(min_length=10, max_length=800)
    product_url: str = Field(max_length=500)
    product_image_url: str = Field(max_length=500)
    logo_url: str = Field(default="", max_length=500)
    target_customer: str = Field(min_length=3, max_length=400)
    brief: str = Field(min_length=10, max_length=1000)
    prohibited_claims: str = Field(default="", max_length=600)
    disclosure: str = Field(default="", max_length=300)
    sponsor_email: str = Field(min_length=5, max_length=160)
    event_at: datetime
    duration_minutes: int = Field(default=30, ge=12, le=180)
    platform_fee_paise: int = Field(default=500000, ge=100)
    prize_paise: int = Field(default=2500000, ge=100)


class SponsorVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class GenerateIn(BaseModel):
    creator_name: str = Field(min_length=1, max_length=40)
    creator_email: str = Field(min_length=5, max_length=160)
    angle: str = Field(min_length=5, max_length=500)
    model_id: str | None = None


class SubmitIn(BaseModel):
    generation_id: str
    concept_index: int = Field(ge=0, le=2)
    headline: str | None = Field(default=None, max_length=100)


class VoteIn(BaseModel):
    side: str


class ModelIn(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    provider: str = Field(default="nebius", max_length=40)
    label: str = Field(min_length=2, max_length=100)
    model: str = Field(min_length=2, max_length=160)
    base_url: str = Field(min_length=8, max_length=500)
    credential_env: str = Field(min_length=2, max_length=80)
    enabled: bool = True


@router.post("/sponsors/campaigns")
async def create_campaign(body: CampaignIn):
    db = get_db()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.sponsor_email):
        raise HTTPException(400, "Use a valid sponsor email.")
    data = body.model_dump()
    data["product_url"] = await verify_destination(data["product_url"])
    data["product_image_url"] = safe_url(data["product_image_url"])
    if data.get("logo_url"):
        data["logo_url"] = safe_url(data["logo_url"])
    ident = "cmp_" + uuid.uuid4().hex[:12]
    doc = {**data, "id": ident, "slug": slugify(body.product_name), "status": "payment_pending",
           "total_paise": body.platform_fee_paise + body.prize_paise, "created_at": now(),
           "payment": {}}
    await db.campaigns.insert_one(doc)
    return {"id": ident, "slug": doc["slug"], "status": doc["status"],
            "total_paise": doc["total_paise"], "total_label": fmt(doc["total_paise"], "INR")}


@router.post("/sponsors/campaigns/{campaign_id}/checkout")
async def campaign_checkout(campaign_id: str):
    db = get_db()
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        raise HTTPException(404, "No such campaign.")
    if campaign.get("status") not in ("payment_pending", "draft"):
        raise HTTPException(409, "This campaign has already left checkout.")
    if not payments.configured():
        await db.campaigns.update_one({"id": campaign_id}, {"$set": {"status": "pending_review", "payment.mode": "manual"}})
        return {"mode": "manual", "status": "pending_review"}
    order = await asyncio.to_thread(payments.create_order, int(campaign["total_paise"]), "sponsor_" + campaign_id[-12:],
                                    {"kind": "sponsored_event", "campaign_id": campaign_id})
    await db.campaigns.update_one({"id": campaign_id}, {"$set": {"razorpay_order_id": order["id"]}})
    return {"mode": "checkout", "order_id": order["id"], "amount_paise": order["amount"],
            "currency": "INR", "key_id": payments.key_id(), "campaign_id": campaign_id}


@router.post("/sponsors/campaigns/{campaign_id}/verify")
async def campaign_verify(campaign_id: str, body: SponsorVerifyIn):
    db = get_db()
    campaign = await db.campaigns.find_one({"id": campaign_id, "razorpay_order_id": body.razorpay_order_id})
    if not campaign:
        raise HTTPException(404, "No matching sponsor order.")
    if not payments.verify_payment_signature(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "That payment does not check out.")
    await db.campaigns.update_one({"id": campaign_id}, {"$set": {"status": "pending_review",
        "razorpay_payment_id": body.razorpay_payment_id, "payment.status": "paid", "paid_at": now()}})
    await db.prize_payouts.update_one({"campaign_id": campaign_id}, {"$set": {"campaign_id": campaign_id,
        "amount_paise": campaign["prize_paise"], "status": "unclaimed", "created_at": now()}}, upsert=True)
    return {"ok": True, "status": "pending_review"}


@router.get("/campaigns/{slug}")
async def get_campaign(slug: str):
    db = get_db()
    campaign = await db.campaigns.find_one({"slug": slug, "status": {"$in": ["approved", "submissions_open", "scheduled", "live", "completed", "archived"]}})
    if not campaign:
        raise HTTPException(404, "This campaign is not open.")
    models = [providers.public_model(m) for m in await providers.enabled_models(db)]
    event = await db.events.find_one({"campaign_id": campaign["id"]})
    return {"campaign": clean_doc(campaign), "models": models, "event_slug": event.get("slug") if event else None}


def fallback_concepts(campaign, angle, constraint, model):
    product = campaign["product_name"]
    seeds = [
        (angle.upper()[:88], "The shortest route from curiosity to " + product + ".", "Make the claim impossible to ignore."),
        (("YOU DO NOT NEED " + product).upper()[:88], "Until the moment you try it.", "Use resistance as the opening."),
        ((product + " HAS ENTERED THE CHAT").upper()[:88], angle[:120], "Let the product interrupt the category."),
    ]
    return [{"headline": h, "supporting_line": s, "benefit": campaign["product_description"][:140],
             "cta": "SEE THE PRODUCT", "template": TEMPLATES[i], "ink": INKS[i],
             "composition": ["oversized_type", "product_right", "classified_stack"][i],
             "crop": "hard_square", "image_treatment": "product_cutout", "rationale": r,
             "constraint_check": "Built for: " + constraint,
             "model": providers.public_model(model)} for i, (h, s, r) in enumerate(seeds)]


@router.post("/campaigns/{campaign_id}/generate")
async def generate_concepts(campaign_id: str, body: GenerateIn, request: Request):
    db = get_db()
    campaign = await db.campaigns.find_one({"id": campaign_id, "status": {"$in": ["approved", "submissions_open", "scheduled"]}})
    if not campaign:
        raise HTTPException(404, "This campaign is not taking entries.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body.creator_email):
        raise HTTPException(400, "Use a valid creator email.")
    mod = await ai.moderate(body.angle, body.creator_name)
    if not mod["allow"]:
        raise HTTPException(422, ai.BLOCK_COPY)
    model = await providers.get_model(db, body.model_id)
    constraint = random.choice(CONSTRAINTS)
    system = """You are the creative department for a public billboard contest. Return JSON with key concepts, exactly three items. Each item must contain headline, supporting_line, benefit, cta, template, ink, composition, crop, image_treatment, rationale, constraint_check. Templates: type_monument, product_evidence, classified_panic. Inks: tomato, mustard, teal. No unverifiable claims. Headlines max 12 words. No markdown."""
    try:
        result = await providers.chat_json(db, model, system=system, payload={
            "product": campaign["product_name"], "description": campaign["product_description"],
            "target_customer": campaign["target_customer"], "brief": campaign["brief"],
            "prohibited_claims": campaign.get("prohibited_claims"), "required_disclosure": campaign.get("disclosure"),
            "creator_angle": body.angle, "creative_constraint": constraint,
        }, purpose="contest_concepts")
        concepts = result.get("concepts") if isinstance(result, dict) else None
        if not isinstance(concepts, list) or len(concepts) != 3:
            raise providers.ProviderError("Expected three concepts.")
        for i, concept in enumerate(concepts):
            concept["template"] = concept.get("template") if concept.get("template") in TEMPLATES else TEMPLATES[i]
            concept["ink"] = concept.get("ink") if concept.get("ink") in INKS else INKS[i]
            for key, limit in {"headline": 100, "supporting_line": 180, "benefit": 180, "cta": 40,
                               "composition": 40, "crop": 40, "image_treatment": 60,
                               "rationale": 240, "constraint_check": 240}.items():
                concept[key] = str(concept.get(key) or "")[:limit]
            concept["model"] = providers.public_model(model)
    except Exception:
        concepts = fallback_concepts(campaign, body.angle, constraint, model)
    token, sid, fresh = session_token(request)
    gen_id = "gen_" + uuid.uuid4().hex[:12]
    await db.submission_generations.insert_one({"id": gen_id, "campaign_id": campaign_id,
        "creator_name": body.creator_name.strip(), "creator_email": body.creator_email.strip().lower(),
        "angle": body.angle.strip(), "constraint": constraint, "concepts": concepts,
        "session_hash": hashlib.sha256(sid.encode()).hexdigest(), "created_at": now(), "expires_at": now() + timedelta(hours=24)})
    response = JSONResponse({"generation_id": gen_id, "constraint": constraint, "concepts": concepts})
    return set_session(response, token, fresh)


@router.post("/campaigns/{campaign_id}/submissions")
async def submit_concept(campaign_id: str, body: SubmitIn, request: Request):
    db = get_db()
    token, sid, fresh = session_token(request)
    generation = await db.submission_generations.find_one({"id": body.generation_id, "campaign_id": campaign_id,
        "session_hash": hashlib.sha256(sid.encode()).hexdigest(), "expires_at": {"$gt": now()}})
    if not generation:
        raise HTTPException(404, "That creative session has expired.")
    concept = dict(generation["concepts"][body.concept_index])
    if body.headline:
        concept["headline"] = body.headline.strip()
    mod = await ai.moderate(concept.get("headline", ""), generation["creator_name"])
    if not mod["allow"]:
        raise HTTPException(422, ai.BLOCK_COPY)
    ident = "ad_" + uuid.uuid4().hex[:12]
    doc = {"id": ident, "campaign_id": campaign_id, "creator_name": generation["creator_name"],
        "creator_email": generation["creator_email"], "angle": generation["angle"],
        "constraint": generation["constraint"], "creative": concept, "status": "submitted",
        "created_at": now(), "session_hash": hashlib.sha256(sid.encode()).hexdigest()}
    await db.submissions.insert_one(doc)
    response = JSONResponse({"id": ident, "status": "submitted", "copy": "Your ad is at the paste table."})
    return set_session(response, token, fresh)


@router.get("/events/{slug}")
async def get_event(slug: str):
    return await event_payload(get_db(), slug)


@router.get("/events/{slug}/stream")
async def event_stream(slug: str, request: Request):
    async def events():
        last = None
        while not await request.is_disconnected():
            try:
                payload = await event_payload(get_db(), slug)
                encoded = json.dumps(payload, default=str, separators=(",", ":"))
                if encoded != last:
                    yield "event: state\ndata: " + encoded + "\n\n"
                    last = encoded
                else:
                    yield ": keepalive\n\n"
            except Exception as exc:
                yield "event: error\ndata: " + json.dumps({"error": str(exc)}) + "\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/rounds/{round_id}/vote")
async def vote(round_id: str, body: VoteIn, request: Request):
    if body.side not in ("king", "challenger"):
        raise HTTPException(400, "Choose one side.")
    db = get_db()
    round_doc = await db.rounds.find_one({"id": round_id, "status": "live"})
    if not round_doc or round_phase(round_doc)[0] != "voting":
        raise HTTPException(409, "Voting is closed.")
    token, sid, fresh = session_token(request)
    sid_hash = hashlib.sha256(sid.encode()).hexdigest()
    try:
        await db.votes.insert_one({"id": uuid.uuid4().hex, "round_id": round_id, "side": body.side,
            "session_hash": sid_hash, "created_at": now()})
    except Exception:
        raise HTTPException(409, "This audience ticket has already voted.")
    response = JSONResponse({"ok": True, "side": body.side})
    return set_session(response, token, fresh)


@router.get("/rounds/{round_id}/out/{ad_id}")
async def tracked_out(round_id: str, ad_id: str, request: Request):
    db = get_db()
    doc = await db.rounds.find_one({"id": round_id})
    if not doc or ad_id not in (doc.get("king_id"), doc.get("challenger_id")):
        raise HTTPException(404, "No such ad in this round.")
    event = await db.events.find_one({"id": doc["event_id"]})
    campaign = await db.campaigns.find_one({"id": event["campaign_id"]})
    side = "king" if ad_id == doc["king_id"] else "challenger"
    token, sid, fresh = session_token(request)
    try:
        await db.tracked_clicks.insert_one({"id": uuid.uuid4().hex, "round_id": round_id, "ad_id": ad_id,
            "side": side, "session_hash": hashlib.sha256(sid.encode()).hexdigest(), "created_at": now()})
    except Exception:
        pass
    response = RedirectResponse(campaign["product_url"], status_code=302)
    return set_session(response, token, fresh)


def fallback_personas(round_doc, ads):
    output = []
    for i in range(100):
        archetype = ARCHETYPES[i % len(ARCHETYPES)]
        side = "king" if i % 3 else "challenger"
        creative = ads[round_doc[side + "_id"]]["creative"]
        base = 48 + ((i * 17) % 45)
        output.append({"id": i + 1, "archetype": archetype, "favored": side,
            "reaction": ("I remember the headline. " if base > 70 else "I understand it, but I am not convinced. ") + creative.get("headline", "")[:70],
            "ratings": {"attention": base, "clarity": 55 + (i * 7) % 40, "desire": 42 + (i * 11) % 50,
                "trust": 50 + (i * 5) % 42, "originality": 54 + (i * 13) % 42, "brand_fit": 57 + (i * 3) % 38}})
    return output


async def run_ai_audience(run_id: str):
    db = get_db()
    run = await db.ai_audience_runs.find_one({"id": run_id})
    round_doc = await db.rounds.find_one({"id": run["round_id"]})
    ads = {}
    for side in ("king", "challenger"):
        ads[round_doc[side + "_id"]] = await db.submissions.find_one({"id": round_doc[side + "_id"]})
    models = await providers.enabled_models(db)
    people = []
    errors = []
    system = """You simulate a clearly labeled synthetic customer panel for an advertising game. Return JSON with key people containing exactly 10 reactions. Each reaction: archetype, favored (king or challenger), reaction (max 22 words), ratings with attention, clarity, desire, trust, originality, brand_fit integers 0-100. Be varied, specific, and avoid demographic stereotypes. No markdown."""
    async def batch(index):
        model = models[index % len(models)]
        archetypes = [ARCHETYPES[(index + j) % len(ARCHETYPES)] for j in range(10)]
        try:
            data = await providers.chat_json(db, model, system=system, payload={"archetypes": archetypes,
                "king": clean_doc(ads[round_doc["king_id"]]), "challenger": clean_doc(ads[round_doc["challenger_id"]])},
                purpose="ai_audience", timeout=50)
            rows = data.get("people") or []
            if len(rows) != 10:
                raise ValueError("expected ten people")
            for row in rows:
                row["model"] = providers.public_model(model)
            return rows
        except Exception as exc:
            errors.append(str(exc)[:160])
            return []
    for future in asyncio.as_completed([batch(i) for i in range(10)]):
        rows = await future
        people.extend(rows)
        await db.ai_audience_runs.update_one({"id": run_id}, {"$set": {"people": people, "completed": len(people), "errors": errors}})
    if len(people) < 100:
        fallback = fallback_personas(round_doc, ads)
        for row in fallback[len(people):]:
            row["model"] = {"id": "fallback-panel", "label": "Fallback panel", "provider": "local"}
        people.extend(fallback[len(people):])
    dims = ["attention", "clarity", "desire", "trust", "originality", "brand_fit"]
    ratings = {dim: round(sum(int(p.get("ratings", {}).get(dim, 0)) for p in people) / max(1, len(people))) for dim in dims}
    favored = {"king": sum(p.get("favored") == "king" for p in people),
               "challenger": sum(p.get("favored") == "challenger" for p in people)}
    summary = {"ratings": ratings, "favored": favored,
        "strongest_signal": max(ratings, key=ratings.get), "weakest_signal": min(ratings, key=ratings.get),
        "research_note": "Synthetic panel only. Use these reactions as creative hypotheses, not market truth.",
        "suggested_improvement": "Strengthen " + min(ratings, key=ratings.get).replace("_", " ") + " without sacrificing " + max(ratings, key=ratings.get).replace("_", " ") + "."}
    await db.ai_audience_runs.update_one({"id": run_id}, {"$set": {"status": "complete", "people": people[:100],
        "completed": 100, "summary": summary, "errors": errors, "finished_at": now()}})


@router.post("/rounds/{round_id}/ai-audience")
async def release_audience(round_id: str, background: BackgroundTasks):
    db = get_db()
    if not await db.rounds.find_one({"id": round_id}):
        raise HTTPException(404, "No such round.")
    existing = await db.ai_audience_runs.find_one({"round_id": round_id})
    if existing:
        return clean_doc(existing)
    run = {"id": "aud_" + uuid.uuid4().hex[:12], "round_id": round_id, "status": "running",
           "people": [], "completed": 0, "created_at": now()}
    try:
        await db.ai_audience_runs.insert_one(run)
    except Exception:
        return clean_doc(await db.ai_audience_runs.find_one({"round_id": round_id}))
    background.add_task(run_ai_audience, run["id"])
    return clean_doc(run)


@router.get("/rounds/{round_id}/ai-audience")
async def get_audience(round_id: str):
    run = await get_db().ai_audience_runs.find_one({"round_id": round_id})
    if not run:
        return {"status": "idle", "completed": 0, "people": []}
    return clean_doc(run)


# -------------------------------------------------------------- admin game desk
@router.get("/admin/games")
async def admin_games(x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    db = get_db()
    campaigns = [clean_doc(x, True) async for x in db.campaigns.find({}).sort("created_at", -1).limit(40)]
    submissions = [clean_doc(x, True) async for x in db.submissions.find({}).sort("created_at", -1).limit(100)]
    events = [clean_doc(x, True) async for x in db.events.find({}).sort("created_at", -1).limit(30)]
    models = [clean_doc(x, True) async for x in db.model_catalog.find({}).sort("label", 1)]
    payouts = [clean_doc(x, True) async for x in db.prize_payouts.find({}).sort("created_at", -1).limit(30)]
    return {"campaigns": campaigns, "submissions": submissions, "events": events, "models": models, "payouts": payouts}


@router.post("/admin/games/campaigns/{campaign_id}/approve")
async def approve_campaign(campaign_id: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    db = get_db()
    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        raise HTTPException(404, "No such campaign.")
    slug = campaign["slug"]
    event = await db.events.find_one({"campaign_id": campaign_id})
    if not event:
        event = {"id": "evt_" + uuid.uuid4().hex[:12], "campaign_id": campaign_id, "slug": slug,
            "status": "scheduled", "scheduled_at": campaign["event_at"], "duration_minutes": campaign["duration_minutes"],
            "queue": [], "queue_index": 0, "created_at": now()}
        await db.events.insert_one(event)
    await db.campaigns.update_one({"id": campaign_id}, {"$set": {"status": "submissions_open", "approved_at": now()}})
    return {"ok": True, "event_slug": slug}


@router.post("/admin/games/campaigns/{campaign_id}/reject")
async def reject_campaign(campaign_id: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    await get_db().campaigns.update_one({"id": campaign_id}, {"$set": {"status": "rejected", "reviewed_at": now()}})
    return {"ok": True}


@router.post("/admin/games/submissions/{submission_id}/{action}")
async def moderate_submission(submission_id: str, action: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    if action not in ("approve", "reject", "queue"):
        raise HTTPException(400, "Unknown action.")
    db = get_db()
    sub = await db.submissions.find_one({"id": submission_id})
    if not sub:
        raise HTTPException(404, "No such submission.")
    status = {"approve": "approved", "reject": "rejected", "queue": "queued"}[action]
    await db.submissions.update_one({"id": submission_id}, {"$set": {"status": status, "reviewed_at": now()}})
    if action == "queue":
        await db.events.update_one({"campaign_id": sub["campaign_id"], "status": {"$in": ["scheduled", "ready"]}},
                                   {"$addToSet": {"queue": submission_id}})
    return {"ok": True, "status": status}


@router.post("/admin/games/events/{event_id}/start")
async def start_event(event_id: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    db = get_db()
    event = await db.events.find_one({"id": event_id})
    if not event:
        raise HTTPException(404, "No such event.")
    queue = list(event.get("queue") or [])
    if len(queue) < 2:
        raise HTTPException(409, "Queue at least two approved ads.")
    if event.get("current_round_id"):
        return {"ok": True, "already": True, "round_id": event["current_round_id"]}
    round_doc = {"id": "rnd_" + uuid.uuid4().hex[:12], "event_id": event_id,
        "campaign_id": event["campaign_id"], "number": 1, "king_id": queue[0], "challenger_id": queue[1],
        "status": "live", "started_at": now(), "created_at": now()}
    await db.rounds.insert_one(round_doc)
    await db.events.update_one({"id": event_id}, {"$set": {"status": "live", "started_at": now(),
        "current_round_id": round_doc["id"], "king_id": queue[0], "queue_index": 1}})
    await db.campaigns.update_one({"id": event["campaign_id"]}, {"$set": {"status": "live"}})
    await db.submissions.update_many({"id": {"$in": queue[:2]}}, {"$set": {"status": "competing"}})
    return {"ok": True, "round_id": round_doc["id"]}


@router.post("/admin/games/events/{event_id}/advance")
async def advance_event(event_id: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    db = get_db()
    event = await db.events.find_one({"id": event_id})
    current = await db.rounds.find_one({"id": event.get("current_round_id")}) if event else None
    if not current:
        raise HTTPException(404, "No active round.")
    await db.rounds.update_one({"id": current["id"]}, {"$set": {"started_at": now() - timedelta(seconds=ROUND_SECONDS)}})
    result = await finish_round(db, await db.rounds.find_one({"id": current["id"]}))
    return {"ok": True, "winner_id": result.get("winner_id")}


@router.post("/admin/games/models")
async def upsert_model(body: ModelIn, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    if not providers._allowed_host(body.base_url):
        raise HTTPException(400, "Endpoint is not in MODEL_ENDPOINT_ALLOWLIST.")
    doc = {**body.model_dump(), "updated_at": now()}
    await get_db().model_catalog.update_one({"id": body.id}, {"$set": doc, "$setOnInsert": {"created_at": now()}}, upsert=True)
    return {"ok": True, "model": providers.public_model(doc)}


@router.post("/admin/games/models/{model_id}/health")
async def model_health(model_id: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    model = await get_db().model_catalog.find_one({"id": model_id})
    if not model:
        raise HTTPException(404, "No such model.")
    return await providers.health(model)


@router.post("/admin/games/payouts/{campaign_id}/{status}")
async def payout_status(campaign_id: str, status: str, x_admin_password: str | None = Header(default=None)):
    admin_required(x_admin_password)
    if status not in ("unclaimed", "claimed", "paid", "failed"):
        raise HTTPException(400, "Unknown payout state.")
    await get_db().prize_payouts.update_one({"campaign_id": campaign_id}, {"$set": {"status": status, "updated_at": now()}}, upsert=True)
    return {"ok": True, "status": status}


async def create_indexes(db):
    await db.campaigns.create_index("id", unique=True)
    await db.campaigns.create_index("slug", unique=True)
    await db.submissions.create_index("id", unique=True)
    await db.submission_generations.create_index("id", unique=True)
    await db.submission_generations.create_index("expires_at", expireAfterSeconds=0)
    await db.events.create_index("id", unique=True)
    await db.events.create_index("slug", unique=True)
    await db.rounds.create_index("id", unique=True)
    await db.votes.create_index([("round_id", 1), ("session_hash", 1)], unique=True)
    await db.tracked_clicks.create_index([("round_id", 1), ("ad_id", 1), ("session_hash", 1)], unique=True)
    await db.ai_audience_runs.create_index("round_id", unique=True)
    await db.model_catalog.create_index("id", unique=True)
    await db.model_usage.create_index("created_at")
    await db.prize_payouts.create_index("campaign_id", unique=True)
