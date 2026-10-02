# ============================================================
#  SCANNER ENGINE — FULL MARKET SCAN VERSION
#  Scans ALL Bybit USDT futures pairs (200+)
#  No artificial pre-screen limit — every coin gets analysed
# ============================================================

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import TOP_N_COINS, PRIMARY_TF
from data_fetcher import (
    get_all_usdt_futures, get_tickers,
    filter_coins, get_multitf_data
)
from analysis import (
    add_all_indicators, find_order_blocks, find_major_sr,
    detect_buildup, analyze_pressure, build_trade_setup, score_coin
)
from advanced_analysis import (
    run_advanced_analysis, confirm_short_signal, detect_conflict
)

logger = logging.getLogger(__name__)

MIN_SCORE            = 55     # Raised from 45 — only quality signals
DEFAULT_TRADE_AMOUNT = 100
DEFAULT_LEVERAGE     = 10

# ─────────────────────────────────────────────
#  ANTI-CHASE FILTER
#  Reject coins that have already moved too much
#  — we want setups BEFORE the move, not after
# ─────────────────────────────────────────────

def passes_anti_chase(row, tf_data, daily_df=None):
    """
    Smart anti-chase filter.

    The key insight: NOT all big moves are chases.
    A coin up 7% after a 30-day buildup is a BREAKOUT (like ESPORTS +180%).
    A coin up 7% with no structure is a CHASE (like NOTUSDT that reversed).

    Rules:
    1. HARD REJECT: up >15% OR down >15% — always too extreme
    2. BREAKOUT EXCEPTION: up >6% BUT has buildup/Wyckoff/volume surge → KEEP
    3. SOFT REJECT: up >6% with overbought RSI and no structure → REJECT
    4. SOFT REJECT: down >10% with oversold RSI and no structure → REJECT
    """
    change_24h = row.get("change_24h", 0)

    # ── HARD LIMITS (no exceptions) ──
    if change_24h > 15:
        return False, f"Extreme pump +{change_24h:.1f}% — too dangerous"
    if change_24h < -15:
        return False, f"Extreme dump {change_24h:.1f}% — free-fall"

    # ── CHECK IF THIS IS A VALID BREAKOUT ──
    # A big move is OK if it has structural backing
    is_breakout = False
    breakout_reason = ""

    if daily_df is not None and len(daily_df) >= 50:
        from analysis import detect_buildup

        # Check 1: 30-day buildup → this is a breakout, not a chase
        buildup = detect_buildup(daily_df)
        if buildup.get("detected"):
            is_breakout = True
            breakout_reason = f"30-day buildup detected (score {buildup.get('score',0)}) — valid breakout"

        # Check 2: Volume surge on the breakout candle
        if not is_breakout and len(daily_df) >= 5:
            avg_vol   = daily_df["volume"].iloc[-20:-1].mean()
            last_vol  = daily_df["volume"].iloc[-1]
            vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
            if vol_ratio >= 2.5:   # volume 2.5x average on breakout day
                is_breakout = True
                breakout_reason = f"Volume surge {vol_ratio:.1f}x average — institutional breakout"

    # Check OI from tf_data for additional confirmation
    h1_df = tf_data.get("1h")
    h4_df = tf_data.get("4h")

    # ── SOFT LIMITS — check RSI ──
    overbought = False
    oversold   = False
    rsi_note   = ""

    for tf_name, df in [("1h", h1_df)]:   # Only 1H — 4H RSI lags too much on breakouts
        if df is None or len(df) < 20:
            continue
        if "rsi" not in df.columns:
            df = add_all_indicators(df)
        rsi = df["rsi"].iloc[-1]
        if rsi != rsi:   # NaN check
            continue
        if rsi > 80:
            overbought = True
            rsi_note = f"{tf_name} RSI={rsi:.0f}"
            break
        if rsi < 20:
            oversold = True
            rsi_note = f"{tf_name} RSI={rsi:.0f}"
            break

    # ── DECISION LOGIC ──

    # Big upward move
    if change_24h > 6:
        if is_breakout:
            # Valid breakout — keep it even if RSI is high
            return True, f"BREAKOUT: up {change_24h:.1f}% — {breakout_reason}"
        elif overbought:
            return False, f"Chasing pump: up {change_24h:.1f}% + {rsi_note} — no structural backing"
        else:
            # Moderate move, RSI not extreme — allow it
            return True, f"Moderate move +{change_24h:.1f}% — RSI not overbought"

    # Big downward move
    if change_24h < -10:
        if is_breakout:
            # Could be a valid breakdown (bearish breakout)
            return True, f"BREAKDOWN: down {change_24h:.1f}% — {breakout_reason}"
        elif oversold:
            return False, f"Catching knife: down {change_24h:.1f}% + {rsi_note} — no structural backing"
        else:
            return True, f"Down {change_24h:.1f}% — RSI not oversold, may bounce"

    # Small/normal move — always OK
    return True, "OK"


