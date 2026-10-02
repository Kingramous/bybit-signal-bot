# ============================================================
#  TECHNICAL ANALYSIS ENGINE - PROFESSIONAL v3.0
#  - Order Blocks, S/R, Buildup, Pressure
#  - Wyckoff Accumulation/Distribution
#  - Smart Money Concepts (SMC)
#  - Risk Scoring
# ============================================================

import numpy as np
import pandas as pd
from config import (
    OB_LOOKBACK, OB_MIN_BODY_RATIO, OB_MITIGATION_PCT,
    SR_LOOKBACK, SR_TOUCH_MIN, SR_ZONE_PCT,
    BUILDUP_DAYS, BUILDUP_MAX_RANGE, BUILDUP_MIN_VOLUME,
    TP1_RR, TP2_RR, TP3_RR
)


# ─────────────────────────────────────────────
#  SMART DECIMAL PRECISION HELPER
# ─────────────────────────────────────────────

def smart_round(value, price):
    """
    Round a price value to the correct number of decimal places
    based on the magnitude of the coin's price.
    Ensures SL and TP values are never identical due to insufficient precision.
    Examples:
      price=0.0005 -> 6 decimal places  (e.g. 0.000490)
      price=0.016  -> 5 decimal places  (e.g. 0.01568)
      price=2.228  -> 3 decimal places  (e.g. 2.183)
      price=68.12  -> 2 decimal places  (e.g. 66.76)
      price=50000  -> 2 decimal places  (e.g. 49000.00)
    """
    if price <= 0 or value <= 0:
        return round(value, 8)
    sl_dist = price * 0.02  # 2% SL distance as reference
    if sl_dist == 0:
        return round(value, 8)
    import math
    sig_pos = -int(math.floor(math.log10(abs(sl_dist)))) + 1
    decimals = max(sig_pos, 2)
    return round(value, decimals)


# ─────────────────────────────────────────────
#  INDICATORS
# ─────────────────────────────────────────────

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(series):
    fast   = calc_ema(series, 12)
    slow   = calc_ema(series, 26)
    macd   = fast - slow
    signal = calc_ema(macd, 9)
    return macd, signal, macd - signal

def calc_bollinger(series, period=20, std=2.0):
    mid   = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    return mid + std * sigma, mid, mid - std * sigma

def calc_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).cumsum() / df["volume"].cumsum()

def add_all_indicators(df):
    df = df.copy()
    df["ema9"]   = calc_ema(df["close"], 9)
    df["ema21"]  = calc_ema(df["close"], 21)
    df["ema50"]  = calc_ema(df["close"], 50)
    df["ema200"] = calc_ema(df["close"], 200)
    df["atr"]    = calc_atr(df)
    df["rsi"]    = calc_rsi(df["close"])
    df["macd"], df["macd_signal"], df["macd_hist"] = calc_macd(df["close"])
    df["bb_upper"], df["bb_mid"], df["bb_lower"]   = calc_bollinger(df["close"])
    df["vwap"]   = calc_vwap(df)
    df["candle_range"]     = (df["high"] - df["low"]).replace(0, np.nan)
    df["buy_pressure"]     = ((df["close"] - df["low"])  / df["candle_range"]) * df["volume"]
    df["sell_pressure"]    = ((df["high"]  - df["close"]) / df["candle_range"]) * df["volume"]
    df["delta"]            = df["buy_pressure"] - df["sell_pressure"]
    df["cumulative_delta"] = df["delta"].cumsum()
    return df


# ─────────────────────────────────────────────
#  SUPPORT & RESISTANCE
# ─────────────────────────────────────────────

