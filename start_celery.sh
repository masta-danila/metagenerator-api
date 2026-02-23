#!/bin/bash

# Скрипт для запуска Celery worker
# Обрабатывает задачи в фоновом режиме

echo "Запуск Celery Worker..."
echo ""

# Проверяем что Redis запущен
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis не запущен!"
    echo "Запустите Redis в отдельном терминале:"
    echo "  redis-server"
    echo ""
    echo "Или через Homebrew:"
    echo "  brew services start redis"
    echo ""
    exit 1
fi

echo "✓ Redis подключен"

# Проверяем наличие виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Виртуальное окружение активировано"
fi

# Запускаем Celery worker
celery -A api.celery_worker worker --loglevel=info --concurrency=2