# ─────────────────────────────────────────────
#  SINGLE COIN ANALYSIS
# ─────────────────────────────────────────────

def analyse_single_coin(row):
    symbol = row["symbol"]
    try:
        # 1. Fetch ALL timeframes
        tf_data = get_multitf_data(symbol)

        daily_df = tf_data.get(PRIMARY_TF)
        if daily_df is None or len(daily_df) < 50:
            actual_len = len(daily_df) if daily_df is not None else 0
            logger.info(f"⬛ {symbol}: insufficient daily data ({actual_len} candles, need 50)")
            return None

        # 2. Add indicators to daily (needed for anti-chase buildup check)
        daily_df = add_all_indicators(daily_df)

        # 3. Anti-chase filter — smart, breakout-aware
        ok, reason = passes_anti_chase(row, tf_data, daily_df)
        if not ok:
            logger.info(f"⛔ {symbol}: ANTI-CHASE: {reason}")
            return None

        # 4. Multi-TF confluence score
        score_result = score_coin(symbol, tf_data)
        score        = score_result["score"]
        direction    = score_result["direction"]

        if direction == "NEUTRAL":
            logger.info(f"⬛ {symbol}: NEUTRAL direction — no clear trend")
            return None
        if score < MIN_SCORE:
            logger.info(f"⬛ {symbol}: score too low ({score}/{MIN_SCORE} minimum)")
            return None

        # 5. Order Blocks & S/R
        obs     = find_order_blocks(daily_df)
        sr      = find_major_sr(daily_df)
        buildup = detect_buildup(daily_df)

        # 6. Buy/Sell pressure (1H for recency)
        h1_df = tf_data.get("1h")
        if h1_df is not None and len(h1_df) > 20:
            h1_df    = add_all_indicators(h1_df)
            pressure = analyze_pressure(h1_df)
        else:
            pressure = analyze_pressure(daily_df)

        # 7. SHORT confirmation filter
        if direction == "SHORT":
            from advanced_analysis import get_funding_rate, get_open_interest
            funding_check = get_funding_rate(symbol)
            oi_check      = get_open_interest(symbol)
            short_confirm = confirm_short_signal(tf_data, funding_check, oi_check)
            if not short_confirm["valid"]:
                logger.info(f"⛔ {symbol}: SHORT rejected — only {short_confirm['confirmed']}/3 confirmations")
                return None

        # 8. Build trade setup
        setup = build_trade_setup(daily_df, direction, sr, obs)

        # 9. Advanced analysis
        advanced = run_advanced_analysis(
            symbol           = symbol,
            df_1h            = h1_df if h1_df is not None else daily_df,
            df_daily         = daily_df,
            sr               = sr,
            setup            = setup,
            confluence_score = score,
            trade_amount     = DEFAULT_TRADE_AMOUNT,
            leverage         = DEFAULT_LEVERAGE,
        )

        # Attach short confirmation if applicable
        if direction == "SHORT":
            advanced["short_confirmation"] = short_confirm

        # 10. Conflict warning (read-only, last step)
        conflict = detect_conflict(direction, score_result, pressure, tf_data)
        if conflict.get("detected"):
            advanced["conflict_warning"] = conflict

        # 11. Score bonuses for strong signals
        if buildup.get("detected"):                               score = min(100, score + 10)
        if pressure["divergence"] != "NONE":                      score = min(100, score + 5)
        if advanced["wyckoff"].get("detected"):                   score = min(100, score + 8)
        if advanced["smc"].get("bos_bullish") and direction == "LONG":  score = min(100, score + 5)
        if advanced["smc"].get("bos_bearish") and direction == "SHORT": score = min(100, score + 5)
        if advanced["open_interest"].get("strength") == "STRONG":       score = min(100, score + 5)

        # 12. Penalty for conflict (we keep the signal but lower score)
        if conflict.get("detected"):
            score = max(0, score - 10)

        return {
            "symbol":       symbol,
            "score":        score,
            "direction":    direction,
            "setup":        setup,
            "sr":           sr,
            "order_blocks": obs,
            "buildup":      buildup,
            "pressure":     pressure,
            "advanced":     advanced,
            "reasons":      score_result["reasons"],
            "warnings":     score_result["warnings"],
            "ticker": {
                "last_price": row["last_price"],
                "volume_24h": row["volume_24h"],
                "change_24h": row["change_24h"],
            },
        }

    except Exception as e:
        logger.error(f"Error analysing {symbol}: {e}")
        return None


