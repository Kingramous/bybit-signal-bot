# ============================================================
#  ADVANCED ANALYSIS ENGINE
#  - Wyckoff Accumulation & Distribution
#  - Smart Money Concepts (SMC)
#  - Funding Rate Analysis
#  - Open Interest Analysis
#  - Liquidation Heatmap Levels
#  - Risk Score
#  - Position Size & Dollar P&L
# ============================================================

import requests
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bybit.com"


# ─────────────────────────────────────────────
#  WYCKOFF ANALYSIS
# ─────────────────────────────────────────────

def detect_wyckoff(df):
    """
    Detect Wyckoff accumulation or distribution phases.

    ACCUMULATION (buy signal):
    Phase A: Selling climax — huge volume, price stops falling
    Phase B: Building cause — price ranges, volume decreasing
    Phase C: Spring — price fakes breakdown then reverses up
    Phase D: Markup begins — price breaks out of range

    DISTRIBUTION (sell signal):
    Opposite of accumulation — big players selling into strength
    """
    if len(df) < 60:
        return {"detected": False, "phase": "UNKNOWN", "type": "NONE"}

    recent  = df.tail(60).copy().reset_index(drop=True)
    price   = recent["close"].iloc[-1]

    # Safety: avoid division by zero for an invalid/zero price
    if price == 0:
        return {"detected": False, "phase": "UNKNOWN", "type": "NONE",
                "confidence": 0, "spring": False, "upthrust": False,
                "is_ranging": False, "sell_climax": False, "buy_climax": False}

    volumes = recent["volume"]
    closes  = recent["close"]
    highs   = recent["high"]
    lows    = recent["low"]

    avg_vol   = volumes.mean()
    avg_range = (highs - lows).mean()

    # ── PHASE A: Climax detection ──
    # Selling climax = huge down candle with massive volume
    sell_climax = False
    buy_climax  = False
    for i in range(10, 50):
        candle_vol   = volumes.iloc[i]
        candle_range = highs.iloc[i] - lows.iloc[i]
        is_bearish   = closes.iloc[i] < recent["open"].iloc[i]
        is_bullish   = closes.iloc[i] > recent["open"].iloc[i]

        if candle_vol > avg_vol * 2.5 and candle_range > avg_range * 2 and is_bearish:
            sell_climax = True
        if candle_vol > avg_vol * 2.5 and candle_range > avg_range * 2 and is_bullish:
            buy_climax = True

    # ── PHASE B: Ranging/building cause ──
    last_20_range = (recent["high"].tail(20).max() - recent["low"].tail(20).min())
    price_range_pct = last_20_range / price
    is_ranging = price_range_pct < 0.12   # Less than 12% range = consolidating

    # ── PHASE C: Spring (false breakdown) for accumulation ──
    # Price briefly goes below support then comes back up
    low_20  = recent["low"].tail(20).min()
    low_40  = recent["low"].tail(40).min()
    spring  = low_20 < low_40 and closes.iloc[-1] > low_20 * 1.005

    # ── PHASE C: Upthrust (false breakout) for distribution ──
    high_20  = recent["high"].tail(20).max()
    high_40  = recent["high"].tail(40).max()
    upthrust = high_20 > high_40 and closes.iloc[-1] < high_20 * 0.995

    # ── PHASE D: Markup / Markdown ──
    ema20    = closes.ewm(span=20).mean()
    trending_up   = closes.iloc[-1] > ema20.iloc[-1] and ema20.iloc[-1] > ema20.iloc[-5]
    trending_down = closes.iloc[-1] < ema20.iloc[-1] and ema20.iloc[-1] < ema20.iloc[-5]

    # ── Volume trend ──
    vol_decreasing = volumes.tail(10).mean() < volumes.tail(30).mean()

    # ── CLASSIFY ──
    wyckoff_type  = "NONE"
    wyckoff_phase = "UNKNOWN"
    confidence    = 0

    if sell_climax and is_ranging and spring:
        wyckoff_type  = "ACCUMULATION"
        wyckoff_phase = "PHASE C — Spring detected (strong buy)"
        confidence    = 85
    elif sell_climax and is_ranging and vol_decreasing:
        wyckoff_type  = "ACCUMULATION"
        wyckoff_phase = "PHASE B — Building cause (prepare to buy)"
        confidence    = 70
    elif sell_climax and trending_up:
        wyckoff_type  = "ACCUMULATION"
        wyckoff_phase = "PHASE D — Markup in progress (buy dips)"
        confidence    = 75
    elif buy_climax and is_ranging and upthrust:
        wyckoff_type  = "DISTRIBUTION"
        wyckoff_phase = "PHASE C — Upthrust detected (strong sell)"
        confidence    = 85
    elif buy_climax and is_ranging and vol_decreasing:
        wyckoff_type  = "DISTRIBUTION"
        wyckoff_phase = "PHASE B — Building cause (prepare to sell)"
        confidence    = 70
    elif buy_climax and trending_down:
        wyckoff_type  = "DISTRIBUTION"
        wyckoff_phase = "PHASE D — Markdown in progress (sell rallies)"
        confidence    = 75

    detected = wyckoff_type != "NONE"

    return {
        "detected":    detected,
        "type":        wyckoff_type,
        "phase":       wyckoff_phase,
        "confidence":  confidence,
        "spring":      spring,
        "upthrust":    upthrust,
        "is_ranging":  is_ranging,
        "sell_climax": sell_climax,
        "buy_climax":  buy_climax,
    }


