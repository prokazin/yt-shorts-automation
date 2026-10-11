"""
Локальная обработка видео через FFmpeg.
"""
import os
import subprocess


def process_video(input_path, output_path, duration=55):
    """
    Обрезает видео до вертикального формата 9:16 и заданной длительности.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-t", str(duration),
        "-vf", "crop=ih*9/16:ih,scale=1080:1920",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"[processor] Обработано: {output_path}")
    return output_path
