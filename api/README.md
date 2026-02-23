# Metagenerator API

REST API для автоматической генерации SEO метатегов с использованием LLM.

## Архитектура

- **FastAPI** - веб-фреймворк для API
- **Celery** - фоновая обработка задач
- **Redis** - брокер сообщений и хранилище результатов
- **metagenerator_pipeline** - ядро обработки данных

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

### Создание задачи

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-api-key-123" \
  -d '{
    "spreadsheet_ids": ["1Vshm7t0QemnBYtD67i9nZLb_B1l47C6v7fAxGYMZ9mQ"],
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
  "message": "Задача создана для обработки 1 таблиц"
}
```

### Проверка статуса задачи

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
    "spreadsheet_ids": ["1Vshm7t0Q..."],
    "data_update": {...},
    "meta_update": {...},
    "completed_at": "2026-02-23T15:45:00"
  },
  "completed_at": "2026-02-23T15:45:00"
}
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
| POST | `/generate` | Создать задачу |
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
