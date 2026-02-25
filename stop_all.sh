#!/bin/bash
# Скрипт для остановки FastAPI и Celery worker

set -e

echo "⏹️  Остановка Metagenerator API..."

# Остановить по PID файлам
if [ -f /tmp/metagenerator-api/celery.pid ]; then
    CELERY_PID=$(cat /tmp/metagenerator-api/celery.pid)
    if kill -0 $CELERY_PID 2>/dev/null; then
        kill $CELERY_PID
        echo "✅ Celery worker остановлен (PID: $CELERY_PID)"
    fi
    rm /tmp/metagenerator-api/celery.pid
fi

if [ -f /tmp/metagenerator-api/fastapi.pid ]; then
    FASTAPI_PID=$(cat /tmp/metagenerator-api/fastapi.pid)
    if kill -0 $FASTAPI_PID 2>/dev/null; then
        kill $FASTAPI_PID
        echo "✅ FastAPI остановлен (PID: $FASTAPI_PID)"
    fi
    rm /tmp/metagenerator-api/fastapi.pid
fi

if [ -f /tmp/metagenerator-api/flower.pid ]; then
    FLOWER_PID=$(cat /tmp/metagenerator-api/flower.pid)
    if kill -0 $FLOWER_PID 2>/dev/null; then
        kill $FLOWER_PID
        echo "✅ Flower остановлен (PID: $FLOWER_PID)"
    fi
    rm /tmp/metagenerator-api/flower.pid
fi

if [ -f /tmp/metagenerator-api/xvfb.pid ]; then
    XVFB_PID=$(cat /tmp/metagenerator-api/xvfb.pid)
    if kill -0 $XVFB_PID 2>/dev/null; then
        kill $XVFB_PID
        echo "✅ Xvfb остановлен (PID: $XVFB_PID)"
    fi
    rm /tmp/metagenerator-api/xvfb.pid
fi

# Дополнительно убить по имени процесса (на всякий случай)
pkill -f "celery.*worker" 2>/dev/null || true
pkill -f "uvicorn.*api.app" 2>/dev/null || true
pkill -f "celery.*flower" 2>/dev/null || true
pkill -f "Xvfb" 2>/dev/null || true

echo "✅ Все сервисы остановлены"
