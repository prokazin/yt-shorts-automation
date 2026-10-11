"""
Хранение состояния в Supabase.
Таблицы: pending_videos, best_publish_times.
"""
import os
from datetime import datetime, timezone
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_pending_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
    query: str = "",
    mood: str = "calm",
) -> dict:
    """Сохраняет видео в очередь на одобрение."""
    result = supabase.table("pending_videos").insert({
        "video_path": video_path,
        "title": title,
        "description": description,
        "tags": tags or [],
        "query": query,
        "mood": mood,
        "status": "pending",
    }).execute()
    return result.data[0] if result.data else {}


def update_telegram_message_id(video_id: str, message_id: int) -> None:
    """Сохраняет ID сообщения в Telegram для дальнейшей обработки."""
    supabase.table("pending_videos").update(
        {"telegram_message_id": message_id}
    ).eq("id", video_id).execute()


def approve_video(video_id: str) -> dict:
    """Помечает видео как одобренное."""
    result = supabase.table("pending_videos").update({
        "status": "approved",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", video_id).execute()
    return result.data[0] if result.data else {}


def reject_video(video_id: str) -> dict:
    """Помечает видео как отклонённое."""
    result = supabase.table("pending_videos").update({
        "status": "rejected",
    }).eq("id", video_id).execute()
    return result.data[0] if result.data else {}


def mark_published(video_id: str, youtube_id: str) -> None:
    """Помечает видео как опубликованное."""
    supabase.table("pending_videos").update({
        "status": "published",
        "youtube_video_id": youtube_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", video_id).execute()


def get_approved_videos() -> list:
    """Возвращает все одобренные, но ещё не опубликованные видео."""
    result = supabase.table("pending_videos").select("*").eq(
        "status", "approved"
    ).execute()
    return result.data or []


def get_pending_video_by_message_id(message_id: int) -> dict:
    """Находит видео по ID сообщения в Telegram."""
    result = supabase.table("pending_videos").select("*").eq(
        "telegram_message_id", message_id
    ).execute()
    return result.data[0] if result.data else {}


def save_best_publish_time(hour_utc: int, day_of_week: int,
                           avg_views: float, sample_count: int) -> None:
    """Сохраняет данные об оптимальном времени публикации."""
    supabase.table("best_publish_times").upsert({
        "hour_utc": hour_utc,
        "day_of_week": day_of_week,
        "avg_views": avg_views,
        "sample_count": sample_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="hour_utc,day_of_week").execute()


def get_best_publish_times() -> list:
    """Возвращает все сохранённые оптимальные времена."""
    result = supabase.table("best_publish_times").select("*").order(
        "avg_views", desc=True
    ).execute()
    return result.data or []


def cleanup_old_videos(days: int = 30) -> None:
    """Удаляет старые отклонённые видео из БД."""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    supabase.table("pending_videos").delete().eq(
        "status", "rejected"
    ).lt("created_at", cutoff_iso).execute()
