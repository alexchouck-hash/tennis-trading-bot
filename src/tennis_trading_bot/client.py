"""HTTP client for fetching iPredictSport public prediction feeds."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from tennis_trading_bot.models import PredictionsFeed

logger = logging.getLogger("tennis_trading_bot.client")


class PredictionClient:
    """Client for retrieving open tennis match probabilities and market evaluations."""

    def __init__(
        self,
        feed_url: str = "https://ipredictsport.com/predictions.json",
        cache_ttl_seconds: int = 60,
        timeout_seconds: float = 12.0,
    ) -> None:
        self.feed_url = feed_url
        self.cache_ttl = cache_ttl_seconds
        self.timeout = timeout_seconds
        self._cached_feed: PredictionsFeed | None = None
        self._last_fetch_ts: float = 0.0

    def get_predictions(self, force_refresh: bool = False) -> PredictionsFeed:
        """Fetch and parse predictions from the remote feed or local cache."""
        now = time.time()
        if not force_refresh and self._cached_feed and (now - self._last_fetch_ts) < self.cache_ttl:
            return self._cached_feed

        # Support local file:// or local path URLs for testing / development
        if self.feed_url.startswith("file://") or Path(self.feed_url).exists():
            local_path = Path(self.feed_url.replace("file://", ""))
            try:
                raw_json = json.loads(local_path.read_text(encoding="utf-8"))
                feed = PredictionsFeed.model_validate(raw_json)
                self._cached_feed = feed
                self._last_fetch_ts = now
                return feed
            except Exception as exc:
                logger.error(f"Error loading local predictions feed: {exc}")
                if self._cached_feed:
                    return self._cached_feed
                raise

        headers = {
            "User-Agent": "tennis-trading-bot/0.1.0 (Open-Source Kalshi Bot; https://ipredictsport.com)",
            "Accept": "application/json",
        }

        try:
            resp = requests.get(self.feed_url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            feed = PredictionsFeed.model_validate(data)
            self._cached_feed = feed
            self._last_fetch_ts = now
            return feed
        except requests.RequestException as exc:
            logger.warning(f"Failed to fetch live feed from {self.feed_url}: {exc}")
            if self._cached_feed:
                logger.info("Serving stale cached predictions feed as fallback.")
                return self._cached_feed
            # Return empty feed on complete failure rather than crashing
            return PredictionsFeed()

    def get_track_record(self, track_url: str = "https://ipredictsport.com/track_record.json") -> dict[str, Any]:
        """Fetch historical model accuracy and closing-line value benchmarks."""
        headers = {"User-Agent": "tennis-trading-bot/0.1.0"}
        try:
            resp = requests.get(track_url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f"Could not load track record: {exc}")
            return {}
