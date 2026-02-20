"""
Батчевый процессор для парсинга HTML структуры отфильтрованных URL
"""
import json
import asyncio
import httpx
import sys
from typing import Dict, List, Set
from pathlib import Path
from collections import defaultdict

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from site_parser.html_parser import parse_for_ml
from logger_config import get_html_parser_logger

logger = get_html_parser_logger()


async def parse_url_with_retry(
    url: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    min_html_length: int = 100,
    url_index: int = 0,
    total_urls: int = 0,
    use_proxy: bool = False,
    proxy_manager = None
) -> Dict:
    """
    Парсит URL с повторными попытками при ошибках
    
    Args:
        url: URL для парсинга
        client: HTTP клиент (базовый, без прокси)
        semaphore: Семафор для ограничения одновременных запросов
        max_retries: Максимальное количество попыток
        min_html_length: Минимальная длина HTML для валидного результата
        use_proxy: использовать ли прокси
        proxy_manager: менеджер прокси для ротации
    
    Returns:
        Словарь с результатом парсинга
    """
    async with semaphore:
        # Выбираем случайный прокси для ЭТОГО URL
        current_client = client
        if use_proxy and proxy_manager:
            proxy = proxy_manager.get_random_proxy()
            if proxy:
                proxy_url = proxy_manager.get_httpx_proxy_url(proxy)
                logger.info(f"→ Прокси для запроса: {proxy['ip']}:{proxy['port']}")
                # Создаем новый клиент с этим прокси
                current_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0),
                    follow_redirects=True,
                    proxy=proxy_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    }
                )
        
        try:
            for attempt in range(max_retries):
                try:
                    progress = f"[{url_index}/{total_urls}]" if total_urls > 0 else ""
                    logger.info(f"{progress} [{attempt + 1}/{max_retries}] Парсинг: {url}")
                    
                    # Парсим страницу
                    parse_result = await parse_for_ml(url, current_client, min_html_length=min_html_length)
                    
                    # Проверяем результат
                    if parse_result is None:
                        raise Exception("Функция parse_for_ml вернула None")
                    
                    if 'error' in parse_result:
                        raise Exception(f"Ошибка парсинга: {parse_result['error']}")
                    
                    logger.info(f"[OK] {url}")
                    return parse_result
                    
                except Exception as e:
                    logger.error(f"[ОШИБКА] Попытка {attempt + 1} для {url}: {str(e)}")
                    
                    if attempt == max_retries - 1:
                        # Последняя попытка - возвращаем ошибку
                        return {
                            "url": url,
                            "error": str(e)
                        }
                    
                    # Ждем перед следующей попыткой
                    await asyncio.sleep(2 * (attempt + 1))
            
            # На случай непредвиденной ситуации
            return {
                "url": url,
                "error": "Unknown error - no result returned"
            }
        finally:
            # Закрываем клиент если создали новый для прокси
            if use_proxy and proxy_manager and current_client != client:
                await current_client.aclose()


