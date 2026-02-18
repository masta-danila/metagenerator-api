"""
Модуль для пакетной генерации метатегов через LLM
"""
import json
import asyncio
import sys
import os
from typing import Dict, List
from pathlib import Path

# Добавляем путь к текущей папке
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, str(Path(__file__).parent.parent))

from metagenerator import generate_seo_texts
from logger_config import get_metagenerator_logger

logger = get_metagenerator_logger()


async def generate_for_single_url(
    url: str,
    url_data: Dict,
    semaphore: asyncio.Semaphore,
    model: str = "claude-sonnet-4-5-20250929",
    max_retries: int = 3,
    max_competitors_for_examples: int = 3,
    max_title_length: int = None,
    max_description_length: int = None,
    use_main_query_in_h1: bool = True,
    use_main_query_in_title: bool = True,
    use_main_query_in_description: bool = True
) -> Dict:
    """
    Генерирует метатеги для одного URL с повторными попытками при ошибках
    
    Args:
        url: URL для генерации
        url_data: Данные URL (lemmatized_title_words, queries, company_name и т.д.)
        semaphore: Семафор для ограничения одновременных запросов
        model: Модель LLM
        max_retries: Максимальное количество попыток при ошибках
        max_competitors_for_examples: Максимальное количество конкурентов для примеров (по умолчанию 3)
        max_title_length: Максимальная длина Title в символах (если None, ограничение не указывается)
        max_description_length: Максимальная длина Description в символах (если None, ограничение не указывается)
        use_main_query_in_h1: Использовать ли основной запрос в требованиях к H1 (по умолчанию True)
        use_main_query_in_title: Использовать ли основной запрос в требованиях к Title (по умолчанию True)
        use_main_query_in_description: Использовать ли основной запрос в требованиях к Description (по умолчанию True)
        
    Returns:
        Словарь с результатами генерации или ошибкой
    """
    async with semaphore:
        for attempt in range(max_retries):
            try:
                logger.info(f"[{attempt + 1}/{max_retries}] Генерация для: {url}")
                
                # Извлекаем данные
                title_words = url_data.get("lemmatized_title_words", [])
                description_words = url_data.get("lemmatized_description_words", [])
                h1_words = url_data.get("lemmatized_h1_words", [])
                company_name = url_data.get("company_name", "")
                queries_list = url_data.get("queries", [])
                
                # Берем основной запрос из первого query
                if queries_list and isinstance(queries_list[0], dict):
                    main_query = queries_list[0].get("query", "")
                else:
                    main_query = ""
                
                # Переменные Битрикса
                h1_variables = url_data.get("variables_h1", [])
                title_variables = url_data.get("variables_title", [])
                description_variables = url_data.get("variables_description", [])
                
                # Текущие метатеги (если есть)
                current_meta = url_data.get("current_meta", {})
                current_h1 = current_meta.get("h1", "") if current_meta else None
                
                if current_h1:
                    logger.info(f"[ТЕКУЩИЙ H1] {current_h1}")
                else:
                    logger.info(f"[ТЕКУЩИЙ H1] Отсутствует")
                
                # Определяем тип основного URL
                main_page_classification = url_data.get('page_classification', {})
                main_page_type = main_page_classification.get('page_type') if main_page_classification else None
                
                # Собираем примеры от конкурентов с приоритетом по типу страницы
                same_type_examples = {'titles': [], 'descriptions': [], 'h1s': []}
                other_examples = {'titles': [], 'descriptions': [], 'h1s': []}
                
                for query_item in queries_list:
                    if isinstance(query_item, dict):
                        filtered_urls = query_item.get('filtered_urls', [])
                        
                        for item in filtered_urls:
                            if isinstance(item, dict):
                                # Пропускаем конкурентов с ошибками
                                if 'error' in item or 'parsing_error' in item:
                                    continue
                                
                                competitor_meta = item.get('competitor_meta', {})
                                if not competitor_meta:
                                    continue
                                
                                # Определяем тип конкурента
                                page_classification = item.get('page_classification', {})
                                page_type = page_classification.get('page_type') if page_classification else None
                                
                                # Выбираем группу для добавления
                                is_same_type = (main_page_type and page_type == main_page_type)
                                target = same_type_examples if is_same_type else other_examples
                                
                                # Добавляем в соответствующую группу
                                if competitor_meta.get('title'):
                                    target['titles'].append(competitor_meta['title'])
                                if competitor_meta.get('description'):
                                    target['descriptions'].append(competitor_meta['description'])
                                if competitor_meta.get('h1'):
                                    target['h1s'].append(competitor_meta['h1'])
                
                # Формируем итоговые списки примеров: сначала с тем же типом, потом остальные
                example_titles = same_type_examples['titles'][:max_competitors_for_examples]
                if len(example_titles) < max_competitors_for_examples:
                    example_titles.extend(other_examples['titles'][:max_competitors_for_examples - len(example_titles)])
                
                example_descriptions = same_type_examples['descriptions'][:max_competitors_for_examples]
                if len(example_descriptions) < max_competitors_for_examples:
                    example_descriptions.extend(other_examples['descriptions'][:max_competitors_for_examples - len(example_descriptions)])
                
                example_h1s = same_type_examples['h1s'][:max_competitors_for_examples]
                if len(example_h1s) < max_competitors_for_examples:
                    example_h1s.extend(other_examples['h1s'][:max_competitors_for_examples - len(example_h1s)])
                
                # Генерируем SEO-тексты
                result = await generate_seo_texts(
                    title_words=title_words,
                    description_words=description_words,
                    h1_words=h1_words,
                    company_name=company_name,
                    main_query=main_query,
                    h1_variables=h1_variables,
                    title_variables=title_variables,
                    description_variables=description_variables,
                    example_titles=example_titles,
                    example_descriptions=example_descriptions,
                    example_h1s=example_h1s,
                    current_h1=current_h1,
                    max_title_length=max_title_length,
                    max_description_length=max_description_length,
                    use_main_query_in_h1=use_main_query_in_h1,
                    use_main_query_in_title=use_main_query_in_title,
                    use_main_query_in_description=use_main_query_in_description,
                    model=model
                )
                
                # Проверяем, есть ли ошибка в результате (например, ошибка парсинга JSON)
                if "error" in result:
                    error_msg = result["error"]
                    # Логируем сырой ответ для отладки, если он есть
                    if "raw_content" in result:
                        logger.debug(f"Raw LLM response: {result['raw_content'][:500]}")
                    raise Exception(error_msg)
                
                # Добавляем метаданные
                result["url"] = url
                result["metadata"] = {
                    "h1_words": h1_words,
                    "title_words": title_words,
                    "description_words": description_words,
                    "company_name": company_name,
                    "main_query": main_query,
                    "h1_variables": h1_variables,
                    "title_variables": title_variables,
                    "description_variables": description_variables,
                    "examples_count": {
                        "h1": len(example_h1s),
                        "title": len(example_titles),
                        "description": len(example_descriptions)
                    },
                    "examples_same_type_count": {
                        "h1": len([h for h in example_h1s if h in same_type_examples['h1s']]),
                        "title": len([t for t in example_titles if t in same_type_examples['titles']]),
                        "description": len([d for d in example_descriptions if d in same_type_examples['descriptions']])
                    }
                }
                
                # Выводим вводные данные и результаты вместе
                logger.info("ВВОДНЫЕ ДАННЫЕ:")
                logger.info(f"Основной запрос: {main_query}")
                logger.info(f"Компания: {company_name}")
                logger.info(f"Тип страницы: {main_page_type if main_page_type else 'Не определен'}")
                logger.info(f"H1 words: {h1_words}")
                logger.info(f"Title words: {title_words}")
                logger.info(f"Description words: {description_words}")
                
                if h1_variables or title_variables or description_variables:
                    logger.info(f"Переменные: H1={h1_variables}, Title={title_variables}, Desc={description_variables}")
                
                # Подсчитываем примеры по типам
                same_h1 = len([h for h in example_h1s if h in same_type_examples['h1s']])
                same_title = len([t for t in example_titles if t in same_type_examples['titles']])
                same_desc = len([d for d in example_descriptions if d in same_type_examples['descriptions']])
                
                logger.info(f"Примеры: H1={len(example_h1s)} ({same_h1} того же типа), Title={len(example_titles)} ({same_title} того же типа), Desc={len(example_descriptions)} ({same_desc} того же типа)")
                
                logger.info("РЕЗУЛЬТАТЫ ГЕНЕРАЦИИ:")
                logger.info(f"H1: {result.get('h1', '')}")
                logger.info(f"Title: {result.get('title', '')}")
                logger.info(f"Description: {result.get('description', '')}")
                logger.info(f"Стоимость: ${result.get('cost', 0):.6f}")
                
                logger.info(f"[OK] {url}")
                return result
                
            except Exception as e:
                logger.error(f"[ОШИБКА] Попытка {attempt + 1} для {url}: {str(e)}")
                
                if attempt == max_retries - 1:
                    # Последняя попытка - возвращаем ошибку
                    return {
                        "url": url,
                        "error": str(e),
                        "h1": None,
                        "title": None,
                        "description": None,
                        "cost": 0
                    }
                
                # Ждем перед следующей попыткой
                await asyncio.sleep(2 * (attempt + 1))
        
        # На случай непредвиденной ситуации
        return {
            "url": url,
            "error": "Unknown error - no result returned",
            "h1": None,
            "title": None,
            "description": None,
            "cost": 0
        }


