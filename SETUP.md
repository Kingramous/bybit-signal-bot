# ============================================================
#  BYBIT FUTURES SIGNAL BOT — SETUP GUIDE
# ============================================================

## WHAT THIS BOT DOES
- Scans ALL Bybit USDT perpetual futures pairs (200+)
- Filters by volume ($10M+) and volatility
- Pre-screens top 30 candidates
- Runs deep multi-timeframe analysis on all 30
- Scores each coin 0–100 using:
  ✅ EMA stack (9/21/50/200) across ALL timeframes
  ✅ Order Blocks (Bullish & Bearish OBs)
  ✅ Buy/Sell Pressure (Delta Volume analysis)
  ✅ Delta Divergence (smart money detection)
  ✅ Major Support & Resistance (min 3 touches to qualify)
  ✅ 30-Day buildup / consolidation detection
  ✅ ATR compression (volatility squeeze)
  ✅ RSI, MACD, Bollinger Bands, VWAP
  ✅ Multi-timeframe confluence (1m/5m/15m/1h/4h/1D)
- Returns TOP 5 coins with full trade setup
- Sends to Telegram every 30 minutes

---

## STEP 1: INSTALL PYTHON DEPENDENCIES

```bash
pip install requests pandas numpy schedule
```

---

## STEP 2: GET YOUR BYBIT API KEY

1. Go to https://www.bybit.com
2. Sign up / Log in
3. Click your avatar (top right) → API Management
4. Create a new API key:
   - Type: System-generated
   - Permissions: Read only (we only need to read market data)
   - No IP restriction needed for signals-only bot
5. Copy your API Key and API Secret

---

## STEP 3: GET YOUR TELEGRAM BOT TOKEN & CHAT ID

### Create Bot:
1. Open Telegram, search for @BotFather
2. Send: /newbot
3. Follow prompts, give it a name
4. BotFather will give you a TOKEN like: 1234567890:AAFxxx...
5. Copy that token

### Get Your Chat ID:
1. Start a chat with your new bot (send /start)
2. Open this URL in your browser (replace YOUR_TOKEN):
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
3. Look for "chat":{"id": XXXXXXXXX}
4. That number is your CHAT_ID

---

## STEP 4: CONFIGURE THE BOT

Open config.py and fill in:

```python
BYBIT_API_KEY    = "your_key_here"
BYBIT_API_SECRET = "your_secret_here"
TELEGRAM_BOT_TOKEN = "your_telegram_token"
TELEGRAM_CHAT_ID   = "your_chat_id"
```

---

## STEP 5: RUN THE BOT

```bash
cd bybit_bot
python main.py
```

The bot will:
1. Send a startup message to Telegram
2. Run the first scan immediately
3. Send top 5 signals to Telegram
4. Repeat every 30 minutes automatically

---

## SIGNAL EXPLAINED

Each Telegram signal includes:
- Score (0-100) and confidence level
- Direction (LONG or SHORT)
- Entry price
- Stop Loss (ATR-based, below key support)
- TP1, TP2, TP3 (at 1:1.5, 1:3, 1:5 RR)
- Major support & resistance levels
- Order block zones
- Buy/Sell pressure %
- Delta divergence warnings
- 30-day buildup status
- Full confluence breakdown

---

## RUNNING 24/7 (Optional)

### On a VPS (recommended):
```bash
# Install screen
sudo apt install screen

# Start bot in background
screen -S bybitbot
python main.py
# Press Ctrl+A then D to detach

# To reattach:
screen -r bybitbot
```

### Using nohup:
```bash
nohup python main.py > bot.log 2>&1 &
```

---

## FILE STRUCTURE

```
bybit_bot/
├── main.py           # Entry point — run this
├── config.py         # All settings (edit this)
├── scanner.py        # Main scan orchestrator
├── analysis.py       # TA engine (OB, S/R, scores)
├── data_fetcher.py   # Bybit API data fetcher
├── telegram_sender.py # Telegram formatting & sending
├── requirements.txt  # Python dependencies
└── SETUP.md          # This guide
```

---

## IMPORTANT NOTES

⚠️ This bot sends SIGNALS ONLY — it does NOT place trades.
⚠️ Always use your own judgment before entering a trade.
⚠️ Past performance does not guarantee future results.
⚠️ Never risk more than you can afford to lose.
⚠️ Start on Bybit TESTNET by setting BYBIT_TESTNET = True in config.py

---

## CUSTOMIZING

- Change SCAN_INTERVAL_MINS in config.py for more/less frequent scans
- Adjust MIN_SCORE_TO_SIGNAL (default 70) to be more/less strict
- Adjust DEFAULT_LEVERAGE for your risk appetite
- SR_TOUCH_MIN=3 means a level needs 3 touches to qualify as MAJOR
