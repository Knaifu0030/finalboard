"""The Last Billboard - backend.

One wall. One message. A price ladder in INR paise, displayed in the visitor's currency.
"""
import os
import re
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from core import ai, og, payments, mailer, wall  # noqa: E402
from core.db import get_db  # noqa: E402
from core.money import fmt, currency_for_country, usd_to_paise, paise_per_usd  # noqa: E402
import games  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("billboard")

app = FastAPI(title="The Last Billboard")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PENDING_WINDOW_MIN = 20
BLOCK_COPY = ai.BLOCK_COPY
MIN_BID_COPY = "Someone already paid more than that."


# --------------------------------------------------------------- helpers
def base_url() -> str:
    return (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")


def pick_currency(request: Request, cur: str | None = None, tz: str | None = None) -> str:
    if cur in ("INR", "USD"):
        return cur
    for h in ("cf-ipcountry", "x-vercel-ip-country", "x-appengine-country", "x-country-code"):
        v = request.headers.get(h)
        if v and v.upper() != "XX":
            return currency_for_country(v)
    if tz and ("kolkata" in tz.lower() or "calcutta" in tz.lower()):
        return "INR"
    return "USD"


def admin_ok(pw: str | None) -> bool:
    real = os.environ.get("ADMIN_PASSWORD", "")
    return bool(real) and pw == real


def require_admin(pw: str | None):
    if not admin_ok(pw):
        raise HTTPException(status_code=401, detail="Wrong password. The wall does not know you.")


async def active_pending(db):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PENDING_WINDOW_MIN)
    return await db.pending.find_one(
        {"status": {"$in": ["created", "paid", "awaiting_approval"]},
         "created_at": {"$gte": cutoff}},
        sort=[("created_at", -1)],
    )


async def wall_state(db, currency: str) -> dict:
    await wall.freeze_if_expired(db)
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    frozen = await wall.is_frozen(db)

    behind = []
    if current:
        cursor = db.messages.find(
            {"seq": {"$lt": current.get("seq", 0)}, "reverted": {"$ne": True}}
        ).sort("seq", -1).limit(3)
        behind = [wall.public_message(m, currency) async for m in cursor]

    recent = [wall.public_message(m, currency)
              async for m in db.messages.find({"reverted": {"$ne": True}}).sort("seq", -1).limit(11)]
    recent = [r for r in recent if not current or r["id"] != current["id"]][:10]

    cur_paise = int(current["amount_paise"]) if current else 0
    next_paise = wall.min_next_paise(s, current)
    pend = await active_pending(db)

    total = 0
    async for m in db.messages.find({"reverted": {"$ne": True}}, {"amount_paise": 1}):
        total += int(m.get("amount_paise") or 0)

    return {
        "currency": currency,
        "current": wall.public_message(current, currency, is_current=True) if current else None,
        "behind": behind,
        "recent": recent,
        "price": {
            "current_paise": cur_paise,
            "current_label": fmt(cur_paise, currency) if current else None,
            "next_paise": next_paise,
            "next_label": fmt(next_paise, currency),
            "bump_label": fmt(int(s["min_bump_paise"]), currency),
            "start_label": fmt(int(s["start_price_paise"]), currency),
            "unit_paise": 100 if currency == "INR" else paise_per_usd(),
        },
        "clock": {
            "paused": bool(s.get("paused")),
            "ends_at": wall.iso(wall.parse(s.get("ends_at"))),
            "duration_hours": s.get("duration_hours", 48),
            "server_now": wall.iso(wall.now()),
        },
        "frozen": frozen,
        "takeovers": s.get("seq", 0),
        "total_paid_label": fmt(total, currency),
        "pending": ({"name": pend["name"], "amount_label": fmt(int(pend["amount_paise"]), currency),
                     "status": pend["status"]} if pend else None),
        "razorpay_key_id": payments.key_id(),
        "razorpay_ready": payments.configured(),
    }


def rail_segments(msg: dict, next_label: str, currency: str, frozen: bool):
    """The one mono line under the wall, as coloured segments."""
    if frozen:
        return [("The Last Billboard \u00b7 Held by %s \u00b7 Forever" % msg.get("name", "nobody"), "cream")]
    if msg.get("ended_at"):
        return [("Held %s \u00b7 Dethroned by %s \u00b7 Paste over it for " %
                 (msg.get("reign_label") or ai.human_reign(msg.get("reign_seconds")),
                  msg.get("dethroned_by") or "someone"), "cream"),
                (next_label, "ink")]
    return [("Currently held \u00b7 %s \u00b7 Paste over it for " %
             fmt(int(msg.get("amount_paise", 0)), currency), "cream"), (next_label, "ink")]


