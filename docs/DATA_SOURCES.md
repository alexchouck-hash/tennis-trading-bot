# Data Sources & Agent Integrations

The **tennis-trading-bot** is powered by real-time quantitative machine learning tennis predictions and closing-line value analytics from [iPredictSport.com](https://ipredictsport.com).

This document outlines how the data feed works, the available endpoints, and how external AI agents (like Claude Desktop, Cursor, or LangChain) can consume the same data via the official Model Context Protocol (MCP) server.

---

## 1. The Open Predictions Feed (`/predictions.json`)

- **Primary URL:** `https://ipredictsport.com/predictions.json`
- **Authentication:** Zero authentication required (completely open & free).
- **Update Frequency:** Continuously refreshed every 10 minutes from live ATP/WTA schedules and Kalshi/Polymarket order books.
- **CORS:** Enabled for direct browser and frontend widget embedding.

### Feed Payload Schema

```json
{
  "generated_utc": "2026-09-09T22:00:00Z",
  "upcoming_board": [
    {
      "tourney": "US Open",
      "round": "Semifinal",
      "surface": "hard",
      "start": "2026-09-11T04:00:00Z",
      "p1": "Ben Shelton",
      "p2": "Frances Tiafoe",
      "p1_win_prob": 0.622,
      "favorite": "Ben Shelton",
      "favorite_prob": 0.622,
      "confidence": 0.6565,
      "confidence_band": "high"
    }
  ],
  "kalshi_evaluations": [
    {
      "match": "Frances Tiafoe vs Ben Shelton",
      "match_start": "2026-09-11T22:00:00Z",
      "our_p1": 0.4002,
      "kalshi_p1": 0.27,
      "edge_pp": 13.0,
      "confidence_band": "medium",
      "kelly_quarter": 0.038,
      "trade_action": {
        "platform": "Kalshi",
        "ticker": "KXATPMATCH-26SEP11TIASHE",
        "trade_url": "https://kalshi.com/markets/kxatpmatch-26sep11tiashe?referral=eb2fd257-2bc9-465a-a18c-5e9a0ab4848d",
        "referral_bonus_url": "https://kalshi.com/r/eb2fd257-2bc9-465a-a18c-5e9a0ab4848d"
      }
    }
  ]
}
```

---

## 2. Model Context Protocol (MCP) Server

If you use AI coding assistants or desktop agents (like Claude Desktop, Cursor, Zed, or Windsurf), you can install the **iPredictSport MCP Server** to query live predictions and +EV betting edges directly in your AI chat.

### Connecting in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tennis-predict": {
      "command": "python",
      "args": ["-m", "scripts.mcp_server"]
    }
  }
}
```

### Available MCP Tools:
1. `get_live_board(confidence_min)`: Queries upcoming tennis matches and calibrated win probabilities.
2. `get_betting_edges(min_edge_pp, confidence)`: Finds active prediction market contracts where model probability exceeds market price, returning quarter-Kelly bet sizes and direct trade links.
3. `get_track_record()`: Displays audited Brier score accuracy and closing-line value (CLV) statistics.

---

## 3. Audited Performance & Provenance

Unlike black-box sports betting tipsters, all predictions published by iPredictSport are held to rigorous statistical benchmarks:
- **Chrono Holdout Accuracy:** 66.1% out-of-sample on tour matches.
- **CLV Direction:** +4.5pp average closing-line value over market open.
- **Quarter-Kelly Sizing:** Fee-aware stake calculations protecting bankrolls against market variance.
- **Track Record:** Full verifiable public ledger available at [ipredictsport.com/track-record.html](https://ipredictsport.com/track-record.html).
