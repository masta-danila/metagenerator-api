# Инструкция по развертыванию SEO Tools на сервере

## Предварительные требования

- Ubuntu/Debian сервер
- Python 3.11+
- Доступ по SSH
- Права sudo

## Структура на сервере

Проект будет развернут в директории:
```
/home/callchecker/seotools/
```

Рядом с существующими проектами:
```
/home/callchecker/callchecker/
/home/callchecker/revchecker/
/home/callchecker/seotools/  ← новый проект
```

## Шаг 1: Клонирование проекта на сервер

### 1.1. Подключитесь к серверу:
```bash
ssh callchecker@YOUR_SERVER_IP
```

### 1.2. Клонируйте проект из GitHub:
```bash
cd /home/callchecker
git clone https://github.com/masta-danila/seotools.git
cd seotools
```

## Шаг 2: Копирование конфигурационных файлов

**ВАЖНО:** Эти файлы содержат секретные данные и не хранятся в Git!

### 2.1. На локальной машине убедитесь, что у вас есть:
- `.env` - API ключи (ANTHROPIC_API_KEY, OPENAI_API_KEY, ARSENKIN_API_KEY, GROK_API_KEY, DEEPSEEK_API_KEY и др.)
- `gsheets/credentials.json` - credentials из Google Cloud Console
- `gsheets/spreadsheets.json` - ID Google таблиц
- `utils/usd_rate.json` - конфигурация курса USD (создастся автоматически, если отсутствует)

### 2.2. Скопируйте файлы на сервер:
```bash
# На локальной машине
cd /Users/daniladzhiev/PycharmProjects/seotools

# Копируем .env
scp .env callchecker@YOUR_SERVER_IP:/home/callchecker/seotools/

# Копируем Google Sheets credentials
scp gsheets/credentials.json callchecker@YOUR_SERVER_IP:/home/callchecker/seotools/gsheets/

# Копируем конфигурацию таблиц
scp gsheets/spreadsheets.json callchecker@YOUR_SERVER_IP:/home/callchecker/seotools/gsheets/
```

## Шаг 3: Установка зависимостей и проверка

### 3.1. Сделайте скрипты исполняемыми:
```bash
chmod +x deploy_server.sh
chmod +x setup_systemd_service.sh
```

### 3.2. Запустите скрипт развертывания:
```bash
./deploy_server.sh
```

Этот скрипт:
- Создаст виртуальное окружение
- Установит зависимости из requirements.txt (включая Selenium, ChromeDriver и др.)
- Проверит наличие .env и credentials.json
- Проверит подключение к Google Sheets
- Создаст необходимые директории (logs/, jsontests/)
- Создаст xmlriver/blacklist_domains.json если его нет
- Проверит наличие конфигурационных файлов (page_types.json, llm_pricing.json, xmlriver_pricing.json)
- Создаст utils/usd_rate.json с начальной конфигурацией курса USD

## Шаг 4: Настройка systemd службы

### 4.1. Установите службу:
```bash
./setup_systemd_service.sh
```

Этот скрипт:
- Скопирует `seotools.service` в `/etc/systemd/system/`
- Включит автозапуск при перезагрузке сервера
- Запустит службу

### 4.2. Проверьте статус:
```bash
sudo systemctl status seotools
```

## Управление службой

### Основные команды:
```bash
# Статус
sudo systemctl status seotools

# Перезапуск
sudo systemctl restart seotools

# Остановка
sudo systemctl stop seotools

# Запуск
sudo systemctl start seotools

# Отключить автозапуск
sudo systemctl disable seotools

# Включить автозапуск
sudo systemctl enable seotools
```

### Просмотр логов:
```bash
# Логи systemd в реальном времени
sudo journalctl -u seotools -f

# Логи за сегодня
sudo journalctl -u seotools --since today

# Последние 100 строк
sudo journalctl -u seotools -n 100

# Логи приложения (из папки logs/)
tail -f /home/callchecker/seotools/logs/pipeline.log
tail -f /home/callchecker/seotools/logs/search.log
tail -f /home/callchecker/seotools/logs/html_parser.log
tail -f /home/callchecker/seotools/logs/browser_fetcher.log
tail -f /home/callchecker/seotools/logs/page_classifier.log
tail -f /home/callchecker/seotools/logs/metagenerator.log
tail -f /home/callchecker/seotools/logs/sheets_updater.log
```

## Обновление проекта

На сервере выполните:
```bash
cd /home/callchecker/seotools

# Остановите службу
sudo systemctl stop seotools

# Получите последние изменения из GitHub
git pull origin main

# Обновите зависимости (если нужно)
source venv/bin/activate
pip install -r requirements.txt

# Запустите службу
sudo systemctl start seotools
```

**Примечание:** Если вы обновили `.env` или файлы в `gsheets/`, скопируйте их заново с локальной машины (см. Шаг 2).

