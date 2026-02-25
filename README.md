# Metagenerator API - REST API для генерации SEO метатегов

REST API сервис для автоматической генерации H1, Title и Description на основе анализа конкурентов и LLM.

## 🎯 Назначение

**Это API-сервер**, который:
- Принимает на вход данные о URL и поисковых запросах
- Выполняет полный цикл обработки (10 шагов)
- Возвращает готовые метатеги и аналитику

**Не включает:**
- Чтение/запись Google Sheets (делает клиент)
- Scheduling и автоматизацию (делает клиент)

## 🏗️ Архитектура

```
┌─────────────┐                    ┌──────────────────┐
│   Клиент    │ ──── HTTP ────────>│ Metagenerator    │
│  (seotools) │                    │      API         │
│             │                    │                  │
│ - Читает    │                    │ FastAPI:         │
│   Sheets    │                    │ - /process       │
│ - Отправляет│                    │ - /status        │
│   данные    │                    │                  │
│ - Получает  │<──── JSON ─────────│ Celery Worker:   │
│   результат │                    │ - Pipeline (10   │
│ - Обновляет │                    │   шагов)         │
│   Sheets    │                    │ - Async задачи   │
└─────────────┘                    │                  │
                                   │ Redis:           │
                                   │ - Очередь задач  │
                                   │ - Кеш статусов   │
                                   └──────────────────┘
```

## ⚙️ Возможности

- 📈 Частотность запросов через XMLRiver Wordstat API
- 🔍 Поиск конкурентов через XMLRiver Yandex Search API
- 🌐 Парсинг HTML (httpx + Selenium для JavaScript-сайтов)
- 🏷️ Извлечение существующих метатегов
- 🔖 Классификация типов страниц через LLM (опционально)
- 🧠 Лемматизация текстов и извлечение ключевых слов
- 🤖 Генерация метатегов через LLM (Claude/GPT/Grok/DeepSeek)
- ✏️ Проверка и корректировка метатегов (опционально)
- 💰 Автоматический подсчет стоимости обработки
- 💱 Конвертация USD → RUB по курсу ЦБ РФ
- 📝 Подробное логирование всех операций
- 🚀 Асинхронная обработка через Celery + Redis

## 🚀 Быстрый старт API

**Подробная документация:** см. [`api/README.md`](api/README.md)

### 1. Клонирование репозитория
```bash
git clone https://github.com/masta-danila/metagenerator-api.git
cd metagenerator-api
```

### 2. Установка Redis
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
```

### 3. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # Для Linux/Mac
```

### 4. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 5. Настройка окружения

Создайте файл `.env` в корне проекта:
```bash
# API ключи для внешних сервисов
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ARSENKIN_API_KEY=your_arsenkin_key
DEEPSEEK_API_KEY=your_deepseek_key
GROK_API_KEY=your_grok_key

# API ключи для доступа к вашему API (через запятую)
API_KEYS=key1,key2,key3

# Redis настройки (опционально, есть defaults)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Celery настройки (опционально)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 6. Запуск API-сервера

**Вариант 1: Все сервисы одной командой (фоновый режим)**
```bash
./start_all.sh
# Остановка: ./stop_all.sh
```

**Вариант 2: Раздельный запуск (для разработки)**

Терминал 1 - Celery Worker:
```bash
./start_celery.sh
```

Терминал 2 - FastAPI:
```bash
./start_api.sh
# Или вручную:
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен на `http://localhost:8000`

### 7. Документация API

После запуска откройте в браузере:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Файл документации:** `api/README.md`

## Структура проекта

