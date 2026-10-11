"""
Главный скрипт пайплайна. Запускается через cron.
Полный цикл: скачивание → обработка → музыка → Telegram → одобрение → публикация.
"""
import os
import sys
import tempfile
from datetime import datetime, timezone

from downloader import search_and_download
from processor import process_video
from music import search_music, download_music, mix_audio_with_video
from publisher_youtube import upload_video as upload_youtube
from publisher_instagram import upload_reel as upload_instagram
from analytics import analyze_best_times, get_optimal_publish_time
from storage import (
    save_pending_video, update_video, get_video,
    get_approved_videos, cleanup_old_videos,
)
from telegram_bot import send_video_for_approval, send_status_message


PIPELINE_CONFIGS = [
    {
        "query": "atmospheric nature",
        "mood": "calm",
        "title": "Атмосферная нарезка",
        "description": "Успокаивающее видео с природой #shorts #atmospheric",
        "tags": ["atmospheric", "nature", "relax", "shorts"],
        "platforms": ["youtube", "instagram"],
    },
    {
        "query": "vintage city 1950s",
        "mood": "nostalgic",
        "title": "Ретро-город",
        "description": "Винтажные кадры города #shorts #retro #vintage",
        "tags": ["retro", "vintage", "city", "shorts"],
        "platforms": ["youtube", "instagram"],
    },
    {
        "query": "ocean waves sunset",
        "mood": "peaceful",
        "title": "Океан на закате",
        "description": "Волны и закат #shorts #ocean #sunset",
        "tags": ["ocean", "sunset", "waves", "shorts"],
        "platforms": ["youtube", "instagram"],
    },
]


def run_pipeline(config_index=0):
    cfg = PIPELINE_CONFIGS[config_index % len(PIPELINE_CONFIGS)]
    print(f"[pipeline] Запуск: {cfg['title']}")

    try:
        tmp_dir = tempfile.mkdtemp(prefix="pipeline_")

        raw_video = search_and_download(query=cfg["query"])

        processed = os.path.join(tmp_dir, "processed.mp4")
        process_video(raw_video, processed, duration=55)

        music_url = search_music(duration=55, mood=cfg["mood"])
        music_path = os.path.join(tmp_dir, "music.mp3")
        download_music(music_url, music_path)

        final_video = os.path.join(tmp_dir, "final.mp4")
        mix_audio_with_video(processed, music_path, final_video)

        db_record = save_pending_video(
            video_path=final_video,
            title=cfg["title"],
            description=cfg["description"],
            tags=cfg["tags"],
            query=cfg["query"],
            mood=cfg["mood"],
            platforms=cfg["platforms"],
        )
        video_db_id = db_record["id"]

        send_video_for_approval(
            final_video,
            caption=f"🎬 {cfg['title']}\n\n{cfg['description']}",
            video_db_id=video_db_id,
        )

        print(f"[pipeline] Видео отправлено на одобрение: {video_db_id}")
        return video_db_id

    except Exception as e:
        error_msg = f"❌ Ошибка пайплайна: {e}"
        print(error_msg)
        send_status_message(error_msg)
        raise


def publish_approved():
    approved = get_approved_videos()
    if not approved:
        print("[publish] Нет одобренных видео")
        return

    now = datetime.now(timezone.utc)

    for video in approved:
        scheduled = video.get("scheduled_publish_time")
        if not scheduled:
            continue
        try:
            scheduled_dt = datetime.fromisoformat(scheduled)
            if scheduled_dt > now:
                continue
        except (ValueError, TypeError):
            continue

        _publish_single_video(video)


def _publish_single_video(video):
    results = []
    platforms = video.get("platforms", ["youtube"])

    try:
        if "youtube" in platforms:
            yt_id = upload_youtube(
                video_path=video["video_path"],
                title=video["title"],
                description=video.get("description", ""),
                tags=video.get("tags", []),
                publish_at=video.get("scheduled_publish_time"),
            )
            update_video(video["id"], youtube_video_id=yt_id)
            results.append(f"YouTube: https://youtu.be/{yt_id}")

        if "instagram" in platforms:
            ig_id = upload_instagram(
                video_path=video["video_path"],
                caption=video.get("description", ""),
            )
            update_video(video["id"], instagram_media_id=ig_id)
            results.append(f"Instagram: {ig_id}")

        update_video(
            video["id"],
            status="published",
            published_at=datetime.now(timezone.utc).isoformat(),
        )
        send_status_message(
            f"✅ Опубликовано: {video['title']}\n" + "\n".join(results)
        )

    except Exception as e:
        send_status_message(f"❌ Ошибка публикации «{video['title']}»: {e}")


def run_analytics():
    try:
        analyze_best_times()
        send_status_message("📊 Анализ времени публикации завершён")
    except Exception as e:
        send_status_message(f"❌ Ошибка анализа: {e}")


def handle_telegram_commands():
    import requests
    from telegram_bot import TELEGRAM_BOT_TOKEN

    state_file = os.path.join(os.path.dirname(__file__), "telegram_offset.txt")
    offset = 0
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            offset = int(f.read().strip() or "0")

    resp = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
        params={"offset": offset, "timeout": 5},
        timeout=30,
    )
    if not resp.ok:
        return

    updates = resp.json().get("result", [])
    for update in updates:
        offset = update["update_id"] + 1

        if "callback_query" in update:
            callback = update["callback_query"]
            callback_id = callback.get("id", "")
            callback_data = callback.get("data", "")

            from telegram_bot import parse_callback_data, answer_callback
            action, video_db_id = parse_callback_data(callback_data)

            if not video_db_id:
                answer_callback(callback_id, "Ошибка: видео не найдено")
                continue

            if action == "approve":
                video = get_video(video_db_id)
                if not video:
                    answer_callback(callback_id, "Видео не найдено")
                    continue

                publish_time = get_optimal_publish_time()
                update_video(
                    video_db_id,
                    status="approved",
                    approved_at=datetime.now(timezone.utc).isoformat(),
                    scheduled_publish_time=publish_time,
                )
                answer_callback(callback_id, f"✅ Одобрено! Публикация: {publish_time}")
                send_status_message(
                    f"✅ Видео одобрено.\n"
                    f"Оптимальное время публикации: {publish_time}"
                )

            elif action == "reject":
                update_video(video_db_id, status="rejected")
                answer_callback(callback_id, "❌ Отклонено")
                send_status_message("❌ Видео отклонено.")

    with open(state_file, "w") as f:
        f.write(str(offset))


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "pipeline"

    if action == "pipeline":
        config_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        run_pipeline(config_index)

    elif action == "publish":
        publish_approved()

    elif action == "analytics":
        run_analytics()

    elif action == "telegram":
        handle_telegram_commands()

    elif action == "cleanup":
        cleanup_old_videos()
        print("[cleanup] Старые видео удалены")
