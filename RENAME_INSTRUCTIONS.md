# Инструкции по переименованию в metagenerator-api

## 🎯 Цель

Переименовать этот проект в `metagenerator-api` и сделать его чистым REST API сервером (без Google Sheets интеграции).

## ✅ Что уже подготовлено

- [x] Основной README обновлен под API-сервер
- [x] API документация в `api/README.md`
- [x] Структура проекта очищена от упоминаний Google Sheets в документации
- [x] Тестовые скрипты API готовы (`test_api.py`, `test_simple.py`)
- [x] Пример клиента создан (`example_client.py`)

## 📝 Шаги для переименования (на локальной машине)

### 1. Создать копию для клиента
```bash
cd /Users/daniladzhiev/PycharmProjects
cp -r seotools seotools-client-backup
```

### 2. Переименовать текущую папку
```bash
mv seotools metagenerator-api
cd metagenerator-api
```

### 3. Пересоздать виртуальное окружение
```bash
# Удалить старое
rm -rf venv

# Создать новое
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Перезапустить сервисы
```bash
# Остановить старые процессы
pkill -f "celery.*worker"
pkill -f "uvicorn"

# Запустить заново
./start_celery.sh  # В терминале 1
./start_api.sh     # В терминале 2
```

### 5. Проверить работу
```bash
python api/test_simple.py
python api/test_api.py
```

## 🚀 Шаги для сервера

### 1. Обновить на сервере
```bash
ssh user@server
cd /home/callchecker
git clone <repo-url> metagenerator-api
cd metagenerator-api

# Настроить
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактировать .env
```

### 2. Обновить systemd service
Отредактировать `seotools.service` (или создать новый `metagenerator-api.service`):
- Изменить `WorkingDirectory=/home/callchecker/metagenerator-api`
- Изменить пути в `Environment` и `ExecStart`

### 3. Перезапустить службы
```bash
sudo systemctl daemon-reload
sudo systemctl restart metagenerator-api
sudo systemctl status metagenerator-api
```

## 🗂️ Создание клиента (seotools)

Восстановить копию и упростить:

```bash
cd /Users/daniladzhiev/PycharmProjects
mv seotools-client-backup seotools
cd seotools
```

### Что удалить из клиента:
- `api/celery_worker.py`, `api/celery_config.py` (они в API-сервере)
- `metagenerator_pipeline.py` (вызывается через API)
- Все batch-процессоры (они в API)

### Что оставить в клиенте:
- `gsheets/` - чтение/запись Google Sheets
- `main.py` - обновить для работы через API
- `api_client.py` - создать клиент для API

### Что изменить в `main.py`:
Заменить локальный вызов pipeline на API-запрос:

```python
# Было:
result = await run_metagenerator_pipeline(all_data)

# Станет:
import requests
response = requests.post(
    "http://server-ip:8000/process",
    headers={"X-API-Key": "..."},
    json={"data": all_data, ...}
)
# Ждать и получить результат
```

## ⚠️ Важно

После переименования обязательно:
1. Обновить удаленный репозиторий (если есть)
2. Обновить ссылки в документации
3. Сообщить команде о новом названии
