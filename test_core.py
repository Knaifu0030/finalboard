"""Phase 1 POC — The Last Billboard core, tested in isolation.

Proves, in one run:
  A. Razorpay Standard Checkout: real order creation + HMAC-SHA256 signature verify + webhook verify
  B. Moderation: nuanced ALLOW/BLOCK per the content rules (promote yes, attack no)
  C. The billboard's voice: strict JSON {ad_line, heckle, obituary} in the right tone
  D. Price ladder + atomic takeover against MongoDB (incl. self-dethrone + race guard)
  E. Server-rendered OG card PNG that looks like the wall
"""
import asyncio
import os
import sys
import json
import uuid
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / "backend" / ".env")

from core import payments, ai, wall, og, mailer  # noqa: E402
from core.money import usd_to_paise, fmt  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

OUT = Path("/app/tmp")
OUT.mkdir(exist_ok=True)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + ((" :: " + str(detail)[:200]) if detail else ""))
    return ok


# ---------------------------------------------------------------- A. Razorpay
def test_razorpay():
    print("\n[A] RAZORPAY")
    ref = "lb_" + uuid.uuid4().hex[:12]
    amount = usd_to_paise(1.50)
    print("  ladder: $1.50 ->", amount, "paise ->", fmt(amount, "INR"), "/", fmt(amount, "USD"))
    try:
        order = payments.create_order(amount, receipt=ref, notes={"ref": ref, "kind": "takeover"})
        check("create_order returns order id", str(order.get("id", "")).startswith("order_"), order.get("id"))
        check("order amount echoes paise", order.get("amount") == amount, order.get("amount"))
        check("order currency INR", order.get("currency") == "INR")
        order_id = order["id"]
    except Exception as e:
        check("create_order", False, e)
        order_id = "order_TESTFAKE0000001"

    pay_id = "pay_" + uuid.uuid4().hex[:14]
    sig = payments.expected_signature(order_id, pay_id)
    check("valid signature verifies", payments.verify_payment_signature(order_id, pay_id, sig))
    check("tampered signature rejected", not payments.verify_payment_signature(order_id, pay_id, sig[:-1] + ("0" if sig[-1] != "0" else "1")))
    check("empty signature rejected", not payments.verify_payment_signature(order_id, pay_id, ""))
    check("wrong order id rejected", not payments.verify_payment_signature("order_other", pay_id, sig))

    import hmac, hashlib
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": pay_id}}}}).encode()
    wsig = hmac.new(payments.webhook_secret().encode(), body, hashlib.sha256).hexdigest()
    check("webhook signature verifies", payments.verify_webhook_signature(body, wsig))
    check("webhook bad signature rejected", not payments.verify_webhook_signature(body, "deadbeef"))

    try:
        payments.create_order(50, receipt="tiny")
        check("sub-100-paise order rejected", False, "no exception raised")
    except ValueError:
        check("sub-100-paise order rejected", True)
    except Exception as e:
        check("sub-100-paise order rejected", False, e)


# ------------------------------------------------------------- B. Moderation
MOD_CASES = [
    ("hello", True),
    ("marry me sarah, i have a wall", True),
    ("come to my cafe in bandra, best filter coffee", True),
    ("i love Nike", True),
    ("try my app, it turns receipts into spreadsheets", True),
    ("i paid $2 to say no", True),
    ("XYZ Coffee is a scam, they water the milk", False),
    ("Swiggy's delivery is garbage, use anything else", False),
    ("i am Nike. just do it.", False),
    ("i will find you and kill you", False),
]


async def test_moderation():
    print("\n[B] MODERATION")
    results = await asyncio.gather(*[ai.moderate(t, name="tester") for t, _ in MOD_CASES])
    for (text, expected), res in zip(MOD_CASES, results):
        got = res["allow"]
        check("mod %-52s -> %s" % ('"' + text[:48] + '"', "ALLOW" if got else "BLOCK"),
              got == expected, "expected %s | %s" % ("ALLOW" if expected else "BLOCK", res.get("reason")))
    hit = ai.wordlist_hit("you are a retard")
    check("word-list gate fires before the model", hit is not None, hit)


