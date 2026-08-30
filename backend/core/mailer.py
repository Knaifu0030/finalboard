"""Dethrone mail. Everything is written to an outbox first; Resend drains it when keyed."""
import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
log = logging.getLogger("billboard.mail")

SUBJECT_DETHRONED = "You were dethroned."
SUBJECT_FINAL = "You are the Final Holder."


def resend_ready() -> bool:
    return bool(os.environ.get("RESEND_API_KEY") and os.environ.get("RESEND_FROM"))


def base_url() -> str:
    return (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")


def dethrone_body(old, new_text, new_name, heckle, reign_label, next_price_label, permalink) -> str:
    return "\n".join([
        "%s took the wall with:" % (new_name or "someone"),
        '"%s"' % new_text,
        "",
        heckle or "",
        "",
        "You held it for %s." % (reign_label or "no time at all"),
        "",
        "Paste over it for %s \u2192 %s" % (next_price_label, permalink),
    ])


def final_body(name, text, permalink) -> str:
    return "\n".join([
        "The wall is closed.",
        "",
        'The Last Billboard. Held by %s. Forever, or until the server bill.' % (name or "you"),
        '"%s"' % text,
        "",
        permalink,
    ])


async def queue(db, to, subject, body, kind="dethrone", meta=None):
    doc = {
        "id": str(uuid.uuid4()),
        "to": to,
        "subject": subject,
        "body": body,
        "kind": kind,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc),
        "sent": False,
        "provider_id": None,
        "error": None,
    }
    await db.outbox.insert_one(dict(doc))
    log.info("OUTBOX [%s] -> %s | %s\n%s", kind, to, subject, body)
    if resend_ready():
        await try_send(db, doc["id"])
    return doc["id"]


async def try_send(db, outbox_id):
    doc = await db.outbox.find_one({"id": outbox_id})
    if not doc or doc.get("sent"):
        return False
    if not resend_ready():
        await db.outbox.update_one({"id": outbox_id}, {"$set": {"error": "resend not configured"}})
        return False
    try:
        import httpx

        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": "Bearer %s" % os.environ["RESEND_API_KEY"]},
            json={
                "from": os.environ["RESEND_FROM"],
                "to": [doc["to"]],
                "subject": doc["subject"],
                "text": doc["body"],
            },
            timeout=15.0,
        )
        r.raise_for_status()
        pid = r.json().get("id")
        await db.outbox.update_one({"id": outbox_id}, {"$set": {"sent": True, "provider_id": pid, "error": None}})
        return True
    except Exception as e:
        await db.outbox.update_one({"id": outbox_id}, {"$set": {"error": str(e)[:300]}})
        log.warning("resend failed: %s", e)
        return False


async def drain(db, limit=50):
    sent = 0
    if not resend_ready():
        return 0
    async for doc in db.outbox.find({"sent": False}).limit(limit):
        if await try_send(db, doc["id"]):
            sent += 1
    return sent
