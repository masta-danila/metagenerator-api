#!/bin/bash

# Скрипт для запуска API сервера
# Запускает FastAPI через uvicorn

echo "Запуск Metagenerator API..."
echo "Документация будет доступна на: http://localhost:8000/docs"
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

# Запускаем API
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
