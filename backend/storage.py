"""
Локальное хранение состояния (JSON-файл).
"""
import os
import json
from datetime import datetime, timezone

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


def _load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"videos": [], "best_publish_times": []}


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def save_pending_video(video_path, title, description="", tags=None,
                       query="", mood="calm", platforms=None):
    state = _load_state()
    video_id = f"vid_{int(datetime.now(timezone.utc).timestamp())}"
    video = {
        "id": video_id,
        "video_path": video_path,
        "title": title,
        "description": description,
        "tags": tags or [],
        "query": query,
        "mood": mood,
        "platforms": platforms or ["youtube"],
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": None,
        "published_at": None,
        "youtube_video_id": None,
        "instagram_media_id": None,
        "scheduled_publish_time": None,
    }
    state["videos"].append(video)
    _save_state(state)
    return video


def update_video(video_id, **kwargs):
    state = _load_state()
    for v in state["videos"]:
        if v["id"] == video_id:
            v.update(kwargs)
            break
    _save_state(state)


def get_video(video_id):
    state = _load_state()
    for v in state["videos"]:
        if v["id"] == video_id:
            return v
    return {}


def get_approved_videos():
    state = _load_state()
    return [v for v in state["videos"] if v["status"] == "approved"]


def save_best_publish_time(hour_utc, day_of_week, avg_views, sample_count):
    state = _load_state()
    for item in state["best_publish_times"]:
        if item["hour_utc"] == hour_utc and item["day_of_week"] == day_of_week:
            item.update({
                "avg_views": avg_views,
                "sample_count": sample_count,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            _save_state(state)
            return
    state["best_publish_times"].append({
        "hour_utc": hour_utc,
        "day_of_week": day_of_week,
        "avg_views": avg_views,
        "sample_count": sample_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    _save_state(state)


def get_best_publish_times():
    state = _load_state()
    return sorted(state["best_publish_times"],
                  key=lambda x: x["avg_views"], reverse=True)


def cleanup_old_videos(days=30):
    state = _load_state()
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    state["videos"] = [
        v for v in state["videos"]
        if v["status"] != "rejected" or
        datetime.fromisoformat(v["created_at"]).timestamp() > cutoff
    ]
    _save_state(state)
