"""
Обработка видео через облачный FFmpeg API.
"""
import os
import time
import requests

FFMPEG_API_KEY = os.environ.get("FFMPEG_API_KEY", "")
FFMPEG_BASE_URL = os.environ.get("FFMPEG_BASE_URL", "https://api.renderio.dev/v1")


def process_video(input_path: str, output_path: str,
                  duration: int = 55) -> str:
    """Обрезает видео до вертикального формата 9:16 и заданной длительности."""
    if not FFMPEG_API_KEY:
        raise RuntimeError("FFMPEG_API_KEY не задан")

    ffmpeg_command = (
        f"-i input.mp4 -t {duration} "
        f"-vf 'crop=ih*9/16:ih,scale=1080:1920' "
        f"-c:v libx264 -preset fast -crf 23 -an output.mp4"
    )

    with open(input_path, "rb") as f:
        response = requests.post(
            f"{FFMPEG_BASE_URL}/jobs",
            headers={"Authorization": f"Bearer {FFMPEG_API_KEY}"},
            files={"file": f},
            data={"command": ffmpeg_command},
            timeout=300,
        )
    response.raise_for_status()
    job_id = response.json()["job_id"]

    for _ in range(60):
        status_resp = requests.get(
            f"{FFMPEG_BASE_URL}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {FFMPEG_API_KEY}"},
            timeout=30,
        )
        if status_resp.json().get("status") == "completed":
            break
        time.sleep(10)
    else:
        raise RuntimeError("Job не завершился")

    video_data = requests.get(
        status_resp.json()["output_url"], timeout=120
    ).content
    with open(output_path, "wb") as f:
        f.write(video_data)
    print(f"[processor] Обработано: {output_path}")
    return output_path
