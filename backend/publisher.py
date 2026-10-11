"""
Публикация видео на YouTube через Data API v3.
Поддерживает отложенную публикацию (scheduled publish).
"""
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.pickle")
SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")


def get_authenticated_service():
    """Авторизация в YouTube API."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
    category_id: str = "22",
    privacy_status: str = "public",
    publish_at: str = None,
) -> str:
    """
    Загружает видео на YouTube.
    Если publish_at задан (ISO 8601 UTC), видео публикуется по расписанию.
    """
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy_status,
        },
    }

    if publish_at:
        body["status"]["publishAt"] = publish_at
        body["status"]["privacyStatus"] = "private"

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[publisher] Загружено {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"[publisher] Видео: https://youtu.be/{video_id}")
    return video_id