# ─────────────────────────────────────────────
#  SMART MONEY CONCEPTS (SMC)
# ─────────────────────────────────────────────

def detect_smc(df):
    """
    Smart Money Concepts:
    1. Break of Structure (BOS) — trend confirmation
    2. Change of Character (CHOCH) — trend reversal warning
    3. Liquidity grabs — stop hunts above/below key levels
    4. Fair Value Gaps (FVG) — imbalance zones price returns to
    5. Inducement — fake moves to grab liquidity before real move
    """
    if len(df) < 50:
        return {"detected": False}

    df   = df.tail(50).copy().reset_index(drop=True)
    n    = len(df)
    price = df["close"].iloc[-1]

    # Safety: avoid division by zero for an invalid/zero price
    if price == 0:
        return {"detected": False, "bos_bullish": False, "bos_bearish": False,
                "choch": False, "signals": [], "liquidity_levels": [],
                "fair_value_gaps": [], "inducement": False, "inducement_note": "",
                "swing_highs": [], "swing_lows": []}

    signals = []
    fvgs    = []
    liquidity_levels = []

    # ── BREAK OF STRUCTURE (BOS) ──
    # Bullish BOS: price breaks above previous swing high
    # Bearish BOS: price breaks below previous swing low
    swing_highs = []
    swing_lows  = []

    for i in range(2, n - 2):
        if df.loc[i,"high"] > df.loc[i-1,"high"] and df.loc[i,"high"] > df.loc[i+1,"high"]:
            swing_highs.append((i, df.loc[i,"high"]))
        if df.loc[i,"low"] < df.loc[i-1,"low"] and df.loc[i,"low"] < df.loc[i+1,"low"]:
            swing_lows.append((i, df.loc[i,"low"]))

    bos_bullish = False
    bos_bearish = False
    choch       = False

    if swing_highs:
        last_sh = swing_highs[-1][1]
        if price > last_sh:
            bos_bullish = True
            signals.append("🟢 Bullish BOS — structure broken upward")

    if swing_lows:
        last_sl = swing_lows[-1][1]
        if price < last_sl:
            bos_bearish = True
            signals.append("🔴 Bearish BOS — structure broken downward")

    # ── CHANGE OF CHARACTER (CHOCH) ──
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        # Was making higher highs but now made lower high = bearish CHOCH
        if swing_highs[-1][1] < swing_highs[-2][1] and bos_bearish:
            choch = True
            signals.append("⚠️ CHOCH — trend may be reversing bearish")
        # Was making lower lows but now made higher low = bullish CHOCH
        if swing_lows[-1][1] > swing_lows[-2][1] and bos_bullish:
            choch = True
            signals.append("⚠️ CHOCH — trend may be reversing bullish")

    # ── LIQUIDITY GRABS ──
    # Equal highs/lows = liquidity pools (stop hunt targets)
    for i in range(len(swing_highs) - 1):
        h1 = swing_highs[i][1]
        h2 = swing_highs[i+1][1]
        if h1 != 0 and abs(h1 - h2) / h1 < 0.003:   # within 0.3% = equal highs
            liquidity_levels.append({
                "level": round((h1 + h2) / 2, 4),
                "type":  "SELL SIDE LIQUIDITY",
                "note":  "Stop hunts likely above this level",
            })

    for i in range(len(swing_lows) - 1):
        l1 = swing_lows[i][1]
        l2 = swing_lows[i+1][1]
        if l1 != 0 and abs(l1 - l2) / l1 < 0.003:
            liquidity_levels.append({
                "level": round((l1 + l2) / 2, 4),
                "type":  "BUY SIDE LIQUIDITY",
                "note":  "Stop hunts likely below this level",
            })

    # ── FAIR VALUE GAPS (FVG) ──
    # FVG = 3 candle pattern where candle 1 high < candle 3 low (bullish)
    # or candle 1 low > candle 3 high (bearish)
    for i in range(1, n - 1):
        c1_high = df.loc[i-1, "high"]
        c1_low  = df.loc[i-1, "low"]
        c3_high = df.loc[i+1, "high"]
        c3_low  = df.loc[i+1, "low"]

        # Bullish FVG
        if c1_high < c3_low:
            gap_size = (c3_low - c1_high) / price * 100
            if gap_size > 0.3:   # Only significant gaps
                fvgs.append({
                    "type":   "BULLISH FVG",
                    "high":   round(c3_low, 4),
                    "low":    round(c1_high, 4),
                    "mid":    round((c3_low + c1_high) / 2, 4),
                    "size":   round(gap_size, 2),
                    "note":   "Price likely returns here to fill gap",
                })

        # Bearish FVG
        if c1_low > c3_high:
            gap_size = (c1_low - c3_high) / price * 100
            if gap_size > 0.3:
                fvgs.append({
                    "type":   "BEARISH FVG",
                    "high":   round(c1_low, 4),
                    "low":    round(c3_high, 4),
                    "mid":    round((c1_low + c3_high) / 2, 4),
                    "size":   round(gap_size, 2),
                    "note":   "Price likely returns here to fill gap",
                })

    # Keep only most recent FVGs near current price
    fvgs_near = sorted(fvgs, key=lambda x: abs(price - x["mid"]))[:3]

    # ── INDUCEMENT ──
    # Fake move beyond a level then sharp reversal
    inducement = False
    inducement_note = ""
    if len(df) >= 5:
        recent_5 = df.tail(5)
        range_high = recent_5["high"].max()
        range_low  = recent_5["low"].min()
        last_close = recent_5["close"].iloc[-1]

        # Price spiked above range then came back = bearish inducement
        if range_high > df.tail(20)["high"].quantile(0.9) and last_close < range_high * 0.995:
            inducement = True
            inducement_note = "🪤 Bearish inducement — price spiked up to grab stops then reversed"

        # Price spiked below range then came back = bullish inducement
        if range_low < df.tail(20)["low"].quantile(0.1) and last_close > range_low * 1.005:
            inducement = True
            inducement_note = "🪤 Bullish inducement — price spiked down to grab stops then reversed"

    return {
        "detected":          len(signals) > 0,
        "bos_bullish":       bos_bullish,
        "bos_bearish":       bos_bearish,
        "choch":             choch,
        "signals":           signals,
        "liquidity_levels":  liquidity_levels[:4],
        "fair_value_gaps":   fvgs_near,
        "inducement":        inducement,
        "inducement_note":   inducement_note,
        "swing_highs":       [round(h[1], 4) for h in swing_highs[-3:]],
        "swing_lows":        [round(l[1], 4) for l in swing_lows[-3:]],
    }


