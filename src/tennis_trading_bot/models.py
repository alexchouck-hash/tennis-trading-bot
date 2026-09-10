"""Strongly-typed data models for tennis-trading-bot using Pydantic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TradeAction(BaseModel):
    """Direct execution action metadata embedded in the prediction feed."""
    platform: str = "Kalshi"
    ticker: str | None = None
    url: str | None = None
    trade_url: str | None = None
    referral_bonus_url: str | None = None
    cta: str | None = None


class UpcomingMatch(BaseModel):
    """Upcoming ATP or WTA match on the active prediction board."""
    tourney: str | None = None
    round: str | None = None
    surface: str | None = None
    start: str | None = None
    p1: str
    p2: str
    p1_win_prob: float
    favorite: str | None = None
    favorite_prob: float | None = None
    confidence: float | None = None
    confidence_band: str | None = "low"
    market_note: str | None = None


class MarketEvaluation(BaseModel):
    """Market comparison item evaluating model probability against market price."""
    match: str | None = None
    match_start: str | None = None
    our_p1: float | None = None
    kalshi_p1: float | None = None
    edge_pp: float | None = None
    confidence_band: str | None = "low"
    product: str | None = "open_to_pre"
    kelly_quarter: float | None = None
    event_ticker: str | None = None
    trade_action: TradeAction | dict[str, Any] | None = None

    # Optional fields from rich scans
    p1: str | None = None
    p2: str | None = None
    position_side: str | None = None
    position_our_prob: float | None = None
    position_buy_price: float | None = None
    position_bid_price: float | None = None
    position_spread: float | None = None
    position_quote_is_live: bool | None = True
    volume: float | None = None


class PredictionsFeed(BaseModel):
    """Top-level payload returned by https://ipredictsport.com/predictions.json."""
    generated_utc: str | None = None
    upcoming_board: list[UpcomingMatch] = Field(default_factory=list)
    kalshi_evaluations: list[MarketEvaluation] = Field(default_factory=list)


class TradeSignal(BaseModel):
    """Actionable positive-EV trading signal produced by Strategy."""
    event_ticker: str
    match: str
    match_start: str | None = None
    pick: str
    side: Literal["yes", "no", "p1", "p2"]
    model_prob: float
    market_price: float
    edge_pp: float
    spread: float
    confidence_band: str
    kelly_fraction: float
    stake_usd: float
    contracts: int
    direct_trade_url: str | None = None
    reason: str = "Positive fee-aware EV exceeding threshold"


class Order(BaseModel):
    """Order submitted to a broker (Paper or Kalshi)."""
    order_id: str
    ticker: str
    match: str
    side: str
    price: float
    count: int
    stake_usd: float
    status: Literal["pending", "open", "filled", "canceled", "rejected"] = "open"
    placed_at_utc: str
    filled_at_utc: str | None = None
    fill_price: float | None = None
    broker_type: Literal["paper", "kalshi"] = "paper"
    notes: str | None = None


class Position(BaseModel):
    """Active open market position."""
    position_id: str
    ticker: str
    match: str
    side: str
    entry_price: float
    contracts: int
    stake_usd: float
    model_prob_at_entry: float
    opened_at_utc: str
    current_market_price: float | None = None
    unrealized_pnl_usd: float = 0.0
    status: Literal["open", "closed", "settled"] = "open"
    close_price: float | None = None
    clv_pp: float | None = None
    realized_pnl_usd: float | None = None
    settled_at_utc: str | None = None
