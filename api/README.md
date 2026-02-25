# Metagenerator API

REST API для обработки данных через metagenerator_pipeline.

## Что делает API

API выполняет **только обработку данных** (10 шагов pipeline):
- Получение частотности запросов (Wordstat)
- Получение конкурентов (Yandex Search)
- Парсинг HTML (httpx + browser)
- Извлечение метатегов
- Классификация страниц (опционально)
- Лемматизация текстов
- Генерация метатегов (LLM)
- Редактирование метатегов (опционально)

**Что НЕ делает API:**
- ❌ Не читает Google Sheets (данные передаются в запросе)
- ❌ Не обновляет Google Sheets (клиент делает это с результатом)

## Архитектура

- **FastAPI** - веб-фреймворк для API
- **Celery** - фоновая обработка задач (асинхронно)
- **Redis** - брокер сообщений и хранилище результатов
- **metagenerator_pipeline** - ядро обработки данных (10 шагов)

## Установка

### 1. Установить Redis (Mac)

```bash
brew install redis
brew services start redis

# Проверить что работает
redis-cli ping  # Должен ответить PONG
```

### 2. Установить Python зависимости

```bash
pip install -r requirements.txt
```

### 3. Настроить переменные окружения

```bash
cp .env.example .env
# Отредактируйте .env и укажите свои API ключи
```

## Запуск

Нужно запустить **3 процесса** в отдельных терминалах:

### Терминал 1: Redis

```bash
redis-server
```

### Терминал 2: Celery Worker

```bash
celery -A api.celery_worker worker --loglevel=info
```

### Терминал 3: FastAPI сервер

```bash
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

## Использование API

### Проверка статуса сервиса

```bash
curl http://localhost:8000/health
```

### 1. Подготовка данных (на клиенте)

Клиент подготавливает данные (может прочитать из Google Sheets и преобразовать):

```python
# Пример подготовки данных (структура упрощена - только URL и их данные)
data = {
  "https://example.com/": {
    "queries": [{"query": "купить товар"}],
    "company_name": "Моя Компания",
    "region": 213,  # ID региона Яндекса
    "variables_h1": ["вариант 1"],
    "variables_title": [],
    "variables_description": []
  },
  "https://example.com/products/": {
    "queries": [{"query": "каталог товаров"}],
    "company_name": "Моя Компания",
    "region": 213,
    "variables_h1": [],
    "variables_title": [],
    "variables_description": []
  }
}
```

### 2. Создание задачи через API

**Важно:** API принимает на вход готовый словарь с данными

```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "data": {
      "https://example.com/page/": {
        "queries": [{"query": "текст запроса"}],
        "company_name": "Компания",
        "region": 213,
        "variables_h1": [],
        "variables_title": [],
        "variables_description": []
      },
      "https://example.com/about/": {
        "queries": [{"query": "о компании"}],
        "company_name": "Компания",
        "region": 213,
        "variables_h1": [],
        "variables_title": [],
        "variables_description": []
      }
    },
    "enable_classification": false,
    "enable_metatag_editor": false
  }'
```

Ответ:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2026-02-23T15:30:00",
  "message": "Задача создана для обработки 2 URL",
  "urls_count": 2
}
```

Через Python (полный пример):
```python
import requests

# 1. Подготовить данные
data = {
    "https://example.com/page1/": {
        "queries": [{"query": "ключевой запрос"}],
        "company_name": "Моя Компания",
        "region": 213,
        "variables_h1": [],
        "variables_title": [],
        "variables_description": []
    }
}

# 2. Отправить в API
response = requests.post(
    "http://localhost:8000/process",
    headers={"X-API-Key": "your-api-key"},
    json={
        "data": data,
        "enable_classification": False,
        "enable_metatag_editor": False
    }
)

task_info = response.json()
task_id = task_info["task_id"]
print(f"Задача создана: {task_id}")
```

### 3. Проверка статуса задачи