# ─────────────────────────────────────────────
#  FULL MARKET SCAN
# ─────────────────────────────────────────────

def run_full_scan():
    """
    Scans ALL Bybit USDT perpetual futures pairs.
    No pre-screen limit — every coin that passes the
    volume/volatility filter gets fully analysed.
    Returns top 5 highest-scoring setups.
    """
    logger.info("=" * 60)
    logger.info("STARTING FULL MARKET SCAN — ALL BYBIT USDT FUTURES")
    logger.info("=" * 60)

    # Step 1: Get ALL pairs
    all_symbols = get_all_usdt_futures()
    if not all_symbols:
        logger.error("Could not fetch symbols from Bybit")
        return []
    logger.info(f"Total pairs on Bybit: {len(all_symbols)}")

    # Step 2: Fetch tickers for all
    df_tickers = get_tickers(all_symbols)
    if df_tickers.empty:
        logger.error("Could not fetch tickers")
        return []

    # Step 3: Apply volume & volatility filters
    df_filtered = filter_coins(df_tickers)
    if df_filtered.empty:
        logger.warning("No coins passed volume/volatility filters")
        return []
    logger.info(f"After volume/volatility filter: {len(df_filtered)} coins")

    # Step 4: Analyse ALL filtered coins in parallel (no pre-screen cap)
    candidates_list = df_filtered.to_dict("records")
    logger.info(f"Analysing ALL {len(candidates_list)} candidates...")

    results    = []
    rejected   = {"anti_chase": 0, "low_score": 0, "no_data": 0, "short_rejected": 0}
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {
            executor.submit(analyse_single_coin, row): row["symbol"]
            for row in candidates_list
        }
        done = 0
        for future in as_completed(future_map):
            sym = future_map[future]
            done += 1
            try:
                result = future.result()
                if result:
                    results.append(result)
                    logger.info(
                        f"✅ {sym}: score={result['score']} "
                        f"dir={result['direction']} "
                        f"({done}/{len(candidates_list)})"
                    )
                else:
                    logger.debug(f"⬛ {sym}: filtered out ({done}/{len(candidates_list)})")
            except Exception as e:
                logger.error(f"Future error {sym}: {e}")

            # Progress log every 20 coins
            if done % 20 == 0:
                elapsed = time.time() - start_time
                logger.info(
                    f"Progress: {done}/{len(candidates_list)} analysed | "
                    f"{len(results)} valid | {elapsed:.0f}s elapsed"
                )

    elapsed = time.time() - start_time
    logger.info(f"Full scan complete in {elapsed:.0f}s — {len(results)} valid signals found")

    # Step 5: Sort by score, return top 5
    results.sort(key=lambda x: x["score"], reverse=True)
    top5 = results[:TOP_N_COINS]

    logger.info(f"TOP {len(top5)} SIGNALS:")
    for i, r in enumerate(top5):
        logger.info(
            f"  #{i+1} {r['symbol']}: {r['score']}/100 — "
            f"{r['direction']} — 24h: {r['ticker']['change_24h']:+.1f}%"
        )

    # If nothing qualifies after anti-chase, warn and return best available
    if not top5:
        logger.warning("No signals passed all filters. Market may be overextended.")

    return top5