async def parse_filtered_urls_batch(
    data: Dict,
    max_concurrent: int = 5,
    max_retries: int = 3,
    domain_pause: float = 0.5,
    use_proxy: bool = False,
    proxy_manager=None,
    min_html_length: int = 100
) -> Dict:
    """
    Батчевый парсинг HTML структуры отфильтрованных URL
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {...}}}}
        max_concurrent: Максимальное количество одновременных запросов
        max_retries: Максимальное количество попыток при ошибках
        domain_pause: Пауза между запросами к одному домену (секунды)
        use_proxy: использовать ли прокси
        proxy_manager: экземпляр ProxyManager (опционально)
        min_html_length: Минимальная длина HTML (символов) для валидного результата
    
    Returns:
        Обновленный словарь с добавленными HTML структурами
    """
    logger.info("Начало батчевого парсинга HTML отфильтрованных URL:")
    
    # Автоматически загружаем прокси если use_proxy=True но proxy_manager=None
    if use_proxy and proxy_manager is None:
        proxy_file = Path(__file__).parent / "proxy.txt"
        if proxy_file.exists():
            try:
                from proxy_manager import ProxyManager
                proxy_manager = ProxyManager()
                if proxy_manager.proxies:
                    logger.info(f"Автоматически загружено {len(proxy_manager.proxies)} прокси из {proxy_file}")
                else:
                    logger.warning("proxy.txt пустой - работаем без прокси")
                    use_proxy = False
            except Exception as e:
                logger.warning(f"Не удалось загрузить прокси: {e}")
                logger.info("Работаем без прокси")
                use_proxy = False
        else:
            logger.info("proxy.txt не найден - работаем без прокси")
            use_proxy = False
    
    logger.info(f"- Одновременных запросов: {max_concurrent}")
    logger.info(f"- Попыток на URL: {max_retries}")
    logger.info(f"- Пауза между запросами к домену: {domain_pause}s")
    logger.info(f"- Минимальная длина HTML: {min_html_length} символов")
    if use_proxy and proxy_manager:
        logger.info(f"- Используются прокси: {len(proxy_manager.proxies)} доступно (с ротацией)")
    
    # Создаем семафор для ограничения одновременных запросов
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Копируем исходные данные
    import copy
    result_data = copy.deepcopy(data)
    
    # Собираем все уникальные URL для парсинга: основные URL + filtered_urls
    all_urls_to_parse = set()
    main_urls_set = set()  # Основные URL
    url_to_queries = defaultdict(list)  # Маппинг URL -> список запросов, где он встречается
    url_to_main_urls = defaultdict(list)  # Маппинг URL -> список основных URL, которым он принадлежит
    
    for spreadsheet_id, spreadsheet_info in data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        
        for main_url, url_data in urls_dict.items():
            # Добавляем основной URL для парсинга
            all_urls_to_parse.add(main_url)
            main_urls_set.add(main_url)
            url_to_main_urls[main_url].append({
                'spreadsheet_id': spreadsheet_id,
                'main_url': main_url
            })
            
            # Собираем filtered_urls
            queries = url_data.get('queries', [])
            
            for query_idx, query_item in enumerate(queries):
                if isinstance(query_item, dict):
                    filtered_urls = query_item.get('filtered_urls', [])
                    
                    for filtered_url_item in filtered_urls:
                        # Извлекаем URL (может быть строкой или словарем)
                        if isinstance(filtered_url_item, dict):
                            filtered_url = filtered_url_item.get('url', '')
                        else:
                            filtered_url = filtered_url_item
                        
                        if filtered_url:  # Пропускаем пустые URL
                            all_urls_to_parse.add(filtered_url)
                            url_to_queries[filtered_url].append({
                                'spreadsheet_id': spreadsheet_id,
                                'main_url': main_url,
                                'query_index': query_idx
                            })
    
    logger.info(f"Собрано {len(main_urls_set)} основных URL для парсинга")
    logger.info(f"Собрано {len(all_urls_to_parse) - len(main_urls_set)} уникальных отфильтрованных URL для парсинга")
    logger.info(f"ВСЕГО для парсинга: {len(all_urls_to_parse)} URL")
    
    # Создаем HTTP клиент
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Формируем настройки базового клиента БЕЗ прокси
    # Прокси будут ротироваться для каждого URL отдельно внутри parse_url_with_retry
    client_kwargs = {
        'timeout': 30.0,
        'follow_redirects': True,
        'verify': False,
        'headers': headers
    }
    
    if use_proxy and proxy_manager:
        logger.info(f"Режим ротации прокси: каждый URL → новый прокси из {len(proxy_manager.proxies)} доступных")
    
    async with httpx.AsyncClient(**client_kwargs) as client:
        
        # Парсим все URL с контролем домена
        domain_last_request = {}
        tasks = []
        total_urls = len(all_urls_to_parse)
        
        for idx, url in enumerate(all_urls_to_parse, 1):
            # Извлекаем домен
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
            # Проверяем, нужно ли подождать для этого домена
            if domain in domain_last_request:
                time_since_last = asyncio.get_event_loop().time() - domain_last_request[domain]
                if time_since_last < domain_pause:
                    await asyncio.sleep(domain_pause - time_since_last)
            
            # Запускаем задачу с индексом и прокси
            task = parse_url_with_retry(url, client, semaphore, max_retries, min_html_length, idx, total_urls, use_proxy, proxy_manager)
            tasks.append((url, task))
            
            # Обновляем время последнего запроса к домену
            domain_last_request[domain] = asyncio.get_event_loop().time()
        
        # Выполняем все задачи
        results = await asyncio.gather(*[task for _, task in tasks])
        
        # Создаем маппинг URL -> результат парсинга
        parsed_data = {}
        successful = 0
        failed = 0
        
        for (url, _), result in zip(tasks, results):
            parsed_data[url] = result
            
            if 'error' in result:
                failed += 1
                logger.warning(f"[FAILED] {url}: {result['error']}")
            else:
                successful += 1
        
        logger.info(f"Парсинг завершен:")
        logger.info(f"- Успешно: {successful}")
        logger.info(f"- Ошибок: {failed}")
        
        # Добавляем результаты парсинга для основных URL
        for url in main_urls_set:
            html_data = parsed_data.get(url, {"error": "Not processed"})
            
            locations = url_to_main_urls.get(url, [])
            for location in locations:
                spreadsheet_id = location['spreadsheet_id']
                main_url = location['main_url']
                
                # Добавляем HTML структуру на верхний уровень url_data
                result_data[spreadsheet_id]['urls'][main_url]['html_structure'] = html_data.get('html_structure', '')
                if html_data.get('error'):
                    result_data[spreadsheet_id]['urls'][main_url]['parsing_error'] = html_data.get('error')
        
        logger.info(f"Добавлена HTML структура для {len(main_urls_set)} основных URL")
        
        # Добавляем результаты парсинга для filtered_urls
        for url, locations in url_to_queries.items():
            html_data = parsed_data.get(url, {"error": "Not processed"})
            
            for location in locations:
                spreadsheet_id = location['spreadsheet_id']
                main_url = location['main_url']
                query_idx = location['query_index']
                
                # Получаем query объект
                query_obj = result_data[spreadsheet_id]['urls'][main_url]['queries'][query_idx]
                
                # Обновляем filtered_urls - добавляем HTML данные к каждому URL
                if 'filtered_urls' in query_obj:
                    updated_filtered = []
                    
                    for filtered_url_item in query_obj['filtered_urls']:
                        # Извлекаем URL (может быть строкой или словарем)
                        if isinstance(filtered_url_item, dict):
                            current_url = filtered_url_item.get('url', '')
                        else:
                            current_url = filtered_url_item
                        
                        # Ищем данные парсинга для этого URL
                        html_data_for_url = parsed_data.get(current_url, {"error": "Not found"})
                        
                        # Добавляем данные парсинга
                        updated_item = {
                            'url': current_url,
                            'html_structure': html_data_for_url.get('html_structure', '')
                        }
                        
                        # Добавляем ошибку, если есть
                        if html_data_for_url.get('error'):
                            updated_item['error'] = html_data_for_url['error']
                        
                        updated_filtered.append(updated_item)
                    
                    result_data[spreadsheet_id]['urls'][main_url]['queries'][query_idx]['filtered_urls'] = updated_filtered
    
    return result_data


