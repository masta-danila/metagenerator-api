"""
Параллельный батчевый классификатор типов страниц (альтернативная реализация)

Отличия от batch_page_classifier.py:
- Все основные URLs обрабатываются параллельно
- Внутри каждого основного URL filtered URLs обрабатываются последовательно
- Глобальный кэш для repeated URLs
- Проще и быстрее при небольшом количестве основных URLs

ВАЖНО: HTML структура должна быть УЖЕ СЖАТА после parse_for_ml().
"""
import json
import asyncio
import sys
from typing import Dict, List
from pathlib import Path
from collections import defaultdict

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from site_parser.page_classifier import classify_page
from logger_config import get_html_parser_logger

logger = get_html_parser_logger()


async def process_main_url(
    spreadsheet_id: str,
    main_url: str,
    url_data: Dict,
    main_urls_cache: Dict,
    url_locks: Dict,
    global_semaphore: asyncio.Semaphore,
    model: str = "gpt-4o-mini",
    max_retries: int = 3,
    max_urls_per_type: int = 10,
    max_length: int = None
) -> Dict:
    """
    Обрабатывает один основной URL и его filtered URLs
    
    Args:
        spreadsheet_id: ID таблицы
        main_url: Основной URL
        url_data: Данные URL с queries и filtered_urls
        main_urls_cache: Кэш классификаций ТОЛЬКО для основных URLs
        url_locks: Словарь блокировок для каждого URL
        global_semaphore: Семафор для ограничения LLM запросов
        model: Модель LLM
        max_retries: Максимальное количество попыток
        max_urls_per_type: Максимальное количество URL для классификации
        max_length: Максимальная длина HTML для классификации
    
    Returns:
        Словарь с обновленными данными и статистикой
    """
    # Локальный кэш для filtered URLs этого основного URL
    local_filtered_cache = {}
    logger.info(f"[START] {main_url}")
    
    # Копируем данные
    import copy
    result_data = copy.deepcopy(url_data)
    
    queries = url_data.get('queries', [])
    
    # Получаем HTML основного URL
    main_html_structure = url_data.get('html_structure', '')
    main_has_error = 'error' in url_data or 'parsing_error' in url_data
    
    # Если нет на верхнем уровне, ищем в filtered_urls
    if not main_html_structure and not main_has_error and queries:
        for query_item in queries:
            if isinstance(query_item, dict):
                filtered_urls = query_item.get('filtered_urls', [])
                for item in filtered_urls:
                    if isinstance(item, dict) and item.get('url') == main_url:
                        if 'error' in item or 'parsing_error' in item:
                            main_has_error = True
                            break
                        main_html_structure = item.get('html_structure', '')
                        break
                if main_html_structure or main_has_error:
                    break
    
    # Классифицируем основной URL
    if main_has_error:
        logger.warning(f"[SKIP] {main_url}: есть ошибка парсинга")
        main_page_type = None
        total_cost = 0.0
    elif not main_html_structure:
        logger.warning(f"[SKIP] {main_url}: нет HTML структуры")
        main_page_type = None
        total_cost = 0.0
    else:
        # Используем блокировку для этого URL
        async with url_locks[main_url]:
            if main_url in main_urls_cache:
                logger.info(f"[CACHE] Основной URL из кэша")
                main_classification = main_urls_cache[main_url]
            else:
                async with global_semaphore:
                    for attempt in range(max_retries):
                        try:
                            logger.info(f"[CLASSIFY] Основной URL (попытка {attempt + 1}/{max_retries})")
                            classification = await classify_page(
                                main_html_structure, 
                                model=model, 
                                max_length=max_length
                            )
                            
                            # Парсим результат
                            content = classification["content"].strip()
                            
                            # Убираем markdown code blocks
                            if content.startswith("```"):
                                lines = content.split('\n')
                                start_idx = next((i for i, line in enumerate(lines) if line.strip().startswith("```")), 0) + 1
                                end_idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().startswith("```")), len(lines))
                                content = '\n'.join(lines[start_idx:end_idx]).strip()
                            
                            # Извлекаем JSON
                            first_brace = content.find('{')
                            last_brace = content.rfind('}')
                            if first_brace != -1 and last_brace != -1:
                                content = content[first_brace:last_brace + 1]
                            
                            result = json.loads(content)
                            main_classification = {
                                "url": main_url,
                                "page_type": result.get("page_type", "Неизвестно"),
                                "confidence": result.get("confidence", "low"),
                                "cost": classification.get("cost", 0)
                            }
                            
                            main_urls_cache[main_url] = main_classification
                            break
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"[ERROR] JSON parsing failed: {e}")
                            if attempt == max_retries - 1:
                                main_classification = {
                                    "url": main_url,
                                    "page_type": "Ошибка",
                                    "confidence": "low",
                                    "error": f"Failed to parse JSON: {e}",
                                    "cost": classification.get("cost", 0)
                                }
                                main_urls_cache[main_url] = main_classification
                        except Exception as e:
                            logger.error(f"[ERROR] Classification failed: {e}")
                            if attempt == max_retries - 1:
                                main_classification = {
                                    "url": main_url,
                                    "page_type": "Ошибка",
                                    "confidence": "low",
                                    "error": str(e),
                                    "cost": 0
                                }
                                main_urls_cache[main_url] = main_classification
        
        total_cost = main_classification.get('cost', 0)
        main_page_type = main_classification['page_type']
        
        logger.info(f"[MAIN] Тип: {main_page_type}")
        
        # Добавляем классификацию в результат
        result_data['page_classification'] = {
            "page_type": main_classification['page_type'],
            "confidence": main_classification['confidence']
        }
    
    # Собираем уникальные filtered URLs с приоритетом
    url_frequency = {}
    urls_by_query = []
    skipped_no_meta = 0
    
    for query_item in queries:
        if isinstance(query_item, dict):
            filtered_urls = query_item.get('filtered_urls', [])
            query_urls = []
            
            for item in filtered_urls:
                if isinstance(item, dict):
                    url_str = item.get('url', '')
                    competitor_meta = item.get('competitor_meta', {})
                    has_all_meta = (
                        competitor_meta.get('title') and 
                        competitor_meta.get('description') and 
                        competitor_meta.get('h1')
                    )
                    
                    if url_str and has_all_meta:
                        url_frequency[url_str] = url_frequency.get(url_str, 0) + 1
                        query_urls.append(url_str)
                    elif url_str:
                        skipped_no_meta += 1
                elif item:
                    skipped_no_meta += 1
            
            if query_urls:
                urls_by_query.append(query_urls)
    
    # Сортируем по частоте
    sorted_by_frequency = sorted(url_frequency.items(), key=lambda x: x[1], reverse=True)
    priority_urls = [url for url, count in sorted_by_frequency if count > 1]
    seen_urls = set(priority_urls)
    
    # Round-robin для остальных
    remaining_urls = []
    if urls_by_query:
        max_len = max(len(query_urls) for query_urls in urls_by_query)
        for i in range(max_len):
            for query_urls in urls_by_query:
                if i < len(query_urls):
                    url = query_urls[i]
                    if url not in seen_urls:
                        remaining_urls.append(url)
                        seen_urls.add(url)
    
    all_filtered_urls = priority_urls + remaining_urls
    
    logger.info(f"[COMPETITORS] {len(all_filtered_urls)} уникальных (приоритет: {len(priority_urls)}, остальные: {len(remaining_urls)})")
    if skipped_no_meta > 0:
        logger.info(f"[SKIPPED] {skipped_no_meta} без полных метатегов")
    
    # ПОСЛЕДОВАТЕЛЬНО классифицируем filtered URLs
    same_type_count = 0
    total_classified = 0
    
    for competitor_url in all_filtered_urls:
        # Проверяем лимит
        if same_type_count >= max_urls_per_type:
            logger.info(f"[LIMIT] Достигнут лимит {max_urls_per_type}")
            break
        
        # Ищем HTML в queries
        competitor_html = ''
        has_error = False
        
        for query_item in queries:
            if isinstance(query_item, dict):
                filtered_urls_list = query_item.get('filtered_urls', [])
                for item in filtered_urls_list:
                    if isinstance(item, dict) and item.get('url') == competitor_url:
                        if 'error' in item or 'parsing_error' in item:
                            has_error = True
                            break
                        competitor_html = item.get('html_structure', '')
                        break
                if competitor_html or has_error:
                    break
        
        if has_error or not competitor_html:
            continue
        
        # Проверяем локальный кэш (без блокировки, т.к. локальный для этого потока)
        if competitor_url in local_filtered_cache:
            logger.info(f"[CACHE] {competitor_url}")
            competitor_classification = local_filtered_cache[competitor_url]
        else:
            async with global_semaphore:
                for attempt in range(max_retries):
                    try:
                        logger.info(f"[CLASSIFY {total_classified + 1}] {competitor_url}")
                        classification = await classify_page(
                            competitor_html, 
                            model=model, 
                            max_length=max_length
                        )
                        
                        # Парсим (тот же код что выше)
                        content = classification["content"].strip()
                        
                        if content.startswith("```"):
                            lines = content.split('\n')
                            start_idx = next((i for i, line in enumerate(lines) if line.strip().startswith("```")), 0) + 1
                            end_idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().startswith("```")), len(lines))
                            content = '\n'.join(lines[start_idx:end_idx]).strip()
                        
                        first_brace = content.find('{')
                        last_brace = content.rfind('}')
                        if first_brace != -1 and last_brace != -1:
                            content = content[first_brace:last_brace + 1]
                        
                        result = json.loads(content)
                        competitor_classification = {
                            "url": competitor_url,
                            "page_type": result.get("page_type", "Неизвестно"),
                            "confidence": result.get("confidence", "low"),
                            "cost": classification.get("cost", 0)
                        }
                        
                        local_filtered_cache[competitor_url] = competitor_classification
                        break
                        
                    except Exception as e:
                        if attempt == max_retries - 1:
                            competitor_classification = {
                                "url": competitor_url,
                                "page_type": "Ошибка",
                                "confidence": "low",
                                "error": str(e),
                                "cost": 0
                            }
                            local_filtered_cache[competitor_url] = competitor_classification
        
        total_cost += competitor_classification.get('cost', 0)
        total_classified += 1
        
        page_type = competitor_classification['page_type']
        is_same_type = (main_page_type is None or page_type == main_page_type)
        
        if is_same_type:
            same_type_count += 1
            if main_page_type:
                logger.info(f"[MATCH {same_type_count}/{max_urls_per_type}] {page_type}")
            else:
                logger.info(f"[CLASSIFIED {same_type_count}/{max_urls_per_type}] {page_type}")
        else:
            logger.info(f"[SKIP] {page_type} (не совпадает с '{main_page_type}')")
    
    # Добавляем классификации в filtered_urls
    for query_idx, query_item in enumerate(queries):
        if isinstance(query_item, dict):
            filtered_urls_list = query_item.get('filtered_urls', [])
            updated_filtered = []
            
            for item in filtered_urls_list:
                if isinstance(item, dict):
                    item_url = item.get('url', '')
                    
                    # Проверяем локальный кэш filtered URLs или кэш основных URLs
                    classification = None
                    if item_url in local_filtered_cache:
                        classification = local_filtered_cache[item_url]
                    elif item_url in main_urls_cache:
                        classification = main_urls_cache[item_url]
                    
                    if classification:
                        item_copy = item.copy()
                        item_copy['page_classification'] = {
                            "page_type": classification['page_type'],
                            "confidence": classification['confidence']
                        }
                        updated_filtered.append(item_copy)
                    else:
                        updated_filtered.append(item)
                else:
                    updated_filtered.append(item)
            
            result_data['queries'][query_idx]['filtered_urls'] = updated_filtered
    
    logger.info(f"[DONE] {main_url}: classified={total_classified}, same_type={same_type_count}, cost=${total_cost:.4f}")
    
    return {
        'data': result_data,
        'cost': total_cost,
        'classified': total_classified,
        'same_type': same_type_count
    }


