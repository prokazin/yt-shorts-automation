"""
Анализ лучшего времени публикации через YouTube Analytics API.
"""
import os
import pickle
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from storage import save_best_publish_time, get_best_publish_times

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.pickle")
SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")


def _get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return creds


def analyze_best_times():
    creds = _get_credentials()
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=90)

    try:
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics="views",
            dimensions="day",
            sort="day",
        ).execute()
    except Exception as e:
        print(f"[analytics] Ошибка запроса: {e}")
        return []

    rows = response.get("rows", [])
    if not rows:
        print("[analytics] Нет данных для анализа")
        return []

    hourly_views = defaultdict(lambda: defaultdict(float))
    hourly_counts = defaultdict(lambda: defaultdict(int))

    for row in rows:
        date_str, views = row[0], row[1]
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_of_week = date_obj.weekday()
        except ValueError:
            continue

        peak_hours = [18, 19, 20, 21]
        for hour in peak_hours:
            hourly_views[hour][day_of_week] += views / len(peak_hours)
            hourly_counts[hour][day_of_week] += 1

    results = []
    for hour, days in hourly_views.items():
        for day, total_views in days.items():
            count = hourly_counts[hour][day]
            avg = total_views / count if count > 0 else 0
            save_best_publish_time(hour, day, avg, count)
            results.append({
                "hour_utc": hour,
                "day_of_week": day,
                "avg_views": avg,
                "sample_count": count,
            })

    results.sort(key=lambda x: x["avg_views"], reverse=True)
    print(f"[analytics] Проанализировано {len(results)} комбинаций")
    return results


def get_optimal_publish_time():
    best_times = get_best_publish_times()
    now = datetime.now(timezone.utc)

    if best_times:
        best = best_times[0]
        target_hour = best["hour_utc"]
        target_day = best["day_of_week"]

        days_ahead = (target_day - now.weekday()) % 7
        if days_ahead == 0 and now.hour >= target_hour:
            days_ahead = 7

        publish_time = now.replace(
            hour=target_hour, minute=0, second=0, microsecond=0
        ) + timedelta(days=days_ahead)

        print(f"[analytics] Оптимальное время: {publish_time.isoformat()}")
        return publish_time.isoformat()

    fallback = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if fallback <= now:
        fallback += timedelta(days=1)
    while fallback.weekday() >= 5:
        fallback += timedelta(days=1)

    print(f"[analytics] Fallback время: {fallback.isoformat()}")
    return fallback.isoformat()
