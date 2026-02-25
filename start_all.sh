#!/bin/bash
# Скрипт для одновременного запуска FastAPI и Celery worker

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Запуск Metagenerator API..."
echo "Проект: $PROJECT_DIR"

# Активировать виртуальное окружение
source venv/bin/activate

# Проверить Redis
echo "📡 Проверка Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis не запущен! Запустите: brew services start redis (macOS) или sudo systemctl start redis (Linux)"
    exit 1
fi
echo "✅ Redis работает"

# Создать директории для PID и логов
mkdir -p /tmp/metagenerator-api
mkdir -p logs

# Запустить Celery worker в фоне
echo "🔄 Запуск Celery worker..."
nohup celery -A api.celery_worker worker \
    --loglevel=info \
    --concurrency=2 \
    --pool=solo \
    --without-heartbeat \
    --pidfile=/tmp/metagenerator-api/celery.pid \
    > logs/celery.log 2>&1 &

CELERY_PID=$!
echo "✅ Celery worker запущен (PID: $CELERY_PID)"

# Небольшая задержка для инициализации Celery
sleep 2

# Запустить FastAPI в фоне
echo "🌐 Запуск FastAPI..."
nohup uvicorn api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    > logs/fastapi.log 2>&1 &

FASTAPI_PID=$!
echo "✅ FastAPI запущен (PID: $FASTAPI_PID)"

# Запустить Flower (мониторинг Celery) в фоне
echo "🌸 Запуск Flower (мониторинг)..."
nohup celery -A api.celery_worker flower \
    --port=5555 \
    --url_prefix=flower \
    > logs/flower.log 2>&1 &

FLOWER_PID=$!
echo "✅ Flower запущен (PID: $FLOWER_PID)"

# Сохранить PID'ы
echo $CELERY_PID > /tmp/metagenerator-api/celery.pid
echo $FASTAPI_PID > /tmp/metagenerator-api/fastapi.pid
echo $FLOWER_PID > /tmp/metagenerator-api/flower.pid

echo ""
echo "✅ Все сервисы запущены!"
echo "   Celery PID: $CELERY_PID"
echo "   FastAPI PID: $FASTAPI_PID"
echo "   Flower PID: $FLOWER_PID"
echo ""
echo "📖 API документация: http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/health"
echo "🌸 Flower мониторинг: http://localhost:5555"
echo ""
echo "📝 Логи:"
echo "   Celery: tail -f logs/celery.log"
echo "   FastAPI: tail -f logs/fastapi.log"
echo "   Flower: tail -f logs/flower.log"
echo ""
echo "⏹️  Остановка: ./stop_all.sh"
