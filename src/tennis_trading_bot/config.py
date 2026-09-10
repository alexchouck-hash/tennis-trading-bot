"""Configuration settings for tennis-trading-bot."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Automatically load .env if present
load_dotenv()

KALSHI_REFERRAL_CODE = "eb2fd257-2bc9-465a-a18c-5e9a0ab4848d"
KALSHI_REFERRAL_URL = f"https://kalshi.com/r/{KALSHI_REFERRAL_CODE}"


class BotConfig(BaseModel):
    """Trading bot configuration and risk parameters."""

    # Execution Mode
    trade_mode: Literal["paper", "kalshi"] = Field(
        default_factory=lambda: os.getenv("TRADE_MODE", "paper").lower()  # type: ignore
    )

    # Bankroll Management
    bankroll_usd: float = Field(
        default_factory=lambda: float(os.getenv("BANKROLL_USD", "1000.0"))
    )
    max_stake_fraction: float = Field(
        default_factory=lambda: float(os.getenv("MAX_STAKE_FRACTION", "0.05"))
    )

    # Strategy & Filter Thresholds
    min_edge_pp: float = Field(
        default_factory=lambda: float(os.getenv("MIN_EDGE_PP", "8.0"))
    )
    max_spread: float = Field(
        default_factory=lambda: float(os.getenv("MAX_SPREAD", "0.15"))
    )
    min_confidence: str = Field(
        default_factory=lambda: os.getenv("MIN_CONFIDENCE", "medium_plus").lower()
    )
    min_minutes_to_start: float = Field(
        default_factory=lambda: float(os.getenv("MIN_MINUTES_TO_START", "30.0"))
    )

    # Polling & Execution Loop
    poll_interval_seconds: int = Field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
    )
    predictions_feed_url: str = Field(
        default_factory=lambda: os.getenv(
            "PREDICTIONS_FEED_URL", "https://ipredictsport.com/predictions.json"
        )
    )

    # Kalshi API Credentials (Required only for live/demo Kalshi trading)
    kalshi_api_key_id: str = Field(
        default_factory=lambda: os.getenv("KALSHI_API_KEY_ID", "")
    )
    kalshi_private_key_path: str = Field(
        default_factory=lambda: os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    )
    kalshi_use_demo: bool = Field(
        default_factory=lambda: os.getenv("KALSHI_USE_DEMO", "true").lower() in ("true", "1", "yes")
    )

    # Storage paths
    data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", "data"))
    )
    ledger_path: Path = Field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", "data")) / "paper_ledger.jsonl"
    )

    @classmethod
    def load(cls) -> BotConfig:
        """Load configuration from active environment."""
        config = cls()
        config.data_dir.mkdir(parents=True, exist_ok=True)
        return config
