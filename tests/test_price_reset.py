import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from core import wall


def test_price_override_resets_next_price_without_mutating_poster():
    current = {"id": "poster-1", "amount_paise": 5000}
    settings = {"start_price_paise": 1000, "min_bump_paise": 500,
                "next_price_override_paise": 1000}

    assert wall.min_next_paise(settings, current) == 1000
    assert current["amount_paise"] == 5000


def test_normal_ladder_resumes_when_override_is_absent():
    current = {"id": "poster-2", "amount_paise": 1000}
    settings = {"start_price_paise": 1000, "min_bump_paise": 500}

    assert wall.min_next_paise(settings, current) == 1500
