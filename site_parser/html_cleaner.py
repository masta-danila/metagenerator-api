"""
Модуль для очистки и упрощения HTML структуры

Основные функции:
- compress_html_for_classification - агрессивная очистка HTML для ML-классификации
"""

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from logger_config import get_html_parser_logger
    logger = get_html_parser_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def compress_html_for_classification(html_structure: str) -> str:
    """
    Упрощает HTML для классификации: оставляет теги с текстом, но убирает атрибуты и мусор
    
    Оставляет:
    - Все теги с их иерархией
    - Текстовое содержимое внутри тегов
    - Meta теги с атрибутами name/property/content
    
    Удаляет:
    - Все атрибуты (class, id, style, data-*, onclick и т.д.)
    - Скрипты, стили, счетчики, трекеры
    - SVG, iframe, link
    - Комментарии
    - Экранированный HTML
    - Табуляции и лишние пробелы
    
    Args:
        html_structure: Полная HTML структура страницы
        
    Returns:
        Чистая HTML структура с тегами и текстом, но без атрибутов
    """
    if not html_structure:
        return "Empty HTML"
    
    try:
        soup = BeautifulSoup(html_structure, 'lxml')
        
        # Удаляем весь мусор: скрипты, стили, счетчики, трекеры (но оставляем meta и title)
        for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe', 'link']):
            tag.decompose()
        
        # Удаляем все атрибуты у всех тегов, кроме meta (оставляем name/property и content)
        for tag in soup.find_all(True):
            if tag.name == 'meta':
                # Для meta оставляем только name/property и content
                new_attrs = {}
                if tag.get('name'):
                    new_attrs['name'] = tag['name']
                if tag.get('property'):
                    new_attrs['property'] = tag['property']
                if tag.get('content'):
                    new_attrs['content'] = tag['content']
                tag.attrs = new_attrs
            else:
                # Для остальных тегов удаляем все атрибуты
                tag.attrs = {}
        
        # Удаляем текстовые узлы, содержащие экранированный HTML (мусор)
        for element in soup.find_all(string=True):
            text = str(element)
            # Если текст содержит экранированные теги - удаляем его полностью
            if '&lt;' in text or '&gt;' in text or 'class=' in text or 'id=' in text:
                element.extract()
        
        # Получаем чистый HTML с head и body (для сохранения meta и title)
        clean_html = str(soup)
        
        # Дополнительная очистка от экранированного HTML и мусора (если остался)
        clean_html = re.sub(r'&lt;[^&]*&gt;', '', clean_html)  # Убираем &lt;...&gt;
        clean_html = re.sub(r'&lt;', '', clean_html)  # Убираем одиночные &lt;
        clean_html = re.sub(r'&gt;', '', clean_html)  # Убираем одиночные &gt;
        clean_html = re.sub(r'&amp;', '&', clean_html)  # Декодируем &amp;
        clean_html = re.sub(r'class="[^"]*"', '', clean_html)  # Убираем class="..."
        clean_html = re.sub(r'id="[^"]*"', '', clean_html)  # Убираем id="..."
        clean_html = re.sub(r'style="[^"]*"', '', clean_html)  # Убираем style="..."
        clean_html = re.sub(r'data-[a-zA-Z-]+="[^"]*"', '', clean_html)  # Убираем data-*
        
        # Убираем HTML комментарии
        clean_html = re.sub(r'<!--.*?-->', '', clean_html, flags=re.DOTALL)
        
        # Убираем табуляции и заменяем их на пробелы
        clean_html = clean_html.replace('\t', ' ')
        
        # Убираем множественные пробелы и пустые строки
        clean_html = re.sub(r'\n\s*\n', '\n', clean_html)
        clean_html = re.sub(r'  +', ' ', clean_html)
        
        return clean_html
        
    except Exception as e:
        logger.error(f"Ошибка упрощения HTML: {e}")
        # В случае ошибки возвращаем первые 5000 символов оригинала
        return html_structure[:5000] + "..." if len(html_structure) > 5000 else html_structure