# ------------------------------------------------------------------ C. Voice
async def test_voice():
    print("\n[C] VOICE")
    v = await ai.voice("my cat is better than yours", "hello", "dan", 252, "$1.50")
    print("    ad_line  :", v["ad_line"])
    print("    heckle   :", v["heckle"])
    print("    obituary :", v["obituary"])
    check("ad_line present", bool(v["ad_line"]))
    check("ad_line <= 15 words", len(v["ad_line"].split()) <= 15, v["ad_line"])
    check("heckle present", bool(v["heckle"]))
    check("heckle <= 20 words", len(v["heckle"].split()) <= 20)
    check("obituary present", bool(v["obituary"]))
    check("no exclamation marks", "!" not in (v["ad_line"] + v["heckle"] + v["obituary"]))
    blob = (v["heckle"] + " " + v["obituary"]).lower()
    check("heckle references the dethroned message or reign",
          ("hello" in blob) or ("4m" in blob) or ("four" in blob) or ("minute" in blob), blob)

    v2 = await ai.voice("come to my cafe in bandra, best filter coffee", "buy $DOGE", "moonboy", 61, "$2.00")
    print("    promo ad_line :", v2["ad_line"])
    print("    promo heckle  :", v2["heckle"])
    check("promotional message still gets an ad line", bool(v2["ad_line"]))
    check("obituary for $DOGE references it", "doge" in v2["obituary"].lower() or "doge" in v2["heckle"].lower(),
          v2["obituary"])

    v3 = await ai.voice("hello", None, None, None, "$1.00")
    check("first-ever poster has empty heckle/obituary", v3["heckle"] == "" and v3["obituary"] == "")

    r = await ai.recap([
        {"name": "dan", "text": "hello", "price": "$1.00", "reign": "4m 12s"},
        {"name": "mo", "text": "no", "price": "$1.50", "reign": "12m"},
    ])
    print("    recap    :", r.replace("\n", "\n               "))
    check("recap generated", len(r) > 20 and "!" not in r)


# ------------------------------------------------- D. Ladder + atomic takeover
async def test_ladder():
    print("\n[D] PRICE LADDER + ATOMIC TAKEOVER")
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    dbname = "poc_billboard_" + uuid.uuid4().hex[:6]
    db = client[dbname]
    try:
        s = await wall.get_settings(db)
        check("start price is $1.00", fmt(s["start_price_paise"], "USD") == "$1.00", s["start_price_paise"])
        check("min bump is $0.50", fmt(s["min_bump_paise"], "USD") == "$0.50")
        check("wall starts paused", s["paused"] is True)

        cur = await wall.current_message(db)
        check("min next bid on empty wall is $1.00",
              fmt(wall.min_next_paise(s, cur), "USD") == "$1.00")

        r1 = await wall.execute_takeover(db, text="hello", name="dan", email="dan@example.com",
                                         image_url=None, amount_paise=usd_to_paise(1.00),
                                         source="seed", run_voice=False)
        check("first takeover at $1.00 succeeds", r1["ok"], r1.get("error"))

        s = await wall.get_settings(db)
        cur = await wall.current_message(db)
        check("min next bid is now $1.50", fmt(wall.min_next_paise(s, cur), "USD") == "$1.50",
              fmt(wall.min_next_paise(s, cur), "USD"))

        low = await wall.execute_takeover(db, text="cheapskate", name="lo", email="lo@example.com",
                                          image_url=None, amount_paise=usd_to_paise(1.20), run_voice=False)
        check("underbid at $1.20 rejected", (not low["ok"]) and low["error"] == "below_min", low)

        selfd = await wall.execute_takeover(db, text="again", name="dan", email="DAN@example.com",
                                            image_url=None, amount_paise=usd_to_paise(5.00), run_voice=False)
        check("same email cannot dethrone itself", (not selfd["ok"]) and selfd["error"] == "self_dethrone", selfd)

        r2 = await wall.execute_takeover(db, text="no", name="mo", email="mo@example.com",
                                         image_url=None, amount_paise=usd_to_paise(1.50), run_voice=False)
        check("second takeover at $1.50 succeeds", r2["ok"], r2.get("error"))
        check("previous poster is now dethroned", r2["dethroned"] and r2["dethroned"].get("ended_at") is not None)
        check("dethroned records who did it", r2["dethroned"].get("dethroned_by") == "mo")
        check("adjacent posters never share an ink",
              r2["message"]["ink"] != r1["message"]["ink"],
              (r1["message"]["ink"], r2["message"]["ink"]))
        check("rotation within -1.5..1.5", abs(r2["message"]["rotation"]) <= 1.5, r2["message"]["rotation"])

        # concurrent bids: exactly one may win against the same wall state
        both = await asyncio.gather(
            wall.execute_takeover(db, text="race A", name="a", email="a@example.com", image_url=None,
                                  amount_paise=usd_to_paise(2.00), run_voice=False),
            wall.execute_takeover(db, text="race B", name="b", email="b@example.com", image_url=None,
                                  amount_paise=usd_to_paise(2.00), run_voice=False),
        )
        wins = [x for x in both if x["ok"]]
        check("concurrent equal bids: exactly one wins", len(wins) == 1, [x.get("error") for x in both])

        cur = await wall.current_message(db)
        s = await wall.get_settings(db)
        check("settings pointer matches the top poster", s["current_message_id"] == cur["id"])
        check("settings amount matches the top poster", s["current_amount_paise"] == cur["amount_paise"])

        rev = await wall.revert_last(db)
        check("admin can revert the last takeover", rev["ok"], rev)
        cur2 = await wall.current_message(db)
        check("reverting restores the previous holder to live", cur2 and cur2.get("ended_at") is None, cur2 and cur2.get("text"))

        # currency display, one ladder underneath
        check("USD label", fmt(usd_to_paise(6.50), "USD") == "$6.50")
        check("INR label", fmt(usd_to_paise(6.50), "INR") == "\u20b9572", fmt(usd_to_paise(6.50), "INR"))

        # clock + freeze
        await wall.start_clock(db, hours=48)
        check("clock starts and unpauses", not (await wall.get_settings(db))["paused"])
        check("not frozen with 48h left", not await wall.is_frozen(db))
        await db.settings.update_one({"_id": "settings"}, {"$set": {"ends_at": wall.now()}})
        check("frozen once ends_at passes", await wall.is_frozen(db))
        check("freeze stamps the final holder", await wall.freeze_if_expired(db))
        cur3 = await wall.current_message(db)
        check("top poster marked FINAL HOLDER", bool(cur3.get("is_final")))

        # outbox
        oid = await mailer.queue(db, "dan@example.com", mailer.SUBJECT_DETHRONED,
                                 mailer.dethrone_body({}, "no", "mo", "Held four minutes. The pigeons stayed longer.",
                                                      "4m 12s", "$2.00", "https://x/m/abc"))
        doc = await db.outbox.find_one({"id": oid})
        check("dethrone email queued in outbox", doc is not None and doc["subject"] == "You were dethroned.")
        check("email body carries the price link", "Paste over it for $2.00" in doc["body"])

        return {"msgs": [wall.public_message(m, "USD") for m in
                         await db.messages.find({}).sort("seq", 1).to_list(20)]}
    finally:
        await client.drop_database(dbname)
        client.close()


