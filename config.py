# ============================================================
#  BYBIT FUTURES SIGNAL BOT — CONFIGURATION
# ============================================================

# --- BYBIT API (get from bybit.com > API Management) --------
BYBIT_API_KEY    = "Ga7MHQjJh6hLHY5C6z"
BYBIT_API_SECRET = "0slYQIjQLF0NoHTjISUhStC4hxVWC6XhCgPC"
BYBIT_TESTNET    = False          # Set True to test without real money

# --- TELEGRAM (get from @BotFather) --------------------------
TELEGRAM_BOT_TOKEN = "8786856212:AAFDpn0L16j9cDuH4nSNllY_JtXj1HeHcWM"
TELEGRAM_CHAT_ID   = "6273650640"

# --- SCANNING SETTINGS ---------------------------------------
TOP_N_COINS          = 5          # How many top coins to return
MIN_SCORE_TO_SIGNAL  = 70         # Minimum score (0-100) to send signal
SCAN_INTERVAL_MINS   = 30         # How often to scan (minutes)

# --- TIMEFRAMES TO ANALYZE -----------------------------------
# Bot analyses ALL timeframes and scores each coin holistically
TIMEFRAMES = {
    "1m":  "1",
    "5m":  "5",
    "15m": "15",
    "1h":  "60",
    "4h":  "240",
    "1D":  "D",
}
PRIMARY_TF   = "1D"   # Daily — used for 30-day buildup & major S/R
CONFIRM_TF   = "4h"   # 4H — used for entry confirmation
ENTRY_TF     = "1h"   # 1H — used for precise entry timing

# --- ORDER BLOCK SETTINGS ------------------------------------
OB_LOOKBACK       = 50    # Candles to look back for Order Blocks
OB_MIN_BODY_RATIO = 0.6   # Min body/range ratio to qualify as OB candle
OB_MITIGATION_PCT = 0.3   # How deep into OB price can go (30%)

# --- SUPPORT & RESISTANCE ------------------------------------
SR_LOOKBACK       = 200   # Candles to find major S/R levels
SR_TOUCH_MIN      = 3     # Minimum touches to qualify as MAJOR level
SR_ZONE_PCT       = 0.005 # 0.5% zone around level (cluster nearby levels)

# --- 30-DAY BUILDUP DETECTION --------------------------------
BUILDUP_DAYS         = 30    # Minimum days of consolidation
BUILDUP_MAX_RANGE    = 0.15  # Max 15% range to qualify as buildup
BUILDUP_MIN_VOLUME   = 1.2   # Volume must be 1.2x average during buildup

# --- VOLUME & VOLATILITY FILTERS -----------------------------
MIN_24H_VOLUME_USDT  = 10_000_000   # $10M minimum 24h volume
MIN_VOLATILITY_PCT   = 1.5          # Minimum 1.5% daily move
MAX_VOLATILITY_PCT   = 15.0         # Maximum 15% (avoid pump/dump)

# --- RISK SETTINGS -------------------------------------------
DEFAULT_LEVERAGE     = 10     # 10x leverage
RISK_REWARD_MIN      = 2.0    # Minimum 1:2 risk/reward ratio
SL_ATR_MULTIPLIER    = 1.5    # Stop loss = 1.5x ATR below entry
TP1_RR               = 1.5    # Take profit 1 at 1:1.5
TP2_RR               = 3.0    # Take profit 2 at 1:3
TP3_RR               = 5.0    # Take profit 3 at 1:5 (runner)
