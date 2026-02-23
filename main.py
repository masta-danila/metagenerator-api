"""
Полный цикл генерации метатегов из Google Sheets

Выполняет 13 последовательных шагов:
1. Чтение данных из Google Sheets
2. Получение частотности запросов через XMLRiver Wordstat API (данные остаются в памяти)
3. Получение filtered_urls через XMLRiver Yandex Search API (используем самые частотные запросы)
4. Парсинг HTML filtered_urls (httpx)
5. Повторный парсинг неудачных URL через браузер
6. Валидация качества парсинга (при неудаче - повтор с шага 1)
7. Извлечение метатегов из HTML
8. Классификация страниц через LLM
9. Лемматизация текстов конкурентов
10. Генерация метатегов через LLM
11. Проверка и исправление метатегов через LLM
12. Обновление листа Data в Google Sheets частотностью
13. Обновление листа Meta в Google Sheets метатегами
"""

import asyncio
import time
import sys
import json
from pathlib import Path

# Добавляем пути к модулям
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "gsheets"))
sys.path.insert(0, str(project_root / "xmlriver"))
sys.path.insert(0, str(project_root / "site_parser"))
sys.path.insert(0, str(project_root / "lemmatizers"))
sys.path.insert(0, str(project_root / "metagenerators"))

from sheets_reader import process_all_spreadsheets  # type: ignore
from wordstat_batch import process_sheets_data_wordstat  # type: ignore
from data_updater import update_all_data_sheets  # type: ignore
from yandex_parser import process_sheets_data  # type: ignore
from batch_html_processor import parse_filtered_urls_batch  # type: ignore
from batch_browser_processor import reparse_failed_urls_with_browser  # type: ignore
from batch_meta_processor import extract_meta_from_filtered_urls  # type: ignore
from batch_page_classifier import classify_batch  # type: ignore
from lemmatizer_processor import process_urls_with_lemmatization  # type: ignore
from metagenerator_batch import generate_metatags_batch  # type: ignore
from metatag_editor_batch import review_metatags_batch  # type: ignore
from sheets_updater import update_all_spreadsheets  # type: ignore
from parsing_validator import validate_parsing_quality  # type: ignore
from logger_config import get_pipeline_logger

logger = get_pipeline_logger()


def save_step_results(data, filename: str):
    """Сохраняет результаты шага в JSON файл"""
    output_file = project_root / "jsontests" / filename
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"  → Сохранено в {filename}")


