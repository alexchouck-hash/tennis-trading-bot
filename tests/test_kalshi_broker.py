"""Tests for KalshiBroker request signing, payload formatting, and credentials handling."""

from __future__ import annotations

from pathlib import Path

from tennis_trading_bot.brokers.kalshi import KalshiBroker
from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.models import TradeSignal


def test_kalshi_broker_missing_credentials() -> None:
    config = BotConfig(
        trade_mode="kalshi",
        kalshi_api_key_id="",
        kalshi_private_key_path="",
    )
    broker = KalshiBroker(config)
    assert broker.get_balance() == 0.0
    assert broker.get_open_positions() == []

    signal = TradeSignal(
        event_ticker="KXATPMATCH-TEST",
        match="Player 1 vs Player 2",
        pick="Player 1",
        side="yes",
        model_prob=0.70,
        market_price=0.45,
        edge_pp=23.0,
        spread=0.02,
        confidence_band="high",
        kelly_fraction=0.05,
        stake_usd=25.0,
        contracts=55,
    )

    order = broker.place_order(signal)
    assert order.status == "rejected"
    assert "not loaded" in (order.notes or "")


def test_kalshi_rsa_signing_if_cryptography(tmp_path: Path) -> None:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        return  # skip test if cryptography not installed

    # Generate temporary RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_file = tmp_path / "kalshi_test.key"
    key_file.write_bytes(pem_bytes)

    config = BotConfig(
        trade_mode="kalshi",
        kalshi_api_key_id="test-key-uuid-1234",
        kalshi_private_key_path=str(key_file),
    )
    broker = KalshiBroker(config)
    headers = broker.sign_request("GET", "/portfolio/balance?limit=5")

    assert headers["KALSHI-ACCESS-KEY"] == "test-key-uuid-1234"
    assert "KALSHI-ACCESS-TIMESTAMP" in headers
    assert "KALSHI-ACCESS-SIGNATURE" in headers
    assert len(headers["KALSHI-ACCESS-SIGNATURE"]) > 30
