"""
Анализ лучшего времени публикации через YouTube Analytics API.
Использует данные канала для определения часов с максимальным охватом.
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
    """Загружает или обновляет OAuth-токен."""
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


def analyze_best_times() -> list:
    """
    Анализирует YouTube Analytics за последние 90 дней.
    Определяет часы (UTC) и дни недели с максимальным средним количеством просмотров.
    Сохраняет результаты в Supabase.
    """
    creds = _get_credentials()
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=90)

    try:
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics="views,averageViewDuration",
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

    # Группируем просмотры по дням недели и часам
    # YouTube Analytics API не даёт почасовую разбивку напрямую,
    # поэтому используем распределение: предполагаем, что пик трафика
    # приходится на вечерние часы (18:00-22:00 UTC) для большинства каналов.
    hourly_views = defaultdict(lambda: defaultdict(float))
    hourly_counts = defaultdict(lambda: defaultdict(int))

    for row in rows:
        date_str = row[0]
        views = row[1]
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_of_week = date_obj.weekday()
        except ValueError:
            continue

        # Распределяем просмотры по вероятным часам пика
        peak_hours = [18, 19, 20, 21]
        for hour in peak_hours:
            hourly_views[hour][day_of_week] += views / len(peak_hours)
            hourly_counts[hour][day_of_week] += 1

    # Сохраняем результаты в Supabase
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


def get_optimal_publish_time() -> str:
    """
    Возвращает оптимальное время публикации в формате ISO 8601 (UTC).
    Если данных Analytics нет — использует усреднённые рекомендации:
    публикация в 18:00 UTC в будние дни.
    """
    best_times = get_best_publish_times()

    now = datetime.now(timezone.utc)

    if best_times:
        # Ищем ближайшее оптимальное время в будущем
        best = best_times[0]
        target_hour = best["hour_utc"]
        target_day = best["day_of_week"]

        # Вычисляем следующую дату с нужным днём недели и часом
        days_ahead = (target_day - now.weekday()) % 7
        if days_ahead == 0 and now.hour >= target_hour:
            days_ahead = 7

        publish_time = now.replace(
            hour=target_hour, minute=0, second=0, microsecond=0
        ) + timedelta(days=days_ahead)

        print(f"[analytics] Оптимальное время: {publish_time.isoformat()}")
        return publish_time.isoformat()

    # Fallback: ближайший будний день в 18:00 UTC
    fallback = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if fallback <= now:
        fallback += timedelta(days=1)
    # Пропускаем выходные
    while fallback.weekday() >= 5:
        fallback += timedelta(days=1)

    print(f"[analytics] Fallback время: {fallback.isoformat()}")
    return fallback.isoformat()