async def run_full_pipeline() -> bool:
    """
    Запускает полный цикл генерации метатегов
    
    Returns:
        True если pipeline завершен успешно, False если валидация не прошла
    """
    
    logger.info("ЗАПУСК ПОЛНОГО ЦИКЛА ГЕНЕРАЦИИ МЕТАТЕГОВ")
    
    # Шаг 1: Чтение Google Sheets
    logger.info("ШАГ 1/13: Чтение данных из Google Sheets")
    data = process_all_spreadsheets()
    # save_step_results(data, "step1_sheets_data.json")
    
    # Шаг 2: Получение частотности через XMLRiver Wordstat
    logger.info("ШАГ 2/13: Получение частотности запросов через XMLRiver Wordstat API")
    data = await process_sheets_data_wordstat(
        sheets_data=data,
        default_region=213,  # Москва
        device="",  # desktop, tablet, mobile
        max_concurrent=10,  # XMLRiver: до 10 одновременных запросов
        task_start_delay=0.0  # XMLRiver: прямые запросы, задержка не нужна
    )
    save_step_results(data, "step2_frequency_data.json")
    
    # Шаги 3-4 удалены: обновление Data листа перенесено в конец
    
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
    save_step_results(data, "step3_filtered_urls.json")
    
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
    # save_step_results(data, "step6_html_parsed.json")

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
        # save_step_results(data, "step7_html_reparsed.json")
    except Exception as e:
        logger.error(f"  ✗ Ошибка браузерного парсинга: {e}")
        logger.warning("  → Пропускаем этап браузерного парсинга, продолжаем с имеющимися данными")
    
    # Шаг 6: Валидация качества парсинга
    logger.info("ШАГ 6/13: Валидация качества парсинга")
    validation = validate_parsing_quality(
        data=data,
        min_success_rate=0.6  # 70% успешных URL
    )
    
    if not validation['valid']:
        logger.warning("  ✗ Валидация не пройдена - прерываем pipeline")
        return False  # Прерываем pipeline - данные некачественные
    
    logger.info("  ✓ Валидация пройдена")
    
    # Шаг 7: Извлечение метатегов из HTML
    logger.info("ШАГ 7/13: Извлечение метатегов из HTML (title, description, h1)")
    data = extract_meta_from_filtered_urls(data)
    #     save_step_results(data, "step7_meta_extracted.json")
    
    # Шаг 8: Классификация страниц через LLM
    ENABLE_CLASSIFICATION = False  # Флаг: измените на False чтобы пропустить этот шаг
    
    if ENABLE_CLASSIFICATION:
        logger.info("ШАГ 8/13: Классификация страниц через LLM")
        data = await classify_batch(
            data=data,
            model="grok-4-1-fast-non-reasoning",  # Модель для классификации
            max_concurrent=50,  # Количество одновременных запросов к LLM
            max_retries=3,  # Повторные попытки при ошибках
            max_urls_per_type=4  # Максимум URL каждого типа для классификации
        )
        save_step_results(data, "step8_classified.json")
    else:
        logger.info("ШАГ 8/13: Классификация страниц [ПРОПУЩЕНА]")
    
    # Шаг 9: Лемматизация текстов конкурентов
    logger.info("ШАГ 9/13: Лемматизация текстов конкурентов")
    data = process_urls_with_lemmatization(
        data=data,
        h1_min_frequency_percent=0.75,  # H1: 20%
        title_min_frequency_percent=0.75,  # Title: 25%
        description_min_frequency_percent=0.75,  # Description: 25%
        max_competitors=4  # Максимум 5 конкурентов для анализа
    )
    save_step_results(data, "step9_lemmatized.json")
    
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
    #     save_step_results(data, "step10_generated_metatags.json")
    
    # Шаг 11: Проверка и исправление метатегов через LLM
    ENABLE_METATAG_EDITOR = False  # Флаг: измените на True чтобы включить этот шаг
    
    if ENABLE_METATAG_EDITOR:
        logger.info("ШАГ 11/13: Проверка и исправление метатегов через LLM")
        data = await review_metatags_batch(
            data=data,
            model="claude-sonnet-4-5-20250929",  # Модель для проверки метатегов
            max_concurrent=50,  # Количество одновременных запросов к LLM
            max_retries=3,  # Повторные попытки при ошибках
            max_title_length=90,  # Максимум 90 символов для Title
            max_description_length=170  # Максимум 170 символов для Description
        )
        save_step_results(data, "step11_reviewed_metatags.json")
    else:
        logger.info("ШАГ 11/13: Проверка и исправление метатегов [ПРОПУЩЕНА]")
    
    # Шаг 12: Обновление листа Data в Google Sheets (частотность)
    logger.info("ШАГ 12/13: Обновление листа Data в Google Sheets частотностью")
    data_update_stats = update_all_data_sheets(frequency_data=data)
    save_step_results(data_update_stats, "step12_data_update_stats.json")
    
    # Шаг 13: Обновление листа Meta в Google Sheets (метатеги)
    logger.info("ШАГ 13/13: Обновление листа Meta в Google Sheets метатегами")
    meta_update_stats = update_all_spreadsheets(
        data=data,
        sheet_name="Meta"
    )
    save_step_results(meta_update_stats, "step13_meta_update_stats.json")
    
    logger.info("ЦИКЛ ЗАВЕРШЕН УСПЕШНО")
    return True  # Pipeline выполнен успешно


if __name__ == "__main__":
    logger.info("Запуск бесконечного цикла обработки")
    logger.info("Интервал между циклами: 10 минут")
    
    while True:
        try:
            asyncio.run(run_full_pipeline())
            logger.info("Следующий запуск через 10 минут")
            
        except KeyboardInterrupt:
            logger.info("ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ")
            break
            
        except Exception as e:
            logger.error(f"ОШИБКА: {e}", exc_info=True)
            logger.info("Следующая попытка через 10 минут")
        
        # Пауза перед следующим циклом
        time.sleep(600)  # 10 минут в секундах
