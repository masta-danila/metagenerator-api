"""
Массовая проверка частотности запросов через XMLRiver Wordstat API.

Принимает структуру sheets_data.json и добавляет частотность для каждого запроса.
Использует асинхронность с семафором для контроля параллелизма.
"""
import os
import sys
import json
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import get_search_logger
from xmlriver.wordstat_frequency import get_query_frequency

logger = get_search_logger()

# Загружаем переменные окружения
load_dotenv()


async def process_sheets_data_wordstat(
    sheets_data: Dict,
    default_region: int = 213,
    device: str = "desktop",
    exact_match: bool = True,
    max_concurrent: int = 10,
    task_start_delay: float = 0.0,
) -> Dict:
    """
    Обрабатывает все запросы из sheets_data и добавляет частотность.
    
    ОПТИМИЗИРОВАННАЯ ВЕРСИЯ:
    1. Собирает только те запросы, у которых НЕТ частотности
    2. Обрабатывает их параллельно (до max_concurrent одновременно)
    3. Добавляет частотность обратно в структуру данных, сохраняя существующие
    
    Args:
        sheets_data: Словарь с данными из Google Sheets
        default_region: ID региона по умолчанию (если не указан в данных URL)
        device: Устройство (desktop, phone, tablet)
        exact_match: Тип частотности (True - точная, False - широкая)
        max_concurrent: Максимальное количество одновременных запросов (10 для стандартного аккаунта)
        task_start_delay: Задержка между стартами задач (в секундах)
    
    Returns:
        Обновлённый словарь с добавленной частотностью для каждого запроса
    """
    # Шаг 1: Собираем только запросы БЕЗ частотности
    queries_without_frequency = set()
    total_queries_count = 0
    queries_with_frequency_count = 0
    
    for spreadsheet_id, spreadsheet_info in sheets_data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        for url, url_data in urls_dict.items():
            queries = url_data.get('queries', [])
            for query_item in queries:
                total_queries_count += 1
                
                # Запрос может быть строкой или объектом {query, frequency}
                if isinstance(query_item, str):
                    # Строка - нет частотности
                    queries_without_frequency.add(query_item)
                elif isinstance(query_item, dict):
                    query_text = query_item.get('query')
                    frequency = query_item.get('frequency')
                    
                    # Если частотность отсутствует или None - нужно получить
                    if frequency is None:
                        queries_without_frequency.add(query_text)
                    else:
                        queries_with_frequency_count += 1
    
    queries_to_process = list(queries_without_frequency)
    total_urls = sum(len(si.get('urls', {})) for si in sheets_data.values())
    
    logger.info(f"[STEP 1] Всего запросов: {total_queries_count} из {total_urls} URL")
    logger.info(f"[STEP 1] Запросов с частотностью: {queries_with_frequency_count}")
    logger.info(f"[STEP 1] Запросов БЕЗ частотности: {len(queries_to_process)}")
    
    if len(queries_to_process) == 0:
        logger.info("[STEP 1] Все запросы уже имеют частотность, обработка не требуется")
        return sheets_data
    
    logger.info(f"[CONFIG] Регион: {default_region}, Устройство: {device}, Точная частота: {exact_match}")
    logger.info(f"[CONFIG] Параллелизм: {max_concurrent} запросов одновременно")
    
    # Шаг 2: Обрабатываем все запросы параллельно (до max_concurrent одновременно)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_query_with_semaphore(query: str, query_index: int, total_queries: int) -> tuple:
        """Обрабатывает один запрос с контролем через семафор"""
        if task_start_delay > 0 and query_index > 0:
            await asyncio.sleep(task_start_delay * query_index)
        
        async with semaphore:
            logger.info(f"[QUERY {query_index}/{total_queries}] Запрос: '{query}'")
            
            # Получаем частотность для запроса
            result = await get_query_frequency(
                query=query,
                regions=default_region,
                device=device,
                exact_match=exact_match,
            )
            
            frequency = result.get('frequency')
            error = result.get('error')
            api_requests = result.get('api_requests', 0)
            
            if error:
                logger.error(f"[QUERY {query_index}/{total_queries}] ОШИБКА: {error}")
                return query, None, api_requests
            else:
                logger.info(f"[QUERY {query_index}/{total_queries}] Частота: {frequency:,}")
                return query, frequency, api_requests
    
    # Создаём задачи только для запросов без частотности
    tasks = []
    for query_index, query in enumerate(queries_to_process, 1):
        task = process_query_with_semaphore(query, query_index, len(queries_to_process))
        tasks.append(task)
    
    # Запускаем все задачи параллельно
    logger.info(f"[STEP 2] Запуск {len(tasks)} задач (до {max_concurrent} одновременно)...")
    query_results = await asyncio.gather(*tasks)
    
    # Создаём маппинг: запрос → частотность и запрос → api_requests
    query_frequencies = {}
    query_api_requests = {}
    total_api_requests = 0
    for query, freq, api_requests in query_results:
        query_frequencies[query] = freq
        query_api_requests[query] = api_requests
        total_api_requests += api_requests
    
    logger.info(f"[STEP 2] Обработано запросов. Всего API запросов: {total_api_requests}")
    
    successful = sum(1 for _, freq, _ in query_results if freq is not None)
    failed = len(query_results) - successful
    
    logger.info(f"[STEP 2] Завершено: {successful} успешно, {failed} ошибок")
    
    # Загружаем прайс для расчета стоимости
    pricing_file = Path(__file__).parent / "xmlriver_pricing.json"
    try:
        with open(pricing_file, 'r', encoding='utf-8') as f:
            pricing_data = json.load(f)
            price_per_request = pricing_data.get('price_per_request', 0.025)
            currency = pricing_data.get('currency', 'RUB')
    except Exception as e:
        logger.warning(f"Не удалось загрузить прайс из {pricing_file}: {e}. Используем значения по умолчанию.")
        price_per_request = 0.025
        currency = 'RUB'
    
    # Шаг 3: Добавляем частотность обратно в структуру данных
    logger.info(f"[STEP 3] Добавление частотности в структуру данных...")
    
    result_data = {}
    for spreadsheet_id, spreadsheet_info in sheets_data.items():
        result_data[spreadsheet_id] = {
            'urls': {}
        }
        
        urls_dict = spreadsheet_info.get('urls', {})
        for url, url_data in urls_dict.items():
            # Копируем исходные данные
            new_url_data = dict(url_data)
            
            # Обрабатываем queries: сохраняем существующую частотность или добавляем новую
            queries_with_frequency = []
            url_total_api_requests = 0  # Счетчик API запросов для этого URL
            
            for query_item in url_data.get('queries', []):
                # Запрос может быть строкой или объектом
                if isinstance(query_item, str):
                    # Строка - получаем частотность из новых данных
                    query_text = query_item
                    frequency = query_frequencies.get(query_text)
                    
                    # Получаем информацию о стоимости для этого запроса
                    query_requests = query_api_requests.get(query_text, 0)
                    query_cost = query_requests * price_per_request
                    
                    queries_with_frequency.append({
                        'query': query_text,
                        'frequency': frequency,
                        'wordstat_api_requests': query_requests,
                        'wordstat_cost': round(query_cost, 4)
                    })
                    
                    # Накапливаем API запросы для URL
                    url_total_api_requests += query_requests
                    
                elif isinstance(query_item, dict):
                    # Объект - проверяем, есть ли уже частотность
                    query_text = query_item.get('query')
                    existing_frequency = query_item.get('frequency')
                    
                    if existing_frequency is not None:
                        # Частотность уже есть - сохраняем её
                        # Для существующих частотностей API запросов не было
                        queries_with_frequency.append({
                            'query': query_text,
                            'frequency': existing_frequency,
                            'wordstat_api_requests': 0,
                            'wordstat_cost': 0
                        })
                    else:
                        # Частотности нет - берём из новых данных
                        new_frequency = query_frequencies.get(query_text)
                        
                        # Получаем информацию о стоимости для этого запроса
                        query_requests = query_api_requests.get(query_text, 0)
                        query_cost = query_requests * price_per_request
                        
                        queries_with_frequency.append({
                            'query': query_text,
                            'frequency': new_frequency,
                            'wordstat_api_requests': query_requests,
                            'wordstat_cost': round(query_cost, 4)
                        })
                        
                        # Накапливаем API запросы для URL
                        url_total_api_requests += query_requests
            
            # Рассчитываем стоимость для этого URL
            url_cost = url_total_api_requests * price_per_request
            
            # Заменяем queries на обновлённый массив
            new_url_data['queries'] = queries_with_frequency
            
            # Добавляем информацию о стоимости Wordstat
            new_url_data['wordstat_cost'] = {
                'api_requests': url_total_api_requests,
                'cost': round(url_cost, 4),
                'currency': currency
            }
            
            result_data[spreadsheet_id]['urls'][url] = new_url_data
    
    logger.info(f"[COMPLETE] Обработка завершена!")
    logger.info(f"[STATS] Всего URL: {total_urls}")
    logger.info(f"[STATS] Всего запросов: {total_queries_count}")
    logger.info(f"[STATS] Запросов с существующей частотностью: {queries_with_frequency_count}")
    logger.info(f"[STATS] Запросов обработано (новых): {len(queries_to_process)}")
    logger.info(f"[STATS] Успешно получено частот: {successful}")
    logger.info(f"[STATS] Ошибок: {failed}")
    
    return result_data


if __name__ == "__main__":
    """
    Тестовый запуск - загружает данные из jsontests/sheets_data.json
    и сохраняет результат с частотностями
    """
    async def test():
        # Загружаем тестовые данные
        project_root = Path(__file__).parent.parent
        input_file = project_root / "jsontests" / "sheets_data.json"
        
        logger.info(f"Загрузка данных из: {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            sheets_data = json.load(f)
        
        # Обрабатываем данные
        logger.info("ЗАПУСК МАССОВОЙ ПРОВЕРКИ ЧАСТОТНОСТИ")
        
        result = await process_sheets_data_wordstat(
            sheets_data=sheets_data,
            default_region=213,  # Москва
            device="",
            exact_match=True,  # Точная частотность
            max_concurrent=10,
            task_start_delay=0.0,
        )
        
        # Сохраняем результат
        output_file = project_root / "jsontests" / "wordstat_batch_result.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Результат сохранен в: {output_file}")
    
    asyncio.run(test())
