#!/bin/bash
# Скрипт для запуска пайплайна. Вызывается через cron.

cd ~/yt-shorts-automation/backend

# Загружаем переменные окружения
export TELEGRAM_BOT_TOKEN="ВАШ_ТОКЕН"
export TELEGRAM_CHAT_ID="ВАШ_CHAT_ID"
export IG_USERNAME="ВАШ_IG_ЛОГИН"
export IG_PASSWORD="ВАШ_IG_ПАРОЛЬ"

# Запускаем пайплайн (индекс конфигурации: 0, 1 или 2)
python3 main.py pipeline $1