# --------------------------------------------------------------- models
class ModerateIn(BaseModel):
    text: str = Field(max_length=200)
    name: str = Field(default="", max_length=60)
    image_url: str = Field(default="", max_length=500)


class OrderIn(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=24)
    email: str = Field(min_length=3, max_length=120)
    image_url: str = Field(default="", max_length=500)
    amount_paise: int


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class AdminIn(BaseModel):
    password: str


class ChatIn(BaseModel):
    name: str = Field(default="", max_length=24)
    text: str = Field(min_length=1, max_length=140)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_submission(d: OrderIn):
    if not d.text.strip():
        raise HTTPException(400, "Say something. It won't last.")
    if not EMAIL_RE.match(d.email.strip()):
        raise HTTPException(400, "That email will not reach you.")
    if d.image_url and not re.match(r"^https?://", d.image_url.strip()):
        raise HTTPException(400, "An image needs a real http address.")


# --------------------------------------------------------------- public api
@api.get("/wall")
async def get_wall(request: Request, cur: str | None = None, tz: str | None = None):
    db = get_db()
    return await wall_state(db, pick_currency(request, cur, tz))


@api.get("/messages")
async def list_messages(request: Request, sort: str = "reign", cur: str | None = None,
                        tz: str | None = None, limit: int = Query(400, le=1000)):
    db = get_db()
    currency = pick_currency(request, cur, tz)
    s = await wall.get_settings(db)
    out = []
    async for m in db.messages.find({"reverted": {"$ne": True}}).sort("seq", -1).limit(limit):
        out.append(wall.public_message(m, currency, is_current=(m["id"] == s.get("current_message_id"))))
    if sort == "price":
        out.sort(key=lambda x: -x["amount_paise"])
    elif sort == "reign":
        out.sort(key=lambda x: -x["reign_seconds"])
    return {"messages": out, "currency": currency, "count": len(out)}


async def find_message(db, ident: str):
    m = await db.messages.find_one({"id": ident})
    if not m and str(ident).isdigit():
        m = await db.messages.find_one({"seq": int(ident)})
    return m


@api.get("/message/{ident}")
async def get_message(ident: str, request: Request, cur: str | None = None, tz: str | None = None):
    db = get_db()
    m = await find_message(db, ident)
    if not m:
        raise HTTPException(404, "No such poster. The wall does not remember it.")
    currency = pick_currency(request, cur, tz)
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    frozen = await wall.is_frozen(db)
    is_current = bool(current and current["id"] == m["id"])
    pm = wall.public_message(m, currency, is_current=is_current)
    next_paise = wall.min_next_paise(s, current)
    next_label = fmt(next_paise, currency)
    return {
        "message": pm,
        "currency": currency,
        "frozen": frozen,
        "is_current": is_current,
        "next_label": next_label,
        "next_paise": next_paise,
        "share_url": "%s/api/m/%s" % (base_url(), m.get("seq") or m["id"]),
        "og_url": "%s/api/og/%s.png" % (base_url(), m["id"]),
        "rail": [list(x) for x in rail_segments(pm, next_label, currency, frozen and is_current)],
    }


@api.get("/og/{ident}.png")
async def og_image(ident: str, request: Request):
    db = get_db()
    m = await find_message(db, ident)
    if not m:
        raise HTTPException(404, "no such poster")
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    frozen = await wall.is_frozen(db)
    is_current = bool(current and current["id"] == m["id"])
    currency = pick_currency(request)
    pm = wall.public_message(m, currency, is_current=is_current)
    next_label = fmt(wall.min_next_paise(s, current), currency)
    segs = rail_segments(pm, next_label, currency, frozen and is_current)
    png = await asyncio.to_thread(og.render_og, pm, segs, bool(frozen and is_current))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=60"})


