"""Kalshi Trade API v2 Broker with RSA-PSS authentication and resting limit orders."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from tennis_trading_bot.brokers.base import BaseBroker
from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.models import Order, Position, TradeSignal

logger = logging.getLogger("tennis_trading_bot.brokers.kalshi")

KALSHI_PROD_URL = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"


class KalshiBroker(BaseBroker):
    """Execution broker for Kalshi event contracts using Trade API v2."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.base_url = KALSHI_DEMO_URL if config.kalshi_use_demo else KALSHI_PROD_URL
        self.api_key_id = config.kalshi_api_key_id
        self.private_key_path = config.kalshi_private_key_path
        self._private_key = None
        self._load_private_key()

    def _load_private_key(self) -> None:
        """Load RSA private key for request signing."""
        if not self.private_key_path:
            return

        key_path = Path(self.private_key_path)
        if not key_path.exists():
            logger.warning(f"Kalshi private key file not found at: {key_path}")
            return

        try:
            from cryptography.hazmat.primitives import serialization
            key_data = key_path.read_bytes()
            self._private_key = serialization.load_pem_private_key(
                key_data, password=None
            )
            logger.info("Successfully loaded Kalshi RSA private key.")
        except ImportError:
            logger.error("Package 'cryptography' is required for Kalshi live trading. Install via: pip install cryptography")
        except Exception as exc:
            logger.error(f"Failed to parse Kalshi private key: {exc}")

    def sign_request(self, method: str, path: str) -> dict[str, str]:
        """Generate Kalshi v2 RSA-PSS signature headers."""
        if not self._private_key or not self.api_key_id:
            raise ValueError("Kalshi API credentials (api_key_id and private_key) are required for signing.")

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        timestamp = str(int(time.time() * 1000))
        # Path must omit query parameters per Kalshi specification
        clean_path = path.split("?")[0]
        message = f"{timestamp}{method.upper()}{clean_path}".encode()

        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        sig_b64 = base64.b64encode(signature).decode("utf-8")

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": sig_b64,
            "Content-Type": "application/json",
            "User-Agent": "tennis-trading-bot/0.1.0",
        }

    def _request(self, method: str, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute signed HTTP request against Kalshi Trade API v2."""
        url = f"{self.base_url}{endpoint}"
        headers = self.sign_request(method, endpoint)

        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data if data else None,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_balance(self) -> float:
        """Fetch available USD balance from Kalshi portfolio."""
        if not self._private_key:
            return 0.0
        try:
            data = self._request("GET", "/portfolio/balance")
            cents = data.get("balance", 0)
            return float(cents) / 100.0
        except Exception as exc:
            logger.error(f"Failed to fetch Kalshi balance: {exc}")
            return 0.0

    def get_open_positions(self) -> list[Position]:
        """Retrieve active market positions from Kalshi."""
        if not self._private_key:
            return []
        try:
            data = self._request("GET", "/portfolio/positions")
            positions: list[Position] = []
            for p in data.get("market_positions", []):
                ticker = p.get("ticker", "")
                contracts = int(p.get("position", 0))
                if contracts <= 0:
                    continue
                positions.append(
                    Position(
                        position_id=f"kalshi-{ticker}",
                        ticker=ticker,
                        match=ticker,
                        side="yes",
                        entry_price=float(p.get("market_exposure", 0)) / (contracts * 100) if contracts else 0.5,
                        contracts=contracts,
                        stake_usd=float(p.get("market_exposure", 0)) / 100.0,
                        model_prob_at_entry=0.5,
                        opened_at_utc=datetime.now(UTC).isoformat(),
                    )
                )
            return positions
        except Exception as exc:
            logger.error(f"Error getting Kalshi positions: {exc}")
            return []

    def place_order(self, signal: TradeSignal) -> Order:
        """Place a resting limit buy order on Kalshi."""
        order_id = f"k-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()

        if not self._private_key:
            return Order(
                order_id=order_id,
                ticker=signal.event_ticker,
                match=signal.match,
                side=signal.side,
                price=signal.market_price,
                count=signal.contracts,
                stake_usd=signal.stake_usd,
                status="rejected",
                placed_at_utc=now_iso,
                broker_type="kalshi",
                notes="Kalshi private key credentials not loaded",
            )

        # Price in cents (1 to 99)
        price_cents = int(round(signal.market_price * 100))
        payload = {
            "action": "buy",
            "type": "limit",
            "ticker": signal.event_ticker,
            "side": "yes" if signal.side in ("yes", "p1") else "no",
            "count": signal.contracts,
            "yes_price": price_cents if signal.side in ("yes", "p1") else None,
            "no_price": price_cents if signal.side not in ("yes", "p1") else None,
            "client_order_id": order_id,
            "post_only": True,  # Capture maker rebates ($0 fee)
        }
        # Strip None fields
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            resp = self._request("POST", "/portfolio/orders", data=payload)
            order_data = resp.get("order", {})
            logger.info(f"Kalshi order submitted: {signal.event_ticker} ({order_data.get('order_id')})")
            return Order(
                order_id=order_data.get("order_id", order_id),
                ticker=signal.event_ticker,
                match=signal.match,
                side=signal.side,
                price=signal.market_price,
                count=signal.contracts,
                stake_usd=signal.stake_usd,
                status="open",
                placed_at_utc=now_iso,
                broker_type="kalshi",
                notes=f"Resting limit order placed on Kalshi ({self.base_url})",
            )
        except Exception as exc:
            logger.error(f"Failed to place Kalshi order: {exc}")
            return Order(
                order_id=order_id,
                ticker=signal.event_ticker,
                match=signal.match,
                side=signal.side,
                price=signal.market_price,
                count=signal.contracts,
                stake_usd=signal.stake_usd,
                status="rejected",
                placed_at_utc=now_iso,
                broker_type="kalshi",
                notes=f"Kalshi API error: {exc}",
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open Kalshi order."""
        if not self._private_key:
            return False
        try:
            self._request("DELETE", f"/portfolio/orders/{order_id}")
            logger.info(f"Canceled Kalshi order: {order_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to cancel Kalshi order {order_id}: {exc}")
            return False

    def sync_portfolio(self) -> dict[str, Any]:
        """Summarize Kalshi account metrics."""
        balance = self.get_balance()
        positions = self.get_open_positions()
        invested = sum(p.stake_usd for p in positions)
        return {
            "broker": "kalshi",
            "environment": "demo" if self.config.kalshi_use_demo else "production",
            "cash_usd": round(balance, 2),
            "invested_usd": round(invested, 2),
            "total_equity_usd": round(balance + invested, 2),
            "open_positions_count": len(positions),
        }
