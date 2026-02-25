# Инструкция по деплою на сервер

## Выкладка Metagenerator API (FastAPI + Celery + Redis)

### Чеклист перед выкладкой

- [ ] **Сервер**: Ubuntu/Debian, Python 3.11+, Redis, Chrome (для браузерного парсинга)
- [ ] **Системные зависимости**: `./install_server_deps.sh` (устанавливает Python, Redis, Xvfb, Chrome)
- [ ] **Проект**: клонирован, `python3 -m venv venv`, `pip install -r requirements.txt`
- [ ] **Файл .env**: скопирован из `.env.example`, заданы `API_KEYS`, при необходимости Redis (host/port). Для pipeline: `XMLRIVER_USER_ID`, `XMLRIVER_API_KEY`, минимум один LLM-ключ (ANTHROPIC_API_KEY, OPENAI_API_KEY и т.д.)
- [ ] **config/usd_rate.json**: создаётся скриптом `deploy_server.sh` при отсутствии; иначе создать вручную (см. пример в deploy_server.sh)
- [ ] **Redis**: запущен (`systemctl start redis-server` или `brew services start redis`)
- [ ] **Проверка**: `./start_all.sh`, затем `curl http://localhost:8000/health` — в ответе `redis_connected: true`, `celery_workers > 0`
- [ ] **Systemd** (опционально): отредактировать `metagenerator-api.service` (User, WorkingDirectory, PATH), затем `./setup_systemd_service.sh`

### Быстрый деплой API

```bash
./install_server_deps.sh
cd /path/to/metagenerator-api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # и отредактировать .env
./deploy_server.sh     # проверки и создание config/usd_rate.json при необходимости
./start_all.sh
curl http://localhost:8000/health
```

Остановка: `./stop_all.sh`. Документация API: http://localhost:8000/docs

---

## Парсер (SEO Tools Parser, Xvfb + Chrome)

## Системные требования

- **ОС**: Ubuntu 20.04+, Debian 11+, CentOS 7+, RHEL 7+
- **Python**: 3.8+
- **RAM**: минимум 4GB (рекомендуется 8GB+)
- **Дисковое пространство**: минимум 10GB
- **Chrome/Chromium**: будет установлен автоматически

## Быстрый старт

### 1. Установка системных зависимостей

Скрипт автоматически установит все необходимые пакеты (Xvfb, Chrome, шрифты и т.д.):

```bash
chmod +x install_server_deps.sh
./install_server_deps.sh
```

### 2. Настройка проекта

```bash
# Клонируйте репозиторий
cd /opt  # или любая другая директория
git clone <repository-url> seotools
cd seotools

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите Python зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настройка конфигурации

Создайте файл `.env` с необходимыми переменными окружения:

```bash
cp .env.example .env  # если есть пример
nano .env
```

Добавьте в файл прокси (если используются):

```bash
nano proxy.txt
```

Формат прокси (каждая строка):
```
IP:PORT
IP:PORT:USERNAME:PASSWORD
```

### 4. Тестовый запуск

Сделайте скрипт исполняемым и запустите:

```bash
chmod +x start_with_xvfb.sh
./start_with_xvfb.sh
```

Скрипт автоматически:
- Найдет свободный виртуальный дисплей (избегая конфликтов)
- Запустит Xvfb на этом дисплее
- Запустит парсер
- Корректно остановит Xvfb при завершении

## Автоматический запуск через systemd

### 1. Настройка systemd service

Отредактируйте файл `seotools.service`:

```bash
nano seotools.service
```

Замените в файле:
- `YOUR_USERNAME` → ваше имя пользователя (например, `ubuntu`, `centos`, `root`)
- `/path/to/seotools` → полный путь к проекту (например, `/opt/seotools`)

Пример готового файла:
```ini
[Unit]
Description=SEO Tools Parser with Xvfb
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/seotools
Environment="PATH=/opt/seotools/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/bin/bash /opt/seotools/start_with_xvfb.sh

Restart=on-failure
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=seotools

TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### 2. Установка service

```bash
# Скопируйте файл в systemd
sudo cp seotools.service /etc/systemd/system/

# Перезагрузите systemd
sudo systemctl daemon-reload

# Включите автозапуск при загрузке системы
sudo systemctl enable seotools

# Запустите сервис
sudo systemctl start seotools

# Проверьте статус
sudo systemctl status seotools
```

### 3. Управление сервисом

