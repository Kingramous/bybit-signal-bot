# 🤖 Bybit Futures Signal Bot

A professional-grade cryptocurrency futures trading signal bot built in Python. Scans all 581+ Bybit USDT perpetual futures pairs and delivers the top 5 high-confidence trade setups directly to Telegram — twice daily.

---

## 📌 What It Does

- **Scans every Bybit USDT futures pair** (581+ coins) in parallel
- **Filters out pump-and-dump traps** with a smart anti-chase filter
- **Identifies the top 5 setups** using multi-layered technical analysis
- **Sends rich signals to Telegram** at 7:00 AM and 7:00 PM (WAT) daily
- **Shows exact entry, stop loss, and 3 take profit levels** with dollar P&L

---

## ⚙️ Features

### 📊 Technical Analysis Engine
- Multi-timeframe confluence scoring (1m / 5m / 15m / 1H / 4H / 1D)
- EMA stack analysis (9 / 21 / 50 / 200)
- RSI, MACD, Bollinger Bands, VWAP
- ATR-based stop loss calculation

### 🧠 Advanced Market Structure
- **Wyckoff Analysis** — Detects accumulation/distribution phases (Spring, Upthrust, Phase A-D)
- **Smart Money Concepts (SMC)** — Break of Structure, Change of Character, Fair Value Gaps, Liquidity Grabs, Inducement
- **Order Block Detection** — Bullish and bearish institutional order blocks
- **30-Day Buildup Detection** — Identifies coins consolidating before a major breakout

### 📈 Futures-Specific Analysis
- **Funding Rate** — Detects overleveraged markets
- **Open Interest** — Confirms real money entering or leaving
- **Liquidation Heatmap** — Identifies stop hunt zones near round numbers and S/R clusters

### 💰 Risk Management
- Smart entry at **major support/resistance** levels (not market price)
- S/R levels filtered to within **25% of current price** (no stale historical levels)
- **Risk score (1-10)** per signal
- **Dollar P&L calculator** — exact profit/loss at each TP and SL
- Individual **Risk/Reward ratios** for TP1, TP2, TP3

### 🛡️ Signal Quality Filters
- **Anti-chase filter** — Rejects coins already up >10% unless backed by 30-day buildup
- **SHORT confirmation** — Requires 2 of 3 confirmations (Daily+4H bearish, Funding rate, OI)
- **Conflict warning** — Flags when indicators disagree with the called direction
- **Minimum score threshold** — Only signals scoring 55+/100 are sent
- **Precision rounding** — Correct decimal places for any price scale ($0.0001 to $100,000)

### 📱 Telegram Integration
- Morning session header (🌅 7:00 AM WAT)
- Evening session header (🌆 7:00 PM WAT)
- Full signal card per coin with all analysis sections
- Startup notification with feature list
- Error alerts if something goes wrong

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| Exchange API | Bybit V5 REST API |
| Notifications | Telegram Bot API |
| Data Processing | Pandas, NumPy |
| Scheduling | Schedule |
| Concurrency | ThreadPoolExecutor (8 workers) |

---

## 📁 Project Structure

```
bybit-signal-bot/
├── main.py              # Entry point — scheduler and startup
├── config.py            # API keys and all settings
├── scanner.py           # Full market scan orchestrator
├── analysis.py          # Core TA engine (indicators, S/R, OBs, scoring)
├── advanced_analysis.py # Wyckoff, SMC, Funding, OI, Risk Score, P&L
├── data_fetcher.py      # Bybit API data layer
├── telegram_sender.py   # Signal formatting and Telegram delivery
└── requirements.txt     # Python dependencies
```

---

## 🚀 How to Run

### 1. Install dependencies
```bash
pip install requests pandas numpy schedule
```

### 2. Configure API keys
Edit `config.py`:
```python
BYBIT_API_KEY      = "your_bybit_api_key"
BYBIT_API_SECRET   = "your_bybit_api_secret"
TELEGRAM_BOT_TOKEN = "your_telegram_token"
TELEGRAM_CHAT_ID   = "your_chat_id"
```

### 3. Run the bot
```bash
python main.py
```

The bot will:
1. Send a startup message to Telegram
2. Run an immediate scan on startup
3. Schedule daily scans at 7:00 AM and 7:00 PM WAT
4. Send top 5 signals (or a "market overextended" notice if nothing qualifies)

---

## 📨 Sample Signal Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 SIGNAL #1 — ICPUSDT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥🔥🔥⬜⬜  60/100 — ✅ GOOD SETUP
Direction: 🟢 LONG
24h Vol: $21,569,619 | Change: +2.91%

📊 TRADE SETUP
    CMP:    2.568 (current price)
    Entry:  2.4 ← Entry at major support
    SL:     2.311  🛑
    TP1:    2.534  🎯 (1:1.5)
    TP2:    2.668  🎯 (1:3.0)
    TP3:    2.847  🎯 (1:5.0) runner

💰 YOUR MONEY (100$ at 10x)
    Position size: $1000
    If SL hits:  -$37.21 loss
    If TP1 hits: +$55.79 profit
    If TP2 hits: +$111.63 profit
    If TP3 hits: +$186.04 profit

⚖️ RISK SCORE: 4/10 — 🟡 MEDIUM RISK

📦 ACCUMULATION DETECTED
    Phase: PHASE D — Markup in progress
    Confidence: 75%

📊 OPEN INTEREST
    🟢 Price UP + OI UP — Real buyers entering. STRONG BULLISH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📋 Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `TOP_N_COINS` | 5 | Number of signals to send |
| `MIN_SCORE_TO_SIGNAL` | 55 | Minimum confluence score |
| `DEFAULT_LEVERAGE` | 10 | Display leverage for P&L |
| `BUILDUP_DAYS` | 30 | Days to look back for consolidation |
| `SR_TOUCH_MIN` | 3 | Minimum touches for a major S/R level |

---

## ⚠️ Disclaimer

This bot sends **signals only** — it does not place trades automatically. Always use your own judgment before entering any trade. Cryptocurrency trading involves significant risk. Past signal performance does not guarantee future results.

---

## 👤 Author

Built by **Gbenga** — self-taught Python developer specialising in trading automation and crypto market analysis.

*Open to freelance opportunities in trading bot development, Python automation, and financial data analysis.*

---

## 📬 Contact

Feel free to reach out for collaborations, custom bot development, or questions about this project.
