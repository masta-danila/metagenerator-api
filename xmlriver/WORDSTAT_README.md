# XMLRiver Wordstat API - Сбор частотности запросов

Модуль для получения частотности поисковых запросов через XMLRiver Wordstat API.

## API Endpoint

```
http://xmlriver.com/wordstat/new/json
```

## Основная функция

### `get_query_frequency(query, regions, device)`

Получает частотность для одного поискового запроса.

**Параметры:**
- `query` (str, обязательный) - Поисковый запрос
- `regions` (int, опционально) - ID региона Яндекса (None = все регионы, 213 = Москва)
- `device` (str, опционально) - Устройство: "desktop", "phone", "tablet" (по умолчанию "desktop")
- `exact_match` (bool, опционально) - Тип частотности:
  - `True` (по умолчанию) - **точная** частотность: добавляет кавычки и ! перед каждым словом (`"!входные !двери"`)
  - `False` - **широкая** частотность: передается как есть, включает все словоформы и похожие запросы
- `max_retries` (int, опционально) - Количество повторных попыток (по умолчанию 3)

**Возвращает:**
```python
{
    "query": "теплообменник купить",
    "frequency": 15420,  # totalValue из API
    "error": None        # или текст ошибки
}
```

**Пример использования:**
```python
import asyncio
from xmlriver import get_query_frequency

async def main():
    # Точная частотность (по умолчанию)
    # "входные двери" -> "!входные !двери" -> ~1500
    result = await get_query_frequency(
        query="входные двери",
        regions=213,       # Москва
        device="desktop",
        exact_match=True   # по умолчанию
    )
    print(f"Точная частота: {result['frequency']:,}")
    
    # Широкая частотность
    # "входные двери" -> "входные двери" -> ~120000
    result2 = await get_query_frequency(
        query="входные двери",
        regions=213,
        device="desktop",
        exact_match=False
    )
    print(f"Широкая частота: {result2['frequency']:,}")

asyncio.run(main())
```

### Обработка нескольких запросов

Если нужно обработать несколько запросов параллельно, используйте `asyncio.gather`:

```python
import asyncio
from xmlriver import get_query_frequency

async def main():
    queries = [
        "теплообменник купить",
        "пластинчатый теплообменник",
        "теплообменник для отопления"
    ]
    
    # Параллельный запуск с чистыми запросами
    tasks = [
        get_query_frequency(query=q, regions=213, device="desktop", exact_match=True)
        for q in queries
    ]
    results = await asyncio.gather(*tasks)
    
    for result in results:
        if result["error"]:
            print(f"ОШИБКА {result['query']}: {result['error']}")
        else:
            print(f"OK {result['query']}: {result['frequency']:,}")

asyncio.run(main())
```

## Технические детали

### Как работает API

1. **Запрос делается к основной вкладке Wordstat** (без `pagetype`)
2. **Частота извлекается из поля `totalValue`** в JSON ответе
3. **Подготовка запроса:**
   - **Точная частотность** (`exact_match=True`): "входные двери" → `"!входные !двери"` → частота ≈1500
     - Кавычки фиксируют точное соответствие
     - Оператор `!` фиксирует словоформу
   - **Широкая частотность** (`exact_match=False`): "входные двери" → `входные двери` → частота ≈120000
     - Включает все словоформы и похожие запросы
4. **Автоматическое URL-кодирование:**
   - Все специальные символы кодируются автоматически библиотекой `httpx`
   - Кавычки `"` → `%22`, пробелы → `+`, кириллица → UTF-8 коды

### Структура API запроса

```
GET http://xmlriver.com/wordstat/new/json
Parameters:
  - user: [user_id]
  - key: [api_key]
  - query: [поисковый запрос]
  - regions: [id региона]
  - device: [desktop|phone|tablet]
  - pagetype: history
```

### Credentials

Credentials берутся из `.env` файла:
```env
XMLRIVER_USER_ID=8834
XMLRIVER_API_KEY=e5a50999a40533aa928bb89be21e53c1ebd93ef2
```

### Обработка ошибок

Функция автоматически обрабатывает:
- Таймауты запросов (90 секунд)
- HTTP ошибки (4xx, 5xx)
- Ошибки парсинга JSON
- Ошибки API (error_code в ответе)
- Автоматические повторные попытки (по умолчанию 3)

### Регионы Яндекса (примеры)

- `213` - Москва
- `2` - Санкт-Петербург
- `54` - Екатеринбург
- `None` - Все регионы

## Тестовый запуск

Запустите файл напрямую для теста:
```bash
python xmlriver/wordstat_frequency.py
```

Результат будет сохранен в `jsontests/wordstat_frequency_result.json`

## Логирование

Модуль использует централизованное логирование через `logger_config`:
- Успешные запросы
- Предупреждения (totalValue не найден)
- Ошибки с подробностями

Логи сохраняются в `logs/search.log`

## Ограничения API

- **Максимум 10 одновременных запросов** (ограничение XMLRiver)
- Рекомендуется использовать `max_concurrent=5` для стабильности
- Таймаут запроса: 90 секунд
- Автоматические retry с экспоненциальной задержкой

## Интеграция с другими модулями

Модуль можно использовать совместно с:
- `gsheets/sheets_reader.py` - для чтения списка запросов из Google Sheets
- `lemmatizers/lemmatizer.py` - для подготовки запросов перед сбором частотности
- Любыми другими модулями, которым нужна частотность запросов
