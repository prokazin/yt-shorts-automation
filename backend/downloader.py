"""
Скачивание public domain видео с Internet Archive.
"""
import os
import tempfile
from internetarchive import search_items, download


def search_and_download(query="atmospheric nature", max_items=1):
    search = search_items(f'{query} AND mediatype:movies')
    for result in search:
        identifier = result["identifier"]
        try:
            tmp_dir = tempfile.mkdtemp(prefix="yt_shorts_")
            download(identifier, destdir=tmp_dir, glob_pattern="*.mp4")
            for f in os.listdir(tmp_dir):
                if f.endswith(".mp4"):
                    path = os.path.join(tmp_dir, f)
                    print(f"[downloader] Скачано: {path}")
                    return path
        except Exception as e:
            print(f"[downloader] Ошибка {identifier}: {e}")
            continue
    raise RuntimeError("Не удалось скачать видео")
