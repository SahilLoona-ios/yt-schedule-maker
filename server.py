# ============================================================
#  server.py — Flask REST API for the Dashboard
#  Run: python server.py → open http://localhost:5000
# ============================================================

import os
import sys
import json
import threading
import queue
import logging
import urllib.request
from datetime import datetime, date
from flask import Flask, jsonify, request, send_file, Response   # ← fixed import
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ

sys.path.insert(0, os.path.dirname(__file__))

from auth           import get_credentials
from youtube_client import _parse_iso8601_duration
from channel_filter import should_include_channel
from scheduler      import build_schedule
from excel_writer   import write_excel
from state_manager  import (
    load_state, save_state,
    get_fetch_since_date, get_already_scheduled_ids,
    update_state_after_run
)
import config as cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".", template_folder=".")
CORS(app)

_creds          = None
_channels_cache = None
_videos_cache   = {}          # { channel_id: [video, ...] }
_progress_queue = queue.Queue()


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

@app.route("/api/auth/status")
def auth_status():
    global _creds
    _creds = _try_load_existing_creds()
    return jsonify({
        "authenticated": _creds is not None and _creds.valid,
        "token_exists":  os.path.exists(cfg.TOKEN_FILE)
    })


@app.route("/api/auth/connect", methods=["POST"])
def auth_connect():
    global _creds
    result = {"creds": None, "error": None}
    done   = threading.Event()

    def _do_auth():
        try:
            result["creds"] = get_credentials()
        except Exception as e:
            result["error"] = str(e)
        finally:
            done.set()

    threading.Thread(target=_do_auth, daemon=True).start()
    done.wait(timeout=180)

    if result["error"]:
        return jsonify({"success": False, "error": result["error"]}), 400
    if result["creds"]:
        _creds = result["creds"]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Auth timed out"}), 408


@app.route("/api/auth/disconnect", methods=["POST"])
def auth_disconnect():
    global _creds, _channels_cache, _videos_cache
    _creds = None
    _channels_cache = None
    _videos_cache   = {}
    if os.path.exists(cfg.TOKEN_FILE):
        os.remove(cfg.TOKEN_FILE)
    return jsonify({"success": True})


# ══════════════════════════════════════════════════════════════
#  CHANNELS
# ══════════════════════════════════════════════════════════════

