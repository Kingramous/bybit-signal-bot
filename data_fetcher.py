# ============================================================
#  BYBIT DATA FETCHER - PROFESSIONAL v3.0
#  Adds: Funding Rate, Open Interest, Liquidation Levels
# ============================================================

import time
import logging
import requests
import pandas as pd
from config import (
    BYBIT_TESTNET, TIMEFRAMES,
    MIN_24H_VOLUME_USDT, MIN_VOLATILITY_PCT, MAX_VOLATILITY_PCT
)

logger  = logging.getLogger(__name__)
BASE_URL = "https://api-testnet.bybit.com" if BYBIT_TESTNET else "https://api.bybit.com"


def get_all_usdt_futures():
    url    = f"{BASE_URL}/v5/market/instruments-info"
    params = {"category": "linear", "status": "Trading", "limit": 1000}
    try:
        r    = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("retCode") != 0: return []
        return [
            item["symbol"] for item in data["result"]["list"]
            if item["symbol"].endswith("USDT") and item["contractType"] == "LinearPerpetual"
        ]
    except Exception as e:
        logger.error(f"Instruments error: {e}"); return []


def get_tickers(symbols):
    url    = f"{BASE_URL}/v5/market/tickers"
    params = {"category": "linear"}
    try:
        r    = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("retCode") != 0: return pd.DataFrame()
        rows = []
        for item in data["result"]["list"]:
            sym = item["symbol"]
            if sym not in symbols: continue
            try:
                rows.append({
                    "symbol":     sym,
                    "last_price": float(item["lastPrice"]),
                    "volume_24h": float(item["turnover24h"]),
                    "change_24h": float(item["price24hPcnt"]) * 100,
                    "high_24h":   float(item["highPrice24h"]),
                    "low_24h":    float(item["lowPrice24h"]),
                    "volatility": abs(float(item["price24hPcnt"])) * 100,
                })
            except (KeyError, ValueError, TypeError):
                continue
        return pd.DataFrame(rows)
    except Exception as e:
        logger.error(f"Tickers error: {e}"); return pd.DataFrame()


def filter_coins(df_tickers):
    if df_tickers.empty: return df_tickers
    df = df_tickers[df_tickers["volume_24h"] >= MIN_24H_VOLUME_USDT]
    df = df[df["volatility"] >= MIN_VOLATILITY_PCT]
    df = df[df["volatility"] <= MAX_VOLATILITY_PCT]
    # Exclude stablecoin PAIRS (e.g. "USDCUSDT", "TUSDUSDT") — must match
    # at the START of the symbol, not anywhere in it. A substring/regex
    # check here would wrongly exclude coins like "GRADIENTUSDT" or
    # "ROCKETUSDT" (which contain "TUSD" as a substring but aren't stablecoins).
    stables = ["USDC", "BUSD", "TUSD", "DAI", "FDUSD"]
    df = df[~df["symbol"].apply(lambda s: any(s.startswith(st) for st in stables))]
    logger.info(f"Filtered to {len(df)} coins")
    return df.reset_index(drop=True)


def get_klines(symbol, interval, limit=300):
    url    = f"{BASE_URL}/v5/market/kline"
    params = {"category":"linear","symbol":symbol,"interval":interval,"limit":limit}
    try:
        r    = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("retCode") != 0: return pd.DataFrame()
        raw = data["result"]["list"]
        if not raw: return pd.DataFrame()
        df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume","turnover"])
        df = df.astype({"timestamp":"int64","open":"float64","high":"float64",
                        "low":"float64","close":"float64","volume":"float64"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df.sort_values("timestamp").reset_index(drop=True)
    except Exception as e:
        logger.error(f"Klines error {symbol} {interval}: {e}"); return pd.DataFrame()


def get_multitf_data(symbol):
    tf_data = {}
    for tf_name, tf_interval in TIMEFRAMES.items():
        limit = 300 if tf_name == "1D" else 200
        df    = get_klines(symbol, tf_interval, limit=limit)
        tf_data[tf_name] = df if not df.empty else None
        time.sleep(0.05)
    return tf_data


def pre_screen(df_tickers, top_n=30):
    df = df_tickers.copy()
    max_vol = df["volume_24h"].max()
    vol_score = (df["volume_24h"] / max_vol * 50) if max_vol > 0 else 0
    df["pre_score"] = (
        vol_score +
        df["volatility"].clip(1,10) / 10 * 30 +
        df["change_24h"].abs().clip(0,10) / 10 * 20
    )
    return df.nlargest(top_n, "pre_score").reset_index(drop=True)
