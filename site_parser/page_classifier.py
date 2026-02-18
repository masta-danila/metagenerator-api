"""
Модуль для классификации типов веб-страниц через LLM
"""
import json
import asyncio
from pathlib import Path
import sys
import os

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import llm_request


def load_page_types(json_path: str = None) -> list:
    """
    Загружает типы страниц из JSON файла
    
    Args:
        json_path: Путь к файлу page_types.json. Если None, ищет в папке site_parser
    
    Returns:
        Список типов страниц
    """
    if json_path is None:
        # По умолчанию используем файл в папке site_parser
        json_path = Path(__file__).parent / "page_types.json"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_page_types_for_prompt(page_types: list) -> str:
    """Форматирует типы страниц для промпта"""
    result = []
    for item in page_types:
        page_type = item['page_type']
        site_types = ', '.join(item['site_types'])
        result.append(f"- {page_type} (для сайтов: {site_types})")
    return '\n'.join(result)


async def classify_page(html_structure: str, model: str = "gpt-4o-mini", max_length: int = None) -> dict:
    """
    Классифицирует страницу по HTML структуре (асинхронная версия)
    
    Args:
        html_structure: HTML структура страницы (сжатая, без атрибутов)
        model: Модель LLM для классификации (по умолчанию gpt-4o-mini)
        max_length: Максимальное количество символов HTML для классификации (None = без ограничений)
        
    Returns:
        dict с результатом классификации от LLM
    """
    # Обрезаем HTML до max_length, если задан параметр (экономия токенов)
    if max_length and len(html_structure) > max_length:
        html_structure = html_structure[:max_length] + "\n...(HTML обрезан для экономии токенов)"
    
    # Загружаем типы страниц
    page_types = load_page_types()
    page_types_text = format_page_types_for_prompt(page_types)
    
    # Формируем промпт
    system_prompt = """Ты эксперт по анализу структуры веб-страниц. 
Твоя задача - определить тип страницы на основе упрощенной HTML структуры с текстовым контентом.

Доступные типы страниц:
{}

ФОРМАТ ВХОДНЫХ ДАННЫХ:
Ты получишь упрощенный HTML:
- <head> содержит <title> и <meta> теги (с атрибутами name, property, content)
- <body> содержит структуру (div, nav, header, ul, li, a, p, h1-h6) БЕЗ атрибутов class/id/style
- Весь текстовый контент сохранён
- Удалены: скрипты, стили, SVG, iframe, комментарии, табуляции

АНАЛИЗИРУЙ:
1. <head>:
   - <title> - заголовок страницы
   - <meta name="description"> - описание страницы
   - <meta name="keywords"> - ключевые слова
   
2. <body> структура и контент:
   - H1, H2, H3 - заголовки и иерархия контента
   - Текст в параграфах (p, div) - описание товара, статья, информация
   - Навигация (nav, ul > li > a) - меню и структура сайта
   - Формы (form, input, button) - заказ, поиск, подписка
   - Списки товаров (много div > a + h2/h3) - каталог
   - Таблицы (table) - характеристики, цены

ПАТТЕРНЫ ТИПОВ СТРАНИЦ:
- Карточка товара: Title "Купить [товар]", H1 название товара, кнопки "купить"/"в корзину", форма заказа, характеристики, цена
- Категория каталога: Title "[категория] купить", H1 название категории, много H2/H3 (названия товаров), много ссылок на товары, фильтры
- Главная страница: Общий Title (название компании), разделы "О нас", "Каталог", "Услуги", много nav, разнообразные блоки
- Статья/блог: Title статьи, H1 заголовок статьи, много P (текст статьи), дата публикации, автор
- Информационная: Title "О компании"/"Контакты"/"Доставка", простая структура, текстовое описание, контактные данные

Ответь СТРОГО в формате JSON без дополнительных пояснений и текста:
{{
    "page_type": "Название типа страницы строго как в доступных типах страниц",
    "confidence": "high/medium/low"
}}

ВАЖНО: Верни ТОЛЬКО JSON, без каких-либо пояснений до или после него.""".format(page_types_text)
    
    user_prompt = f"Определи тип следующей страницы на основе упрощенного HTML:\n\n{html_structure}\n\nВерни ТОЛЬКО JSON."
    
    # Отправляем запрос к LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Запускаем синхронную функцию в executor, чтобы не блокировать event loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, llm_request, model, messages)
    
    return response


async def classify_from_parse_result(parse_result: dict, model: str = "gpt-4o-mini", max_length: int = None) -> dict:
    """
    Классифицирует страницу из результата парсинга (асинхронная версия)
    
    Args:
        parse_result: dict с результатом парсинга (должен содержать html_structure)
        model: Модель LLM для классификации
        max_length: Максимальное количество символов HTML для классификации (None = без ограничений)
        
    Returns:
        dict с результатом классификации
    """
    if 'html_structure' not in parse_result:
        raise ValueError("parse_result должен содержать поле 'html_structure'")
    
    return await classify_page(parse_result['html_structure'], model=model, max_length=max_length)


def save_classification_result(result: dict, output_path: str = "jsontests/classification_result.json"):
    """Сохраняет результат классификации в JSON файл"""
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Результат сохранен в {output_path}")


if __name__ == "__main__":
    """Пример использования"""
    
    # Загружаем результат парсинга из html_parser
    from html_parser import parse_for_ml
    
    async def main():
        test_url = "https://roswep.ru/product/teploobmenniki-dlya-ventilyacii/"
        
        print(f"Парсинг страницы: {test_url}")
        parse_result = await parse_for_ml(test_url)
        
        if 'error' in parse_result:
            print(f"Ошибка парсинга: {parse_result['error']}")
        else:
            print("\nКлассификация страницы...")
            print(f"URL: {parse_result.get('url', 'N/A')}")
            print()
            
            # Классифицируем (с ограничением 40000 символов для экономии токенов)
            classification = await classify_from_parse_result(
                parse_result, 
                model="grok-4-1-fast-non-reasoning",
                max_length=40000
            )
            
            # Парсим JSON из content (если LLM вернула JSON строку)
            try:
                classification_data = json.loads(classification["content"])
            except (json.JSONDecodeError, KeyError):
                classification_data = classification["content"]
            
            # Выводим результат
            print("Результат классификации:")
            print(json.dumps(classification_data, ensure_ascii=False, indent=2))
            print(f"\nСтоимость запроса: ${classification.get('cost', 0):.6f}")
            
            # Сохраняем
            full_result = {
                "url": parse_result.get('url'),
                "classification": classification_data,
                "cost": classification.get('cost', 0)
            }
            save_classification_result(full_result, "jsontests/classification_result.json")
    
    asyncio.run(main())