```
seotools/
├── gsheets/                    # Модули работы с Google Sheets
│   ├── sheets_reader.py        # Чтение данных
│   ├── sheets_updater.py       # Обновление метатегов
│   ├── data_updater.py         # Обновление Data листа
│   ├── credentials.json        # (не в git)
│   └── spreadsheets.json       # (не в git)
├── xmlriver/                   # XMLRiver API
│   ├── wordstat_frequency.py   # Частотность запросов
│   ├── wordstat_batch.py       # Батч обработка Wordstat
│   ├── yandex_parser.py        # Поиск конкурентов
│   ├── xmlriver_pricing.json   # Прайсинг XMLRiver
│   └── blacklist_domains.json  # Черный список доменов
├── site_parser/                # Парсинг HTML
│   ├── html_parser.py          # Парсер через httpx
│   ├── batch_html_processor.py # Батч парсинг
│   ├── browser_fetcher.py      # Браузерный парсинг (Selenium)
│   ├── batch_browser_processor.py
│   ├── page_classifier.py      # Классификация страниц
│   ├── batch_page_classifier.py
│   ├── meta_extractor.py       # Извлечение метатегов
│   ├── batch_meta_processor.py
│   ├── parsing_validator.py    # Валидация качества парсинга
│   └── page_types.json         # Типы страниц
├── lemmatizers/                # Лемматизация текстов
│   ├── lemmatizer.py
│   └── lemmatizer_processor.py
├── metagenerators/             # Генерация метатегов через LLM
│   ├── metagenerator.py        # Генератор для одного URL
│   ├── metagenerator_batch.py  # Батч генерация
│   ├── metatag_editor.py       # Редактор метатегов
│   └── metatag_editor_batch.py # Батч редактирование
├── llm/                        # LLM клиенты
│   ├── llm_router.py           # Роутер запросов
│   ├── llm_response_cleaner.py # Очистка JSON ответов
│   ├── claude_request.py       # Anthropic Claude
│   ├── gpt_request.py          # OpenAI GPT
│   ├── grok_request.py         # xAI Grok
│   ├── deepseek_request.py     # DeepSeek
│   └── llm_pricing.json        # Прайсинг LLM
├── utils/                      # Утилиты
│   ├── usd_rate_updater.py     # Курс USD от ЦБ РФ
│   └── usd_rate.json           # Кэш курса (не в git)
├── logs/                       # Логи (не в git)
├── jsontests/                  # Промежуточные данные (не в git)
├── main.py                     # Главный пайплайн (14 шагов)
├── logger_config.py            # Настройка логирования
├── requirements.txt            # Зависимости
├── deploy_server.sh            # Скрипт деплоя
├── setup_systemd_service.sh    # Установка systemd
├── seotools.service            # Systemd unit
├── DEPLOY.md                   # Инструкция по деплою
├── QUICKSTART.md               # Быстрый старт
└── README.md                   # Этот файл
```

## 📖 Использование API

### Основной процесс обработки (через API)

API принимает данные о URL и выполняет pipeline из 10 шагов:

1. Получение частотности запросов (Wordstat)
2. Поиск конкурентов (Yandex Search)
3. Первичный парсинг HTML (httpx)
4. Повторный парсинг через браузер (для сложных сайтов)
5. Извлечение метатегов из HTML
6. Валидация качества парсинга
7. **Классификация страниц** (опционально, LLM)
8. Лемматизация текстов
9. **Генерация метатегов** (через LLM)
10. **Проверка метатегов** (опционально, LLM)

### Пример использования API

```python
import requests

# Подготовка данных
data = {
    "https://example.com/": {
        "queries": [{"query": "купить товар"}],
        "company_name": "Моя Компания",
        "region": 213
    }
}

# Создание задачи
response = requests.post(
    "http://localhost:8000/process",
    headers={"X-API-Key": "your-key"},
    json={
        "data": data,
        "enable_classification": True,
        "enable_metatag_editor": True
    }
)

task_id = response.json()["task_id"]

# Ожидание результата
import time
while True:
    status = requests.get(
        f"http://localhost:8000/status/{task_id}",
        headers={"X-API-Key": "your-key"}
    ).json()
    
    if status["status"] == "completed":
        result = status["result"]["data"]
        print(result["https://example.com/"]["generated_metatags"])
        break
    
    time.sleep(3)
```

### Тестирование API

```bash
# Быстрый smoke test
python api/test_simple.py

# Полный тест с реальными данными
python api/test_api.py

# Пример полного клиента (с Google Sheets)
python api/example_client.py
```

## ⚙️ Конфигурация

### Настройки API (`.env`)

```bash
# API сервер
API_TITLE="Metagenerator API"
API_VERSION="1.0.0"
API_KEYS=key1,key2,key3  # Через запятую

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_TIME_LIMIT=3600  # 1 час на задачу
```

### Параметры pipeline

Параметры обработки задаются внутри модулей pipeline:

