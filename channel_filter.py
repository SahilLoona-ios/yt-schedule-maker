# ============================================================
#  channel_filter.py — Classify channels as tech vs finance
#  Strategy:
#    1. Skip list check (exact names)
#    2. YouTube topicDetails (Wikipedia URLs) — most reliable
#    3. Fallback: keyword scan of channel name + description
#    4. Default: INCLUDE (never miss a tech channel)
# ============================================================

import logging
from config import (
    SKIP_CHANNELS,
    FINANCE_TOPIC_KEYWORDS, TECH_TOPIC_KEYWORDS,
    FINANCE_DESC_KEYWORDS, TECH_DESC_KEYWORDS
)

logger = logging.getLogger(__name__)

# Pre-process to lowercase sets for fast lookup
_SKIP_LOWER        = [s.lower() for s in SKIP_CHANNELS]
_FINANCE_TOPICS    = [kw.lower() for kw in FINANCE_TOPIC_KEYWORDS]
_TECH_TOPICS       = [kw.lower() for kw in TECH_TOPIC_KEYWORDS]
_FINANCE_DESC      = [kw.lower() for kw in FINANCE_DESC_KEYWORDS]
_TECH_DESC         = [kw.lower() for kw in TECH_DESC_KEYWORDS]


def should_include_channel(
    channel_name: str,
    description: str,
    topic_categories: list
) -> tuple[bool, str]:
    """
    Returns (should_include: bool, reason: str)
    """
    name_lower = channel_name.lower().strip()
    desc_lower = (description or "").lower()
    combined   = f"{name_lower} {desc_lower}"

    # ── 1. Explicit skip list ────────────────────────────────
    for skip in _SKIP_LOWER:
        if skip in name_lower:
            return False, f"skip list match: '{skip}'"

    # ── 2. Topic categories from YouTube API ────────────────
    if topic_categories:
        topic_str = " ".join(topic_categories).lower()

        has_finance_topic = any(kw in topic_str for kw in _FINANCE_TOPICS)
        has_tech_topic    = any(kw in topic_str for kw in _TECH_TOPICS)

        if has_finance_topic and not has_tech_topic:
            return False, f"finance topic detected in topicCategories"

        if has_tech_topic:
            return True, "tech topic confirmed via topicCategories"

    # ── 3. Keyword fallback on name + description ────────────
    has_finance_kw = any(kw in combined for kw in _FINANCE_DESC)
    has_tech_kw    = any(kw in combined for kw in _TECH_DESC)

    if has_finance_kw and not has_tech_kw:
        return False, "finance keywords in description, no tech keywords found"

    if has_tech_kw:
        return True, "tech keywords found in description"

    # ── 4. Default: include (err on the side of inclusion) ───
    return True, "no clear classification — included by default"


def filter_channels(channels: list, channel_details: dict) -> list:
    """
    Takes raw channel list + detail map, returns only tech channels.
    Logs each decision at DEBUG level.
    """
    included = []
    excluded = []

    for ch in channels:
        cid     = ch["channel_id"]
        name    = ch["channel_name"]
        details = channel_details.get(cid, {})

        include, reason = should_include_channel(
            name,
            details.get("description", ""),
            details.get("topic_categories", [])
        )

        if include:
            included.append(ch)
            logger.debug(f"  ✅ {name:<40} → {reason}")
        else:
            excluded.append(name)
            logger.info(f"  ⛔ Excluded: {name:<40} ({reason})")

    logger.info(
        f"Channel filter: {len(included)} included, "
        f"{len(excluded)} excluded out of {len(channels)} total."
    )
    if excluded:
        logger.info(f"  Excluded channels: {', '.join(excluded)}")

    return included
