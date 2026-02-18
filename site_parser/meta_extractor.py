"""
Извлечение метатегов (title, description, h1) из HTML структуры
"""
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from logger_config import get_meta_extractor_logger
    logger = get_meta_extractor_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def extract_meta(html_structure: str) -> dict:
    """
    Извлекает метатеги из HTML структуры
    
    Args:
        html_structure: HTML строка (упрощённая структура)
        
    Returns:
        Словарь с метатегами: {
            'title': str или None,
            'description': str или None,
            'h1': str или None
        }
    """
    if not html_structure:
        return {
            'title': None,
            'description': None,
            'h1': None
        }
    
    soup = BeautifulSoup(html_structure, 'lxml')
    
    # Извлекаем title
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else None
    
    # Извлекаем description из meta тега
    description = None
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if not meta_desc:
        meta_desc = soup.find('meta', attrs={'property': 'og:description'})
    if meta_desc and meta_desc.get('content'):
        description = meta_desc.get('content').strip()
    
    # Извлекаем первый h1
    h1_tag = soup.find('h1')
    h1 = h1_tag.get_text(strip=True) if h1_tag else None
    
    return {
        'title': title,
        'description': description,
        'h1': h1
    }


def process_html_for_classification(html_structure: str) -> dict:
    """
    УСТАРЕВШАЯ: Извлекает метатеги из HTML структуры
    
    ВАЖНО: HTML должен быть УЖЕ СЖАТ после parse_for_ml().
    Для новых проектов используйте extract_meta() напрямую.
    
    Эта функция оставлена для обратной совместимости.
    
    Args:
        html_structure: Сжатая HTML строка
        
    Returns:
        Словарь только с метатегами: {
            'meta': {'title': str, 'description': str, 'h1': str}
        }
    """
    if not html_structure:
        return {
            'meta': {
                'title': None,
                'description': None,
                'h1': None
            }
        }
    
    # Извлекаем метатеги из уже сжатого HTML
    meta_tags = extract_meta(html_structure)
    
    return {
        'meta': meta_tags
    }


def extract_meta_from_dict(data: dict) -> dict:
    """
    Извлекает метатеги из словаря с ключом 'html_structure'
    
    Args:
        data: Словарь с ключом 'html_structure'
        
    Returns:
        Словарь с метатегами и оригинальным URL
    """
    html_structure = data.get('html_structure', '')
    url = data.get('url', '')
    
    meta_tags = extract_meta(html_structure)
    
    return {
        'url': url,
        **meta_tags
    }


def save_to_json(data, filename="jsontests/meta_result.json"):
    """
    Сохраняет результаты в JSON файл
    
    Args:
        data: Данные для сохранения
        filename: Путь к файлу
        
    Returns:
        Путь к файлу
    """
    import os
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в файл: {filename}")
    return filename


if __name__ == "__main__":
    # Читаем parse_result.json
    input_file = "jsontests/parse_result.json"
    logger.info(f"Чтение файла: {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Файл загружен")
        logger.info(f"URL: {data.get('url', 'N/A')}")
        
        # Получаем HTML структуру (уже сжатую после parse_for_ml)
        html_structure = data.get('html_structure', '')
        
        if not html_structure:
            logger.error("HTML структура отсутствует в файле")
            exit(1)
        
        # Извлекаем метатеги из уже сжатого HTML
        logger.info("Извлечение метатегов из сжатого HTML...")
        meta_tags = extract_meta(html_structure)
        
        # Выводим результат
        logger.info("Извлечённые метатеги:")
        logger.info(f"Title: {meta_tags['title']}")
        logger.info(f"Description: {meta_tags['description']}")
        logger.info(f"H1: {meta_tags['h1']}")
        
        logger.info(f"Размер HTML структуры: {len(html_structure):,} символов")
        logger.info("(HTML уже сжат после parse_for_ml)")
        
        # Формируем результат для сохранения
        result = {
            'url': data.get('url', ''),
            'meta': meta_tags
        }
        
        # Сохраняем в JSON
        output_file = "jsontests/meta_result.json"
        save_to_json(result, output_file)
        
        logger.info(f"✅ Метатеги сохранены в {output_file}")
        
    except FileNotFoundError:
        logger.error(f"Файл не найден: {input_file}")
        logger.error("Сначала запустите: python site_parser/html_parser.py")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