async def classify_batch(
    data: Dict,
    model: str = "gpt-4o-mini",
    max_concurrent: int = 50,
    max_retries: int = 3,
    max_urls_per_type: int = 10,
    max_length: int = None
) -> Dict:
    """
    Параллельная батчевая классификация страниц
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {...}}}}
        model: Модель LLM
        max_concurrent: Максимальное количество одновременных LLM запросов
        max_retries: Максимальное количество попыток
        max_urls_per_type: Максимальное количество URL для классификации
        max_length: Максимальная длина HTML
    
    Returns:
        Обновленный словарь с классификациями
    """
    logger.info("ПАРАЛЛЕЛЬНАЯ БАТЧЕВАЯ КЛАССИФИКАЦИЯ")
    logger.info(f"Модель: {model}")
    logger.info(f"Max concurrent LLM requests: {max_concurrent}")
    logger.info(f"Попыток на URL: {max_retries}")
    logger.info(f"URL на основной URL: {max_urls_per_type}")
    if max_length:
        logger.info(f"Обрезка HTML до: {max_length} символов")
    
    # Глобальные структуры
    main_urls_cache = {}  # Кэш ТОЛЬКО для основных URLs
    url_locks = defaultdict(asyncio.Lock)  # {url: Lock}
    global_semaphore = asyncio.Semaphore(max_concurrent)
    
    # Копируем данные
    import copy
    result_data = copy.deepcopy(data)
    
    # Собираем все задачи
    tasks = []
    
    for spreadsheet_id, spreadsheet_info in data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        
        for main_url, url_data in urls_dict.items():
            task = asyncio.create_task(
                process_main_url(
                    spreadsheet_id,
                    main_url,
                    url_data,
                    main_urls_cache,
                    url_locks,
                    global_semaphore,
                    model,
                    max_retries,
                    max_urls_per_type,
                    max_length
                )
            )
            tasks.append((spreadsheet_id, main_url, task))
    
    logger.info(f"Запущено {len(tasks)} параллельных задач")
    
    # Ждем завершения всех задач
    results = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)
    
    # Обновляем результаты
    total_cost = 0.0
    total_classified = 0
    total_same_type = 0
    
    for (spreadsheet_id, main_url, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"[ERROR] {main_url}: {result}")
            continue
        
        result_data[spreadsheet_id]['urls'][main_url] = result['data']
        
        # Добавляем стоимость классификации (единый формат)
        result_data[spreadsheet_id]['urls'][main_url]['classification_cost'] = {
            'api_requests': result['classified'],
            'cost': round(result['cost'], 6),
            'currency': 'USD'
        }
        
        total_cost += result['cost']
        total_classified += result['classified']
        total_same_type += result['same_type']
    
    logger.info("ИТОГО:")
    logger.info(f"- Классифицировано URL: {total_classified}")
    logger.info(f"- Совпадающего типа: {total_same_type}")
    logger.info(f"- Основных URLs в кэше: {len(main_urls_cache)}")
    logger.info(f"- Общая стоимость: ${total_cost:.4f}")
    
    return result_data


# Тестовый блок
if __name__ == "__main__":
    test_file = Path(__file__).parent.parent / "jsontests" / "step9_meta_extracted.json"
    
    if not test_file.exists():
        test_file = Path(__file__).parent.parent / "jsontests" / "step7_meta_extracted.json"
    
    if not test_file.exists():
        logger.error(f"Тестовый файл не найден: {test_file}")
        sys.exit(1)
    
    with open(test_file, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    # Запускаем классификацию
    result = asyncio.run(
        classify_batch(
            test_data,
            model="grok-4-1-fast-non-reasoning",
            max_concurrent=17,  # По количеству основных URLs
            max_urls_per_type=5,
            max_length=40000  # Увеличено с 4000 до 40000 для правильной классификации
        )
    )
    
    # Сохраняем результат
    output_file = Path(__file__).parent.parent / "jsontests" / "step10_pages_classified_parallel.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результат сохранен: {output_file}")
