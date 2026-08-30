"""Deterministic rules for sponsored Billboard Games."""
from datetime import timedelta
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import games


def test_score_is_seventy_percent_votes_thirty_percent_clicks():
    score = games.compute_score(70, 30, 20, 80)
    assert score["king"] == 55.0
    assert score["challenger"] == 45.0


def test_zero_clicks_are_neutral():
    score = games.compute_score(6, 4, 0, 0)
    assert score["click_share"] == {"king": 50.0, "challenger": 50.0}
    assert score["king"] == 57.0


def test_zero_activity_is_tied():
    score = games.compute_score(0, 0, 0, 0)
    assert score["king"] == score["challenger"] == 50.0


@pytest.mark.parametrize("url", [
    "http://example.com/product", "https://localhost/product", "https://127.0.0.1/x",
    "https://192.168.1.10/x", "file:///etc/passwd",
])
def test_product_url_rejects_unsafe_destinations(url):
    with pytest.raises(HTTPException):
        games.safe_url(url)


def test_round_phase_follows_three_minute_show_clock():
    assert games.round_phase({"started_at": games.now() - timedelta(seconds=10), "status": "live"})[0] == "reveal"
    assert games.round_phase({"started_at": games.now() - timedelta(seconds=60), "status": "live"})[0] == "voting"
    assert games.round_phase({"started_at": games.now() - timedelta(seconds=145), "status": "live"})[0] == "panel"
    assert games.round_phase({"started_at": games.now() - timedelta(seconds=170), "status": "live"})[0] == "result"
