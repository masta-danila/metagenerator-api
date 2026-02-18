"""
Парсер статей с использованием BeautifulSoup и httpx (асинхронный)
"""
import json
import os
import sys
import asyncio
import warnings
import httpx
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

try:
    from logger_config import get_html_parser_logger
    logger = get_html_parser_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Подавляем предупреждения SSL
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Импортируем функцию очистки HTML из html_cleaner
try:
    from .html_cleaner import compress_html_for_classification
except ImportError:
    from html_cleaner import compress_html_for_classification


def save_to_json(data, filename=None, output_dir="jsontests"):
    """
    Сохраняет результаты парсинга в JSON файл
    
    Args:
        data: Словарь с данными для сохранения
        filename: Имя файла (по умолчанию parse_result.json)
        output_dir: Директория для сохранения (по умолчанию jsontests)
        
    Returns:
        Путь к сохранённому файлу
    """
    # Создаём директорию, если не существует
    os.makedirs(output_dir, exist_ok=True)
    
    # Используем фиксированное имя файла
    if not filename:
        filename = "parse_result.json"
    
    filepath = os.path.join(output_dir, filename)
    
    # Сохраняем
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в файл: {filepath}")
    return filepath


async def parse_for_ml(url, client=None, use_proxy=False, proxy_manager=None, min_html_length=100):
    """
    Асинхронный парсинг для ML-классификации типа страницы
    
    Извлекает упрощённую HTML-структуру (без атрибутов class/id)
    
    Args:
        url: URL страницы для парсинга
        client: httpx.AsyncClient (опционально, для переиспользования)
        use_proxy: использовать ли прокси
        proxy_manager: экземпляр ProxyManager (опционально)
        min_html_length: минимальная длина HTML (символов) для валидного результата
        
    Returns:
        Словарь с данными для ML-модели или None при ошибке
    """
    # Если клиент не передан, создаём временный
    if client is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # Формируем настройки клиента
        client_kwargs = {
            'timeout': 30.0,
            'follow_redirects': True,
            'verify': False,
            'headers': headers
        }
        
        # Добавляем прокси если нужно
        if use_proxy and proxy_manager:
            proxy = proxy_manager.get_random_proxy()
            if proxy:
                proxy_url = proxy_manager.get_httpx_proxy_url(proxy)
                client_kwargs['proxy'] = proxy_url
                logger.info(f"Используется прокси: {proxy['ip']}:{proxy['port']}")
        
        async with httpx.AsyncClient(**client_kwargs) as temp_client:
            return await _parse_with_client(url, temp_client, min_html_length)
    else:
        return await _parse_with_client(url, client, min_html_length)


async def _parse_with_client(url, client, min_html_length=100):
    """
    Внутренняя функция парсинга с переданным клиентом
    
    Args:
        url: URL для парсинга
        client: httpx.AsyncClient
        min_html_length: минимальная длина HTML для валидного результата
    
    Returns:
        Словарь с результатом или словарь с ошибкой
    """
    try:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    except Exception as e:
        logger.error(f"Ошибка при запросе к {url}: {type(e).__name__}: {e}")
        return {
            'url': url,
            'error': f'{type(e).__name__}: {e}'
        }
    
    if not html:
        logger.error(f"Пустой HTML для {url}")
        return {
            'url': url,
            'error': 'Empty HTML response'
        }
    
    soup = BeautifulSoup(html, 'lxml')
    
    # Удаляем шум (скрипты, стили, SVG, iframe)
    for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe']):
        tag.decompose()
    
    # Упрощаем HTML: удаляем атрибуты, но оставляем важные
    for tag in soup.find_all(True):
        if tag.name == 'img' and tag.get('src'):
            # Для img оставляем только src
            tag.attrs = {'src': tag['src']}
        elif tag.name == 'meta':
            # Для meta оставляем name/property и content
            new_attrs = {}
            if tag.get('name'):
                new_attrs['name'] = tag['name']
            if tag.get('property'):
                new_attrs['property'] = tag['property']
            if tag.get('content'):
                new_attrs['content'] = tag['content']
            tag.attrs = new_attrs
        elif tag.name in ['title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # Для заголовков и title оставляем все как есть (без атрибутов)
            tag.attrs = {}
        else:
            # Для остальных тегов удаляем все атрибуты
            tag.attrs = {}
    
    # Получаем полный HTML с head и body
    html_structure = str(soup)
    
    # Применяем агрессивную очистку от мусора (табуляции, переносы, комментарии)
    html_structure = compress_html_for_classification(html_structure)
    
    # Проверяем минимальную длину HTML
    if len(html_structure) < min_html_length:
        logger.error(f"HTML слишком короткий для {url}: {len(html_structure)} < {min_html_length} символов")
        return {
            'url': url,
            'error': f'HTML too short: {len(html_structure)} < {min_html_length} characters'
        }
    
    # Возвращаем результат
    return {
        'url': url,
        'html_structure': html_structure,  # Очищенная HTML структура
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # URL можно передать как аргумент
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://sn22.ru/catalog/payanye-teploobmenniki/_ridan/"
    
    logger.info("Парсинг HTML структуры страницы...")
    logger.info(f"URL: {test_url}")
    
    # Проверяем наличие proxy.txt и используем прокси если есть
    proxy_file = Path(__file__).parent / "proxy.txt"
    use_proxy = False
    proxy_manager = None
    
    if proxy_file.exists():
        try:
            from .proxy_manager import ProxyManager
        except ImportError:
            from proxy_manager import ProxyManager
        
        proxy_manager = ProxyManager()
        if proxy_manager.proxies:
            use_proxy = True
            logger.info(f"Найден файл proxy.txt - используем прокси ({len(proxy_manager.proxies)} доступно)")
        else:
            logger.info("Файл proxy.txt найден, но прокси не загружены")
    else:
        logger.info("Файл proxy.txt не найден - работаем без прокси")
    
    result = asyncio.run(parse_for_ml(
        test_url, 
        use_proxy=use_proxy, 
        proxy_manager=proxy_manager,
        min_html_length=1000  # Минимальная длина HTML в символах
    ))
    
    if result and 'error' not in result:
        logger.info("Успешно распарсено")
        logger.info(f"HTML структура: {len(result['html_structure'])} символов")
        logger.info(f"Первые 500 символов:")
        logger.info(result['html_structure'][:500] + "...")
        
        # Сохраняем результат в JSON
        save_to_json(result)
    elif result and 'error' in result:
        logger.error(f"Ошибка при парсинге: {result['error']}")
    else:
        logger.error("Неизвестная ошибка при парсинге")
