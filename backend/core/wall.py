"""Wall state: the price ladder, ink assignment, and the atomic takeover."""
import os
import random
import uuid
from datetime import datetime, timezone, timedelta

from .money import usd_to_paise, fmt
from . import ai

SETTINGS_ID = "settings"
INK_NAMES = ["tomato", "mustard", "teal"]


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt else None


def parse(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(dt).replace("Z", "+00:00"))


DEFAULT_SETTINGS = {
    "_id": SETTINGS_ID,
    "start_price_paise": None,   # filled from fx at boot
    "min_bump_paise": None,
    "duration_hours": 48,
    "ends_at": None,
    "paused": True,
    "current_message_id": None,
    "current_amount_paise": 0,
    "seq": 0,
}


async def get_settings(db):
    s = await db.settings.find_one({"_id": SETTINGS_ID})
    if not s:
        s = dict(DEFAULT_SETTINGS)
        s["start_price_paise"] = usd_to_paise(1.00)
        s["min_bump_paise"] = usd_to_paise(0.50)
        await db.settings.insert_one(s)
    changed = {}
    if not s.get("start_price_paise"):
        changed["start_price_paise"] = usd_to_paise(1.00)
    if not s.get("min_bump_paise"):
        changed["min_bump_paise"] = usd_to_paise(0.50)
    if changed:
        await db.settings.update_one({"_id": SETTINGS_ID}, {"$set": changed})
        s.update(changed)
    return s


async def current_message(db):
    s = await get_settings(db)
    if not s.get("current_message_id"):
        return None
    return await db.messages.find_one({"id": s["current_message_id"]})


def min_next_paise(settings, current):
    if not current:
        return int(settings["start_price_paise"])
    return int(current["amount_paise"]) + int(settings["min_bump_paise"])


async def is_frozen(db):
    s = await get_settings(db)
    if s.get("paused"):
        return False
    ends = parse(s.get("ends_at"))
    return bool(ends and now() >= ends)


def pick_ink(prev_ink):
    options = [i for i in INK_NAMES if i != prev_ink]
    return random.choice(options)


def pick_mode(prev_mode):
    return "black_bg" if prev_mode == "ink_bg" else "ink_bg"


def pick_rotation():
    r = round(random.uniform(-1.5, 1.5), 2)
    return r if abs(r) > 0.3 else (0.9 if r >= 0 else -0.9)


def reign_seconds(msg, end=None):
    st = parse(msg.get("started_at"))
    en = parse(msg.get("ended_at")) or end or now()
    if not st:
        return 0
    return max(0, (en - st).total_seconds())


def public_message(msg, currency="USD", is_current=False):
    if not msg:
        return None
    secs = reign_seconds(msg)
    return {
        "id": msg["id"],
        "seq": msg.get("seq", 0),
        "text": msg.get("text", ""),
        "name": msg.get("name", "anonymous"),
        "image_url": msg.get("image_url") or None,
        "ink": msg.get("ink", "tomato"),
        "mode": msg.get("mode", "ink_bg"),
        "rotation": msg.get("rotation", 0),
        "amount_paise": msg.get("amount_paise", 0),
        "price_label": fmt(msg.get("amount_paise", 0), currency),
        "started_at": iso(parse(msg.get("started_at"))),
        "ended_at": iso(parse(msg.get("ended_at"))),
        "reign_seconds": secs,
        "reign_label": ai.human_reign(secs),
        "ad_line": msg.get("ad_line") or "",
        "heckle": msg.get("heckle") or "",
        "obituary": msg.get("obituary") or "",
        "dethroned_by": msg.get("dethroned_by") or None,
        "is_current": is_current,
        "is_final": bool(msg.get("is_final")),
    }


