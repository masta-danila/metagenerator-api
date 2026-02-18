# Browser Module

Модуль для получения HTML кода страниц через реальный браузер Chrome с поддержкой JavaScript.

Адаптирован из проекта `yamparser` для упрощенного получения HTML.

## Возможности

- Получение HTML через реальный браузер Chrome
- Поддержка JavaScript-рендеринга (SPA, динамический контент)
- Мобильная и десктопная эмуляция
- Headless режим (без видимого окна)
- Поддержка прокси с авторизацией
- Простой API

## Установка зависимостей

```bash
# Базовая установка
pip install selenium webdriver-manager

# С поддержкой прокси
pip install selenium webdriver-manager selenium-wire
```

## Быстрый старт

### Вариант 1: Упрощенная функция

```python
from browser import fetch_html_simple

# Получить HTML одной страницы
html = fetch_html_simple("https://example.com")
if html:
    print(f"Получено {len(html)} символов")
```

### Вариант 2: Класс с контекстным менеджером

```python
from browser import BrowserFetcher

# Автоматическое закрытие браузера при выходе из контекста
with BrowserFetcher(device_type="desktop", headless=True) as fetcher:
    html = fetcher.fetch_html("https://example.com", wait_time=3)
    if html:
        print(f"Получено {len(html)} символов")
```

### Вариант 3: Ручное управление

```python
from browser import BrowserFetcher

# Создаем браузер
fetcher = BrowserFetcher(device_type="mobile", headless=False)

# Запускаем
if fetcher.start():
    # Получаем HTML нескольких страниц
    html1 = fetcher.fetch_html("https://example.com")
    html2 = fetcher.fetch_html("https://example.org")
    
    # Закрываем браузер
    fetcher.close()
```

## Параметры

### BrowserFetcher

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `device_type` | str | "desktop" | Тип устройства: "mobile" или "desktop" |
| `headless` | bool | True | Запускать без видимого окна |

### fetch_html()

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `url` | str | - | URL страницы |
| `wait_time` | int | 2 | Время ожидания после загрузки (сек) |

## Работа с прокси

Модуль поддерживает прокси с авторизацией через selenium-wire.

### Создание файла proxy.txt

Создайте файл `browser/proxy.txt` с прокси в формате:
```
IP:PORT:USERNAME:PASSWORD
192.168.1.1:8080:user1:pass1
192.168.1.2:8080:user2:pass2
```

### Использование прокси

```python
from browser import BrowserFetcher, ProxyManager

# Создаем менеджер прокси (автоматически загружает browser/proxy.txt)
proxy_manager = ProxyManager()

# Используем с BrowserFetcher
with BrowserFetcher(
    device_type="desktop",
    headless=True,
    use_proxy=True,
    proxy_manager=proxy_manager
) as fetcher:
    html = fetcher.fetch_html("https://example.com")
    print(f"Получено {len(html)} символов")
```

### Упрощенный вариант

```python
from browser import fetch_html_simple, ProxyManager

# Создаем менеджер прокси (автоматически загружает browser/proxy.txt)
proxy_manager = ProxyManager()

# Получаем HTML через прокси
html = fetch_html_simple(
    "https://example.com",
    use_proxy=True,
    proxy_manager=proxy_manager
)
```

## Мобильная эмуляция

По умолчанию эмулируется iPhone 13:
- Разрешение: 390x844
- User-Agent: iOS 15.0 Safari

```python
from browser import fetch_html_simple

# Получить мобильную версию сайта
html = fetch_html_simple(
    "https://example.com",
    device_type="mobile"
)
```

## Интеграция с site_parser

```python
from browser import fetch_html_simple
from site_parser.html_parser import compress_html_for_classification

# Получаем HTML через браузер
raw_html = fetch_html_simple("https://example.com", wait_time=3)

if raw_html:
    # Очищаем и сжимаем для классификации
    clean_html = compress_html_for_classification(raw_html, max_length=15000)
    
    # Используем для классификации
    from site_parser.page_classifier import classify_page
    result = classify_page(clean_html, model="gpt-4o-mini")
    print(f"Тип страницы: {result['page_type']}")
```

## Примеры использования

### Пример 1: Простое получение HTML

```python
from browser import fetch_html_simple

html = fetch_html_simple("https://example.com")
print(html[:500])  # Первые 500 символов
```

### Пример 2: Несколько страниц

```python
from browser import BrowserFetcher

urls = [
    "https://example.com",
    "https://example.org",
    "https://example.net"
]

with BrowserFetcher(headless=True) as fetcher:
    for url in urls:
        html = fetcher.fetch_html(url, wait_time=2)
        if html:
            print(f"{url}: {len(html)} символов")
```

### Пример 3: С обработкой ошибок

```python
from browser import BrowserFetcher

with BrowserFetcher(device_type="desktop", headless=True) as fetcher:
    try:
        html = fetcher.fetch_html("https://example.com", wait_time=5)
        
        if html:
            # Обработка HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.find('title')
            print(f"Заголовок: {title.text if title else 'Не найден'}")
        else:
            print("Не удалось получить HTML")
    
    except Exception as e:
        print(f"Ошибка: {e}")
```

## Тестирование

Запустите встроенный тест:

```bash
# Тест с example.com
python browser/browser_fetcher.py

# Тест с другим URL
python browser/browser_fetcher.py https://example.com

# Тест менеджера прокси
python browser/proxy_manager.py
```

## Отличия от httpx

| Возможность | httpx | browser (Selenium) |
|-------------|-------|-------------------|
| Скорость | Очень быстро | Медленно |
| JavaScript | Не поддерживается | Полная поддержка |
| SPA сайты | Только начальный HTML | Полный рендер |
| Ресурсы | Минимальные | Chrome (~200MB RAM) |
| Использование | Статические сайты | Динамические SPA |

**Рекомендация:** Используйте `httpx` когда возможно, `browser` только для JavaScript-сайтов.

## Известные проблемы

1. **ChromeDriver не найден**: Устанавливается автоматически через `webdriver-manager`
2. **Браузер не закрывается**: Используйте контекстный менеджер `with`
3. **Медленная работа**: Увеличьте `headless=True`, уменьшите `wait_time`

## Лицензия

Адаптировано из проекта yamparser.
