#!/bin/bash

# Скрипт для автоматического развертывания проекта на сервере
# Использование: ./deploy_server.sh

set -e  # Останавливаем выполнение при любой ошибке

echo "Начинаю развертывание проекта SEO Tools..."

# Проверяем что мы в правильной директории
if [ ! -f "requirements.txt" ]; then
    echo "Ошибка: файл requirements.txt не найден. Убедитесь что вы в корневой директории проекта."
    exit 1
fi

# 1. Активируем виртуальное окружение
echo "Активирую виртуальное окружение..."
if [ ! -d "venv" ]; then
    echo "Создаю виртуальное окружение..."
    python3 -m venv venv
fi
source venv/bin/activate

# 2. Устанавливаем зависимости
echo "Устанавливаю зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "ОШИБКА: Файл .env не найден!"
    echo "Создайте файл .env (см. .env.example). Нужны: API_KEYS, Redis; для pipeline: XMLRIVER_USER_ID, XMLRIVER_API_KEY, минимум один LLM ключ (ANTHROPIC_API_KEY, OPENAI_API_KEY и др.)"
    exit 1
else
    echo "Файл .env найден"
fi

# 4. Google Sheets (опционально, нужны только для клиента; API не использует)
if [ -f "gsheets/credentials.json" ]; then
    echo "Google Sheets credentials найдены (опционально)"
else
    echo "Google Sheets credentials не найдены (нужны только для клиента, не для API)"
fi

# 5. Проверяем конфигурационные файлы
if [ ! -f "xmlriver/blacklist_domains.json" ]; then
    echo "Создаю blacklist_domains.json..."
    echo "[]" > xmlriver/blacklist_domains.json
fi

if [ ! -f "xmlriver/xmlriver_pricing.json" ]; then
    echo "ОШИБКА: Файл xmlriver/xmlriver_pricing.json не найден!"
    echo "Этот файл должен быть в репозитории"
    exit 1
fi

if [ ! -f "site_parser/page_types.json" ]; then
    echo "ОШИБКА: Файл site_parser/page_types.json не найден!"
    echo "Этот файл должен быть в репозитории"
    exit 1
fi

if [ ! -f "llm/llm_pricing.json" ]; then
    echo "ОШИБКА: Файл llm/llm_pricing.json не найден!"
    echo "Этот файл должен быть в репозитории"
    exit 1
fi

if [ ! -f "config/usd_rate.json" ]; then
    echo "Создаю config/usd_rate.json с начальными данными..."
    mkdir -p config
    echo '{
  "usd_rate": 91.5,
  "last_updated": "",
  "markup_percentage": 7.5,
  "update_interval_hours": 24
}' > config/usd_rate.json
fi

# 6. Создаем необходимые директории
echo "Создаю директории для логов и тестовых данных..."
mkdir -p logs
mkdir -p jsontests

echo ""
echo "Развертывание завершено успешно!"
echo ""
echo "Запуск API:"
echo "   ./start_all.sh                             # FastAPI + Celery (нужен Redis)"
echo "   ./stop_all.sh                              # Остановка"
echo ""
echo "Управление systemd (если настроен):"
echo "   sudo systemctl status metagenerator-api    # Статус"
echo "   sudo systemctl restart metagenerator-api   # Перезапуск"
echo "   sudo journalctl -u metagenerator-api -f    # Логи"
echo ""
echo "Мониторинг:"
echo "   tail -f logs/celery.log logs/fastapi.log   # Логи API"
echo "   curl http://localhost:8000/health         # Health check"
echo ""
echo "Развертывание завершено!"
echo ""