async def execute_takeover(db, *, text, name, email, image_url, amount_paise,
                           payment=None, source="admin", run_voice=True, at=None):
    """Atomically paste a new poster over the wall.

    Returns {ok, message, dethroned, error}
    """
    s = await get_settings(db)
    current = await current_message(db)
    need = min_next_paise(s, current)
    if amount_paise < need:
        return {"ok": False, "error": "below_min", "need_paise": need}
    if current and email and (current.get("email") or "").strip().lower() == email.strip().lower():
        return {"ok": False, "error": "self_dethrone"}

    t = at or now()
    new_id = str(uuid.uuid4())
    ink = pick_ink(current.get("ink") if current else None)
    mode = pick_mode(current.get("mode") if current else "black_bg")

    # atomic guard: only one takeover can win against a given wall state
    guard = await db.settings.find_one_and_update(
        {"_id": SETTINGS_ID,
         "current_message_id": current["id"] if current else None,
         "current_amount_paise": int(current["amount_paise"]) if current else s.get("current_amount_paise", 0)},
        {"$set": {"current_message_id": new_id, "current_amount_paise": int(amount_paise)},
         "$inc": {"seq": 1}},
        return_document=True,
    )
    if not guard:
        return {"ok": False, "error": "race_lost", "need_paise": need}

    doc = {
        "id": new_id,
        "seq": guard.get("seq", 1),
        "text": text,
        "name": name or "anonymous",
        "email": (email or "").strip().lower(),
        "image_url": image_url or None,
        "ink": ink,
        "mode": mode,
        "rotation": pick_rotation(),
        "amount_paise": int(amount_paise),
        "started_at": t,
        "ended_at": None,
        "ad_line": "",
        "heckle": "",
        "obituary": "",
        "dethroned_by": None,
        "dethroned_by_id": None,
        "is_final": False,
        "payment": payment or {},
        "source": source,
    }
    await db.messages.insert_one(dict(doc))

    dethroned = None
    if current:
        secs = reign_seconds(current, end=t)
        await db.messages.update_one(
            {"id": current["id"]},
            {"$set": {"ended_at": t, "dethroned_by": doc["name"], "dethroned_by_id": new_id,
                      "reign_seconds": secs}},
        )
        dethroned = await db.messages.find_one({"id": current["id"]})

    if run_voice:
        v = await ai.voice(
            text,
            current.get("text") if current else None,
            current.get("name") if current else None,
            reign_seconds(current, end=t) if current else None,
            fmt(int(amount_paise), "USD"),
        )
        await db.messages.update_one({"id": new_id}, {"$set": {"ad_line": v["ad_line"]}})
        doc["ad_line"] = v["ad_line"]
        if current:
            await db.messages.update_one(
                {"id": current["id"]},
                {"$set": {"heckle": v["heckle"], "obituary": v["obituary"]}},
            )
            dethroned = await db.messages.find_one({"id": current["id"]})

    return {"ok": True, "message": await db.messages.find_one({"id": new_id}), "dethroned": dethroned}


async def revert_last(db):
    """Undo the top poster: the wall goes back to the previous holder."""
    current = await current_message(db)
    if not current:
        return {"ok": False, "error": "nothing_to_revert"}
    prev = await db.messages.find_one(
        {"dethroned_by_id": current["id"]},
    )
    await db.messages.update_one({"id": current["id"]}, {"$set": {"reverted": True, "ended_at": now()}})
    if prev:
        await db.messages.update_one(
            {"id": prev["id"]},
            {"$set": {"ended_at": None, "dethroned_by": None, "dethroned_by_id": None,
                      "heckle": "", "obituary": ""}},
        )
        await db.settings.update_one(
            {"_id": SETTINGS_ID},
            {"$set": {"current_message_id": prev["id"], "current_amount_paise": int(prev["amount_paise"])}},
        )
    else:
        await db.settings.update_one(
            {"_id": SETTINGS_ID},
            {"$set": {"current_message_id": None, "current_amount_paise": 0}},
        )
    return {"ok": True, "restored": prev["id"] if prev else None}


async def freeze_if_expired(db):
    s = await get_settings(db)
    if s.get("paused"):
        return False
    ends = parse(s.get("ends_at"))
    if not ends or now() < ends:
        return False
    cur = await current_message(db)
    if cur and not cur.get("is_final"):
        await db.messages.update_one({"id": cur["id"]}, {"$set": {"is_final": True}})
    return True


async def start_clock(db, hours=None):
    s = await get_settings(db)
    h = int(hours or s.get("duration_hours") or 48)
    ends = now() + timedelta(hours=h)
    await db.settings.update_one(
        {"_id": SETTINGS_ID},
        {"$set": {"paused": False, "ends_at": ends, "duration_hours": h}},
    )
    return ends