# ─────────────────────────────────────────────
#  FUNDING RATE
# ─────────────────────────────────────────────

def get_funding_rate(symbol):
    """
    Fetch current funding rate from Bybit.
    Positive = longs paying shorts (market overleveraged long = bearish signal)
    Negative = shorts paying longs (market overleveraged short = bullish signal)
    """
    try:
        url    = f"{BASE_URL}/v5/market/tickers"
        params = {"category": "linear", "symbol": symbol}
        r      = requests.get(url, params=params, timeout=10)
        data   = r.json()

        if data.get("retCode") != 0 or not data["result"]["list"]:
            return {"available": False}

        item            = data["result"]["list"][0]
        funding_rate    = float(item.get("fundingRate", 0))
        next_funding    = item.get("nextFundingTime", "")
        funding_pct     = funding_rate * 100

        # Interpret the funding rate
        if funding_pct > 0.1:
            interpretation = "🔴 HIGHLY OVERLEVERAGED LONG — reversal risk HIGH"
            bias           = "BEARISH"
        elif funding_pct > 0.05:
            interpretation = "🟡 Longs dominant — slight bearish pressure"
            bias           = "SLIGHTLY BEARISH"
        elif funding_pct < -0.1:
            interpretation = "🟢 HIGHLY OVERLEVERAGED SHORT — squeeze risk HIGH"
            bias           = "BULLISH"
        elif funding_pct < -0.05:
            interpretation = "🟡 Shorts dominant — slight bullish pressure"
            bias           = "SLIGHTLY BULLISH"
        else:
            interpretation = "⚪ Funding neutral — balanced market"
            bias           = "NEUTRAL"

        return {
            "available":      True,
            "rate":           round(funding_pct, 4),
            "bias":           bias,
            "interpretation": interpretation,
            "next_funding":   next_funding,
            "8h_cost":        round(abs(funding_pct), 4),
        }

    except Exception as e:
        logger.error(f"Funding rate error {symbol}: {e}")
        return {"available": False}


