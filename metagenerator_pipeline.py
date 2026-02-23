"""
Основной пайплайн обработки данных для генерации метатегов
Выполняет шаги 2-11 (от получения частотности до генерации метатегов)
"""

import asyncio
import sys
from typing import Dict
from pathlib import Path

# Добавляем пути к модулям
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "gsheets"))
sys.path.insert(0, str(project_root / "xmlriver"))
sys.path.insert(0, str(project_root / "site_parser"))
sys.path.insert(0, str(project_root / "metagenerators"))
sys.path.insert(0, str(project_root / "lemmatizers"))

# Импорты модулей
from wordstat_batch import process_sheets_data_wordstat  # type: ignore
from yandex_parser import process_sheets_data  # type: ignore
from batch_html_processor import parse_filtered_urls_batch  # type: ignore
from batch_browser_processor import reparse_failed_urls_with_browser  # type: ignore
from batch_meta_processor import extract_meta_from_filtered_urls  # type: ignore
from batch_page_classifier import classify_batch  # type: ignore
from lemmatizer_processor import process_urls_with_lemmatization  # type: ignore
from metagenerator_batch import generate_metatags_batch  # type: ignore
from metatag_editor_batch import review_metatags_batch  # type: ignore
from parsing_validator import validate_parsing_quality  # type: ignore
from logger_config import get_pipeline_logger

logger = get_pipeline_logger()


def cleanup_pipeline_data(data: Dict) -> Dict:
    """
    Очищает данные от промежуточной информации, оставляя только то, что нужно для Google Sheets
    
    Удаляет:
    - html и html_compressed из filtered_urls
    - competitor_meta из filtered_urls
    - lemmatized_* поля
    - page_classification
    - весь массив filtered_urls
    
    Оставляет:
    - queries с frequency и wordstat_cost
    - *_cost поля (wordstat, yandex_search, classification, metageneration, metatag_editor)
    - generated_metatags
    - company_name, region, variables_*
    
    Args:
        data: Словарь с полными данными после пайплайна
        
    Returns:
        Очищенный словарь для обновления Google Sheets
    """
    logger.info("Очистка данных от промежуточной информации...")
    
    cleaned_data = {}
    
    for spreadsheet_id, spreadsheet_info in data.items():
        cleaned_data[spreadsheet_id] = {"urls": {}}
        urls_dict = spreadsheet_info.get('urls', {})
        
        for url, url_data in urls_dict.items():
            # Создаем очищенную версию URL данных
            cleaned_url_data = {}
            
            # Копируем основные поля
            if 'company_name' in url_data:
                cleaned_url_data['company_name'] = url_data['company_name']
            if 'region' in url_data:
                cleaned_url_data['region'] = url_data['region']
            if 'variables_h1' in url_data:
                cleaned_url_data['variables_h1'] = url_data['variables_h1']
            if 'variables_title' in url_data:
                cleaned_url_data['variables_title'] = url_data['variables_title']
            if 'variables_description' in url_data:
                cleaned_url_data['variables_description'] = url_data['variables_description']
            
            # Копируем queries, но очищаем их от filtered_urls
            if 'queries' in url_data:
                cleaned_queries = []
                for query_item in url_data['queries']:
                    if isinstance(query_item, dict):
                        # Копируем только нужные поля
                        cleaned_query = {}
                        if 'query' in query_item:
                            cleaned_query['query'] = query_item['query']
                        if 'frequency' in query_item:
                            cleaned_query['frequency'] = query_item['frequency']
                        if 'wordstat_cost' in query_item:
                            cleaned_query['wordstat_cost'] = query_item['wordstat_cost']
                        if 'wordstat_api_requests' in query_item:
                            cleaned_query['wordstat_api_requests'] = query_item['wordstat_api_requests']
                        # НЕ копируем filtered_urls!
                        cleaned_queries.append(cleaned_query)
                    else:
                        cleaned_queries.append(query_item)
                cleaned_url_data['queries'] = cleaned_queries
            
            # Копируем cost поля (нужны для обновления Sheets)
            cost_fields = [
                'wordstat_cost',
                'yandex_search_cost',
                'classification_cost',
                'metageneration_cost',
                'metatag_editor_cost'
            ]
            for cost_field in cost_fields:
                if cost_field in url_data:
                    cleaned_url_data[cost_field] = url_data[cost_field]
            
            # Копируем generated_metatags (главный результат!)
            if 'generated_metatags' in url_data:
                cleaned_url_data['generated_metatags'] = url_data['generated_metatags']
            
            # НЕ копируем:
            # - lemmatized_h1_words
            # - lemmatized_title_words
            # - lemmatized_description_words
            # - page_classification
            # - filtered_urls (уже не копируются из queries)
            # - html, html_compressed, competitor_meta (были внутри filtered_urls)
            
            cleaned_data[spreadsheet_id]["urls"][url] = cleaned_url_data
    
    logger.info("Очистка данных завершена")
    return cleaned_data