@app.route("/api/channels")
def get_channels():
    global _creds, _channels_cache
    _creds = _ensure_creds()
    if not _creds:
        return jsonify({"error": "Not authenticated"}), 401

    force = request.args.get("refresh", "0") == "1"
    if _channels_cache and not force:
        return jsonify({"channels": _channels_cache})

    try:
        svc      = _build_yt_service()
        raw      = _fetch_all_subscriptions(svc)
        details  = _fetch_channel_details(svc, [c["channel_id"] for c in raw])
        enriched = _enrich_channels(raw, details)
        _channels_cache = enriched
        return jsonify({"channels": enriched})
    except Exception as e:
        logger.error(f"Channels fetch error: {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  VIDEOS FOR A SINGLE CHANNEL  ← NEW
# ══════════════════════════════════════════════════════════════

@app.route("/api/channels/<channel_id>/videos")
def get_channel_videos(channel_id):
    """
    Fetch videos for a single channel since ?since=YYYY-MM-DD.
    Returns list of {video_id, title, thumbnail, duration_str,
                     duration_seconds, published_at, url}
    Cached per channel_id+since_date pair.
    """
    global _videos_cache
    _creds = _ensure_creds()
    if not _creds:
        return jsonify({"error": "Not authenticated"}), 401

    since_date = request.args.get("since", cfg.VIDEOS_START_DATE)
    cache_key  = f"{channel_id}:{since_date}"

    if cache_key in _videos_cache:
        return jsonify({"videos": _videos_cache[cache_key]})

    # Find uploads playlist from channel cache
    uploads_playlist = ""
    if _channels_cache:
        for ch in _channels_cache:
            if ch["id"] == channel_id:
                uploads_playlist = ch.get("uploads_playlist", "")
                break

    if not uploads_playlist:
        # Fetch it directly
        try:
            svc  = _build_yt_service()
            resp = svc.channels().list(
                part="contentDetails", id=channel_id
            ).execute()
            items = resp.get("items", [])
            if items:
                uploads_playlist = (
                    items[0].get("contentDetails", {})
                            .get("relatedPlaylists", {})
                            .get("uploads", "")
                )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not uploads_playlist:
        return jsonify({"videos": []})

    try:
        svc      = _build_yt_service()
        vid_ids  = _get_video_ids_since_date(svc, uploads_playlist, since_date, set())
        if not vid_ids:
            _videos_cache[cache_key] = []
            return jsonify({"videos": []})

        ids_only    = [v[0] for v in vid_ids]
        pub_map     = {v[0]: v[1] for v in vid_ids}
        details_map = _get_video_details_full(svc, ids_only)

        videos = []
        for vid_id in ids_only:
            d = details_map.get(vid_id)
            if not d or d["duration_seconds"] <= 0:
                continue
            videos.append({
                "video_id":         vid_id,
                "title":            d["title"],
                "thumbnail":        d.get("thumbnail", ""),
                "duration_str":     _fmt_duration(d["duration_seconds"]),
                "duration_seconds": d["duration_seconds"],
                "published_at":     pub_map.get(vid_id, "")[:10],
                "url":              f"https://www.youtube.com/watch?v={vid_id}",
            })

        # Sort oldest first
        videos.sort(key=lambda v: v["published_at"])
        _videos_cache[cache_key] = videos
        return jsonify({"videos": videos})

    except Exception as e:
        logger.error(f"Videos fetch error: {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  HOLIDAYS  — Calendarific (India) + Punjab-specific fallbacks
# ══════════════════════════════════════════════════════════════

# Punjab-specific holidays not reliably in Calendarific national data
_PUNJAB_EXTRA = [
    {"month": 1,  "day": 13, "name": "Lohri"},
    {"month": 4,  "day": 14, "name": "Baisakhi"},
    {"month": 11, "day": 11, "name": "Guru Nanak Jayanti"},
]

_holidays_cache = {}   # { year: [ {date, name}, ... ] }


@app.route("/api/holidays")
def get_holidays():
    year_str = request.args.get("year", str(date.today().year))
    try:
        year = int(year_str)
    except ValueError:
        return jsonify({"error": "Invalid year"}), 400

    if year in _holidays_cache:
        return jsonify({"holidays": _holidays_cache[year]})

    api_key = os.environ.get("CALENDARIFIC_API_KEY", "")
    holidays = []

    if api_key:
        try:
            url = (
                f"https://calendarific.com/api/v2/holidays"
                f"?api_key={api_key}&country=IN&year={year}&type=national,local"
            )
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            for h in data.get("response", {}).get("holidays", []):
                d = h.get("date", {}).get("iso", "")[:10]
                holidays.append({"date": d, "name": h["name"]})
        except Exception as e:
            logger.warning(f"Calendarific fetch failed: {e}")

    # Merge Punjab-specific extras (skip if already present by date)
    existing_dates = {h["date"] for h in holidays}
    for extra in _PUNJAB_EXTRA:
        d = f"{year}-{extra['month']:02d}-{extra['day']:02d}"
        if d not in existing_dates:
            holidays.append({"date": d, "name": extra["name"]})

    # Sort by date
    holidays.sort(key=lambda h: h["date"])
    _holidays_cache[year] = holidays
    return jsonify({"holidays": holidays})


@app.route("/api/config")
def get_config():
    return jsonify({
        "weekday_hours":     cfg.WEEKDAY_BUDGET_HOURS,
        "weekend_hours":     cfg.WEEKEND_BUDGET_HOURS,
        "revision_minutes":  cfg.REVISION_MINUTES,
        "videos_start_date": cfg.VIDEOS_START_DATE,
        "skip_channels":     cfg.SKIP_CHANNELS,
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    _apply_config(request.get_json() or {})
    return jsonify({"success": True})


# ══════════════════════════════════════════════════════════════
#  GENERATE  — now accepts selected_video_ids
# ══════════════════════════════════════════════════════════════

@app.route("/api/generate", methods=["POST"])
def generate():
    """
    Body: {
      selected_video_ids: ["vid1", "vid2", ...],   ← specific videos
      config: { start_date, weekday_hours, ... }
    }
    """
    global _creds
    _creds = _ensure_creds()
    if not _creds:
        return jsonify({"error": "Not authenticated"}), 401

    body              = request.get_json() or {}
    selected_video_ids = set(body.get("selected_video_ids", []))
    user_config        = body.get("config", {})

    if not selected_video_ids:
        return jsonify({"error": "No videos selected"}), 400

    _apply_config(user_config)

    while not _progress_queue.empty():
        _progress_queue.get_nowait()

    def _run():
        try:
            _push("start", "Preparing selected videos…", 5)

            # Build a lookup: video_id → channel_name from _videos_cache
            channel_name_map = {}
            if _channels_cache:
                for ch in _channels_cache:
                    cid = ch["id"]
                    for vid_list in _videos_cache.values():
                        for v in vid_list:
                            channel_name_map[v["video_id"]] = ch["name"]

            # Simpler: build from _videos_cache directly
            vid_to_channel = {}
            for cache_key, vids in _videos_cache.items():
                cid = cache_key.split(":")[0]
                ch_name = next(
                    (c["name"] for c in (_channels_cache or []) if c["id"] == cid),
                    "Unknown"
                )
                for v in vids:
                    vid_to_channel[v["video_id"]] = ch_name

            _push("progress", f"Building VideoInfo for {len(selected_video_ids)} videos…", 20)

            from youtube_client import VideoInfo
            from datetime import datetime as dt

            videos = []
            for cache_key, vids in _videos_cache.items():
                for v in vids:
                    if v["video_id"] not in selected_video_ids:
                        continue
                    try:
                        pub_dt = dt.strptime(v["published_at"][:10], "%Y-%m-%d")
                    except Exception:
                        pub_dt = dt.today()

                    cid     = cache_key.split(":")[0]
                    ch_name = next(
                        (c["name"] for c in (_channels_cache or []) if c["id"] == cid),
                        "Unknown"
                    )
                    videos.append(VideoInfo(
                        channel_name=ch_name,
                        title=v["title"],
                        video_id=v["video_id"],
                        url=v["url"],
                        duration_seconds=v["duration_seconds"],
                        published_at=v["published_at"][:10],
                        published_at_dt=pub_dt,
                    ))

            if not videos:
                _push("done", "No videos to schedule.", 100)
                return

            videos.sort(key=lambda v: v.published_at_dt)
            _push("progress", f"Building schedule for {len(videos)} videos…", 50)

            state    = load_state()
            sessions, last_day, remaining = build_schedule(videos, state)

            _push("progress", f"Writing Excel — {len(sessions)} sessions…", 80)
            write_excel(sessions)

            new_ids = [v.video_id for v in videos]
            updated = update_state_after_run(state, new_ids, last_day, remaining)
            save_state(updated)

            days = len({s.session_date for s in sessions})
            _push("done",
                  f"Done! {len(videos)} videos → {len(sessions)} sessions across {days} days ✅",
                  100)

        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            _push("error", f"Error: {str(e)}", 0)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"success": True})


@app.route("/api/generate/stream")
def generate_stream():
    def _events():
        yield "data: {\"type\":\"connected\"}\n\n"
        while True:
            try:
                event = _progress_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield "data: {\"type\":\"heartbeat\"}\n\n"

    return Response(_events(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/download")
def download():
    if not os.path.exists(cfg.OUTPUT_FILE):
        return jsonify({"error": "No schedule file found yet"}), 404
    return send_file(
        os.path.abspath(cfg.OUTPUT_FILE),
        as_attachment=True,
        download_name="yt_schedule.xlsx"
    )


@app.route("/")
def dashboard():
    return send_file("dashboard.html")


# ══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════

def _push(event_type, message, progress):
    _progress_queue.put({"type": event_type, "message": message, "progress": progress})


def _try_load_existing_creds():
    try:
        from auth import _load_token
        c = _load_token()
        if c and c.valid:
            return c
        if c and c.expired and c.refresh_token:
            from google.auth.transport.requests import Request
            c.refresh(Request())
            return c
    except Exception:
        pass
    return None


def _ensure_creds():
    global _creds
    if _creds and _creds.valid:
        return _creds
    _creds = _try_load_existing_creds()
    return _creds


def _build_yt_service():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_ensure_creds())


def _fetch_all_subscriptions(svc):
    channels, next_page = [], None
    while True:
        resp = svc.subscriptions().list(
            part="snippet", mine=True, maxResults=50,
            pageToken=next_page, order="alphabetical"
        ).execute()
        for item in resp.get("items", []):
            s = item["snippet"]
            channels.append({
                "channel_id":   s["resourceId"]["channelId"],
                "channel_name": s["title"],
                "thumbnail":    s.get("thumbnails", {}).get("default", {}).get("url", "")
            })
        next_page = resp.get("nextPageToken")
        if not next_page or len(channels) >= 1000:
            break
    return channels


def _fetch_channel_details(svc, channel_ids):
    result = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        resp  = svc.channels().list(
            part="snippet,statistics,topicDetails,contentDetails",
            id=",".join(batch), maxResults=50
        ).execute()
        for item in resp.get("items", []):
            cid   = item["id"]
            stats = item.get("statistics", {})
            subs  = int(stats.get("subscriberCount", 0))
            result[cid] = {
                "description":      item["snippet"].get("description", ""),
                "topic_categories": item.get("topicDetails", {}).get("topicCategories", []),
                "uploads_playlist": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
                "subscriber_count": _fmt_subs(subs),
                "video_count":      stats.get("videoCount", "0"),
            }
    return result


def _enrich_channels(raw, details):
    enriched = []
    for ch in raw:
        cid = ch["channel_id"]
        det = details.get(cid, {})
        include, reason = should_include_channel(
            ch["channel_name"],
            det.get("description", ""),
            det.get("topic_categories", [])
        )
        from config import SKIP_CHANNELS
        is_skipped = any(s.lower() in ch["channel_name"].lower() for s in SKIP_CHANNELS)
        category = "skipped" if is_skipped else ("tech" if include else "finance")

        enriched.append({
            "id":               cid,
            "name":             ch["channel_name"],
            "thumbnail":        ch.get("thumbnail", ""),
            "subscriber_count": det.get("subscriber_count", ""),
            "video_count":      det.get("video_count", "0"),
            "category":         category,
            "reason":           reason,
            "uploads_playlist": det.get("uploads_playlist", ""),
            "selected":         (category == "tech"),
        })
    return sorted(enriched, key=lambda c: c["name"].lower())


def _apply_config(body):
    if "weekday_hours"    in body: cfg.WEEKDAY_BUDGET_HOURS = float(body["weekday_hours"])
    if "weekend_hours"    in body: cfg.WEEKEND_BUDGET_HOURS = float(body["weekend_hours"])
    if "revision_minutes" in body: cfg.REVISION_MINUTES     = int(body["revision_minutes"])
    if "start_date"       in body: cfg.VIDEOS_START_DATE    = body["start_date"]
    if "skip_channels"    in body: cfg.SKIP_CHANNELS        = body["skip_channels"]


def _fmt_subs(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)


def _fmt_duration(seconds):
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:   return f"{h}h {m:02d}m"
    if m:   return f"{m}m {s:02d}s"
    return  f"{s}s"


def _get_video_ids_since_date(svc, playlist_id, since_date, already_scheduled):
    from datetime import datetime as dt
    since_dt = dt.strptime(since_date, "%Y-%m-%d")
    results, next_page = [], None
    while True:
        try:
            resp = svc.playlistItems().list(
                part="contentDetails", playlistId=playlist_id,
                maxResults=50, pageToken=next_page
            ).execute()
        except Exception as e:
            logger.warning(f"playlistItems error: {e}")
            break
        hit_old = False
        for item in resp.get("items", []):
            cd  = item["contentDetails"]
            vid = cd["videoId"]
            pub = cd.get("videoPublishedAt", "")
            if not pub:
                continue
            if dt.strptime(pub[:10], "%Y-%m-%d") < since_dt:
                hit_old = True
                break
            if vid not in already_scheduled:
                results.append((vid, pub))
        if hit_old:
            break
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    return results


def _get_video_details_full(svc, video_ids):
    """Like _get_video_details but also returns thumbnail."""
    result = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            resp = svc.videos().list(
                part="snippet,contentDetails", id=",".join(batch), maxResults=50
            ).execute()
            for item in resp.get("items", []):
                thumbs = item["snippet"].get("thumbnails", {})
                thumb  = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
                result[item["id"]] = {
                    "title":            item["snippet"]["title"],
                    "thumbnail":        thumb,
                    "duration_seconds": _parse_iso8601_duration(item["contentDetails"]["duration"])
                }
        except Exception as e:
            logger.warning(f"videos.list error: {e}")
    return result


if __name__ == "__main__":
    print("\n" + "═" * 50)
    print("  📺  YT Schedule Dashboard")
    print("  🌐  Open: http://localhost:5000")
    print("═" * 50 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