def find_major_sr(df):
    if len(df) == 0:
        return {"supports": [], "resistances": [], "nearest_support": None, "nearest_resistance": None, "current_price": 0}
    df    = df.tail(SR_LOOKBACK).copy().reset_index(drop=True)
    price = df["close"].iloc[-1]
    swings = []

    for i in range(2, len(df) - 2):
        if (df.loc[i,"high"] > df.loc[i-1,"high"] and
            df.loc[i,"high"] > df.loc[i-2,"high"] and
            df.loc[i,"high"] > df.loc[i+1,"high"] and
            df.loc[i,"high"] > df.loc[i+2,"high"]):
            swings.append(("resistance", df.loc[i,"high"]))
        if (df.loc[i,"low"] < df.loc[i-1,"low"] and
            df.loc[i,"low"] < df.loc[i-2,"low"] and
            df.loc[i,"low"] < df.loc[i+1,"low"] and
            df.loc[i,"low"] < df.loc[i+2,"low"]):
            swings.append(("support", df.loc[i,"low"]))

    def cluster(levels, kind):
        if not levels:
            return []
        ls = sorted(levels)
        zones, zone = [], [ls[0]]
        for lvl in ls[1:]:
            if (lvl - zone[-1]) / zone[-1] < SR_ZONE_PCT:
                zone.append(lvl)
            else:
                zones.append(zone); zone = [lvl]
        zones.append(zone)
        result = []
        for z in zones:
            if len(z) >= SR_TOUCH_MIN:
                result.append({
                    "level":    round(sum(z)/len(z), 4),
                    "touches":  len(z),
                    "kind":     kind,
                    "strength": "MAJOR" if len(z) >= 4 else "STRONG",
                })
        return sorted(result, key=lambda x: x["touches"], reverse=True)

    supports    = cluster([v for k,v in swings if k=="support"],    "support")
    resistances = cluster([v for k,v in swings if k=="resistance"], "resistance")
    key_sup = sorted([z for z in supports    if z["level"] < price], key=lambda x: x["level"])
    key_res = sorted([z for z in resistances if z["level"] > price], key=lambda x: x["level"])

    return {
        "supports":           key_sup,
        "resistances":        key_res,
        "nearest_support":    key_sup[-1] if key_sup else None,
        "nearest_resistance": key_res[0]  if key_res else None,
        "current_price":      round(price, 4),
    }


# ─────────────────────────────────────────────
#  ORDER BLOCKS
# ─────────────────────────────────────────────

def find_order_blocks(df):
    if len(df) == 0:
        return {"bullish": [], "bearish": []}
    df       = df.tail(OB_LOOKBACK).copy().reset_index(drop=True)
    bull_obs, bear_obs = [], []
    for i in range(1, len(df) - 2):
        body = abs(df.loc[i,"close"] - df.loc[i,"open"])
        rng  = df.loc[i,"high"] - df.loc[i,"low"]
        if rng == 0 or body/rng < OB_MIN_BODY_RATIO: continue
        if df.loc[i,"close"] < df.loc[i,"open"]:
            if df.loc[i+1,"close"] > df.loc[i,"high"]:
                oh,ol = df.loc[i,"high"], df.loc[i,"low"]
                if not any(c < ol-(oh-ol)*OB_MITIGATION_PCT for c in df.loc[i+1:,"close"]):
                    bull_obs.append({"type":"bullish","high":round(oh,4),"low":round(ol,4),"mid":round((oh+ol)/2,4)})
        elif df.loc[i,"close"] > df.loc[i,"open"]:
            if df.loc[i+1,"close"] < df.loc[i,"low"]:
                oh,ol = df.loc[i,"high"], df.loc[i,"low"]
                if not any(c > oh+(oh-ol)*OB_MITIGATION_PCT for c in df.loc[i+1:,"close"]):
                    bear_obs.append({"type":"bearish","high":round(oh,4),"low":round(ol,4),"mid":round((oh+ol)/2,4)})
    cp = df["close"].iloc[-1]
    bull_obs.sort(key=lambda x: abs(cp-x["mid"]))
    bear_obs.sort(key=lambda x: abs(cp-x["mid"]))
    return {"bullish": bull_obs[:3], "bearish": bear_obs[:3]}


