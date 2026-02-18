# SEO Tools - Автоматическая генерация метатегов

Система автоматической генерации H1, Title и Description для сайтов на основе анализа конкурентов и LLM.

## Возможности

- 📊 Чтение данных из Google Sheets
- 📈 Частотность запросов через XMLRiver Wordstat API
- 🔍 Поиск конкурентов через XMLRiver Yandex Search API
- 🌐 Парсинг HTML через httpx + браузерный парсинг (Selenium) для JavaScript-сайтов
- 🏷️ Извлечение метатегов из HTML страниц
- 🔖 Классификация типов страниц через LLM
- 🧠 Лемматизация текстов (извлечение ключевых слов)
- 🤖 Генерация метатегов через LLM (Claude/GPT/Grok/DeepSeek)
- ✏️ Редактор метатегов (дополнительная проверка LLM)
- 💰 Автоматический подсчет стоимости API запросов
- 💱 Конвертация USD → RUB по курсу ЦБ РФ
- ✅ Автоматическая загрузка результатов в Google Sheets
- 📝 Подробное логирование всех операций
- ♻️ Бесконечный цикл работы с настраиваемым интервалом

## Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/masta-danila/seotools.git
cd seotools
```

### 2. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # Для Linux/Mac
# или
venv\Scripts\activate  # Для Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

Создайте файл `.env` в корне проекта:
```bash
# API ключи
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ARSENKIN_API_KEY=your_arsenkin_key
DEEPSEEK_API_KEY=your_deepseek_key
GROK_API_KEY=your_grok_key
```

### 5. Настройка Google Sheets

#### 5.1. Получите credentials.json:
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Google Sheets API и Google Drive API
4. Создайте Service Account
5. Скачайте JSON ключ
6. Сохраните как `gsheets/credentials.json`

#### 5.2. Создайте spreadsheets.json:
```json
[
  "YOUR_SPREADSHEET_ID_1",
  "YOUR_SPREADSHEET_ID_2"
]
```

### 6. Запуск

```bash
python main.py
```

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

## Использование

### Основной пайплайн
```bash
python main.py
```

Выполняет полный цикл из 14 шагов:
1. Чтение данных из Google Sheets
2. Обновление Data листов (сохранение стоимости)
3. Получение частотности через XMLRiver Wordstat
4. Поиск конкурентов через XMLRiver Yandex Search
5. Первичный парсинг HTML (httpx)
6. Повторный парсинг через браузер (опционально)
7. Извлечение метатегов из HTML
8. Валидация качества парсинга
9. Классификация типов страниц (опционально)
10. Лемматизация текстов
11. Подготовка данных для генерации
12. Генерация метатегов через LLM
13. Редактор метатегов (опционально)
14. Загрузка результатов в Google Sheets

### Отдельные модули

#### Чтение Google Sheets
```bash
python gsheets/sheets_reader.py
```

#### Частотность запросов
```bash
python xmlriver/wordstat_batch.py
```

#### Поиск конкурентов
```bash
python xmlriver/yandex_parser.py
```

#### Парсинг HTML
```bash
python site_parser/batch_html_processor.py
```

#### Браузерный парсинг
```bash
python site_parser/batch_browser_processor.py
```

#### Классификация страниц
```bash
python site_parser/batch_page_classifier.py
```

#### Лемматизация
```bash
python lemmatizers/lemmatizer_processor.py
```

#### Генерация метатегов
```bash
python metagenerators/metagenerator_batch.py
```

#### Редактор метатегов
```bash
python metagenerators/metatag_editor_batch.py
```

## Настройка параметров

Параметры в `main.py`:

```python
# Интервал между циклами
SLEEP_MINUTES = 10  # минут

# Флаги модулей
ENABLE_BROWSER_REPARSING = True   # Браузерный парсинг для неудачных URL
ENABLE_PAGE_CLASSIFIER = True     # Классификация типов страниц
ENABLE_METATAG_EDITOR = False     # Редактор метатегов (дополнительная проверка)

# Шаг 4: Поиск конкурентов
max_concurrent=5           # Одновременных запросов к XMLRiver
max_urls_per_query=10      # Максимум URL на запрос
region=213                 # ID региона (213 = Москва)

# Шаг 8: Валидация
min_success_rate=0.5       # Минимальный процент успешных парсингов

# Шаг 9: Классификация (опционально)
model="claude-haiku-4-5-20251001"  # Быстрая модель
max_concurrent=3

# Шаг 10: Лемматизация
title_min_words=4
title_max_words=6
description_min_words=6
description_max_words=10

# Шаг 12: Генерация метатегов
model="claude-sonnet-4-5-20250929"  # Основная модель
max_concurrent=3
max_retries=3
max_title_length=90
max_description_length=170

# Шаг 13: Редактор (опционально)
model="claude-haiku-4-5-20251001"
max_concurrent=3
```

## Логирование

Логи сохраняются в папке `logs/`:
- `pipeline.log` - главный оркестратор (все 14 шагов)
- `search.log` - XMLRiver API запросы (Wordstat + Yandex Search)
- `html_parser.log` - парсинг HTML через httpx
- `browser_fetcher.log` - браузерный парсинг (Selenium)
- `page_classifier.log` - классификация типов страниц
- `lemmatizer.log` - лемматизация текстов
- `metagenerator.log` - генерация метатегов
- `sheets_reader.log` - чтение Google Sheets
- `sheets_updater.log` - обновление Google Sheets

### Просмотр логов в реальном времени
```bash
# Главный лог
tail -f logs/pipeline.log

# Конкретный модуль
tail -f logs/search.log
tail -f logs/browser_fetcher.log
tail -f logs/metagenerator.log
```

## Развертывание на сервере

Подробная инструкция в [DEPLOY.md](DEPLOY.md)

Быстрый деплой:
```bash
./deploy_server.sh
./setup_systemd_service.sh
```

## Требования

- Python 3.11+
- Google Chrome (для браузерного парсинга)
- API ключи:
  - **Обязательные:**
    - XMLRiver API (ARSENKIN_API_KEY) - для Wordstat и Yandex Search
    - Google Service Account - для Google Sheets
  - **Один LLM на выбор:**
    - Anthropic Claude (ANTHROPIC_API_KEY)
    - OpenAI GPT (OPENAI_API_KEY)
    - xAI Grok (GROK_API_KEY)
    - DeepSeek (DEEPSEEK_API_KEY)

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

## Лицензия

MIT

## Автор

Danila Dzhaev