@api.get("/m/{ident}", response_class=HTMLResponse)
async def share_page(ident: str, request: Request):
    """The share unit. Crawlers read the card here; people are bounced to the poster."""
    db = get_db()
    m = await find_message(db, ident)
    if not m:
        return RedirectResponse("/")
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    frozen = await wall.is_frozen(db)
    is_current = bool(current and current["id"] == m["id"])
    currency = pick_currency(request)
    pm = wall.public_message(m, currency, is_current=is_current)
    next_label = fmt(wall.min_next_paise(s, current), currency)
    if frozen and is_current:
        desc = "The Last Billboard. Held by %s. Forever, or until the server bill." % pm["name"]
    elif is_current:
        desc = "Currently held \u00b7 %s \u00b7 Paste over it for %s" % (pm["price_label"], next_label)
    else:
        desc = "Held %s \u00b7 Dethroned by %s \u00b7 Paste over it for %s" % (
            pm["reign_label"], pm["dethroned_by"] or "someone", next_label)
    title = '"%s" \u2014 The Last Billboard' % pm["text"][:80]
    og_url = "%s/api/og/%s.png?v=%s" % (base_url(), m["id"], int(pm["reign_seconds"]))
    page = "%s/m/%s" % (base_url(), m["id"])

    def esc(x):
        return (x or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")

    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="The Last Billboard">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{page}">
<meta property="og:image" content="{og_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{og_url}">
<link rel="canonical" href="{page}">
<style>html,body{{background:#F3E7D3;color:#141414;font-family:ui-monospace,monospace;margin:0;padding:24px}}</style>
<script>location.replace("{page}");</script>
</head><body>
<p>{desc}</p><p><a href="{page}">Open the wall</a></p>
<img src="{og_url}" alt="poster" style="max-width:100%;border:0">
</body></html>""".format(title=esc(title), desc=esc(desc), page=esc(page), og_url=esc(og_url))
    return HTMLResponse(html)


@api.post("/moderate")
async def do_moderate(body: ModerateIn):
    res = await ai.moderate(body.text, body.name, body.image_url)
    return {"allow": res["allow"], "copy": None if res["allow"] else BLOCK_COPY,
            "stage": res["stage"]}


# --------------------------------------------------------------- live chat
CHAT_BLOCK_COPY = "Not on this wall. " + BLOCK_COPY


def chat_public(m: dict) -> dict:
    return {
        "id": m["id"],
        "name": m.get("name") or "anon",
        "text": m.get("text") or "",
        "at": wall.iso(m.get("created_at")),
    }


@api.get("/chat")
async def get_chat(limit: int = Query(60, le=120)):
    db = get_db()
    rows = [chat_public(m) async for m in
            db.chat.find({"hidden": {"$ne": True}}).sort("created_at", -1).limit(limit)]
    rows.reverse()
    return {"messages": rows, "count": len(rows)}


@api.post("/chat")
async def post_chat(body: ChatIn, request: Request):
    db = get_db()
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Say something. Nobody is listening, but say it anyway.")
    name = (body.name or "").strip()[:24] or "anon"
    mod = await ai.moderate(text, name)
    if not mod["allow"]:
        raise HTTPException(422, CHAT_BLOCK_COPY)
    doc = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "text": text[:140],
        "created_at": datetime.now(timezone.utc),
        "hidden": False,
    }
    await db.chat.insert_one(dict(doc))
    return chat_public(doc)


@api.post("/create-order")
async def create_order(body: OrderIn, request: Request, cur: str | None = None, tz: str | None = None):
    db = get_db()
    validate_submission(body)
    currency = pick_currency(request, cur, tz)
    if await wall.is_frozen(db):
        raise HTTPException(409, "The wall is closed.")
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    need = wall.min_next_paise(s, current)
    if int(body.amount_paise) < need:
        raise HTTPException(409, MIN_BID_COPY)
    if current and (current.get("email") or "").lower() == body.email.strip().lower():
        raise HTTPException(409, "You already hold the wall. Dethroning yourself is not a purchase.")

    mod = await ai.moderate(body.text, body.name, body.image_url)
    if not mod["allow"]:
        raise HTTPException(422, BLOCK_COPY)

    ref = "lb_" + uuid.uuid4().hex[:12]
    pending = {
        "id": ref,
        "text": body.text.strip(),
        "name": body.name.strip(),
        "email": body.email.strip().lower(),
        "image_url": (body.image_url or "").strip() or None,
        "amount_paise": int(body.amount_paise),
        "status": "created",
        "created_at": datetime.now(timezone.utc),
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "currency_shown": currency,
    }

    if not payments.configured():
        pending["status"] = "awaiting_approval"
        await db.pending.insert_one(dict(pending))
        return {"mode": "pending", "reference": ref,
                "copy": "PENDING \u00b7 %s \u00b7 %s" % (pending["name"], fmt(pending["amount_paise"], currency))}
    try:
        order = await asyncio.to_thread(
            payments.create_order, int(body.amount_paise), ref,
            {"reference": ref, "holder": pending["name"], "message": pending["text"][:110]})
    except Exception as e:
        log.exception("razorpay order failed")
        pending["status"] = "awaiting_approval"
        pending["error"] = str(e)[:300]
        await db.pending.insert_one(dict(pending))
        return {"mode": "pending", "reference": ref,
                "copy": "PENDING \u00b7 %s \u00b7 %s" % (pending["name"], fmt(pending["amount_paise"], currency))}

    pending["razorpay_order_id"] = order["id"]
    await db.pending.insert_one(dict(pending))
    return {
        "mode": "checkout",
        "reference": ref,
        "order_id": order["id"],
        "amount_paise": order["amount"],
        "currency": "INR",
        "key_id": payments.key_id(),
        "display_label": fmt(int(body.amount_paise), currency),
        "inr_label": fmt(int(body.amount_paise), "INR"),
        "name": pending["name"],
        "email": pending["email"],
    }


async def run_takeover_from_pending(db, pending, source):
    res = await wall.execute_takeover(
        db, text=pending["text"], name=pending["name"], email=pending["email"],
        image_url=pending.get("image_url"), amount_paise=int(pending["amount_paise"]),
        payment={"order_id": pending.get("razorpay_order_id"),
                 "payment_id": pending.get("razorpay_payment_id")},
        source=source,
    )
    if not res["ok"]:
        await db.pending.update_one({"id": pending["id"]},
                                    {"$set": {"status": "failed", "error": res["error"]}})
        return res
    await db.pending.update_one({"id": pending["id"]},
                                {"$set": {"status": "executed",
                                          "message_id": res["message"]["id"]}})
    if res.get("dethroned"):
        await send_dethrone_mail(db, res["dethroned"], res["message"])
    return res


async def send_dethrone_mail(db, old, new):
    if not old.get("email"):
        return
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    next_label = fmt(wall.min_next_paise(s, current), "USD")
    secs = old.get("reign_seconds") or wall.reign_seconds(old)
    permalink = "%s/m/%s" % (base_url(), old["id"])
    body = mailer.dethrone_body(old, new.get("text", ""), new.get("name", "someone"),
                                old.get("heckle", ""), ai.human_reign(secs), next_label, permalink)
    await mailer.queue(db, old["email"], mailer.SUBJECT_DETHRONED, body,
                       kind="dethrone", meta={"message_id": old["id"]})


@api.post("/verify-payment")
async def verify_payment(body: VerifyIn):
    db = get_db()
    if not payments.verify_payment_signature(body.razorpay_order_id, body.razorpay_payment_id,
                                             body.razorpay_signature):
        raise HTTPException(400, "That payment does not check out.")
    pending = await db.pending.find_one({"razorpay_order_id": body.razorpay_order_id})
    if not pending:
        raise HTTPException(404, "No such takeover.")
    if pending["status"] == "executed":
        return {"ok": True, "already": True, "message_id": pending.get("message_id")}
    await db.pending.update_one({"id": pending["id"]},
                                {"$set": {"status": "paid",
                                          "razorpay_payment_id": body.razorpay_payment_id}})
    pending["razorpay_payment_id"] = body.razorpay_payment_id
    res = await run_takeover_from_pending(db, pending, source="razorpay")
    if not res["ok"]:
        if res["error"] in ("below_min", "race_lost"):
            raise HTTPException(409, MIN_BID_COPY)
        raise HTTPException(409, res["error"])
    return {"ok": True, "message_id": res["message"]["id"]}


@api.post("/payment-failed")
async def payment_failed(payload: dict):
    db = get_db()
    oid = (payload or {}).get("order_id")
    if oid:
        await db.pending.update_one({"razorpay_order_id": oid},
                                    {"$set": {"status": "failed",
                                              "error": str((payload or {}).get("reason"))[:300]}})
    return {"ok": True}


@api.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None)):
    raw = await request.body()
    if not payments.verify_webhook_signature(raw, x_razorpay_signature or ""):
        raise HTTPException(400, "bad signature")
    data = json.loads(raw or b"{}")
    if data.get("event") not in ("payment.captured", "order.paid", "payment.authorized"):
        return {"ok": True, "ignored": data.get("event")}
    ent = (((data.get("payload") or {}).get("payment") or {}).get("entity")) or {}
    order_id = ent.get("order_id")
    db = get_db()
    pending = await db.pending.find_one({"razorpay_order_id": order_id}) if order_id else None
    if not pending or pending["status"] == "executed":
        return {"ok": True}
    pending["razorpay_payment_id"] = ent.get("id")
    await db.pending.update_one({"id": pending["id"]},
                                {"$set": {"status": "paid", "razorpay_payment_id": ent.get("id")}})
    await run_takeover_from_pending(db, pending, source="webhook")
    return {"ok": True}


# --------------------------------------------------------------- admin
@api.post("/admin/login")
async def admin_login(body: AdminIn):
    require_admin(body.password)
    return {"ok": True}


@api.get("/admin/state")
async def admin_state(request: Request, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    state = await wall_state(db, "USD")
    cur_id = state["current"]["id"] if state["current"] else None
    pendings = [
        {k: (wall.iso(v) if isinstance(v, datetime) else v) for k, v in p.items() if k != "_id"}
        async for p in db.pending.find({}).sort("created_at", -1).limit(40)
    ]
    outbox = [
        {k: (wall.iso(v) if isinstance(v, datetime) else v) for k, v in o.items() if k != "_id"}
        async for o in db.outbox.find({}).sort("created_at", -1).limit(40)
    ]
    msgs = []
    async for m in db.messages.find({}).sort("seq", -1).limit(60):
        pm = wall.public_message(m, "USD", is_current=(m["id"] == cur_id))
        pm["email"] = m.get("email")
        pm["payment"] = {kk: vv for kk, vv in (m.get("payment") or {}).items()}
        pm["reverted"] = bool(m.get("reverted"))
        pm["source"] = m.get("source")
        msgs.append(pm)
    return {"state": state, "pending": pendings, "outbox": outbox, "messages": msgs,
            "resend_ready": mailer.resend_ready()}


@api.post("/admin/pending/{pid}/approve")
async def admin_approve(pid: str, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    p = await db.pending.find_one({"id": pid})
    if not p:
        raise HTTPException(404, "no such pending")
    if p["status"] == "executed":
        return {"ok": True, "already": True}
    res = await run_takeover_from_pending(db, p, source="admin_approved")
    if not res["ok"]:
        raise HTTPException(409, res["error"])
    return {"ok": True, "message_id": res["message"]["id"]}


@api.post("/admin/pending/{pid}/reject")
async def admin_reject(pid: str, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    await db.pending.update_one({"id": pid}, {"$set": {"status": "rejected"}})
    return {"ok": True}


@api.post("/admin/revert")
async def admin_revert(x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    res = await wall.revert_last(get_db())
    if not res["ok"]:
        raise HTTPException(409, res["error"])
    return res


@api.post("/admin/message/{mid}/delete")
async def admin_delete(mid: str, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    s = await wall.get_settings(db)
    if s.get("current_message_id") == mid:
        await wall.revert_last(db)
    await db.messages.update_one({"id": mid}, {"$set": {"reverted": True, "deleted": True}})
    return {"ok": True}


class PauseIn(BaseModel):
    paused: bool


@api.post("/admin/pause")
async def admin_pause(body: PauseIn, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    if body.paused:
        await db.settings.update_one({"_id": "settings"}, {"$set": {"paused": True}})
    else:
        s = await wall.get_settings(db)
        if not s.get("ends_at"):
            await wall.start_clock(db)
        else:
            await db.settings.update_one({"_id": "settings"}, {"$set": {"paused": False}})
    s = await wall.get_settings(db)
    return {"ok": True, "paused": s.get("paused"), "ends_at": wall.iso(wall.parse(s.get("ends_at")))}


class ClockIn(BaseModel):
    hours: float | None = None
    ends_at: str | None = None


@api.post("/admin/clock")
async def admin_clock(body: ClockIn, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    if body.ends_at:
        await db.settings.update_one({"_id": "settings"},
                                     {"$set": {"ends_at": wall.parse(body.ends_at), "paused": False}})
    elif body.hours is not None:
        await wall.start_clock(db, hours=body.hours)
    s = await wall.get_settings(db)
    return {"ok": True, "ends_at": wall.iso(wall.parse(s.get("ends_at"))), "paused": s.get("paused")}


@api.post("/admin/recap")
async def admin_recap(x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    events = []
    async for m in db.messages.find({"started_at": {"$gte": since}, "reverted": {"$ne": True}}).sort("seq", 1):
        events.append({"name": m.get("name"), "text": m.get("text"),
                       "price": fmt(int(m.get("amount_paise", 0)), "USD"),
                       "reign": ai.human_reign(wall.reign_seconds(m))})
    text = await ai.recap(events)
    return {"recap": text, "events": len(events)}


class SeedIn(BaseModel):
    text: str
    name: str
    email: str
    amount_paise: int | None = None
    image_url: str | None = None


@api.post("/admin/takeover")
async def admin_takeover(body: SeedIn, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    db = get_db()
    s = await wall.get_settings(db)
    current = await wall.current_message(db)
    amt = body.amount_paise or wall.min_next_paise(s, current)
    res = await wall.execute_takeover(db, text=body.text, name=body.name, email=body.email,
                                      image_url=body.image_url, amount_paise=amt, source="admin")
    if not res["ok"]:
        raise HTTPException(409, res["error"])
    if res.get("dethroned"):
        await send_dethrone_mail(db, res["dethroned"], res["message"])
    return {"ok": True, "message_id": res["message"]["id"]}


@api.post("/admin/refund/{pid}")
async def admin_refund(pid: str, x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    try:
        r = await asyncio.to_thread(payments.refund, pid, None)
        return {"ok": True, "refund": {"id": r.get("id"), "status": r.get("status")}}
    except Exception as e:
        raise HTTPException(400, str(e)[:300])


@api.post("/admin/drain-outbox")
async def admin_drain(x_admin_password: str | None = Header(default=None)):
    require_admin(x_admin_password)
    n = await mailer.drain(get_db())
    return {"ok": True, "sent": n, "resend_ready": mailer.resend_ready()}


@api.get("/health")
async def health():
    db = get_db()
    s = await wall.get_settings(db)
    return {"ok": True, "takeovers": s.get("seq", 0), "razorpay": payments.configured(),
            "resend": mailer.resend_ready()}


app.include_router(api)
app.include_router(games.router)


# --------------------------------------------------------------- boot
SEED = [
    # text, name, email, usd, minutes before now that this poster went up
    ("hello", "dan", "dan@thelastbillboard.test", 1.00, 20.0),
    ("no", "mo", "mo@thelastbillboard.test", 1.50, 15.8),
    ("i paid $2 to say no", "ren", "ren@thelastbillboard.test", 2.00, 3.8),
]


async def seed_wall():
    db = get_db()
    await wall.get_settings(db)
    if await db.messages.count_documents({}) > 0:
        return
    log.info("seeding the fight")
    for text, name, email, usd, mins_ago in SEED:
        at = datetime.now(timezone.utc) - timedelta(minutes=mins_ago)
        res = await wall.execute_takeover(db, text=text, name=name, email=email, image_url=None,
                                          amount_paise=usd_to_paise(usd), source="seed", at=at)
        if not res["ok"]:
            log.warning("seed failed for %r: %s", text, res)
            break
        if res.get("dethroned"):
            await send_dethrone_mail(db, res["dethroned"], res["message"])
    log.info("seeded")


async def expiry_loop():
    while True:
        try:
            db = get_db()
            just_froze = await wall.freeze_if_expired(db)
            if just_froze:
                cur = await wall.current_message(db)
                if cur and cur.get("email") and not cur.get("final_mail_sent"):
                    await mailer.queue(
                        db, cur["email"], mailer.SUBJECT_FINAL,
                        mailer.final_body(cur.get("name"), cur.get("text"),
                                          "%s/m/%s" % (base_url(), cur["id"])),
                        kind="final", meta={"message_id": cur["id"]})
                    await db.messages.update_one({"id": cur["id"]}, {"$set": {"final_mail_sent": True}})
            await mailer.drain(db)
        except Exception as e:
            log.warning("expiry loop: %s", e)
        await asyncio.sleep(20)


@app.on_event("startup")
async def startup():
    db = get_db()
    await db.messages.create_index("id")
    await db.messages.create_index("seq")
    await db.pending.create_index("id")
    await db.pending.create_index("razorpay_order_id")
    await db.chat.create_index("created_at")
    await games.create_indexes(db)
    asyncio.create_task(seed_wall())
    asyncio.create_task(expiry_loop())
    log.info("the wall is up")
