#!/usr/bin/env python3
# ============================================================
#  BYBIT FUTURES SIGNAL BOT — MAIN ENTRY POINT
#  - Sends signals IMMEDIATELY on startup
#  - Then sends every day at:
#    🌅 7:00 AM WAT (West Africa Time)
#    🌆 7:00 PM WAT (West Africa Time)
#  Run: python main.py
# ============================================================

import logging
import time
import schedule

from scanner import run_full_scan
from telegram_sender import send_all_signals, send_startup_message, send_error_alert

# ─────────────────────────────────────────────
#  LOGGING SETUP
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("main")

# WAT = UTC+1
MORNING_UTC = "06:00"   # = 7:00 AM WAT
EVENING_UTC = "18:00"   # = 7:00 PM WAT


# ─────────────────────────────────────────────
#  MAIN SCAN JOB
# ─────────────────────────────────────────────
def scan_job(session: str):
    wat_time = "7:00 AM" if session == "morning" else "7:00 PM"
    logger.info(f"🔍 {session.upper()} scan triggered ({wat_time} WAT)")
    try:
        top5 = run_full_scan()
        send_all_signals(top5, session=session)
        logger.info(f"✅ {session.upper()} signals sent for {len(top5)} coins")
    except Exception as e:
        logger.exception(f"Scan job failed: {e}")
        send_error_alert(str(e))


def morning_scan():
    scan_job("morning")

def evening_scan():
    scan_job("evening")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  BYBIT FUTURES SIGNAL BOT  STARTING")
    logger.info("  Schedule: 7:00 AM & 7:00 PM (WAT - Lagos/Accra)")
    logger.info("=" * 60)

    # Notify Telegram the bot is live
    send_startup_message()

    # ── RUN IMMEDIATELY ON STARTUP ──
    logger.info("🚀 Running instant scan on startup...")
    scan_job("morning")

    # Schedule morning and evening scans (in UTC)
    schedule.every().day.at(MORNING_UTC).do(morning_scan)
    schedule.every().day.at(EVENING_UTC).do(evening_scan)

    logger.info(f"⏰ Morning scan scheduled: 7:00 AM WAT ({MORNING_UTC} UTC)")
    logger.info(f"⏰ Evening scan scheduled: 7:00 PM WAT ({EVENING_UTC} UTC)")

    # Keep alive loop
    while True:
        schedule.run_pending()
        time.sleep(60)