# ─────────────────────────────────────────────
#  OPEN INTEREST
# ─────────────────────────────────────────────

def get_open_interest(symbol):
    """
    Fetch open interest history to detect smart money flow.
    Price UP + OI UP   = Real bullish move (strong)
    Price UP + OI DOWN = Short covering (weak, may reverse)
    Price DOWN + OI UP = Real bearish move (strong)
    Price DOWN + OI DOWN = Long liquidation (may bounce)
    """
    try:
        url    = f"{BASE_URL}/v5/market/open-interest"
        params = {
            "category":     "linear",
            "symbol":       symbol,
            "intervalTime": "1h",
            "limit":        48,   # Last 48 hours
        }
        r    = requests.get(url, params=params, timeout=10)
        data = r.json()

        if data.get("retCode") != 0 or not data["result"]["list"]:
            return {"available": False}

        oi_list = data["result"]["list"]
        if len(oi_list) < 5:
            return {"available": False}

        oi_values = [float(x["openInterest"]) for x in oi_list]
        oi_now    = oi_values[0]
        oi_24h    = oi_values[min(24, len(oi_values)-1)]
        oi_change = ((oi_now - oi_24h) / oi_24h * 100) if oi_24h > 0 else 0

        # OI trend
        oi_increasing = oi_now > oi_24h
        oi_trend      = "INCREASING" if oi_increasing else "DECREASING"

        # Get price change over same period
        price_url    = f"{BASE_URL}/v5/market/kline"
        price_params = {"category": "linear", "symbol": symbol, "interval": "60", "limit": 25}
        pr           = requests.get(price_url, params=price_params, timeout=10)
        price_data   = pr.json()

        interpretation = "⚪ Insufficient data"
        signal         = "NEUTRAL"
        strength       = "UNKNOWN"

        if price_data.get("retCode") == 0 and price_data["result"]["list"]:
            candles       = price_data["result"]["list"]
            price_now     = float(candles[0][4])
            price_24h_ago = float(candles[min(24, len(candles)-1)][4])
            price_change  = price_now > price_24h_ago

            if price_change and oi_increasing:
                interpretation = "🟢 Price UP + OI UP — Real buyers entering. STRONG BULLISH"
                signal         = "BULLISH"
                strength       = "STRONG"
            elif price_change and not oi_increasing:
                interpretation = "🟡 Price UP + OI DOWN — Short covering only. WEAK move"
                signal         = "BULLISH"
                strength       = "WEAK"
            elif not price_change and oi_increasing:
                interpretation = "🔴 Price DOWN + OI UP — Real sellers entering. STRONG BEARISH"
                signal         = "BEARISH"
                strength       = "STRONG"
            else:
                interpretation = "🟡 Price DOWN + OI DOWN — Liquidations. Bounce possible"
                signal         = "BEARISH"
                strength       = "WEAK"

        return {
            "available":      True,
            "oi_now":         round(oi_now, 2),
            "oi_change_24h":  round(oi_change, 2),
            "oi_trend":       oi_trend,
            "signal":         signal,
            "strength":       strength,
            "interpretation": interpretation,
        }

    except Exception as e:
        logger.error(f"OI error {symbol}: {e}")
        return {"available": False}


