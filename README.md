<p align="center">
  <h1 align="center">🎾 tennis-trading-bot</h1>
  <p align="center">
    <strong>Autonomous algorithmic trading bot for <a href="https://kalshi.com">Kalshi</a> prediction markets.</strong><br>
    Powered by audited quantitative machine learning tennis predictions from <a href="https://ipredictsport.com">iPredictSport.com</a>.
  </p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg?style=flat-square" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/paper%20trading-default-green.svg?style=flat-square" alt="Paper Trading: Default">
  <img src="https://img.shields.io/badge/data-free%20%26%20open-brightgreen.svg?style=flat-square" alt="Free & Open Feed">
  <a href="https://ipredictsport.com"><img src="https://img.shields.io/badge/powered%20by-iPredictSport-purple.svg?style=flat-square" alt="iPredictSport"></a>
  <a href="https://kalshi.com/r/eb2fd257-2bc9-465a-a18c-5e9a0ab4848d"><img src="https://img.shields.io/badge/Kalshi-Partner%20Bonus-orange.svg?style=flat-square" alt="Kalshi Partner Bonus"></a>
</p>

---

> ### 🎁 Exclusive Kalshi Fee Credits & Sign-Up Bonus
> New to Kalshi? Sign up using our official partner link to receive fee credits and a cash bonus upon your first trades:  
> 👉 **[Claim Your Kalshi Bonus (https://kalshi.com/r/eb2fd257-2bc9-465a-a18c-5e9a0ab4848d)](https://kalshi.com/r/eb2fd257-2bc9-465a-a18c-5e9a0ab4848d)**  
> *(You can test everything in zero-risk Paper mode first before funding an account!)*

---

## 💡 Why tennis-trading-bot? (Turnkey Alpha)

Most open-source trading bots give you the plumbing (exchange connectors, order placement) but leave the hardest part to you: **finding a mathematical edge (alpha)**. As a result, users rely on toy momentum or mean-reversion rules that struggle on binary prediction markets.

**`tennis-trading-bot` solves this by including the alpha out-of-the-box:**
- Connects directly to **[iPredictSport.com](https://ipredictsport.com)'s free public prediction feed** (`https://ipredictsport.com/predictions.json`).
- Uses point-level Markov tennis machine learning models trained on 25+ years of ATP and WTA tour matches (audited holdout accuracy: **66.1%**).
- Continuously calculates fee-aware **quarter-Kelly position sizing** against live Kalshi order books.
- Places resting limit orders at or below model fair price to capture maker fee rebates ($0 taker fees).

---

## ⚡ 30-Second Quickstart (Paper Trading)

No API keys or Kalshi credentials are required to start paper trading.

### 1. Clone & Install
```bash
git clone https://github.com/ipredictsport/tennis-trading-bot.git
cd tennis-trading-bot
pip install -e .
```

### 2. Interactive Setup Wizard
```bash
tennis-bot setup
```
The wizard guides you through selecting starting bankroll, minimum edge thresholds, and risk preferences.

### 3. Run in Dry-Run or Paper Mode
```bash
# Preview current trading edges without placing paper orders:
tennis-bot run --mode paper --dry-run

# Run a single evaluation cycle:
tennis-bot run --mode paper --once

# Run continuous background monitoring loop (refreshes every 5m):
tennis-bot run --mode paper
```

---

## 📊 Live CLI Interface

```
╭───────────────────────────────── Account Summary ─────────────────────────────────╮
│ Broker: PAPER                                                                     │
│ Cash Available: $975.00                                                           │
│ Invested Capital: $25.00                                                          │
│ Total Portfolio Equity: $1,000.00                                                 │
│ Open Positions: 1                                                                 │
╰───────────────────────────────────────────────────────────────────────────────────╯
                              Detected Trading Edges (1 found)                              
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┓
┃ Ticker              ┃ Match               ┃ Pick         ┃ Model % ┃ Ask ┃    Edge ┃ ¼-Kelly ┃ Stake      ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━┩
│ KXATPMATCH-26SEP09… │ Tiafoe vs Shelton   │ Tiafoe (yes) │   40.0% │ 27¢ │ +11.1pp │    3.8% │ $25.00(92x)│ FILLED │
└─────────────────────┴─────────────────────┴──────────────┴─────────┴─────┴─────────┴─────────┴────────────┴────────┘
```

---

## 🧠 Quantitative Strategy & Risk Architecture

The strategy implements the empirically validated selection criteria developed by the iPredictSport research team:

1. **Fee-Aware Edge Floor (`MIN_EDGE_PP`)**:
   $$\text{Edge} = \text{Model Prob} - \text{Ask Price} - \text{Exchange Fee}$$
   Strictly filters for positive expected value ($+8.0\text{pp}$ default).
2. **Spread Cutoff (`MAX_SPREAD`)**:
   Rejects illiquid or placeholder order books where the bid-ask spread exceeds $\$0.15$.
3. **MX2 Coin-Flip Deadband**:
   Excludes matches where the model probability falls into $[0.55, 0.60)$, a region of high historical variance.
4. **Timing Gate**:
   Requires matches to be scheduled at least 30 minutes in advance, targeting the liquid **T-6h** window.
5. **Continuous Kalshi Fee Modeling**:
   Incorporates Kalshi's continuous taker fee formula ($0.07 \cdot p \cdot (1 - p)$) or maker resting rebate ($0.00$) into net expectancy.
6. **Quarter-Kelly Sizing**:
   Sizes each trade to a conservative quarter-Kelly fraction of bankroll, capped at `MAX_STAKE_FRACTION` (default 5% per match).

---

## 🔑 Kalshi Live & Demo Trading

When you are ready to trade with real funds (or on the Kalshi Demo environment):

1. **Obtain API Keys**:
   - In your Kalshi account under **Settings > API**, generate an **API Key ID** and download your **RSA Private Key** (`.key` file).
2. **Configure `.env`**:
   ```ini
   TRADE_MODE=kalshi
   BANKROLL_USD=2500.0
   KALSHI_API_KEY_ID=your-api-key-id-uuid
   KALSHI_PRIVATE_KEY_PATH=path/to/your_kalshi_private_key.key
   KALSHI_USE_DEMO=false   # Set to true for demo-api.kalshi.co
   ```
3. **Execute Live**:
   ```bash
   tennis-bot run --mode kalshi --once
   ```

The bot uses standard **RSA-PSS signing** (`SHA256` with `MGF1`) and places **post-only resting limit orders** directly on the Kalshi order book to avoid paying taker fees.

---

## 🤖 AI Agent & MCP Integrations

Want to query tennis predictions and +EV betting edges directly from **Claude Desktop**, **Cursor**, or **Windsurf**?

We provide an official **Model Context Protocol (MCP) server**:

```json
// Add to claude_desktop_config.json:
{
  "mcpServers": {
    "tennis-predict": {
      "command": "python",
      "args": ["-m", "scripts.mcp_server"]
    }
  }
}
```

Learn more in our [Data Sources & Agent Integrations Guide](docs/DATA_SOURCES.md).

---

## 🌐 Open JSON Data API

External bots, web apps, and syndicates can consume our predictions feed without any API keys or authentication:

```python
import requests

feed = requests.get("https://ipredictsport.com/predictions.json").json()
for match in feed.get("upcoming_board", []):
    print(f"{match['p1']} vs {match['p2']} -> Fav: {match['favorite']} ({match['favorite_prob']*100:.1f}%)")
```

---

## 🧪 Testing

Run the automated test suite with coverage:
```bash
pytest tests/ -v
```

---

## ⚠️ Risk & Disclaimer

*This software is for educational, analytical, and entertainment purposes only. Trading prediction markets and event contracts involves substantial financial risk and can result in the loss of your entire capital. Past simulation results and model accuracy do not guarantee future returns. Always trade responsibly and test in paper mode before risking real capital.*
