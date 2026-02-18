# Быстрая установка Browser Module

## Шаг 1: Установка зависимостей

```bash
# Активируйте виртуальное окружение проекта
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установите зависимости
pip install selenium webdriver-manager
```

## Шаг 2: Проверка установки

```bash
# Запустите тест
python browser/browser_fetcher.py
```

Вы должны увидеть:
```
Запуск браузера (desktop, headless)...
Браузер успешно запущен
Загружаем: https://example.com
HTML получен (1256 символов)
...
Тест завершен
```

## Шаг 3: Запустите примеры

```bash
# Все примеры
python browser/example.py

# Или прямой тест с URL
python browser/browser_fetcher.py https://ya.ru
```

## Проблемы?

### ChromeDriver не найден
- Устанавливается автоматически через `webdriver-manager`
- Если проблема - попробуйте: `pip install --upgrade webdriver-manager`

### Браузер не закрывается
- Используйте контекстный менеджер `with BrowserFetcher() as fetcher:`

### Ошибка при запуске Chrome
- Проверьте что Chrome установлен
- На серверах без GUI используйте `headless=True`

## Готово!

Теперь можете использовать браузерный модуль:

```python
from browser import fetch_html_simple

html = fetch_html_simple("https://example.com")
print(f"Получено {len(html)} символов")
```

См. полную документацию в `README.md`