## Мониторинг

### Проверка работы всех служб:
```bash
# Все службы (callchecker + revchecker + seotools)
sudo systemctl status callchecker-* revchecker seotools

# Проверка процессов
ps aux | grep -E 'callchecker|revchecker|seotools'
```

### Логи всех систем:
```bash
# Все логи systemd
sudo journalctl -u "callchecker-*" -u revchecker -u seotools -f

# Логи приложений
tail -f /home/callchecker/*/logs/*.log
```

## Настройка параметров

Параметры работы настраиваются в `main.py`:

```python
SLEEP_MINUTES = 10  # Интервал между циклами в минутах

# Флаги включения/выключения модулей
ENABLE_BROWSER_REPARSING = True   # Браузерный парсинг для неудачных URL
ENABLE_PAGE_CLASSIFIER = True     # Классификация типов страниц
ENABLE_METATAG_EDITOR = False     # Редактор метатегов (дополнительная проверка LLM)

# Параметры для каждого шага:
# - max_concurrent=5             # Одновременных запросов к XMLRiver API
# - max_urls_per_query=10        # Максимум URL на запрос
# - min_success_rate=0.5         # Минимальный процент успешных парсингов
# - model="claude-sonnet-4-5-20250929"  # Модель LLM для генерации
# - max_title_length=90          # Максимальная длина title
# - max_description_length=170   # Максимальная длина description
```

После изменения параметров:
```bash
sudo systemctl restart seotools
```

## Troubleshooting

### Служба не запускается
```bash
# Проверьте логи
sudo journalctl -u seotools -n 50

# Проверьте конфигурацию
sudo systemctl cat seotools

# Попробуйте запустить вручную
cd /home/callchecker/seotools
source venv/bin/activate
python main.py
```

### Ошибки с Google Sheets
```bash
# Проверьте credentials
ls -la gsheets/credentials.json

# Проверьте подключение
cd /home/callchecker/seotools
source venv/bin/activate
python -c "import gspread; from google.oauth2.service_account import Credentials; \
    creds = Credentials.from_service_account_file('gsheets/credentials.json'); \
    client = gspread.authorize(creds); print('OK')"
```

### Ошибки с XMLRiver API
```bash
# Проверьте .env
cat .env | grep ARSENKIN_API_KEY

# Проверьте конфигурацию
cat xmlriver/xmlriver_pricing.json

# Проверьте курс USD
cat utils/usd_rate.json
```

### Ошибки с браузерным парсингом
```bash
# Проверьте установку ChromeDriver
which chromedriver

# Проверьте Google Chrome
google-chrome --version

# Установка Chrome на сервере (если отсутствует)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# ChromeDriver установится автоматически через webdriver-manager
```

### Ошибки с LLM API
```bash
# Проверьте .env
cat .env | grep -E 'API_KEY'

# Проверьте подключение
cd /home/callchecker/seotools
source venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); \
    print('Anthropic:', 'OK' if os.getenv('ANTHROPIC_API_KEY') else 'MISSING'); \
    print('OpenAI:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING'); \
    print('Grok:', 'OK' if os.getenv('GROK_API_KEY') else 'MISSING'); \
    print('DeepSeek:', 'OK' if os.getenv('DEEPSEEK_API_KEY') else 'MISSING')"

# Проверьте pricing
cat llm/llm_pricing.json
```

## Структура файлов на сервере

```
/home/callchecker/
├── callchecker/                    # Существующий проект
│   ├── venv/
│   ├── bitrix24/
│   ├── logs/
│   └── ...
├── revchecker/                     # Существующий проект
│   ├── venv/
│   ├── llm/
│   ├── gsheets/
│   └── ...
└── seotools/                       # Новый проект
    ├── venv/
    ├── gsheets/
    │   ├── credentials.json        ← Важно! (секрет)
    │   ├── spreadsheets.json       ← Важно! (секрет)
    │   ├── sheets_reader.py
    │   ├── sheets_updater.py
    │   └── data_updater.py
    ├── xmlriver/
    │   ├── wordstat_frequency.py
    │   ├── wordstat_batch.py
    │   ├── yandex_parser.py
    │   ├── xmlriver_pricing.json
    │   └── blacklist_domains.json
    ├── site_parser/
    │   ├── html_parser.py
    │   ├── batch_html_processor.py
    │   ├── browser_fetcher.py
    │   ├── batch_browser_processor.py
    │   ├── page_classifier.py
    │   ├── batch_page_classifier.py
    │   ├── meta_extractor.py
    │   ├── batch_meta_processor.py
    │   ├── parsing_validator.py
    │   └── page_types.json
    ├── lemmatizers/
    │   ├── lemmatizer.py
    │   └── lemmatizer_processor.py
    ├── metagenerators/
    │   ├── metagenerator.py
    │   ├── metagenerator_batch.py
    │   ├── metatag_editor.py
    │   └── metatag_editor_batch.py
    ├── llm/
    │   ├── llm_router.py
    │   ├── llm_response_cleaner.py
    │   ├── claude_request.py
    │   ├── gpt_request.py
    │   ├── grok_request.py
    │   ├── deepseek_request.py
    │   └── llm_pricing.json
    ├── utils/
    │   ├── usd_rate_updater.py
    │   └── usd_rate.json          ← Создается автоматически
    ├── logs/
    ├── jsontests/
    ├── .env                        ← Важно! (секрет)
    ├── main.py
    ├── logger_config.py
    ├── requirements.txt
    ├── deploy_server.sh
    ├── setup_systemd_service.sh
    ├── seotools.service
    └── DEPLOY.md
```

