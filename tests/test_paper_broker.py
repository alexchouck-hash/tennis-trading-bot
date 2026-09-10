"""Tests for PaperBroker simulation, fills, and ledger persistence."""

from __future__ import annotations

from pathlib import Path

from tennis_trading_bot.brokers.paper import PaperBroker
from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.models import TradeSignal


def test_paper_order_fill_and_ledger(tmp_path: Path) -> None:
    ledger_file = tmp_path / "test_ledger.jsonl"
    config = BotConfig(
        bankroll_usd=500.0,
        data_dir=tmp_path,
        ledger_path=ledger_file,
    )

    broker = PaperBroker(config)
    assert broker.get_balance() == 500.0
    assert len(broker.get_open_positions()) == 0

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
    assert order.status == "filled"
    assert order.count == 55
    assert order.stake_usd == 25.0

    # Cash deducted
    assert broker.get_balance() == 475.0

    # Open position created
    positions = broker.get_open_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "KXATPMATCH-TEST"
    assert positions[0].stake_usd == 25.0

    # Verify written to disk
    assert ledger_file.exists()
    lines = [line.strip() for line in ledger_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2  # 1 order + 1 position


def test_insufficient_cash(tmp_path: Path) -> None:
    ledger_file = tmp_path / "test_ledger.jsonl"
    config = BotConfig(
        bankroll_usd=20.0,
        data_dir=tmp_path,
        ledger_path=ledger_file,
    )
    broker = PaperBroker(config)

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
        stake_usd=50.0,  # exceeds $20 bankroll
        contracts=100,
    )

    order = broker.place_order(signal)
    assert order.status == "rejected"
    assert broker.get_balance() == 20.0
    assert len(broker.get_open_positions()) == 0