# ─────────────────────────────────────────────
#  LIQUIDATION HEATMAP LEVELS
# ─────────────────────────────────────────────

def get_liquidation_levels(symbol, df, sr):
    """
    Estimate liquidation levels based on:
    - Key S/R levels (clusters of stop losses)
    - Round numbers (psychological levels)
    - Previous highs/lows (where retail places stops)
    - Funding rate (direction of crowded trade)
    """
    # Safety: empty dataframe or invalid price
    if len(df) == 0:
        return {"available": False, "levels": [], "note": "No price data available"}

    price    = df["close"].iloc[-1]
    levels   = []

    if price <= 0:
        return {"available": False, "levels": [], "note": "Invalid price (zero or negative)"}

    # Round number levels (big magnets for price)
    # Works for any price scale: large (50000) or tiny (0.0001234)
    if price >= 1:
        magnitude = 10 ** (len(str(int(price))) - 2)
        magnitude = max(magnitude, 0.01)
    else:
        # For sub-$1 prices, magnitude = roughly 1-2% of price,
        # rounded to a clean power of 10. e.g. price=0.016331 -> magnitude=0.001
        decimals = 0
        temp = price
        while temp < 1 and decimals < 15:
            temp *= 10
            decimals += 1
        # decimals = position of first significant digit (e.g. 0.016 -> decimals=2)
        # use one extra decimal place for a finer grid (e.g. magnitude=0.001 for price=0.016)
        magnitude = 10 ** (-(decimals + 1))

    if magnitude > 0:
        for mult in range(int(price / magnitude) - 5, int(price / magnitude) + 6):
            level = mult * magnitude
            if level > 0 and abs(level - price) / price < 0.15:
                distance_pct = round((level - price) / price * 100, 2)
                levels.append({
                    "level":    round(level, 8),
                    "type":     "ROUND NUMBER",
                    "distance": f"{distance_pct:+.1f}%",
                    "note":     "High liquidity — stop hunts common here",
                })

    # S/R based liquidation clusters
    for sup in (sr.get("supports") or [])[-3:]:
        distance_pct = round((sup["level"] - price) / price * 100, 2)
        levels.append({
            "level":    sup["level"],
            "type":     f"SUPPORT CLUSTER ({sup['touches']} touches)",
            "distance": f"{distance_pct:+.1f}%",
            "note":     "Long stop losses clustered here",
        })

    for res in (sr.get("resistances") or [])[:3]:
        distance_pct = round((res["level"] - price) / price * 100, 2)
        levels.append({
            "level":    res["level"],
            "type":     f"RESISTANCE CLUSTER ({res['touches']} touches)",
            "distance": f"{distance_pct:+.1f}%",
            "note":     "Short stop losses clustered here",
        })

    # Sort by proximity to current price
    levels.sort(key=lambda x: abs(float(x["distance"].replace("%", "").replace("+", ""))))

    return {
        "available": True,
        "levels":    levels[:6],
        "note":      "Price is magnetically attracted to these levels",
    }


# ─────────────────────────────────────────────
#  RISK SCORE
# ─────────────────────────────────────────────