# ─────────────────────────────────────────────
#  30-DAY BUILDUP
# ─────────────────────────────────────────────

def detect_buildup(df_daily):
    if len(df_daily) < BUILDUP_DAYS + 10:
        return {"detected": False, "reason": "Not enough data"}

    recent = df_daily.tail(BUILDUP_DAYS).copy()
    older  = df_daily.tail(BUILDUP_DAYS * 2).head(BUILDUP_DAYS).copy()
    high   = recent["high"].max()
    low    = recent["low"].min()
    if low == 0:
        return {"detected": False, "reason": "Zero low"}

    price_range = (high - low) / low
    if price_range > BUILDUP_MAX_RANGE:
        return {"detected": False, "reason": f"Range too wide: {price_range:.1%}"}

    vol_ratio  = recent["volume"].mean() / older["volume"].mean() if older["volume"].mean() > 0 else 1
    atr_recent = recent["atr"].mean() if "atr" in recent.columns else 0
    atr_older  = older["atr"].mean()  if "atr" in older.columns  else 1
    atr_ratio  = atr_recent / atr_older if atr_older > 0 else 1

    lows  = recent["low"].values
    highs = recent["high"].values
    hl    = sum(1 for i in range(1,len(lows))  if lows[i]  > lows[i-1])
    lh    = sum(1 for i in range(1,len(highs)) if highs[i] < highs[i-1])
    coil  = (hl + lh) / (2 * (len(lows) - 1))

    bs = 0
    if price_range < 0.08:   bs += 30
    elif price_range < 0.12: bs += 20
    else:                    bs += 10
    if vol_ratio >= BUILDUP_MIN_VOLUME: bs += 25
    if atr_ratio  < 0.8:               bs += 25
    if coil > 0.55:                    bs += 20

    close_now = recent["close"].iloc[-1]
    bias      = "BULLISH" if close_now > (high + low) / 2 else "BEARISH"

    return {
        "detected":      bs >= 50,
        "score":         bs,
        "days":          BUILDUP_DAYS,
        "range_pct":     round(price_range * 100, 2),
        "vol_ratio":     round(vol_ratio, 2),
        "atr_ratio":     round(atr_ratio, 2),
        "coiling_pct":   round(coil * 100, 1),
        "bias":          bias,
        "breakout_zone": {"high": round(high, 4), "low": round(low, 4)},
    }


# ─────────────────────────────────────────────
#  BUY / SELL PRESSURE
# ─────────────────────────────────────────────

def analyze_pressure(df):
    if len(df) < 20:
        return {"buy_pct": 50, "sell_pct": 50, "dominant": "SELLERS",
                "strength": 0, "divergence": "NONE", "delta_trend": "NEGATIVE"}
    if "buy_pressure" not in df.columns:
        df = add_all_indicators(df)
    recent     = df.tail(20)
    total_buy  = recent["buy_pressure"].sum()
    total_sell = recent["sell_pressure"].sum()
    total      = total_buy + total_sell
    buy_pct    = (total_buy  / total * 100) if total > 0 else 50
    sell_pct   = (total_sell / total * 100) if total > 0 else 50
    pc = df["close"].iloc[-1] - df["close"].iloc[-20]
    dc = df["cumulative_delta"].iloc[-1] - df["cumulative_delta"].iloc[-20]
    div = "NONE"
    if pc > 0 and dc < 0: div = "BEARISH_DIVERGENCE"
    elif pc < 0 and dc > 0: div = "BULLISH_DIVERGENCE"
    return {
        "buy_pct":    round(buy_pct,  1),
        "sell_pct":   round(sell_pct, 1),
        "dominant":   "BUYERS" if buy_pct > sell_pct else "SELLERS",
        "strength":   round(abs(buy_pct - sell_pct), 1),
        "divergence": div,
        "delta_trend": "POSITIVE" if dc > 0 else "NEGATIVE",
    }


