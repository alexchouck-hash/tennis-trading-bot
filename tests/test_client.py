"""Tests for prediction client feed loading and fallback handling."""

from __future__ import annotations

import json
from pathlib import Path

from tennis_trading_bot.client import PredictionClient
from tennis_trading_bot.models import PredictionsFeed


def test_client_loads_local_json(tmp_path: Path) -> None:
    sample_data = {
        "generated_utc": "2026-09-09T22:00:00Z",
        "upcoming_board": [
            {
                "p1": "Carlos Alcaraz",
                "p2": "Jannik Sinner",
                "p1_win_prob": 0.52,
                "favorite": "Carlos Alcaraz",
                "favorite_prob": 0.52,
                "confidence": 0.75,
                "confidence_band": "high",
            }
        ],
        "kalshi_evaluations": [
            {
                "match": "Carlos Alcaraz vs Jannik Sinner",
                "our_p1": 0.52,
                "kalshi_p1": 0.40,
                "edge_pp": 12.0,
                "confidence_band": "high",
                "trade_action": {
                    "platform": "Kalshi",
                    "ticker": "KXATPMATCH-26SEP09ALCSIN",
                },
            }
        ],
    }

    feed_file = tmp_path / "test_predictions.json"
    feed_file.write_text(json.dumps(sample_data), encoding="utf-8")

    client = PredictionClient(feed_url=str(feed_file))
    feed = client.get_predictions()

    assert isinstance(feed, PredictionsFeed)
    assert len(feed.upcoming_board) == 1
    assert feed.upcoming_board[0].p1 == "Carlos Alcaraz"
    assert len(feed.kalshi_evaluations) == 1
    assert feed.kalshi_evaluations[0].edge_pp == 12.0


def test_client_caching(tmp_path: Path) -> None:
    sample_data = {"upcoming_board": [], "kalshi_evaluations": []}
    feed_file = tmp_path / "test_predictions.json"
    feed_file.write_text(json.dumps(sample_data), encoding="utf-8")

    client = PredictionClient(feed_url=str(feed_file), cache_ttl_seconds=10)
    _ = client.get_predictions()

    # Modify file
    feed_file.write_text(json.dumps({"upcoming_board": [{"p1": "A", "p2": "B", "p1_win_prob": 0.5}]}))

    # Stale cache returned
    feed2 = client.get_predictions(force_refresh=False)
    assert len(feed2.upcoming_board) == 0

    # Force refresh
    feed3 = client.get_predictions(force_refresh=True)
    assert len(feed3.upcoming_board) == 1
