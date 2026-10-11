"""
Отправка видео на одобрение в Telegram + обработка callback.
"""
import os
import json
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_video_for_approval(video_path: str, caption: str = "",
                            video_db_id: str = "") -> int:
    """
    Отправляет видео в Telegram с кнопками.
    Возвращает message_id для последующей обработки.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Одобрить", "callback_data": f"approve:{video_db_id}"},
            {"text": "❌ Отклонить", "callback_data": f"reject:{video_db_id}"},
        ]]
    }

    with open(video_path, "rb") as video_file:
        files = {"video": video_file}
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption or "Новое видео на одобрение",
            "reply_markup": json.dumps(keyboard),
        }
        response = requests.post(url, files=files, data=data, timeout=120)

    if response.status_code == 200:
        message_id = response.json()["result"]["message_id"]
        print(f"[telegram] Видео отправлено, message_id={message_id}")
        return message_id
    raise RuntimeError(f"Telegram ошибка: {response.text}")


def answer_callback(callback_id: str, text: str = "Принято!") -> None:
    """Подтверждает нажатие кнопки в Telegram."""
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text},
        timeout=10,
    )


def send_status_message(text: str) -> None:
    """Отправляет текстовое уведомление в Telegram."""
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=30,
    )


def parse_callback_data(data: str) -> tuple:
    """
    Парсит callback_data вида "approve:uuid" или "reject:uuid".
    Возвращает (action, video_db_id).
    """
    parts = data.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return data, ""
