# ============================================================
#  scheduler.py — Builds daily watch sessions
#
#  Rules:
#   • Mon–Fri  : 1.5 hr/day budget
#   • Sat–Sun  : 3.0 hr/day budget
#   • Each video gets +30 min revision slot after last session
#   • Continues scheduling from where last run left off (state)
# ============================================================

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Tuple
import logging
from config import WEEKDAY_BUDGET_HOURS, WEEKEND_BUDGET_HOURS, REVISION_MINUTES

logger = logging.getLogger(__name__)


@dataclass
class WatchSession:
    channel_name:           str
    video_title:            str
    url:                    str
    published_at:           str
    total_duration_str:     str    # e.g. "2h 45m"
    session_date:           str    # "YYYY-MM-DD"
    day_number:             int    # 1, 2, 3…
    total_sessions:         int    # total parts this video is split into
    watch_from:             str    # "0:00:00"
    watch_to:               str    # "1:30:00"
    session_duration_str:   str    # "1h 30m"
    has_revision:           bool   # True only on last session of a video
    revision_str:           str    # "30 min" or ""
    video_id:               str    # for state tracking


def get_daily_budget_seconds(d: date) -> int:
    """Returns daily watch budget in seconds based on day of week."""
    if d.weekday() >= 5:    # 5=Saturday, 6=Sunday
        return int(WEEKEND_BUDGET_HOURS * 3600)
    return int(WEEKDAY_BUDGET_HOURS * 3600)


def build_schedule(videos: list, state: dict) -> Tuple[List[WatchSession], str, int]:
    """
    Converts VideoInfo list → WatchSession list.

    Returns:
        sessions             : flat list of WatchSessions
        last_scheduled_day   : date string of last session
        remaining_budget_secs: unused seconds on last_scheduled_day
    """
    revision_secs = REVISION_MINUTES * 60

    # ── Restore scheduling position from state ───────────────
    if state.get("last_scheduled_day"):
        current_date    = date.fromisoformat(state["last_scheduled_day"])
        remaining_today = int(state.get("remaining_budget_seconds", 0))

        # If previous run exhausted the day, move to next
        if remaining_today <= 0:
            current_date    = _advance_day(current_date)
            remaining_today = get_daily_budget_seconds(current_date)
    else:
        current_date    = date.today()
        remaining_today = get_daily_budget_seconds(current_date)

    sessions: List[WatchSession] = []

    for video in videos:
        total_secs  = video.duration_seconds
        total_str   = _fmt_duration(total_secs)
        video_parts: List[Tuple[int, int, date]] = []  # (from_sec, to_sec, date)

        # ── Split video content across days ──────────────────
        cursor = 0
        while cursor < total_secs:
            # How much of the video fits today?
            chunk = min(total_secs - cursor, remaining_today)
            video_parts.append((cursor, cursor + chunk, current_date))

            cursor          += chunk
            remaining_today -= chunk

            if remaining_today <= 0:
                current_date    = _advance_day(current_date)
                remaining_today = get_daily_budget_seconds(current_date)

        # ── Consume revision time after video ends ────────────
        # Revision fits today → deduct from today's budget
        if remaining_today >= revision_secs:
            remaining_today -= revision_secs
        else:
            # Not enough today → revision carries to next day
            current_date    = _advance_day(current_date)
            remaining_today = get_daily_budget_seconds(current_date) - revision_secs
            remaining_today = max(remaining_today, 0)

        # ── Build WatchSession objects ────────────────────────
        num_parts = len(video_parts)
        for i, (from_sec, to_sec, sess_date) in enumerate(video_parts):
            is_last = (i == num_parts - 1)
            sessions.append(WatchSession(
                channel_name=video.channel_name,
                video_title=video.title,
                url=video.url,
                published_at=video.published_at,
                total_duration_str=total_str,
                session_date=sess_date.isoformat(),
                day_number=i + 1,
                total_sessions=num_parts,
                watch_from=_fmt_timestamp(from_sec),
                watch_to=_fmt_timestamp(to_sec),
                session_duration_str=_fmt_duration(to_sec - from_sec),
                has_revision=is_last,
                revision_str="30 min" if is_last else "",
                video_id=video.video_id,
            ))

    last_day = current_date.isoformat()
    logger.info(
        f"Schedule built: {len(sessions)} session(s). "
        f"Last scheduled day: {last_day}, "
        f"remaining budget: {_fmt_duration(remaining_today)}"
    )
    return sessions, last_day, remaining_today


# ── Helpers ──────────────────────────────────────────────────

def _advance_day(d: date) -> date:
    return d + timedelta(days=1)


def _fmt_duration(seconds: int) -> str:
    h, rem = divmod(abs(seconds), 3600)
    m, s   = divmod(rem, 60)
    parts  = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s and not h:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"


def _fmt_timestamp(seconds: int) -> str:
    """Formats as H:MM:SS — usable as a YouTube seek timestamp."""
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"