async def generate_metatags_batch(
    data: Dict,
    model: str = "claude-sonnet-4-5-20250929",
    max_concurrent: int = 3,
    max_retries: int = 3,
    max_competitors_for_examples: int = 3,
    max_title_length: int = None,
    max_description_length: int = None,
    use_main_query_in_h1: bool = True,
    use_main_query_in_title: bool = True,
    use_main_query_in_description: bool = True
) -> Dict:
    """
    Генерирует метатеги для всех URL из словаря и добавляет их в исходную структуру
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {...}}}}
        model: Модель LLM для генерации
        max_concurrent: Максимальное количество одновременных запросов
        max_retries: Максимальное количество попыток при ошибках
        max_competitors_for_examples: Максимальное количество конкурентов для примеров (по умолчанию 3)
        max_title_length: Максимальная длина Title в символах (если None, ограничение не указывается)
        max_description_length: Максимальная длина Description в символах (если None, ограничение не указывается)
        use_main_query_in_h1: Использовать ли основной запрос в требованиях к H1 (по умолчанию True)
        use_main_query_in_title: Использовать ли основной запрос в требованиях к Title (по умолчанию True)
        use_main_query_in_description: Использовать ли основной запрос в требованиях к Description (по умолчанию True)
        
    Returns:
        Обновленный словарь с добавленными сгенерированными метатегами
    """
    logger.info("Начало пакетной генерации метатегов:")
    logger.info(f"- Модель: {model}")
    logger.info(f"- Одновременных запросов: {max_concurrent}")
    logger.info(f"- Попыток на URL: {max_retries}")
    logger.info(f"- Конкурентов для примеров: {max_competitors_for_examples}")
    logger.info(f"- Максимальная длина Title: {max_title_length if max_title_length else 'не указано'} символов")
    logger.info(f"- Максимальная длина Description: {max_description_length if max_description_length else 'не указано'} символов")
    logger.info(f"- Основной запрос в H1: {'да' if use_main_query_in_h1 else 'нет'}")
    logger.info(f"- Основной запрос в Title: {'да' if use_main_query_in_title else 'нет'}")
    logger.info(f"- Основной запрос в Description: {'да' if use_main_query_in_description else 'нет'}")
    
    # Создаем семафор для ограничения одновременных запросов
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Создаем задачи для всех URL
    tasks = []
    url_mapping = []  # Список кортежей (spreadsheet_id, url)
    
    for spreadsheet_id, spreadsheet_info in data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        for url, url_data in urls_dict.items():
            tasks.append(
                generate_for_single_url(
                    url=url,
                    url_data=url_data,
                    semaphore=semaphore,
                    model=model,
                    max_retries=max_retries,
                    max_competitors_for_examples=max_competitors_for_examples,
                    max_title_length=max_title_length,
                    max_description_length=max_description_length,
                    use_main_query_in_h1=use_main_query_in_h1,
                    use_main_query_in_title=use_main_query_in_title,
                    use_main_query_in_description=use_main_query_in_description
                )
            )
            url_mapping.append((spreadsheet_id, url))
    
    logger.info(f"Всего URL для обработки: {len(tasks)}")
    
    # Ждем выполнения всех задач
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Копируем исходные данные
    import copy
    result_data = copy.deepcopy(data)
    
    # Обрабатываем результаты и добавляем их в исходную структуру
    successful = 0
    failed = 0
    total_cost = 0.0
    
    for i, result in enumerate(results):
        spreadsheet_id, url = url_mapping[i]
        
        if isinstance(result, Exception):
            # Исключение
            result_data[spreadsheet_id]["urls"][url]["generated_metatags"] = {
                "error": str(result),
                "h1": None,
                "title": None,
                "description": None,
                "cost": 0
            }
            # Добавляем стоимость (0 при ошибке)
            result_data[spreadsheet_id]["urls"][url]["metageneration_cost"] = {
                "api_requests": 0,
                "cost": 0,
                "currency": "USD"
            }
            failed += 1
        elif result.get("error"):
            # Ошибка в результате
            result_data[spreadsheet_id]["urls"][url]["generated_metatags"] = {
                "error": result.get("error"),
                "h1": result.get("h1"),
                "title": result.get("title"),
                "description": result.get("description"),
                "cost": result.get("cost", 0)
            }
            # Добавляем стоимость (может быть > 0, если LLM ответил, но с ошибкой парсинга)
            cost_value = result.get("cost", 0)
            result_data[spreadsheet_id]["urls"][url]["metageneration_cost"] = {
                "api_requests": 1,
                "cost": round(cost_value, 6),
                "currency": "USD"
            }
            total_cost += cost_value
            failed += 1
        else:
            # Успешный результат - добавляем в исходную структуру
            result_data[spreadsheet_id]["urls"][url]["generated_metatags"] = {
                "h1": result.get("h1"),
                "title": result.get("title"),
                "description": result.get("description"),
                "cost": result.get("cost", 0)
            }
            
            # Добавляем стоимость генерации (единый формат)
            result_data[spreadsheet_id]["urls"][url]["metageneration_cost"] = {
                "api_requests": 1,  # Один запрос к LLM на URL
                "cost": round(result.get("cost", 0), 6),
                "currency": "USD"
            }
            
            successful += 1
            total_cost += result.get("cost", 0)
    
    logger.info("Результаты пакетной генерации:")
    logger.info(f"- Успешно: {successful}")
    logger.info(f"- Ошибок: {failed}")
    logger.info(f"- Общая стоимость: ${total_cost:.6f}")
    
    if failed > 0:
        logger.warning("Не удалось сгенерировать для:")
        for spreadsheet_id, url in url_mapping:
            generated = result_data[spreadsheet_id]["urls"][url].get("generated_metatags", {})
            if generated.get("error"):
                logger.info(f"  - {url}: {generated.get('error', 'Unknown error')}")
    
    return result_data