def calculate_risk_score(score, funding, oi, wyckoff, smc, setup):
    """
    Calculate a risk score from 1 (safest) to 10 (most dangerous).
    Lower is better.
    """
    risk = 5   # Start at medium

    # Confluence score reduces risk
    if score >= 80:   risk -= 2
    elif score >= 65: risk -= 1
    elif score < 50:  risk += 2

    # Funding rate risk
    if funding.get("available"):
        if "HIGHLY OVERLEVERAGED" in funding.get("interpretation", ""):
            risk += 2
        elif "NEUTRAL" in funding.get("bias", ""):
            risk -= 1

    # OI confirms move = lower risk
    if oi.get("available"):
        if oi.get("strength") == "STRONG":
            risk -= 1
        elif oi.get("strength") == "WEAK":
            risk += 1

    # Wyckoff reduces risk if detected
    if wyckoff.get("detected"):
        if wyckoff.get("confidence", 0) >= 80:
            risk -= 1

    # SMC CHOCH = higher risk (trend changing)
    if smc.get("choch"):
        risk += 1

    # Inducement detected = higher risk
    if smc.get("inducement"):
        risk += 1

    # RR ratio reduces risk
    rr = setup.get("rr_ratio", 1)
    if rr >= 3:   risk -= 1
    elif rr < 2:  risk += 1

    risk = max(1, min(10, risk))

    if risk <= 3:
        label = "🟢 LOW RISK — Strong setup"
    elif risk <= 6:
        label = "🟡 MEDIUM RISK — Trade with care"
    else:
        label = "🔴 HIGH RISK — Small size or skip"

    return {"score": risk, "label": label}


# ─────────────────────────────────────────────
#  POSITION SIZE & DOLLAR P&L
# ─────────────────────────────────────────────

def calculate_pnl(setup, trade_amount, leverage=10):
    """
    Calculate exact dollar profit/loss for a trade.
    trade_amount = how much USDT you put in (e.g. $100)
    leverage     = 10x default
    """
    entry = setup["entry"]
    sl    = setup["sl"]
    tp1   = setup["tp1"]
    tp2   = setup["tp2"]
    tp3   = setup["tp3"]
    direction = setup["direction"]

    position_size = trade_amount * leverage   # Total position value

    # Safety: avoid division by zero (entry should never be 0 in practice,
    # but a delisted/invalid symbol could theoretically return 0)
    if entry == 0:
        return {
            "trade_amount": trade_amount, "leverage": leverage,
            "position_size": round(position_size, 2),
            "sl_loss": 0, "tp1_gain": 0, "tp2_gain": 0, "tp3_gain": 0,
            "sl_pct": 0, "tp1_pct": 0, "tp2_pct": 0, "tp3_pct": 0,
        }

    def pct_move(from_price, to_price):
        return (to_price - from_price) / from_price

    if direction == "LONG":
        sl_pct  = pct_move(entry, sl)
        tp1_pct = pct_move(entry, tp1)
        tp2_pct = pct_move(entry, tp2)
        tp3_pct = pct_move(entry, tp3)
    else:
        sl_pct  = -pct_move(entry, sl)
        tp1_pct = -pct_move(entry, tp1)
        tp2_pct = -pct_move(entry, tp2)
        tp3_pct = -pct_move(entry, tp3)

    sl_loss   = round(position_size * sl_pct,  2)
    tp1_gain  = round(position_size * tp1_pct, 2)
    tp2_gain  = round(position_size * tp2_pct, 2)
    tp3_gain  = round(position_size * tp3_pct, 2)

    return {
        "trade_amount":   trade_amount,
        "leverage":       leverage,
        "position_size":  round(position_size, 2),
        "sl_loss":        sl_loss,
        "tp1_gain":       tp1_gain,
        "tp2_gain":       tp2_gain,
        "tp3_gain":       tp3_gain,
        "sl_pct":         round(sl_pct * 100,  2),
        "tp1_pct":        round(tp1_pct * 100, 2),
        "tp2_pct":        round(tp2_pct * 100, 2),
        "tp3_pct":        round(tp3_pct * 100, 2),
    }