- **Классификация** (`enable_classification` в запросе): `claude-haiku-4-5-20251001`
- **Генерация метатегов**: `claude-sonnet-4-5-20250929`
- **Редактор метатегов** (`enable_metatag_editor` в запросе): `claude-haiku-4-5-20251001`
- **Валидация парсинга**: минимум 50% успешных
- **XMLRiver**: до 5 одновременных запросов, до 10 URL на запрос
- **Лемматизация**: 4-6 слов для Title, 6-10 для Description

## 📝 Логирование

### Логи Celery worker

Celery выводит логи в консоль (или перенаправляются в файл):
```bash
# Логи в реальном времени
tail -f celery.log  # если запущено через systemd

# Или смотреть в терминале где запущен Celery
```

### Логи модулей pipeline

Логи модулей сохраняются в папке `logs/`:
- `metagenerator_pipeline.log` - основной pipeline
- `search.log` - XMLRiver API (Wordstat + Yandex Search)
- `html_parser.log` - парсинг HTML
- `browser_fetcher.log` - браузерный парсинг
- `page_classifier.log` - классификация страниц
- `lemmatizer.log` - лемматизация
- `metagenerator.log` - генерация метатегов

```bash
# Просмотр логов
tail -f logs/metagenerator_pipeline.log
tail -f logs/metagenerator.log
```

### Логи FastAPI

FastAPI выводит логи в консоль:
```bash
# Если запущено через systemd
journalctl -u metagenerator-api -f
```

## 🚀 Развертывание на сервере

### Подготовка

1. **Установить зависимости:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv redis-server
   ```

2. **Клонировать репозиторий:**
   ```bash
   cd /home/user
   git clone https://github.com/masta-danila/metagenerator-api.git
   cd metagenerator-api
   ```

3. **Настроить окружение:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Отредактировать .env
   ```

### Запуск через systemd

См. подробную инструкцию в `api/README.md` раздел "Deployment"

Или используйте скрипты:
```bash
./deploy_server.sh         # Автоматическая настройка
./setup_systemd_service.sh # Установка systemd service
```

## Требования

- Python 3.11+
- Redis 5.0+
- Google Chrome (для браузерного парсинга JavaScript сайтов)

### API ключи

**Обязательные:**
- **XMLRiver API** (`ARSENKIN_API_KEY`) - для Wordstat и Yandex Search
- **Минимум один LLM провайдер:**
  - Anthropic Claude (`ANTHROPIC_API_KEY`) - рекомендуется
  - OpenAI GPT (`OPENAI_API_KEY`)
  - xAI Grok (`GROK_API_KEY`)
  - DeepSeek (`DEEPSEEK_API_KEY`)
  - Google Gemini (`GOOGLE_API_KEY`)

## Стоимость API

### XMLRiver
- Wordstat: ~0.09 USD за запрос
- Yandex Search: ~0.18 USD за запрос
- Настройки: `xmlriver/xmlriver_pricing.json`

### LLM (примерно)
- Claude Sonnet 4: ~$0.01-0.05 за URL
- Claude Haiku 4: ~$0.001-0.005 за URL
- GPT-4o: ~$0.01-0.03 за URL
- Grok: ~$0.005-0.015 за URL
- DeepSeek: ~$0.0005-0.002 за URL

**Конвертация USD → RUB:** Автоматически по курсу ЦБ РФ с наценкой (настройка в `utils/usd_rate.json`)

**Итоговая стоимость на 1 URL:** ~15-30 руб (зависит от модели и количества конкурентов)

## Rate Limits

### XMLRiver API
- Зависит от вашего тарифа
- Используйте `max_concurrent` для ограничения одновременных запросов
- Рекомендуется: `max_concurrent=3-5`

### LLM API
- **Claude**: 50-100 RPM (requests per minute)
- **GPT-4**: 500-5000 TPM (tokens per minute)
- **Grok**: см. документацию xAI
- **DeepSeek**: см. документацию DeepSeek
- Используйте `max_concurrent` для контроля нагрузки

## 🔌 Интеграция с Google Sheets

Этот репозиторий содержит **только API-сервер**.

Для работы с Google Sheets (чтение/запись) используйте отдельный **клиент**:
- Клиент читает данные из Google Sheets
- Отправляет POST-запрос к этому API
- Получает обработанные метатеги
- Записывает результаты обратно в Google Sheets

**Пример клиента:** см. `api/example_client.py`

Отдельный репозиторий клиента будет создан позже.

## 📄 Лицензия

MIT

## 👤 Автор

Danila Dzhaev