def save_results(
    results: Dict,
    output_path: str = "jsontests/batch_html_parsed_results.json"
) -> None:
    """
    Сохраняет результаты парсинга в JSON файл
    
    Args:
        results: Словарь с результатами парсинга
        output_path: Путь для сохранения файла
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в {output_path}")


if __name__ == "__main__":
    """
    Тестовый запуск батчевого парсинга HTML
    """
    async def test():
        # Определяем пути относительно корня проекта
        project_root = Path(__file__).parent.parent
        input_file = project_root / "jsontests" / "xmlriver_batch_results.json"
        output_file = project_root / "jsontests" / "step6_html_parsed.json"
        
        # Загружаем данные
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Проверяем наличие proxy.txt
        proxy_file = Path(__file__).parent / "proxy.txt"
        use_proxy = False
        proxy_manager = None
        
        if proxy_file.exists():
            try:
                from proxy_manager import ProxyManager
                proxy_manager = ProxyManager()
                if proxy_manager.proxies:
                    use_proxy = True
                    logger.info(f"Используем прокси: {len(proxy_manager.proxies)} доступно")
            except Exception as e:
                logger.warning(f"Не удалось загрузить прокси: {e}")
        
        # Запускаем батчевый парсинг
        results = await parse_filtered_urls_batch(
            data=data,
            max_concurrent=100,    # 100 одновременных запросов
            max_retries=2,         # 3 попытки на каждый URL
            domain_pause=0.5,      # 0.5 сек пауза между запросами к одному домену
            use_proxy=use_proxy,
            proxy_manager=proxy_manager,
            min_html_length=1000    # Минимальная длина HTML в символах
        )
        
        # Сохраняем результаты
        save_results(results, str(output_file))
    
    asyncio.run(test())