# ─────────────────────────────────────────────
#  FULL ADVANCED ANALYSIS (runs everything)
# ─────────────────────────────────────────────

def run_advanced_analysis(symbol, df_1h, df_daily, sr, setup,
                           confluence_score, trade_amount=100, leverage=10):
    """
    Runs all advanced analysis and returns a complete result dict.
    """
    wyckoff  = detect_wyckoff(df_daily)
    smc      = detect_smc(df_1h if df_1h is not None else df_daily)
    funding  = get_funding_rate(symbol)
    oi       = get_open_interest(symbol)
    liq      = get_liquidation_levels(symbol, df_daily, sr)
    risk     = calculate_risk_score(confluence_score, funding, oi, wyckoff, smc, setup)
    pnl      = calculate_pnl(setup, trade_amount, leverage)

    return {
        "wyckoff":             wyckoff,
        "smc":                 smc,
        "funding":             funding,
        "open_interest":       oi,
        "liquidation_levels":  liq,
        "risk":                risk,
        "pnl":                 pnl,
    }


# ─────────────────────────────────────────────
#  SHORT SIGNAL CONFIRMATION FILTER
# ─────────────────────────────────────────────

def check_daily_4h_bearish(tf_data):
    """
    Check if BOTH Daily and 4H timeframes show bearish EMA alignment.
    Returns True only if both agree on bearish structure.
    """
    from analysis import add_all_indicators

    daily_df = tf_data.get("1D")
    h4_df    = tf_data.get("4h")

    if daily_df is None or h4_df is None:
        return False
    if len(daily_df) < 50 or len(h4_df) < 50:
        return False

    daily_df = add_all_indicators(daily_df)
    h4_df    = add_all_indicators(h4_df)

    daily_last = daily_df.iloc[-1]
    h4_last    = h4_df.iloc[-1]

    daily_bearish = daily_last["ema9"] < daily_last["ema21"] < daily_last["ema50"]
    h4_bearish    = h4_last["ema9"]    < h4_last["ema21"]    < h4_last["ema50"]

    return daily_bearish and h4_bearish


def confirm_short_signal(tf_data, funding, oi):
    """
    SHORT signals require at least 2 of 3 confirmations:
    1. Daily AND 4H both bearish
    2. Funding rate positive (longs overleveraged → bearish pressure)
    3. OI increasing while price falling (real sellers, not just covering)

    Returns dict with confirmation status and details.
    """
    confirmations = []
    confirmed_count = 0

    # ── Confirmation 1: Daily + 4H bearish alignment ──
    daily_4h_bearish = check_daily_4h_bearish(tf_data)
    if daily_4h_bearish:
        confirmed_count += 1
        confirmations.append("✅ Daily + 4H both bearish")
    else:
        confirmations.append("❌ Daily + 4H not aligned bearish")

    # ── Confirmation 2: Funding rate positive (longs overleveraged) ──
    funding_confirmed = False
    if funding.get("available"):
        rate = funding.get("rate", 0)
        if rate > 0.01:   # Positive funding = longs paying shorts
            funding_confirmed = True
            confirmed_count += 1
            confirmations.append(f"✅ Funding positive ({rate:+.4f}%) — longs overleveraged")
        else:
            confirmations.append(f"❌ Funding not bearish ({rate:+.4f}%)")
    else:
        confirmations.append("⚪ Funding data unavailable")

    # ── Confirmation 3: OI increasing while price falling (real selling) ──
    oi_confirmed = False
    if oi.get("available"):
        if oi.get("signal") == "BEARISH" and oi.get("strength") == "STRONG":
            oi_confirmed = True
            confirmed_count += 1
            confirmations.append("✅ OI rising + price falling — real sellers")
        else:
            confirmations.append(f"❌ OI doesn't confirm ({oi.get('interpretation','N/A')[:40]})")
    else:
        confirmations.append("⚪ OI data unavailable")

    is_valid = confirmed_count >= 2

    return {
        "valid":         is_valid,
        "confirmed":     confirmed_count,
        "required":      2,
        "details":       confirmations,
        "daily_4h_bearish": daily_4h_bearish,
        "funding_confirmed": funding_confirmed,
        "oi_confirmed":  oi_confirmed,
    }