async def run_metagenerator_pipeline(
    data: Dict,
    enable_classification: bool = False,
    enable_metatag_editor: bool = False
) -> Dict:
    """
    Выполняет основной пайплайн обработки (шаги 2-11)
    
    Args:
        data: Данные из Google Sheets (после process_all_spreadsheets)
        enable_classification: Включить классификацию страниц (шаг 8)
        enable_metatag_editor: Включить проверку метатегов (шаг 11)
        
    Returns:
        Dict: Обработанные данные с метатегами и частотностью (очищенные от промежуточных данных)
    """
    logger.info("ЗАПУСК METAGENERATOR PIPELINE (ШАГИ 2-11)")
    
    # Шаг 2: Получение частотности через XMLRiver Wordstat
    logger.info("ШАГ 2/13: Получение частотности запросов через XMLRiver Wordstat API")
    data = await process_sheets_data_wordstat(
        sheets_data=data,
        default_region=213,  # Москва
        device="",  # desktop, tablet, mobile
        max_concurrent=10,  # XMLRiver: до 10 одновременных запросов
        task_start_delay=0.0  # XMLRiver: прямые запросы, задержка не нужна
    )
    
    # Шаг 3: Получение filtered_urls через XMLRiver Yandex Search (используем самые частотные запросы)
    logger.info("ШАГ 3/13: Получение filtered_urls через XMLRiver Yandex Search API")
    data = await process_sheets_data(
        sheets_data=data,
        default_region=213,  # Москва
        urls_per_query=10,  # Количество извлекаемых URL из ТОПА от каждого запроса
        queries_per_url=4,  # Запросов на каждый основной URL (берем первые самые частотные)
        device="desktop",  # desktop, tablet, mobile
        domain="ru",  # ru, com, ua...
        lang="ru",  # ru, uk, en...
        max_concurrent=10,  # XMLRiver: до 10 одновременных запросов
        task_start_delay=0.0,  # XMLRiver: прямые запросы, задержка не нужна
        max_retries=3,  # Количество повторных попыток при ошибках API
        retry_delay=5  # Задержка между повторными попытками в секундах
    )
    
    # Шаг 4: Парсинг HTML filtered_urls (httpx)
    logger.info("ШАГ 4/13: Парсинг HTML filtered_urls (httpx)")
    total_filtered = sum(
        len(url_data.get('filtered_urls', []))
        for sheet_info in data.values()
        for url_data in sheet_info.get('urls', {}).values()
    )
    logger.info(f"  Всего filtered_urls для обработки: {total_filtered}")
    
    data = await parse_filtered_urls_batch(
        data=data,
        max_concurrent=100,  # Количество одновременных запросов
        max_retries=2,  # Количество повторных попыток при ошибках
        min_html_length=1000,  # Минимальная длина HTML (меньше = ошибка)
        use_proxy=True  # Использовать прокси с ротацией (автозагрузка из proxy.txt)
    )
    
    # Шаг 5: Повторный парсинг неудачных URL через браузер
    # Управление через флаги reparse_main_urls и reparse_filtered_urls (оба False = пропуск этапа)
    logger.info("ШАГ 5/13: Повторный парсинг неудачных URL через браузер")
    try:
        data = reparse_failed_urls_with_browser(
            data=data,
            max_concurrent=5,  # 5 браузеров параллельно
            max_retries=2,  # 2 попытки на URL
            wait_time=5,  # 5 секунд ожидания после загрузки
            use_proxy=True,  # Автоматически загрузит прокси из proxy.txt если есть
            min_html_length=2000,  # Минимальная длина HTML
            device_type="desktop",  # Тип устройства
            visible=True,  # Видимый режим (headless детектируется)
            reparse_main_urls=True,  # Парсить основные URL (False для пропуска)
            reparse_filtered_urls=False  # Парсить фильтрованные URL (False для пропуска)
        )
    except Exception as e:
        logger.error(f"  ✗ Ошибка браузерного парсинга: {e}")
        logger.warning("  → Пропускаем этап браузерного парсинга, продолжаем с имеющимися данными")
    
    # Шаг 6: Валидация качества парсинга
    logger.info("ШАГ 6/13: Валидация качества парсинга")
    validation = validate_parsing_quality(
        data=data,
        min_success_rate=0.6  # 60% успешных URL
    )
    
    if not validation['valid']:
        logger.warning("  ✗ Валидация не пройдена - прерываем pipeline")
        raise RuntimeError("Валидация парсинга не пройдена - данные некачественные")
    
    logger.info("  ✓ Валидация пройдена")
    
    # Шаг 7: Извлечение метатегов из HTML
    logger.info("ШАГ 7/13: Извлечение метатегов из HTML (title, description, h1)")
    data = extract_meta_from_filtered_urls(data)
    
    # Шаг 8: Классификация страниц через LLM
    if enable_classification:
        logger.info("ШАГ 8/13: Классификация страниц через LLM")
        data = await classify_batch(
            data=data,
            model="grok-4-1-fast-non-reasoning",  # Модель для классификации
            max_concurrent=50,  # Количество одновременных запросов к LLM
            max_retries=3,  # Повторные попытки при ошибках
            max_urls_per_type=4  # Максимум URL каждого типа для классификации
        )
    else:
        logger.info("ШАГ 8/13: Классификация страниц [ПРОПУЩЕНА]")
    
    # Шаг 9: Лемматизация текстов конкурентов
    logger.info("ШАГ 9/13: Лемматизация текстов конкурентов")
    data = process_urls_with_lemmatization(
        data=data,
        h1_min_frequency_percent=0.75,  # H1: 75%
        title_min_frequency_percent=0.75,  # Title: 75%
        description_min_frequency_percent=0.75,  # Description: 75%
        max_competitors=4  # Максимум 4 конкурента для анализа
    )
    
    # Шаг 10: Генерация метатегов через LLM
    logger.info("ШАГ 10/13: Генерация метатегов через LLM")
    data = await generate_metatags_batch(
        data=data,
        model="claude-sonnet-4-5-20250929",
        max_concurrent=50,  # Количество одновременных запросов к LLM
        max_retries=3,  # Повторные попытки при ошибках
        max_competitors_for_examples=3,  # Примеров от конкурентов
        max_title_length=90,  # Максимум 90 символов для Title
        max_description_length=170,  # Максимум 170 символов для Description
        use_main_query_in_h1=True,  # Использовать основной запрос в H1
        use_main_query_in_title=True,  # Использовать основной запрос в Title
        use_main_query_in_description=True  # Использовать основной запрос в Description
    )
    
    # Шаг 11: Проверка и исправление метатегов через LLM
    if enable_metatag_editor:
        logger.info("ШАГ 11/13: Проверка и исправление метатегов через LLM")
        data = await review_metatags_batch(
            data=data,
            model="claude-sonnet-4-5-20250929",  # Модель для проверки метатегов
            max_concurrent=50,  # Количество одновременных запросов к LLM
            max_retries=3,  # Повторные попытки при ошибках
            max_title_length=90,  # Максимум 90 символов для Title
            max_description_length=170  # Максимум 170 символов для Description
        )
    else:
        logger.info("ШАГ 11/13: Проверка и исправление метатегов [ПРОПУЩЕНА]")
    
    # Очищаем данные от промежуточной информации
    data = cleanup_pipeline_data(data)
    
    logger.info("METAGENERATOR PIPELINE ЗАВЕРШЕН УСПЕШНО")
    return data
