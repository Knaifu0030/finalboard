"""Razorpay Standard Web Checkout: orders, signature verify, webhook verify."""
import os
import hmac
import hashlib
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
log = logging.getLogger("billboard.pay")

MIN_PAISE = 100


def key_id() -> str:
    return os.environ.get("RAZORPAY_KEY_ID", "")


def key_secret() -> str:
    return os.environ.get("RAZORPAY_KEY_SECRET", "")


def configured() -> bool:
    return bool(key_id() and key_secret())


def _client():
    import razorpay

    return razorpay.Client(auth=(key_id(), key_secret()))


def create_order(amount_paise: int, receipt: str, notes: dict | None = None) -> dict:
    if amount_paise < MIN_PAISE:
        raise ValueError("amount below Razorpay minimum of 100 paise")
    if not configured():
        raise RuntimeError("razorpay not configured")
    order = _client().order.create({
        "amount": int(amount_paise),
        "currency": "INR",
        "receipt": receipt[:40],
        "payment_capture": 1,
        "notes": notes or {},
    })
    return order


def expected_signature(order_id: str, payment_id: str) -> str:
    body = "%s|%s" % (order_id, payment_id)
    return hmac.new(key_secret().encode(), body.encode(), hashlib.sha256).hexdigest()


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not (order_id and payment_id and signature):
        return False
    return hmac.compare_digest(expected_signature(order_id, payment_id), signature)


def webhook_secret() -> str:
    return os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = webhook_secret()
    if not (secret and signature):
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def fetch_payment(payment_id: str) -> dict:
    return _client().payment.fetch(payment_id)


def refund(payment_id: str, amount_paise: int | None = None) -> dict:
    data = {}
    if amount_paise:
        data["amount"] = int(amount_paise)
    return _client().payment.refund(payment_id, data)