# ─────────────────────────────────────────────
#  PROFESSIONAL TRADE SETUP
#  Shows BOTH CMP entry and S/R entry
# ─────────────────────────────────────────────

def build_trade_setup(df, direction, sr, obs):
    if len(df) == 0:
        return {"direction": direction, "cmp_entry": 0, "entry": 0, "sl": 0,
                "tp1": 0, "tp2": 0, "tp3": 0, "rr_ratio": 2.0, "atr": 0,
                "entry_note": "No data available"}

    price = df["close"].iloc[-1]
    atr   = df["atr"].iloc[-1] if "atr" in df.columns else price * 0.01
    atr   = min(atr, price * 0.02)

    # Helper: round using correct decimal places for this coin's price
    def R(v): return smart_round(v, price)

    # ── CMP Entry (immediate entry) ──
    cmp_entry = R(price)

    # ── S/R Entry (better entry at key level) ──
    used_major_level = False

    if direction == "LONG":
        supports = sr.get("supports", [])
        if supports:
            sr_entry = supports[-1]["level"]
            used_major_level = True
        else:
            sr_entry = price * 0.99

        entry = R(sr_entry)
        sl    = R(entry * 0.98)

        lower_supports = [s for s in supports if s["level"] < entry * 0.999]
        if lower_supports:
            sl = R(lower_supports[-1]["level"] * 0.998)
        if sl >= entry:
            sl = R(entry * 0.98)

        risk = entry - sl
        if risk <= 0:
            risk = entry * 0.02

        resistances = sr.get("resistances", [])
        # TP1: first resistance or 1.5x risk
        tp1 = R(resistances[0]["level"] * 0.999) if len(resistances) >= 1 else R(entry + risk * TP1_RR)
        if tp1 <= entry: tp1 = R(entry + risk * TP1_RR)
        # TP2: second resistance or 3x risk — must be above TP1
        tp2 = R(resistances[1]["level"] * 0.999) if len(resistances) >= 2 else R(entry + risk * TP2_RR)
        if tp2 <= tp1: tp2 = R(tp1 + risk)
        # TP3: always pure RR — must be above TP2
        tp3 = R(entry + risk * TP3_RR)
        if tp3 <= tp2: tp3 = R(tp2 + risk * 2)

    else:  # SHORT
        resistances = sr.get("resistances", [])
        if resistances:
            sr_entry = resistances[0]["level"]
            used_major_level = True
        else:
            sr_entry = price * 1.01

        entry = R(sr_entry)
        sl    = R(entry * 1.02)
        if sl <= entry:
            sl = R(entry * 1.02)

        risk = sl - entry
        if risk <= 0:
            risk = entry * 0.02

        supports = sr.get("supports", [])
        # TP1: nearest support or 1.5x risk
        tp1 = R(supports[-1]["level"] * 1.001) if len(supports) >= 1 else R(entry - risk * TP1_RR)
        if tp1 >= entry: tp1 = R(entry - risk * TP1_RR)
        # TP2: must be below TP1 — use pure RR
        tp2 = R(entry - risk * TP2_RR)
        if tp2 >= tp1: tp2 = R(tp1 - risk)
        # TP3: must be below TP2 — pure RR runner
        tp3 = R(entry - risk * TP3_RR)
        if tp3 >= tp2: tp3 = R(tp2 - risk * 2)

    risk      = abs(entry - sl)
    rr_tp1    = round(abs(tp1 - entry) / risk, 1) if risk > 0 else 1.5
    rr_tp2    = round(abs(tp2 - entry) / risk, 1) if risk > 0 else 3.0
    rr_tp3    = round(abs(tp3 - entry) / risk, 1) if risk > 0 else 5.0
    rr_ratio  = rr_tp2   # kept for backward compat

    return {
        "direction":   direction,
        "cmp_entry":   cmp_entry,
        "entry":       entry,
        "sl":          sl,
        "tp1":         tp1,
        "tp2":         tp2,
        "tp3":         tp3,
        "rr_ratio":    rr_ratio,
        "rr_tp1":      rr_tp1,
        "rr_tp2":      rr_tp2,
        "rr_tp3":      rr_tp3,
        "atr":         R(atr),
        "entry_note":  (
            ("Entry at major support" if used_major_level
             else "Entry near current price (no major support found yet)")
            if direction == "LONG"
            else ("Entry at major resistance" if used_major_level
             else "Entry near current price (no major resistance found yet)")
        ),
    }