```bash
# Запуск
sudo systemctl start seotools

# Остановка
sudo systemctl stop seotools

# Перезапуск
sudo systemctl restart seotools

# Статус
sudo systemctl status seotools

# Логи (последние 100 строк)
sudo journalctl -u seotools -n 100

# Логи в реальном времени
sudo journalctl -u seotools -f

# Все логи за сегодня
sudo journalctl -u seotools --since today
```

## Ручной запуск (без systemd)

### Запуск в фоне с nohup

```bash
cd /opt/seotools
nohup ./start_with_xvfb.sh > logs/parser.log 2>&1 &

# Просмотр логов
tail -f logs/parser.log
```

### Запуск в screen/tmux

```bash
# Создать screen сессию
screen -S seotools
cd /opt/seotools
./start_with_xvfb.sh

# Отсоединиться: Ctrl+A, затем D
# Присоединиться обратно: screen -r seotools
```

## Множественные экземпляры

Скрипт `start_with_xvfb.sh` автоматически находит свободный дисплей, поэтому можно запускать несколько экземпляров одновременно:

```bash
# Экземпляр 1 (использует :99)
./start_with_xvfb.sh &

# Экземпляр 2 (автоматически использует :100)
./start_with_xvfb.sh &

# Экземпляр 3 (автоматически использует :101)
./start_with_xvfb.sh &
```

Каждый экземпляр будет использовать свой уникальный виртуальный дисплей.

## Мониторинг

### Проверка виртуальных дисплеев

```bash
# Список активных Xvfb процессов
ps aux | grep Xvfb

# Список занятых дисплеев
ls -la /tmp/.X*-lock
```

### Проверка Chrome процессов

```bash
# Все Chrome процессы
ps aux | grep chrome

# Количество Chrome процессов
ps aux | grep chrome | wc -l
```

### Использование ресурсов

```bash
# RAM и CPU
top -u ubuntu  # замените на вашего пользователя

# Дисковое пространство
df -h

# Размер логов
du -sh /var/log/journal/
journalctl --disk-usage
```

## Решение проблем

### Ошибка: "Xvfb не установлен"

```bash
# Ubuntu/Debian
sudo apt-get install xvfb

# CentOS/RHEL
sudo yum install xorg-x11-server-Xvfb
```

### Ошибка: "Chrome не найден"

```bash
# Переустановите Chrome
./install_server_deps.sh
```

### Ошибка: "Не найден свободный дисплей"

```bash
# Очистите зависшие lock файлы
sudo rm -f /tmp/.X*-lock

# Или перезагрузите сервер
sudo reboot
```

### Браузер детектируется как бот

Используйте режим `visible=True` (уже настроен по умолчанию). Скрипт `start_with_xvfb.sh` предоставляет виртуальный дисплей для видимого браузера.

### Медленная работа

1. Увеличьте количество прокси
2. Проверьте скорость прокси
3. Увеличьте `max_concurrent` в `main.py`
4. Добавьте больше RAM серверу

### Проверка логов парсера

```bash
# Если запущен через systemd
sudo journalctl -u seotools -f

# Если запущен вручную
tail -f logs/parser.log  # или где вы сохраняете логи
```

## Безопасность

### Firewall (опционально)

Если парсер использует только исходящие подключения, входящий firewall не требуется.

### Обновление зависимостей

```bash
cd /opt/seotools
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Регулярное обслуживание

```bash
# Очистка старых логов (оставить последние 7 дней)
sudo journalctl --vacuum-time=7d

# Очистка кэша undetected-chromedriver
rm -rf ~/.local/share/undetected_chromedriver
rm -rf ~/Library/Application\ Support/undetected_chromedriver  # macOS
```

## Производительность

### Рекомендуемые настройки для разных серверов

**Малый сервер (2 CPU, 4GB RAM)**:
- `max_concurrent` (браузер): 2-3
- `max_concurrent` (httpx): 50

**Средний сервер (4 CPU, 8GB RAM)**:
- `max_concurrent` (браузер): 5
- `max_concurrent` (httpx): 100

**Большой сервер (8+ CPU, 16GB+ RAM)**:
- `max_concurrent` (браузер): 10
- `max_concurrent` (httpx): 200+

Настройки находятся в `main.py`.

## Контакты и поддержка

При возникновении проблем проверьте:
1. Логи systemd: `sudo journalctl -u seotools -n 100`
2. Chrome процессы: `ps aux | grep chrome`
3. Виртуальные дисплеи: `ps aux | grep Xvfb`
4. Использование RAM: `free -h`
