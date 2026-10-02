# ============================================================
#  TELEGRAM SIGNAL SENDER — PREMIUM VERSION
# ============================================================

import logging
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text, parse_mode="HTML"):
    url  = f"{TG_API}/sendMessage"
    data = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def format_signal(rank, result):
    sym      = result["symbol"]
    score    = result["score"]
    setup    = result["setup"]
    sr       = result["sr"]
    obs      = result["order_blocks"]
    buildup  = result["buildup"]
    pressure = result["pressure"]
    reasons  = result["reasons"]
    warnings = result["warnings"]
    ticker   = result["ticker"]
    adv      = result.get("advanced", {})
    now      = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    direction = setup["direction"]
    emoji_dir = "🟢 LONG" if direction == "LONG" else "🔴 SHORT"
    score_bar = "🔥" * (score // 20) + "⬜" * (5 - score // 20)

    if score >= 85:   score_label = "🏆 PREMIUM SETUP"
    elif score >= 75: score_label = "⭐ HIGH CONFIDENCE"
    elif score >= 65: score_label = "✅ GOOD SETUP"
    else:             score_label = "⚠️ MODERATE"

    # ── ENTRY (CMP + S/R) ──
    cmp        = setup.get("cmp_entry", setup["entry"])
    sr_entry   = setup["entry"]
    entry_note = setup.get("entry_note", "")

    rr_tp1 = setup.get("rr_tp1", round(setup["rr_ratio"] * 0.5, 1))
    rr_tp2 = setup.get("rr_tp2", setup["rr_ratio"])
    rr_tp3 = setup.get("rr_tp3", round(setup["rr_ratio"] * 1.5, 1))

    entry_text = (
        f"\n    CMP:    <b>{cmp}</b> (current price)"
        f"\n    Entry:  <b>{sr_entry}</b> ← {entry_note}"
        f"\n    SL:     <b>{setup['sl']}</b>  🛑"
        f"\n    TP1:    <b>{setup['tp1']}</b>  🎯 (1:{rr_tp1})"
        f"\n    TP2:    <b>{setup['tp2']}</b>  🎯 (1:{rr_tp2})"
        f"\n    TP3:    <b>{setup['tp3']}</b>  🎯 (1:{rr_tp3}) runner"
    )

    # ── P&L ──
    pnl = adv.get("pnl", {})
    pnl_text = ""
    if pnl:
        pnl_text = (
            f"\n\n💰 <b>YOUR MONEY ({pnl['trade_amount']}$ at {pnl['leverage']}x)</b>"
            f"\n    Position size: <b>${pnl['position_size']}</b>"
            f"\n    If SL hits:  <b>-${abs(pnl['sl_loss'])}</b> loss ({pnl['sl_pct']:+.1f}%)"
            f"\n    If TP1 hits: <b>+${pnl['tp1_gain']}</b> profit ({pnl['tp1_pct']:+.1f}%)"
            f"\n    If TP2 hits: <b>+${pnl['tp2_gain']}</b> profit ({pnl['tp2_pct']:+.1f}%)"
            f"\n    If TP3 hits: <b>+${pnl['tp3_gain']}</b> profit ({pnl['tp3_pct']:+.1f}%)"
        )

    # ── RISK SCORE ──
    risk     = adv.get("risk", {})
    risk_text = ""
    if risk:
        risk_text = f"\n\n⚖️ <b>RISK SCORE: {risk['score']}/10</b> — {risk['label']}"

    # ── SHORT CONFIRMATION (only shows for SHORT signals) ──
    short_conf = adv.get("short_confirmation", {})
    short_conf_text = ""
    if short_conf:
        conf_lines = "\n".join([f"    {d}" for d in short_conf.get("details", [])])
        short_conf_text = (
            f"\n\n🔍 <b>SHORT CONFIRMATION ({short_conf['confirmed']}/3)</b>\n{conf_lines}"
        )

    # ── CONFLICT WARNING (informational only) ──
    conflict = adv.get("conflict_warning", {})
    conflict_text = ""
    if conflict.get("detected"):
        conflict_text = (
            f"\n\n🟡 <b>CONFLICT NOTICE</b>"
            f"\n    {conflict['note']}"
            f"\n    💡 {conflict['action_plan']}"
        )

    # ── S/R ──
    sr_text = ""
    if sr.get("nearest_support"):
        ns = sr["nearest_support"]
        sr_text += f"\n    🟩 Nearest Support:    <b>{ns['level']}</b> ({ns['touches']} touches — {ns['strength']})"
    if sr.get("nearest_resistance"):
        nr = sr["nearest_resistance"]
        sr_text += f"\n    🟥 Nearest Resistance: <b>{nr['level']}</b> ({nr['touches']} touches — {nr['strength']})"
    if sr.get("supports"):
        all_sup = " | ".join([str(s["level"]) for s in sr["supports"][-3:]])
        sr_text += f"\n    📌 Major Supports: {all_sup}"
    if sr.get("resistances"):
        all_res = " | ".join([str(r["level"]) for r in sr["resistances"][:3]])
        sr_text += f"\n    📌 Major Resistances: {all_res}"

    sr_section = f"\n\n📐 <b>MAJOR S&R</b>{sr_text}" if sr_text else ""

    # ── ORDER BLOCKS ──
    ob_dir  = "bullish" if direction == "LONG" else "bearish"
    ob_list = obs.get(ob_dir, [])
    ob_text = ""
    if ob_list:
        ob_entries = "\n".join([f"    • {ob['low']} — {ob['high']}" for ob in ob_list[:2]])
        ob_label   = "🟩 BULLISH ORDER BLOCKS" if direction == "LONG" else "🟥 BEARISH ORDER BLOCKS"
        ob_text    = f"\n\n{ob_label}\n{ob_entries}"
    # else stays empty string - no empty header

    # ── PRESSURE ──
    p_emoji  = "💚" if pressure["dominant"] == "BUYERS" else "❤️"
    div_text = ""
    if pressure["divergence"] == "BULLISH_DIVERGENCE":
        div_text = "\n    📈 <b>BULLISH DELTA DIVERGENCE</b> — Smart money accumulating"
    elif pressure["divergence"] == "BEARISH_DIVERGENCE":
        div_text = "\n    📉 <b>BEARISH DELTA DIVERGENCE</b> — Smart money distributing"

    pressure_text = (
        f"\n\n{p_emoji} <b>BUY/SELL PRESSURE</b>"
        f"\n    Buyers: {pressure['buy_pct']}% | Sellers: {pressure['sell_pct']}%"
        f"\n    Dominant: <b>{pressure['dominant']}</b> ({pressure['strength']:.1f}% edge)"
        f"\n    Delta: {pressure['delta_trend']}{div_text}"
    )

    # ── WYCKOFF ──
    wyckoff      = adv.get("wyckoff", {})
    wyckoff_text = ""
    if wyckoff.get("detected"):
        w_type = "📦 ACCUMULATION" if wyckoff["type"] == "ACCUMULATION" else "🏭 DISTRIBUTION"
        wyckoff_text = (
            f"\n\n{w_type} DETECTED"
            f"\n    Phase: {wyckoff['phase']}"
            f"\n    Confidence: {wyckoff['confidence']}%"
        )
        if wyckoff.get("spring"):
            wyckoff_text += "\n    🌱 Spring detected — strong reversal signal"
        if wyckoff.get("upthrust"):
            wyckoff_text += "\n    🎯 Upthrust detected — distribution confirmed"

    # ── SMC ──
    smc      = adv.get("smc", {})
    smc_text = ""
    if smc.get("detected"):
        smc_signals = "\n".join([f"    {s}" for s in smc.get("signals", [])[:3]])
        smc_text    = f"\n\n🧠 <b>SMART MONEY (SMC)</b>\n{smc_signals}"

        if smc.get("fair_value_gaps"):
            fvg = smc["fair_value_gaps"][0]
            smc_text += f"\n    📊 FVG: {fvg['low']} — {fvg['high']} ({fvg['type']})"

        if smc.get("inducement"):
            smc_text += f"\n    {smc['inducement_note']}"

        if smc.get("liquidity_levels"):
            liq = smc["liquidity_levels"][0]
            smc_text += f"\n    💧 Liquidity at {liq['level']} ({liq['type']})"

    # ── FUNDING RATE ──
    funding      = adv.get("funding", {})
    funding_text = ""
    if funding.get("available"):
        funding_text = (
            f"\n\n💸 <b>FUNDING RATE</b>"
            f"\n    Rate: {funding['rate']:+.4f}%"
            f"\n    {funding['interpretation']}"
        )

    # ── OPEN INTEREST ──
    oi      = adv.get("open_interest", {})
    oi_text = ""
    if oi.get("available"):
        oi_text = (
            f"\n\n📊 <b>OPEN INTEREST</b>"
            f"\n    24h Change: {oi['oi_change_24h']:+.2f}%"
            f"\n    {oi['interpretation']}"
        )

    # ── LIQUIDATION LEVELS ──
    liq      = adv.get("liquidation_levels", {})
    liq_text = ""
    if liq.get("available") and liq.get("levels"):
        liq_lines = "\n".join([
            f"    💣 {l['level']} ({l['type']}) {l['distance']}"
            for l in liq["levels"][:3]
        ])
        liq_text = f"\n\n💣 <b>LIQUIDATION ZONES</b>\n{liq_lines}"

    # ── BUILDUP ──
    buildup_text = ""
    if buildup.get("detected"):
        buildup_text = (
            f"\n\n🧱 <b>30-DAY BUILDUP DETECTED</b>"
            f"\n    Range: {buildup['range_pct']}% | Vol ratio: {buildup['vol_ratio']}x"
            f"\n    ATR compression: {buildup['atr_ratio']}x | Bias: {buildup['bias']}"
            f"\n    Breakout zone: {buildup['breakout_zone']['low']} — {buildup['breakout_zone']['high']}"
        )

    # ── CONFLUENCE ──
    reasons_text  = "\n".join([f"    ✔ {r}" for r in reasons[:6]])

    # ── WARNINGS ──
    warnings_text = ""
    if warnings:
        w_lines       = "\n".join([f"    ⚠️ {w}" for w in warnings])
        warnings_text = f"\n\n⚠️ <b>WARNINGS</b>\n{w_lines}"

    # ════════════════════════════════════════════
    msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 <b>SIGNAL #{rank} — {sym}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{score_bar}  <b>{score}/100</b> — {score_label}
Direction: <b>{emoji_dir}</b>
24h Vol: ${ticker['volume_24h']:,.0f} | Change: {ticker['change_24h']:+.2f}%

📊 <b>TRADE SETUP</b>{entry_text}
{pnl_text}
{risk_text}{short_conf_text}{conflict_text}{sr_section}{ob_text}{pressure_text}{wyckoff_text}{smc_text}{funding_text}{oi_text}{liq_text}{buildup_text}

🔍 <b>CONFLUENCE</b>
{reasons_text}
{warnings_text}

🕐 {now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""".strip()

    # Collapse 3+ consecutive newlines down to 2 (i.e. max one blank line)
    # This handles cases where multiple optional sections are empty.
    import re
    msg = re.sub(r"\n{3,}", "\n\n", msg)

    return msg


def send_top5_header(top5, session="morning"):
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"  #{i+1} <b>{r['symbol']}</b> — {r['score']}/100 | "
        f"{r['setup']['direction']} | Risk: {r.get('advanced',{}).get('risk',{}).get('score','?')}/10"
        for i, r in enumerate(top5)
    ]
    summary = "\n".join(lines)

    if session == "morning":
        label  = "🌅 MORNING SIGNALS (7:00 AM WAT)"
        advice = "Plan your entries, set your alerts. Trade smart! 💪"
    else:
        label  = "🌆 EVENING SIGNALS (7:00 PM WAT)"
        advice = "Review setups for tomorrow. Patience is profit. 🌙"

    msg = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{label}
🕐 {now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>TOP 5 SETUPS</b>

{summary}

{advice}
Full signals below 👇
""".strip()
    return send_message(msg)


def send_signal(rank, result):
    return send_message(format_signal(rank, result))


def send_all_signals(top5, session="morning"):
    if not top5:
        send_message("⚠️ No qualifying setups found. Next scan at scheduled time.")
        return
    send_top5_header(top5, session)
    import time
    for i, result in enumerate(top5):
        send_signal(i + 1, result)
        time.sleep(1)


def send_startup_message():
    send_message(
        "🤖 <b>Bybit Premium Signal Bot STARTED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Wyckoff Analysis\n"
        "✅ Smart Money Concepts\n"
        "✅ Funding Rate\n"
        "✅ Open Interest\n"
        "✅ Liquidation Zones\n"
        "✅ CMP + S/R Entry\n"
        "✅ Dollar P&L per trade\n"
        "✅ Risk Score\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Scanning all USDT futures now..."
    )


def send_error_alert(error):
    send_message(f"🚨 <b>BOT ERROR</b>\n<code>{error[:500]}</code>")