# ─────────────────────────────────────────────
#  MULTI-TIMEFRAME SCORE
# ─────────────────────────────────────────────

def score_coin(symbol, tf_data):
    score    = 0
    reasons  = []
    warnings = []
    tf_weights   = {"1D": 35, "4h": 25, "1h": 20, "15m": 10, "5m": 7, "1m": 3}
    long_votes   = 0
    short_votes  = 0

    for tf, df in tf_data.items():
        if df is None or len(df) < 50: continue
        df   = add_all_indicators(df)
        w    = tf_weights.get(tf, 5)
        last = df.iloc[-1]
        tf_score = 0
        tf_dir   = "NEUTRAL"

        if last["ema9"] > last["ema21"] > last["ema50"] > last["ema200"]:
            tf_score += 30; tf_dir = "LONG"; reasons.append(f"[{tf}] Full bull EMA stack ✅")
        elif last["ema9"] < last["ema21"] < last["ema50"] < last["ema200"]:
            tf_score += 30; tf_dir = "SHORT"; reasons.append(f"[{tf}] Full bear EMA stack ✅")
        elif last["ema9"] > last["ema21"] > last["ema50"]:
            tf_score += 20; tf_dir = "LONG"
        elif last["ema9"] < last["ema21"] < last["ema50"]:
            tf_score += 20; tf_dir = "SHORT"
        elif last["ema9"] > last["ema21"]:
            tf_score += 10; tf_dir = "LONG"
        elif last["ema9"] < last["ema21"]:
            tf_score += 10; tf_dir = "SHORT"

        rsi = last["rsi"]
        if tf_dir == "LONG"  and rsi < 40:  tf_score += 20; reasons.append(f"[{tf}] RSI oversold ({rsi:.0f})")
        elif tf_dir == "SHORT" and rsi > 60: tf_score += 20; reasons.append(f"[{tf}] RSI overbought ({rsi:.0f})")
        elif 45 <= rsi <= 55: tf_score += 10
        if rsi > 80: warnings.append(f"[{tf}] RSI extremely overbought ({rsi:.0f})")
        if rsi < 20: warnings.append(f"[{tf}] RSI extremely oversold ({rsi:.0f})")

        if last["macd"] > last["macd_signal"] and tf_dir == "LONG":
            tf_score += 15; reasons.append(f"[{tf}] MACD bullish")
        elif last["macd"] < last["macd_signal"] and tf_dir == "SHORT":
            tf_score += 15; reasons.append(f"[{tf}] MACD bearish")

        bb_width = (last["bb_upper"] - last["bb_lower"]) / last["bb_mid"] if last["bb_mid"] else float("inf")
        if bb_width < 0.05: tf_score += 10; reasons.append(f"[{tf}] BB squeeze")

        if last["close"] > last["vwap"] and tf_dir == "LONG":   tf_score += 10
        elif last["close"] < last["vwap"] and tf_dir == "SHORT": tf_score += 10

        if tf_dir == "LONG":   long_votes  += w
        elif tf_dir == "SHORT": short_votes += w
        score += (tf_score / 100) * w

    dominant_dir = "LONG" if long_votes > short_votes else "SHORT" if short_votes > long_votes else "NEUTRAL"

    return {
        "score":     min(100, round(score)),
        "direction": dominant_dir,
        "reasons":   reasons[:8],
        "warnings":  warnings[:3],
        "votes":     {"LONG": long_votes, "SHORT": short_votes},
    }
