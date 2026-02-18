# Быстрый старт SEO Tools

## Локальный запуск (для разработки)

### 1. Клонирование и установка
```bash
git clone https://github.com/masta-danila/seotools.git
cd seotools

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка .env файла

Создайте файл `.env` в корне проекта:
```bash
# API ключи
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ARSENKIN_API_KEY=...
DEEPSEEK_API_KEY=...
GROK_API_KEY=...
```

### 3. Настройка Google Sheets

#### 3.1. Получение credentials.json
1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект
3. Включите APIs:
   - Google Sheets API
   - Google Drive API
4. Создайте Service Account:
   - IAM & Admin → Service Accounts → Create Service Account
   - Дайте имя: `seotools-service`
   - Роль: Editor
5. Создайте ключ:
   - Actions → Manage Keys → Add Key → Create New Key
   - Выберите JSON
   - Скачайте файл
6. Сохраните как `gsheets/credentials.json`

#### 3.2. Создание spreadsheets.json
```bash
# В папке gsheets/ создайте файл spreadsheets.json
cat > gsheets/spreadsheets.json <<EOF
[
  "1O5dGWkcrg09dZRXnT2YpXUQsA23VMFhg-_ShM6Z1g5Q"
]
EOF
```

#### 3.3. Настройка доступа
В каждой Google таблице:
1. Откройте "Настройки доступа"
2. Добавьте email Service Account (из credentials.json, поле "client_email")
3. Дайте права "Редактор"

### 4. Структура Google таблицы

Каждая таблица должна содержать 2 листа:

#### Лист "Meta"
Колонки (регистр не важен):
- `URL` - адрес страницы
- `H1` - заголовок H1 (заполняется автоматически)
- `Title` - мета-тег title (заполняется автоматически)
- `Description` - мета-тег description (заполняется автоматически)

#### Лист "Data"
Колонки:
- `URL` - адрес страницы (должен совпадать с URL в листе Meta)
- `Queries` - поисковые запросы (через запятую)
- `Company Name` - название компании
- `Variables H1` - переменные для H1 (через запятую, например: `{price} р.`)
- `Variables Title` - переменные для Title (через запятую)
- `Variables Description` - переменные для Description (через запятую)

### 5. Blacklist доменов (опционально)

Файл `xmlriver/blacklist_domains.json` уже существует в репозитории. Можете добавить в него домены, которые нужно исключить из анализа:
```json
[
  "yandex.ru",
  "google.com",
  "wikipedia.org"
]
```

### 6. Первый запуск

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Запустите основной пайплайн
python main.py
```

## Тестирование отдельных модулей

### Шаг 1: Чтение Google Sheets
```bash
python gsheets/sheets_reader.py
```
Результат: `jsontests/step1_sheets_data.json`

### Шаг 3: Частотность запросов (XMLRiver Wordstat)
```bash
python xmlriver/wordstat_batch.py
```
Входные данные: `jsontests/step2_data_update_stats.json`
Результат: `jsontests/step3_wordstat_result.json`

### Шаг 4: Поиск конкурентов (XMLRiver Yandex Search)
```bash
python xmlriver/yandex_parser.py
```
Входные данные: `jsontests/step3_wordstat_result.json`
Результат: `jsontests/step4_yandex_competitors.json`

### Шаг 5: Парсинг HTML (httpx)
```bash
python site_parser/batch_html_processor.py
```
Входные данные: `jsontests/step4_yandex_competitors.json`
Результат: `jsontests/step5_html_parsed.json`

### Шаг 6: Повторный парсинг через браузер (Selenium)
```bash
python site_parser/batch_browser_processor.py
```
Входные данные: `jsontests/step5_html_parsed.json`
Результат: `jsontests/step6_browser_reparsed.json`

### Шаг 7: Извлечение метатегов
```bash
python site_parser/batch_meta_processor.py
```
Входные данные: `jsontests/step6_browser_reparsed.json`
Результат: `jsontests/step7_extracted_meta.json`

### Шаг 9: Классификация страниц (LLM)
```bash
python site_parser/batch_page_classifier.py
```
Входные данные: `jsontests/step8_validated.json`
Результат: `jsontests/step9_classified.json`

### Шаг 10: Лемматизация текстов
```bash
python lemmatizers/lemmatizer_processor.py
```
Входные данные: `jsontests/step9_classified.json`
Результат: `jsontests/step10_lemmatized.json`

### Шаг 12: Генерация метатегов (LLM)
```bash
python metagenerators/metagenerator_batch.py
```
Входные данные: `jsontests/step11_metagenerator_input.json`
Результат: `jsontests/step12_generated_metatags.json`

### Шаг 13: Редактор метатегов (LLM)
```bash
python metagenerators/metatag_editor_batch.py
```
Входные данные: `jsontests/step12_generated_metatags.json`
Результат: `jsontests/step13_edited_metatags.json`

### Шаг 14: Обновление Google Sheets
```bash
python gsheets/sheets_updater.py
```
Входные данные: `jsontests/step13_edited_metatags.json` (или `step12_generated_metatags.json` если редактор выключен)
Результат: `jsontests/step14_meta_update_stats.json`

## Просмотр логов

Все логи сохраняются в папке `logs/`:

```bash
# Просмотр в реальном времени
tail -f logs/pipeline.log

# Просмотр конкретного модуля
tail -f logs/search.log              # XMLRiver API запросы
tail -f logs/html_parser.log         # Парсинг HTML через httpx
tail -f logs/browser_fetcher.log     # Браузерный парсинг (Selenium)
tail -f logs/page_classifier.log     # Классификация страниц
tail -f logs/metagenerator.log       # Генерация метатегов
tail -f logs/sheets_updater.log      # Обновление Google Sheets
```

## Настройка параметров

Откройте `main.py` и настройте параметры:

```python
# Интервал между циклами
SLEEP_MINUTES = 10  # Минут между запусками

# Флаги включения/выключения модулей
ENABLE_BROWSER_REPARSING = True   # Повторный парсинг через браузер
ENABLE_PAGE_CLASSIFIER = True     # Классификация типов страниц
ENABLE_METATAG_EDITOR = False     # Редактор метатегов (дополнительная LLM проверка)

# В функции run_full_pipeline():

# Шаг 4: Поиск конкурентов (XMLRiver Yandex Search)
yandex_data = process_sheets_data(
    input_data=wordstat_data,
    max_concurrent=5,       # Одновременных запросов к XMLRiver API
    max_urls_per_query=10,  # Максимум URL на каждый запрос
    region=213,             # ID региона (213 = Москва)
    blacklist_file="xmlriver/blacklist_domains.json"
)

# Шаг 9: Классификация страниц (опционально)
classified_data = classify_batch(
    input_data=validated_data,
    model="claude-haiku-4-5-20251001",  # Быстрая модель для классификации
    max_concurrent=3,       # Одновременных запросов к LLM
    max_retries=3
)

# Шаг 10: Лемматизация
lemmatized_data = process_urls_with_lemmatization(
    data=classified_data,
    title_min_words=4,      # Мин. слов для Title
    title_max_words=6,      # Макс. слов для Title
    description_min_words=6,  # Мин. слов для Description
    description_max_words=10  # Макс. слов для Description
)

# Шаг 12: Генерация метатегов
generated_data = generate_metatags_batch(
    data=prepared_data,
    model="claude-sonnet-4-5-20250929",  # Основная модель для генерации
    max_concurrent=3,       # Одновременных запросов к LLM
    max_retries=3,
    max_title_length=90,    # Макс. длина title
    max_description_length=170  # Макс. длина description
)

# Шаг 13: Редактор метатегов (опционально)
if ENABLE_METATAG_EDITOR:
    edited_data = review_metatags_batch(
        data=generated_data,
        model="claude-haiku-4-5-20251001",  # Быстрая модель для проверки
        max_concurrent=3,
        max_retries=3,
        max_title_length=90,
        max_description_length=170
    )
```

## Остановка программы

```bash
# Нажмите Ctrl+C для остановки
# Программа корректно завершит текущий цикл
```

## Troubleshooting

### Ошибка: credentials.json not found
```bash
# Проверьте наличие файла
ls -la gsheets/credentials.json

# Проверьте права
chmod 600 gsheets/credentials.json
```

### Ошибка: 429 Too Many Requests (XMLRiver)
```bash
# Уменьшите количество одновременных запросов:
# - max_concurrent=3 (или меньше)
# 
# Проверьте стоимость запросов:
cat xmlriver/xmlriver_pricing.json
cat utils/usd_rate.json
```

### Проблемы с браузерным парсингом
```bash
# Проверьте установку Chrome
google-chrome --version

# Если Chrome не установлен:
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# ChromeDriver установится автоматически через webdriver-manager
```

### Ошибка: Google Sheets permission denied
```bash
# Убедитесь что Service Account добавлен в таблицу:
# 1. Откройте таблицу
# 2. Нажмите "Настройки доступа"
# 3. Добавьте email из credentials.json (поле client_email)
# 4. Дайте права "Редактор"
```

### Ошибка: LLM API rate limit
```bash
# Уменьшите max_concurrent в generate_metatags_batch:
# max_concurrent=1  # или 2
```

## Полезные команды

```bash
# Проверка подключения к Google Sheets
python -c "import gspread; from google.oauth2.service_account import Credentials; \
    creds = Credentials.from_service_account_file('gsheets/credentials.json'); \
    client = gspread.authorize(creds); print('OK')"

# Проверка API ключей
python -c "from dotenv import load_dotenv; import os; load_dotenv(); \
    print('XMLRiver (Arsenkin):', 'OK' if os.getenv('ARSENKIN_API_KEY') else 'MISSING'); \
    print('Anthropic:', 'OK' if os.getenv('ANTHROPIC_API_KEY') else 'MISSING'); \
    print('OpenAI:', 'OK' if os.getenv('OPENAI_API_KEY') else 'MISSING'); \
    print('Grok:', 'OK' if os.getenv('GROK_API_KEY') else 'MISSING'); \
    print('DeepSeek:', 'OK' if os.getenv('DEEPSEEK_API_KEY') else 'MISSING')"

# Очистка логов
rm logs/*.log.*

# Очистка тестовых данных
rm jsontests/*.json
```

## Следующие шаги

После успешного тестирования локально:
1. Прочитайте [DEPLOY.md](DEPLOY.md) для деплоя на сервер
2. Настройте systemd службу для автозапуска
3. Настройте мониторинг логов

## Поддержка

При возникновении проблем:
1. Проверьте логи в папке `logs/`
2. Убедитесь что все API ключи корректны
3. Проверьте доступ к Google Sheets
4. Проверьте rate limits API