def save_batch_results(
    results: Dict,
    output_path: str = "jsontests/metagenerator_batch_results.json"
) -> None:
    """
    Сохраняет результаты пакетной генерации в JSON файл
    
    Args:
        results: Словарь с результатами генерации
        output_path: Путь для сохранения файла
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в {output_path}")


if __name__ == "__main__":
    """
    Тестовый запуск пакетной генерации
    """
    async def test():
        # Определяем пути относительно корня проекта
        project_root = Path(__file__).parent.parent
        input_file = project_root / "jsontests" / "lemmatizer_processor_results.json"
        output_file = project_root / "jsontests" / "metagenerator_batch_results.json"
        
        # Загружаем данные
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Запускаем пакетную генерацию
        results = await generate_metatags_batch(
            data=data,
            model="claude-sonnet-4-5-20250929",
            max_concurrent=50,  # 50 одновременных запросов
            max_retries=3,      # 3 попытки на каждый URL
            max_competitors_for_examples=3,  # 3 конкурента для примеров
            max_title_length=90,  # Максимум 90 символов для Title
            max_description_length=170,  # Максимум 150 символов для Description
            use_main_query_in_h1=False,  # Использовать основной запрос в H1
            use_main_query_in_title=True,  # Использовать основной запрос в Title
            use_main_query_in_description=True  # Использовать основной запрос в Description
        )
        
        # Сохраняем результаты
        save_batch_results(results, str(output_file))
    
    asyncio.run(test())