# ─────────────────────────────────────────────
#  CONFLICT WARNING (read-only — does not change direction/score)
# ─────────────────────────────────────────────

def detect_conflict(direction, score_result, pressure, tf_data):
    """
    Detects MEANINGFUL conflicts where multiple indicators disagree
    with the called direction. PURELY INFORMATIONAL — does not change
    direction, score, or setup in any way.

    Triggers when ANY of these are true for a LONG call:
    - Short-term EMA stacks (1m/5m/15m) are mostly bearish
    - Sellers strongly dominate pressure (>55%)
    - OI confirms bearish (price down + OI up)
    - Bearish delta divergence present
    And vice versa for SHORT.
    """
    reasons  = score_result.get("reasons", [])
    conflicts = []

    # ── Check 1: Short-term EMA direction vs called direction ──
    short_tfs = ["1m", "5m", "15m"]
    opposite_stf = 0
    total_stf    = 0

    for tf in short_tfs:
        tf_df = tf_data.get(tf)
        if tf_df is None or (hasattr(tf_df, '__len__') and len(tf_df) < 50):
            continue
        total_stf += 1
        # Look in reasons (capped at 8) AND re-check the actual dataframe
        from analysis import add_all_indicators, calc_ema
        try:
            df_check = tf_df.copy() if hasattr(tf_df, 'copy') else tf_df
            if "ema9" not in df_check.columns:
                df_check = add_all_indicators(df_check)
            last = df_check.iloc[-1]
            tf_bearish = last["ema9"] < last["ema21"] < last["ema50"]
            tf_bullish = last["ema9"] > last["ema21"] > last["ema50"]
            if direction == "LONG"  and tf_bearish: opposite_stf += 1
            if direction == "SHORT" and tf_bullish:  opposite_stf += 1
        except Exception:
            pass

    if total_stf > 0 and opposite_stf >= 2:
        opp_word = "bearish" if direction == "LONG" else "bullish"
        conflicts.append(f"Short-term momentum ({opposite_stf}/{total_stf} of 1m-15m) is {opp_word}")

    # ── Check 2: 1H pressure strongly opposes direction ──
    pressure_dominant = pressure.get("dominant", "NEUTRAL")
    sell_pct = pressure.get("sell_pct", 50)
    buy_pct  = pressure.get("buy_pct",  50)

    if direction == "LONG"  and pressure_dominant == "SELLERS" and sell_pct > 55:
        conflicts.append(f"Sellers dominate 1H pressure ({sell_pct}%)")
    if direction == "SHORT" and pressure_dominant == "BUYERS"  and buy_pct > 55:
        conflicts.append(f"Buyers dominate 1H pressure ({buy_pct}%)")

    # ── Check 3: Delta divergence opposes direction ──
    divergence = pressure.get("divergence", "NONE")
    if direction == "LONG"  and divergence == "BEARISH_DIVERGENCE":
        conflicts.append("Bearish delta divergence — smart money distributing")
    if direction == "SHORT" and divergence == "BULLISH_DIVERGENCE":
        conflicts.append("Bullish delta divergence — smart money accumulating")

    # Only flag if at least 2 independent signals conflict
    has_conflict = len(conflicts) >= 2

    if not has_conflict:
        return {"detected": False}

    direction_word = "LONG" if direction == "LONG" else "SHORT"
    conflict_lines = " | ".join(conflicts)

    note = f"Direction called {direction_word} but {len(conflicts)} signals disagree: {conflict_lines}"

    action_plan = (
        f"The higher timeframes (Daily/4H) overrode short-term signals to call {direction_word}. "
        f"If TP1 doesn't hit within a few hours, consider exiting — "
        f"the short-term signals may be the early warning."
    )

    return {
        "detected":    True,
        "note":        note,
        "action_plan": action_plan,
        "conflict_count": len(conflicts),
        "conflicts":   conflicts,
    }
