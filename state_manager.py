# ============================================================
#  state_manager.py — Persist run state for incremental updates
#
#  state.json structure:
#  {
#    "scheduled_video_ids": [...],      ← IDs already in Excel
#    "last_run_date": "2026-02-01",     ← Date of last successful run
#    "last_scheduled_day": "2026-02-15",← Last day in schedule
#    "remaining_budget_seconds": 2700   ← Unused budget on that day
#  }
# ============================================================

import json
import os
import logging
from datetime import datetime, timedelta
from config import STATE_FILE, VIDEOS_START_DATE

logger = logging.getLogger(__name__)

_DEFAULT_STATE = {
    "scheduled_video_ids": [],
    "last_run_date": None,
    "last_scheduled_day": None,
    "remaining_budget_seconds": 0
}


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        logger.info("No state file found — starting fresh from scratch.")
        return _DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        # Backward compat: fill any missing keys
        for key, default in _DEFAULT_STATE.items():
            state.setdefault(key, default)
        n = len(state["scheduled_video_ids"])
        logger.info(f"State loaded — {n} video(s) already scheduled.")
        return state
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"State file corrupt ({e}). Starting fresh.")
        return _DEFAULT_STATE.copy()


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        logger.info(f"State saved → {STATE_FILE}")
    except IOError as e:
        logger.error(f"Could not save state: {e}")


def get_fetch_since_date(state: dict) -> str:
    """
    Returns the earliest date from which to look for new videos.
    - First run        : VIDEOS_START_DATE (2026-01-01)
    - Subsequent runs  : last_run_date - 3 days (buffer for delayed uploads)
    """
    if not state.get("last_run_date"):
        logger.info(f"First run — fetching from {VIDEOS_START_DATE}")
        return VIDEOS_START_DATE

    last_run  = datetime.strptime(state["last_run_date"], "%Y-%m-%d")
    fetch_from = last_run - timedelta(days=3)           # 3-day safety buffer
    start_cap  = datetime.strptime(VIDEOS_START_DATE, "%Y-%m-%d")
    fetch_from = max(fetch_from, start_cap)

    result = fetch_from.strftime("%Y-%m-%d")
    logger.info(f"Incremental run — fetching videos since {result}")
    return result


def get_already_scheduled_ids(state: dict) -> set:
    return set(state.get("scheduled_video_ids", []))


def update_state_after_run(state: dict, new_video_ids: list,
                            last_scheduled_day: str,
                            remaining_budget_seconds: int) -> dict:
    from datetime import date
    state["scheduled_video_ids"].extend(new_video_ids)
    state["last_run_date"]            = date.today().isoformat()
    state["last_scheduled_day"]       = last_scheduled_day
    state["remaining_budget_seconds"] = remaining_budget_seconds
    return state
