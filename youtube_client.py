# ============================================================
#  youtube_client.py — YouTube API wrapper
#  Quota strategy: uploads-playlist approach (~2 units/channel)
#  vs search.list (100 units/channel)
# ============================================================

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Set
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from channel_filter import filter_channels
from config import MAX_SUBSCRIPTIONS, API_BATCH_SIZE

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    channel_name: str
    title: str
    video_id: str
    url: str
    duration_seconds: int
    published_at: str        # "YYYY-MM-DD"
    published_at_dt: datetime  # for sorting — not shown in Excel


class YouTubeClient:
    def __init__(self, credentials):
        self._svc = build("youtube", "v3", credentials=credentials)

    # ── Public entry point ───────────────────────────────────

    def fetch_new_videos(self, since_date: str, already_scheduled: Set[str]) -> List[VideoInfo]:
        """
        Full pipeline:
          subscriptions → filter tech channels → collect new video IDs
          → fetch details → sort ascending by publishedAt
        """
        # 1. Subscriptions
        logger.info("Fetching subscribed channels...")
        channels = self._get_subscriptions()
        logger.info(f"Found {len(channels)} total subscriptions.")

        # 2. Channel details (snippet + topicDetails + uploads playlist)
        logger.info("Fetching channel details for tech/finance classification...")
        channel_ids     = [c["channel_id"] for c in channels]
        channel_details = self._get_channel_details(channel_ids)

        # 3. Filter — keep only tech channels
        tech_channels = filter_channels(channels, channel_details)
        if not tech_channels:
            logger.warning("No tech channels found after filtering.")
            return []

        # 4. Collect new video IDs from each tech channel
        logger.info(f"Scanning {len(tech_channels)} tech channels for videos since {since_date}...")
        all_video_id_tuples: List[Tuple[str, str, str]] = []  # (video_id, published_at_iso, channel_id)

        for ch in tech_channels:
            cid         = ch["channel_id"]
            uploads_pid = channel_details.get(cid, {}).get("uploads_playlist", "")
            if not uploads_pid:
                logger.warning(f"No uploads playlist for: {ch['channel_name']}")
                continue

            vid_tuples = self._get_video_ids_since(uploads_pid, since_date, already_scheduled)
            for vid, pub in vid_tuples:
                all_video_id_tuples.append((vid, pub, cid))

        logger.info(f"New videos found: {len(all_video_id_tuples)}")
        if not all_video_id_tuples:
            return []

        # 5. Fetch video details in batch (title, duration)
        unique_ids      = list({v[0] for v in all_video_id_tuples})
        channel_name_map = {c["channel_id"]: c["channel_name"] for c in channels}
        details_map     = self._get_video_details(unique_ids)

        # 6. Assemble VideoInfo objects
        videos = []
        for vid, pub_iso, cid in all_video_id_tuples:
            details = details_map.get(vid)
            if not details:
                continue
            if details["duration_seconds"] <= 0:
                logger.debug(f"Skipping zero-duration video: {vid}")
                continue

            try:
                pub_dt = datetime.strptime(pub_iso[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pub_dt = datetime.strptime(pub_iso[:10], "%Y-%m-%d")

            videos.append(VideoInfo(
                channel_name=channel_name_map.get(cid, "Unknown"),
                title=details["title"],
                video_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                duration_seconds=details["duration_seconds"],
                published_at=pub_iso[:10],
                published_at_dt=pub_dt,
            ))

        # 7. Sort ascending by publish date (oldest first → schedule in order)
        videos.sort(key=lambda v: v.published_at_dt)
        logger.info(f"Returning {len(videos)} videos sorted oldest→newest.")
        return videos

    # ── Private API wrappers ─────────────────────────────────

    def _get_subscriptions(self) -> List[dict]:
        channels, next_page = [], None
        while True:
            resp = self._svc.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=API_BATCH_SIZE,
                pageToken=next_page,
                order="alphabetical"
            ).execute()

            for item in resp.get("items", []):
                s = item["snippet"]
                channels.append({
                    "channel_id":   s["resourceId"]["channelId"],
                    "channel_name": s["title"]
                })

            if len(channels) >= MAX_SUBSCRIPTIONS:
                logger.warning(f"Hit MAX_SUBSCRIPTIONS cap ({MAX_SUBSCRIPTIONS})")
                break

            next_page = resp.get("nextPageToken")
            if not next_page:
                break

        return channels

    def _get_channel_details(self, channel_ids: List[str]) -> dict:
        """
        Returns {channel_id: {description, topic_categories, uploads_playlist}}
        Batched to use 1 quota unit per 50 channels.
        """
        result = {}
        for batch in _chunked(channel_ids, API_BATCH_SIZE):
            try:
                resp = self._svc.channels().list(
                    part="snippet,topicDetails,contentDetails",
                    id=",".join(batch),
                    maxResults=API_BATCH_SIZE
                ).execute()

                for item in resp.get("items", []):
                    cid = item["id"]
                    result[cid] = {
                        "description":      item["snippet"].get("description", ""),
                        "topic_categories": (
                            item.get("topicDetails", {})
                                .get("topicCategories", [])
                        ),
                        "uploads_playlist": (
                            item.get("contentDetails", {})
                                .get("relatedPlaylists", {})
                                .get("uploads", "")
                        )
                    }
            except HttpError as e:
                logger.warning(f"channels.list error: {e}")

        return result

    def _get_video_ids_since(self, playlist_id: str, since_date: str,
                               already_scheduled: Set[str]) -> List[Tuple[str, str]]:
        """
        Walks a channel's uploads playlist newest→oldest.
        Stops when it hits a video older than since_date.
        Returns [(video_id, published_at_iso)] for new videos only.
        """
        since_dt    = datetime.strptime(since_date, "%Y-%m-%d")
        results     = []
        next_page   = None

        while True:
            try:
                resp = self._svc.playlistItems().list(
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=API_BATCH_SIZE,
                    pageToken=next_page
                ).execute()
            except HttpError as e:
                logger.warning(f"playlistItems.list error for {playlist_id}: {e}")
                break

            hit_old = False
            for item in resp.get("items", []):
                cd  = item["contentDetails"]
                vid = cd["videoId"]
                pub = cd.get("videoPublishedAt", "")

                if not pub:
                    continue

                pub_dt = datetime.strptime(pub[:10], "%Y-%m-%d")
                if pub_dt < since_dt:
                    hit_old = True
                    break                  # Playlist is newest→oldest; stop here

                if vid not in already_scheduled:
                    results.append((vid, pub))

            if hit_old:
                break

            next_page = resp.get("nextPageToken")
            if not next_page:
                break

        return results

    def _get_video_details(self, video_ids: List[str]) -> dict:
        """
        Returns {video_id: {title, duration_seconds}}
        Batched: 1 quota unit per 50 videos.
        """
        result = {}
        for batch in _chunked(video_ids, API_BATCH_SIZE):
            try:
                resp = self._svc.videos().list(
                    part="snippet,contentDetails",
                    id=",".join(batch),
                    maxResults=API_BATCH_SIZE
                ).execute()

                for item in resp.get("items", []):
                    vid = item["id"]
                    result[vid] = {
                        "title":            item["snippet"]["title"],
                        "duration_seconds": _parse_iso8601_duration(
                            item["contentDetails"]["duration"]
                        )
                    }
            except HttpError as e:
                logger.warning(f"videos.list error: {e}")

        return result


# ── Utilities ────────────────────────────────────────────────

def _parse_iso8601_duration(duration: str) -> int:
    """
    PT4S→4  PT1M→60  PT1H30M25S→5425  P1DT2H→93600
    """
    pattern = r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match   = re.fullmatch(pattern, duration)
    if not match:
        return 0
    days, hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _chunked(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]
