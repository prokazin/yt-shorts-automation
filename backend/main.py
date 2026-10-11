"""
FastAPI — точка входа для Cloudflare Worker и Telegram webhook.
Полный пайплайн: скачивание → монтаж → музыка → одобрение → публикация.
"""
import os
import tempfile
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from downloader import search_and_download
from processor import process_video
from music import search_music, download_music, mix_audio_with_video
from publisher import upload_video
from analytics import analyze_best_times, get_optimal_publish_time
from storage import (
    save_pending_video,
    update_telegram_message_id,
    approve_video,
    reject_video,
    mark_published,
    get_approved_videos,
    get_pending_video_by_message_id,
    cleanup_old_videos,
)
from telegram_bot import (
    send_video_for_approval,
    answer_callback,
    send_status_message,
    parse_callback_data,
)

app = FastAPI(title="YT Shorts Automation")

scheduler = BackgroundScheduler()


# ─── Модели ───────────────────────────────────────────────

class PipelineRequest(BaseModel):
    query: str = "atmospheric nature"
    mood: str = "calm"
    title: str = "Atmospheric Short"
    description: str = ""
    tags: list = []


class PublishRequest(BaseModel):
    video_db_id: str


# ─── Планировщик ──────────────────────────────────────────

def scheduled_publish_job():
    """
    Каждые 30 минут проверяет одобренные видео
    и публикует те, для которых наступило оптимальное время.
    """
    approved = get_approved_videos()
    if not approved:
        return

    now = datetime.now(timezone.utc)

    for video in approved:
        scheduled = video.get("scheduled_publish_time")
        if not scheduled:
            continue
        try:
            scheduled_dt = datetime.fromisoformat(scheduled)
            if scheduled_dt <= now:
                _publish_single_video(video)
        except (ValueError, TypeError):
            continue


def _publish_single_video(video: dict) -> None:
    """Публикует одно видео на YouTube и обновляет статус."""
    try:
        youtube_id = upload_video(
            video_path=video["video_path"],
            title=video["title"],
            description=video.get("description", ""),
            tags=video.get("tags", []),
            publish_at=video.get("scheduled_publish_time"),
        )
        mark_published(video["id"], youtube_id)
        send_status_message(
            f"✅ Опубликовано: {video['title']}\n"
            f"https://youtu.be/{youtube_id}"
        )
    except Exception as e:
        send_status_message(
            f"❌ Ошибка публикации «{video['title']}»: {e}"
        )


# ─── Запуск планировщика ──────────────────────────────────

@app.on_event("startup")
def startup_event():
    scheduler.add_job(scheduled_publish_job, "interval", minutes=30)
    scheduler.add_job(analyze_best_times, "cron", hour=3, minute=0)
    scheduler.add_job(cleanup_old_videos, "cron", hour=4, minute=0)
    scheduler.start()
    print("[startup] Планировщик запущен")


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()


# ─── Эндпоинты ────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/run-pipeline")
def run_pipeline(req: PipelineRequest):
    """
    Полный пайплайн: скачать → обработать → музыка → отправить на одобрение.
    """
    try:
        tmp_dir = tempfile.mkdtemp(prefix="pipeline_")

        # 1. Скачивание
        raw_video = search_and_download(query=req.query)

        # 2. Обработка (вертикальный формат)
        processed = os.path.join(tmp_dir, "processed.mp4")
        process_video(raw_video, processed, duration=55)

        # 3. Подбор и наложение музыки
        music_url = search_music(duration=55, mood=req.mood)
        music_path = os.path.join(tmp_dir, "music.mp3")
        download_music(music_url, music_path)

        final_video = os.path.join(tmp_dir, "final.mp4")
        mix_audio_with_video(processed, music_path, final_video)

        # 4. Сохранение в Supabase
        db_record = save_pending_video(
            video_path=final_video,
            title=req.title,
            description=req.description,
            tags=req.tags,
            query=req.query,
            mood=req.mood,
        )
        video_db_id = db_record.get("id", "")

        # 5. Отправка в Telegram
        message_id = send_video_for_approval(
            final_video,
            caption=f"🎬 {req.title}\n\n{req.description}",
            video_db_id=video_db_id,
        )
        update_telegram_message_id(video_db_id, message_id)

        return {
            "status": "sent_for_approval",
            "video_db_id": video_db_id,
            "message_id": message_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """
    Обрабатывает callback от кнопок «Одобрить» / «Отклонить».
    """
    data = await request.json()

    if "callback_query" not in data:
        return {"ok": True}

    callback = data["callback_query"]
    callback_id = callback.get("id", "")
    callback_data = callback.get("data", "")

    action, video_db_id = parse_callback_data(callback_data)

    if not video_db_id:
        answer_callback(callback_id, "Ошибка: видео не найдено")
        return {"ok": True}

    if action == "approve":
        approve_video(video_db_id)

        # Определяем оптимальное время публикации
        publish_time = get_optimal_publish_time()

        # Обновляем запись с временем публикации
        from storage import supabase
        supabase.table("pending_videos").update({
            "scheduled_publish_time": publish_time,
        }).eq("id", video_db_id).execute()

        answer_callback(callback_id, f"✅ Одобрено! Публикация: {publish_time}")
        send_status_message(
            f"✅ Видео одобрено.\n"
            f"Оптимальное время публикации: {publish_time}"
        )

    elif action == "reject":
        reject_video(video_db_id)
        answer_callback(callback_id, "❌ Отклонено")
        send_status_message("❌ Видео отклонено.")

    return {"ok": True}


@app.post("/approve-and-publish")
def approve_and_publish(video_db_id: str):
    """Принудительная публикация одобренного видео (без ожидания расписания)."""
    approved = get_approved_videos()
    video = next((v for v in approved if v["id"] == video_db_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    _publish_single_video(video)
    return {"status": "published"}


@app.post("/analyze-times")
def trigger_analyze():
    """Ручной запуск анализа лучшего времени публикации."""
    results = analyze_best_times()
    return {"status": "ok", "results": results[:10]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
