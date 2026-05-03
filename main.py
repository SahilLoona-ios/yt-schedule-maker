# ============================================================
#  main.py — Orchestrator. Run this file.
# ============================================================

import logging
import sys
import time

from auth           import get_credentials
from youtube_client import YouTubeClient
from scheduler      import build_schedule
from excel_writer   import write_excel
from state_manager  import (
    load_state,
    save_state,
    get_fetch_since_date,
    get_already_scheduled_ids,
    update_state_after_run
)
from config import (
    OUTPUT_FILE, WEEKDAY_BUDGET_HOURS, WEEKEND_BUDGET_HOURS,
    REVISION_MINUTES, VIDEOS_START_DATE
)

# ── Logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("yt_tracker.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


def main():
    _print_banner()
    start_time = time.time()

    # ── Step 1: Load persistent state ────────────────────────
    logger.info("Step 1/5 — Loading state...")
    state          = load_state()
    since_date     = get_fetch_since_date(state)
    already_sched  = get_already_scheduled_ids(state)

    is_first_run   = not state.get("last_run_date")
    if is_first_run:
        logger.info(f"First run — will fetch all videos since {VIDEOS_START_DATE}")
    else:
        logger.info(
            f"Incremental run — {len(already_sched)} videos already scheduled. "
            f"Looking for new videos since {since_date}."
        )

    # ── Step 2: Authenticate ──────────────────────────────────
    logger.info("Step 2/5 — Authenticating with Google...")
    try:
        creds = get_credentials()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # ── Step 3: Fetch new videos ──────────────────────────────
    logger.info("Step 3/5 — Fetching videos from YouTube...")
    client = YouTubeClient(creds)
    try:
        videos = client.fetch_new_videos(since_date, already_sched)
    except Exception as e:
        logger.error(f"YouTube API error: {e}")
        sys.exit(1)

    if not videos:
        logger.info("✅ No new videos to schedule. Your schedule is up to date!")
        # Still update last_run_date in state
        state = update_state_after_run(
            state, [],
            state.get("last_scheduled_day") or "",
            state.get("remaining_budget_seconds", 0)
        )
        save_state(state)
        return

    # ── Step 4: Build schedule ────────────────────────────────
    logger.info(f"Step 4/5 — Building schedule for {len(videos)} new video(s)...")
    sessions, last_day, remaining_budget = build_schedule(videos, state)

    # ── Step 5: Write Excel ───────────────────────────────────
    logger.info("Step 5/5 — Writing Excel...")
    write_excel(sessions)

    # ── Save state ────────────────────────────────────────────
    new_video_ids = [v.video_id for v in videos]
    state = update_state_after_run(state, new_video_ids, last_day, remaining_budget)
    save_state(state)

    elapsed = time.time() - start_time
    _print_summary(videos, sessions, elapsed)


# ── Helpers ──────────────────────────────────────────────────

def _print_banner():
    print("\n" + "═" * 58)
    print("  📺  YouTube Watch Schedule Tracker")
    print(f"  📅  Videos from      : {VIDEOS_START_DATE} onwards")
    print(f"  ⏱   Weekday budget   : {WEEKDAY_BUDGET_HOURS}h  |  Weekend: {WEEKEND_BUDGET_HOURS}h")
    print(f"  🔁  Revision per video: {REVISION_MINUTES} min")
    print(f"  📄  Output           : {OUTPUT_FILE}")
    print("═" * 58 + "\n")


def _print_summary(videos, sessions, elapsed):
    unique_channels = len({v.channel_name for v in videos})
    unique_dates    = len({s.session_date for s in sessions})

    print("\n" + "═" * 58)
    print(f"  ✅  Done in {elapsed:.1f}s")
    print(f"  📺  Channels  : {unique_channels}")
    print(f"  🎬  Videos    : {len(videos)}")
    print(f"  📋  Sessions  : {len(sessions)}")
    print(f"  📆  Days span : {unique_dates}")
    print(f"  📁  Saved     : {OUTPUT_FILE}")
    print("═" * 58 + "\n")


if __name__ == "__main__":
    main()
