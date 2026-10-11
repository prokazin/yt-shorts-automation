"""
Подбор royalty-free музыки через Tunetank MCP + наложение через FFmpeg.
"""
import os
import subprocess
import requests

TUNETANK_MCP_URL = "https://mcp.tunetank.com"


def search_music(duration=55, mood="calm"):
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "search_music",
            "arguments": {
                "mood": mood,
                "duration": duration,
                "tolerance": 10,
                "limit": 1,
            },
        },
        "id": 1,
    }
    response = requests.post(TUNETANK_MCP_URL, json=payload, timeout=30)
    response.raise_for_status()
    tracks = response.json().get("result", {}).get("content", [])
    if not tracks:
        raise RuntimeError("Tunetank не вернул треков")
    preview_url = tracks[0].get("preview_url")
    print(f"[music] Найден трек: {preview_url}")
    return preview_url


def download_music(preview_url, output_path):
    data = requests.get(preview_url, timeout=60).content
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def mix_audio_with_video(video_path, music_path, output_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[music] Музыка наложена: {output_path}")
    return output_path
