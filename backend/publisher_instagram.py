"""
Публикация Reels в Instagram через instagrapi (приватный API).
"""
import os
from instagrapi import Client

SESSION_FILE = os.path.join(os.path.dirname(__file__), "ig_session.json")


def _get_client():
    """Авторизуется в Instagram и сохраняет сессию."""
    cl = Client()
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
    username = os.environ.get("IG_USERNAME", "")
    password = os.environ.get("IG_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("IG_USERNAME или IG_PASSWORD не заданы")
    cl.login(username, password)
    cl.dump_settings(SESSION_FILE)
    return cl


def upload_reel(video_path, caption=""):
    """
    Публикует Reel в Instagram.
    """
    cl = _get_client()
    media = cl.clip_upload(video_path, caption)
    media_id = media.pk
    print(f"[instagram] Reel опубликован: {media_id}")
    return media_id