## Безопасность

1. **Файлы с секретами не должны попадать в Git:**
   - `.env` - API ключи (добавлен в .gitignore)
   - `gsheets/credentials.json` - Google Cloud credentials (добавлен в .gitignore)
   - `gsheets/spreadsheets.json` - ID таблиц клиентов (добавлен в .gitignore)
   - `jsontests/*.json` - тестовые данные (добавлены в .gitignore)
   - `logs/*.log` - логи могут содержать URL клиентов (добавлены в .gitignore)
   - `utils/usd_rate.json` - может содержать бизнес-данные (добавлен в .gitignore)

2. **Права на файлы:**
```bash
chmod 600 .env
chmod 600 gsheets/credentials.json
chmod 600 gsheets/spreadsheets.json
chmod 755 *.sh
```

3. **Логи могут содержать чувствительные данные:**
```bash
# Регулярно чистите старые логи
find logs/ -name "*.log.*" -mtime +30 -delete

# Проверьте, что логи не попадают в git
cat .gitignore | grep logs
```

## Архитектура пайплайна

Проект работает в бесконечном цикле с интервалом 10 минут:

1. **Шаг 1/14**: Чтение данных из Google Sheets (листы Meta и Data)
2. **Шаг 2/14**: Обновление таблиц Data (сохранение стоимости API запросов)
3. **Шаг 3/14**: Получение частотности запросов через XMLRiver Wordstat API
4. **Шаг 4/14**: Поиск конкурентов через XMLRiver Yandex Search API
5. **Шаг 5/14**: Первичный парсинг HTML (httpx)
6. **Шаг 6/14**: Повторный парсинг неудачных URL через браузер (Selenium) - опционально
7. **Шаг 7/14**: Извлечение метатегов из HTML (основные и конкурентные URL)
8. **Шаг 8/14**: Валидация качества парсинга
9. **Шаг 9/14**: Классификация типов страниц через LLM - опционально
10. **Шаг 10/14**: Лемматизация текстов (pymystem3, pymorphy3)
11. **Шаг 11/14**: Формирование данных для генерации метатегов
12. **Шаг 12/14**: Генерация метатегов через LLM (Claude/GPT/Grok/DeepSeek)
13. **Шаг 13/14**: Редактор метатегов (дополнительная проверка LLM) - опционально
14. **Шаг 14/14**: Загрузка результатов в Google Sheets

### Подсчет стоимости API:
Для каждого URL отслеживается:
- **Wordstat cost**: Стоимость запросов частотности
- **Yandex search cost**: Стоимость поиска конкурентов
- **Classification cost**: Стоимость классификации страниц
- **Metageneration cost**: Стоимость генерации метатегов
- **Metatag editor cost**: Стоимость проверки редактором (если включен)
- **Cost**: Общая стоимость в рублях (с конвертацией через ЦБ РФ)

### XMLRiver API:
- Используется для Wordstat и Yandex Search
- Стоимость настраивается в `xmlriver/xmlriver_pricing.json`
- Автоматический подсчет стоимости для каждого запроса

## Установка Google Chrome на сервере

Для работы браузерного парсинга (Selenium) необходим Google Chrome:

```bash
# Загрузка и установка Chrome
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# Проверка установки
google-chrome --version

# ChromeDriver установится автоматически через webdriver-manager
# при первом запуске браузерного парсинга
```

**Примечание**: Если Chrome уже установлен на сервере (для callchecker или revchecker), повторная установка не требуется.

## Дополнительные ресурсы

- **XMLRiver API**: https://xmlriver.com/
- **Google Sheets API**: https://developers.google.com/sheets/api
- **Anthropic Claude API**: https://docs.anthropic.com/claude/reference
- **OpenAI API**: https://platform.openai.com/docs/api-reference
- **xAI Grok API**: https://docs.x.ai/docs
- **DeepSeek API**: https://platform.deepseek.com/api-docs
- **Selenium Documentation**: https://selenium-python.readthedocs.io/
- **ЦБ РФ API (курс валют)**: https://www.cbr.ru/development/sxml/