# ---------------------------------------------------------------- E. OG card
def test_og(sample):
    print("\n[E] OG CARD")
    dethroned = {
        "id": "abc123", "text": "hello", "name": "dan", "ink": "mustard", "mode": "ink_bg",
        "rotation": -1.2, "ad_line": "Say less. Pay more.", "ended_at": "2025-01-01T00:00:00+00:00",
        "heckle": "Held four minutes. The pigeons stayed longer.", "reign_label": "4M 12S",
        "image_url": None,
    }
    live = {
        "id": "def456", "text": "i paid $2 to say no", "name": "mo", "ink": "teal", "mode": "black_bg",
        "rotation": 1.1, "ad_line": "Finally, a wall that agrees with you.", "ended_at": None,
        "heckle": "", "image_url": None,
    }
    longmsg = {
        "id": "ghi789", "text": "This wall has held Coke ads and divorce lawyers and now it holds my "
                                "unsolicited opinion about lunch", "name": "averylongholdername",
        "ink": "tomato", "mode": "ink_bg", "rotation": 0.9,
        "ad_line": "Lunch. Reconsidered.", "ended_at": None, "heckle": "", "image_url": None,
    }
    finalmsg = dict(live, id="fin", text="THE END", ink="teal", mode="ink_bg")

    jobs = [
        ("og_dethroned.png", dethroned,
         [("Held 4m 12s \u00b7 Dethroned by mo \u00b7 Paste over it for ", "cream"), ("$2.00", "ink")], False),
        ("og_current.png", live,
         [("Currently held \u00b7 $1.50 \u00b7 Paste over it for ", "cream"), ("$2.00", "ink")], False),
        ("og_long.png", longmsg,
         [("Currently held \u00b7 $6.50 \u00b7 Paste over it for ", "cream"), ("$7.00", "ink")], False),
        ("og_final.png", finalmsg, "The Last Billboard \u00b7 Held by mo \u00b7 Forever", True),
    ]
    for fname, msg, rail, final in jobs:
        try:
            png = og.render_og(msg, rail, final=final)
            (OUT / fname).write_bytes(png)
            check("rendered %s (%d KB)" % (fname, len(png) // 1024), len(png) > 8000)
        except Exception as e:
            traceback.print_exc()
            check("rendered " + fname, False, e)

    try:
        st = og.stamp_image("DETHRONED \u00b7 HELD 4M 12S", "The pigeons stayed longer.", 460)
        check("stamp renders rotated with alpha", st.width > 400 and st.mode == "RGBA")
    except Exception as e:
        check("stamp renders", False, e)


async def main():
    print("=" * 74)
    print("THE LAST BILLBOARD :: CORE POC")
    print("=" * 74)
    test_razorpay()
    await test_moderation()
    await test_voice()
    sample = await test_ladder()
    test_og(sample)

    print("\n" + "=" * 74)
    failed = [r for r in RESULTS if not r[1]]
    print("%d/%d checks passed" % (len(RESULTS) - len(failed), len(RESULTS)))
    for n, _, d in failed:
        print("  FAILED: %s :: %s" % (n, d))
    print("images in /app/tmp/")
    print("=" * 74)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
