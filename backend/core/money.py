"""Single price ladder stored in INR paise. Display currency chosen per request.

$1.00 == Rs.88 == 8800 paise (FX fixed by env USD_INR_RATE).
So the dollar ladder ($1.00 start, $0.50 bump) stays clean in paise.
"""
import os


def fx() -> int:
    try:
        return int(float(os.environ.get("USD_INR_RATE", "88")))
    except Exception:
        return 88


def paise_per_usd() -> int:
    return fx() * 100


def usd_to_paise(usd: float) -> int:
    return int(round(usd * paise_per_usd()))


def fmt(paise: int, currency: str = "USD") -> str:
    """Rail/price label. No trailing noise, mono friendly."""
    if currency == "INR":
        rupees = paise / 100.0
        if abs(rupees - round(rupees)) < 0.005:
            return "\u20b9%d" % round(rupees)
        return "\u20b9%.2f" % rupees
    dollars = paise / float(paise_per_usd())
    return "$%.2f" % dollars


INDIA_CODES = {"IN"}


def currency_for_country(code: str | None) -> str:
    if code and code.upper() in INDIA_CODES:
        return "INR"
    return "USD"