```bash
curl http://localhost:8000/status/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: test-api-key-123"
```

Ответ (в процессе):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": "PIPELINE: ШАГ 5/10: Валидация качества парсинга",
  "started_at": "2026-02-23T15:30:15"
}
```

Ответ (завершено):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "status": "completed",
    "data": {
      "https://example.com/": {
        "generated_metatags": {
          "h1": "Заголовок H1",
          "title": "Title страницы",
          "description": "Описание страницы"
        },
        "classification": {
          "page_type": "commercial",
          "confidence": 0.95
        },
        "wordstat_cost": {
          "total_rub": 0.05,
          "api_requests": 2
        },
        "yandex_search_cost": {
          "total_rub": 0.10,
          "queries": 2
        },
        "metageneration_cost": {
          "total_rub": 0.30,
          "tokens": 1500
        }
      }
    },
    "completed_at": "2026-02-23T15:45:00",
    "urls_processed": 1
  },
  "completed_at": "2026-02-23T15:45:00"
}
```

### 4. Обновление Google Sheets с результатом

После получения результата клиент обновляет Google Sheets:

```python
import requests
import time
from gsheets.data_updater import update_all_data_sheets
from gsheets.sheets_updater import update_all_spreadsheets

# Ждем завершения задачи
while True:
    status_response = requests.get(
        f"http://localhost:8000/status/{task_id}",
        headers={"X-API-Key": "your-api-key"}
    )
    status_data = status_response.json()
    
    if status_data["status"] == "completed":
        result_data = status_data["result"]["data"]
        break
    elif status_data["status"] == "failed":
        raise Exception(status_data.get("error", "Task failed"))
    
    print(f"Статус: {status_data.get('progress', 'processing')}")
    time.sleep(5)

# Обновляем Google Sheets с результатами
print("Обновляю Data лист...")
update_all_data_sheets(frequency_data=result_data)

print("Обновляю Meta лист...")
update_all_spreadsheets(data=result_data, sheet_name="Meta")

print("✅ Данные успешно обновлены в Google Sheets!")
```

**Полный пример:** см. `api/example_client.py`

```bash
# Запустить пример клиента
python api/example_client.py
```

### Отмена задачи

```bash
curl -X DELETE http://localhost:8000/cancel/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: test-api-key-123"
```

## Документация API

После запуска доступна по адресам:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/` | Информация о сервисе |
| GET | `/health` | Health check |
| POST | `/process` | Обработать данные через pipeline |
| GET | `/status/{task_id}` | Статус задачи |
| DELETE | `/cancel/{task_id}` | Отменить задачу |

## Мониторинг

### Celery Flower (опционально)

Веб-интерфейс для мониторинга Celery:

```bash
pip install flower
celery -A api.celery_worker flower
```

Откроется на http://localhost:5555

### Redis CLI

Посмотреть очередь задач:

```bash
redis-cli
> KEYS celery*
> GET celery-task-meta-<task_id>
```

## Production

Для production рекомендуется:

1. **Использовать systemd** для автозапуска Celery worker
2. **Nginx** как reverse proxy для FastAPI
3. **Supervisor** или **systemd** для управления процессами
4. **Redis с персистентностью** (RDB или AOF)
5. **Несколько Celery workers** для масштабирования

## Безопасность

- API ключи хранятся в переменных окружения (`.env`)
- Используйте HTTPS в production
- Ограничьте CORS (`allow_origins`) конкретными доменами
- Используйте сильные, уникальные API ключи
- Рассмотрите rate limiting (например, через slowapi)

## Troubleshooting

### Redis не подключается

```bash
redis-cli ping
# Если ошибка - проверьте запущен ли Redis:
brew services list
brew services start redis
```

### Celery worker не видит задачи

Проверьте что используется одинаковый Redis URL в `.env` и при запуске worker.

### Задачи падают с ошибкой

Смотрите логи Celery worker - там полный traceback ошибки.
