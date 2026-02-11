# Data Updater - Обновление листа Data с отсортированными запросами

## Назначение

Модуль обновляет лист **Data** в Google Sheets, сортируя запросы по частотности (от большей к меньшей).

## Логика работы

1. Читает все данные из листа **Data**
2. Для URL, которые есть в словарике с частотностью:
   - Берет запросы с `frequency`
   - Сортирует по `frequency` (по убыванию: сначала самые частотные)
   - Записывает запросы в колонку **Querries** (через `\n`)
   - Записывает частотности в колонку **Demand** (через `\n`, соответствуют запросам)
3. Для URL, которых нет в словарике - оставляет как есть
4. Применяет все изменения **одним batch запросом**

## Основная функция

### `update_all_data_sheets(frequency_data: Dict) -> Dict`

Обновляет листы Data во всех таблицах из `spreadsheets.json`.

**Параметры:**
- `frequency_data` - Словарь с данными частотности из `wordstat_batch_result.json`

**Возвращает:**
```python
{
  "results": [список результатов по каждой таблице],
  "total_stats": {
    "total_spreadsheets": 1,
    "successful_updates": 1,
    "failed_updates": 0,
    "total_urls_updated": 16,
    "total_urls_skipped": 0
  }
}
```

## Пример использования

### Как модуль

```python
from gsheets.data_updater import update_all_data_sheets
import json

# Загружаем данные с частотностью
with open('jsontests/wordstat_batch_result.json', 'r') as f:
    frequency_data = json.load(f)

# Обновляем все таблицы
result = update_all_data_sheets(frequency_data)

print(f"Обновлено URL: {result['total_stats']['total_urls_updated']}")
```

### Как скрипт

```bash
python gsheets/data_updater.py
```

Скрипт автоматически:
1. Загрузит данные из `jsontests/wordstat_batch_result.json`
2. Обновит листы Data во всех таблицах из `spreadsheets.json`
3. Выведет статистику

## Формат входных данных

Ожидается словарь из `wordstat_batch_result.json`:

```json
{
  "SPREADSHEET_ID": {
    "urls": {
      "https://example.com/page": {
        "queries": [
          {"query": "запрос 1", "frequency": 100},
          {"query": "запрос 2", "frequency": 50},
          {"query": "запрос 3", "frequency": 10}
        ],
        ...
      }
    }
  }
}
```

## Результат

После обновления в листе **Data**:

### Колонка Querries (отсортированные запросы):
```
запрос 1
запрос 2
запрос 3
```

### Колонка Demand (соответствующие частотности):
```
100
50
10
```

(Самые частотные сверху, менее частотные снизу)

## Требования

- Python 3.7+
- gspread
- google-auth
- Файл `credentials.json` в папке `gsheets/`
- Файл `spreadsheets.json` в папке `gsheets/`

## Безопасность

- Использует batch update для минимизации количества API запросов
- Обновляет только колонки **Querries** и **Demand**, остальные колонки остаются без изменений
- URL без данных частотности остаются без изменений
- Если колонка **Demand** отсутствует - обновляется только **Querries** (без ошибки)
