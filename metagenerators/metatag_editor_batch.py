"""
Модуль для пакетной проверки и исправления готовых метатегов через LLM
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

from metatag_editor import review_and_fix_metatags
from logger_config import get_metagenerator_logger

logger = get_metagenerator_logger()


async def review_single_url(
    url: str,
    url_data: Dict,
    semaphore: asyncio.Semaphore,
    model: str = "claude-sonnet-4-5-20250929",
    max_retries: int = 3,
    max_title_length: int = None,
    max_description_length: int = None
) -> Dict:
    """
    Проверяет и исправляет метатеги для одного URL с повторными попытками при ошибках
    
    Args:
        url: URL для проверки
        url_data: Данные URL с готовыми метатегами
        semaphore: Семафор для ограничения одновременных запросов
        model: Модель LLM
        max_retries: Максимальное количество попыток при ошибках
        max_title_length: Максимальная длина Title в символах
        max_description_length: Максимальная длина Description в символах
        
    Returns:
        Словарь с результатами проверки и исправления
    """
    async with semaphore:
        for attempt in range(max_retries):
            try:
                logger.info(f"[{attempt + 1}/{max_retries}] Проверка метатегов для: {url}")
                
                # Извлекаем готовые метатеги
                generated = url_data.get("generated_metatags", {})
                if not generated or generated.get("error"):
                    logger.warning(f"[ПРОПУСК] Нет готовых метатегов для {url}")
                    return {
                        "url": url,
                        "skipped": True,
                        "reason": "Нет готовых метатегов или ошибка при генерации"
                    }
                
                h1 = generated.get("h1", "")
                title = generated.get("title", "")
                description = generated.get("description", "")
                
                # Извлекаем параметры
                h1_words = url_data.get("lemmatized_h1_words", [])
                title_words = url_data.get("lemmatized_title_words", [])
                description_words = url_data.get("lemmatized_description_words", [])
                company_name = url_data.get("company_name", "")
                queries = url_data.get("queries", [])
                
                # Определяем основной запрос
                if queries:
                    if isinstance(queries[0], dict):
                        main_query = queries[0].get("query", "")
                    else:
                        main_query = queries[0]
                else:
                    main_query = ""
                
                # Переменные Битрикса
                h1_variables = url_data.get("variables_h1", [])
                title_variables = url_data.get("variables_title", [])
                description_variables = url_data.get("variables_description", [])
                
                # Извлекаем текущий H1 страницы
                current_meta = url_data.get("current_meta", {})
                current_h1 = current_meta.get("h1", "") if current_meta else ""
                
                # Проверяем и исправляем метатеги
                result = await review_and_fix_metatags(
                    h1=h1,
                    title=title,
                    description=description,
                    h1_words=h1_words,
                    title_words=title_words,
                    description_words=description_words,
                    company_name=company_name,
                    main_query=main_query,
                    model=model,
                    current_h1=current_h1,
                    h1_variables=h1_variables,
                    title_variables=title_variables,
                    description_variables=description_variables,
                    max_title_length=max_title_length,
                    max_description_length=max_description_length
                )
                
                # Проверяем, есть ли ошибка в результате
                if "error" in result:
                    error_msg = result["error"]
                    if "raw_content" in result:
                        logger.debug(f"Raw LLM response: {result['raw_content'][:500]}")
                    raise Exception(error_msg)
                
                # Добавляем метаданные
                result["url"] = url
                result["original"] = {
                    "h1": h1,
                    "title": title,
                    "description": description
                }
                
                changes_count = len(result.get("changes", []))
                if changes_count > 0:
                    logger.info(f"[ИСПРАВЛЕНО] {url} - изменений: {changes_count}")
                else:
                    logger.info(f"[OK] {url} - изменений не требуется")
                
                return result
                
            except Exception as e:
                logger.error(f"[ОШИБКА] Попытка {attempt + 1} для {url}: {str(e)}")
                
                if attempt == max_retries - 1:
                    # Последняя попытка - возвращаем ошибку
                    return {
                        "url": url,
                        "error": str(e),
                        "h1": url_data.get("generated_metatags", {}).get("h1"),
                        "title": url_data.get("generated_metatags", {}).get("title"),
                        "description": url_data.get("generated_metatags", {}).get("description"),
                        "changes": [],
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
            "changes": [],
            "cost": 0
        }


async def review_metatags_batch(
    data: Dict,
    model: str = "claude-sonnet-4-5-20250929",
    max_concurrent: int = 3,
    max_retries: int = 3,
    max_title_length: int = None,
    max_description_length: int = None
) -> Dict:
    """
    Проверяет и исправляет метатеги для всех URL из словаря
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {...}}}}
        model: Модель LLM для проверки
        max_concurrent: Максимальное количество одновременных запросов
        max_retries: Максимальное количество попыток при ошибках
        max_title_length: Максимальная длина Title в символах
        max_description_length: Максимальная длина Description в символах
        
    Returns:
        Обновленный словарь с исправленными метатегами
    """
    logger.info("Начало пакетной проверки и исправления метатегов:")
    logger.info(f"- Модель: {model}")
    logger.info(f"- Одновременных запросов: {max_concurrent}")
    logger.info(f"- Попыток на URL: {max_retries}")
    
    # Создаем семафор для ограничения одновременных запросов
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Создаем задачи для всех URL
    tasks = []
    url_mapping = []  # Список кортежей (spreadsheet_id, url)
    
    for spreadsheet_id, spreadsheet_info in data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        for url, url_data in urls_dict.items():
            tasks.append(
                review_single_url(
                    url=url,
                    url_data=url_data,
                    semaphore=semaphore,
                    model=model,
                    max_retries=max_retries,
                    max_title_length=max_title_length,
                    max_description_length=max_description_length
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
    skipped = 0
    changed = 0
    total_cost = 0.0
    
    for i, result in enumerate(results):
        spreadsheet_id, url = url_mapping[i]
        
        if isinstance(result, Exception):
            # Исключение
            result_data[spreadsheet_id]["urls"][url]["reviewed_metatags"] = {
                "error": str(result),
                "h1": None,
                "title": None,
                "description": None,
                "changes": [],
                "cost": 0
            }
            # Добавляем стоимость редактирования (0 при исключении)
            result_data[spreadsheet_id]["urls"][url]["metatag_editor_cost"] = {
                "api_requests": 0,
                "cost": 0,
                "currency": "USD"
            }
            failed += 1
        elif result.get("skipped"):
            # Пропущен
            # Добавляем стоимость редактирования (0 при пропуске)
            result_data[spreadsheet_id]["urls"][url]["metatag_editor_cost"] = {
                "api_requests": 0,
                "cost": 0,
                "currency": "USD"
            }
            skipped += 1
        elif result.get("error"):
            # Ошибка в результате
            result_data[spreadsheet_id]["urls"][url]["reviewed_metatags"] = {
                "error": result.get("error"),
                "h1": result.get("h1"),
                "title": result.get("title"),
                "description": result.get("description"),
                "changes": result.get("changes", []),
                "cost": result.get("cost", 0)
            }
            # Добавляем стоимость (может быть > 0, если LLM ответил, но с ошибкой парсинга)
            cost_value = result.get("cost", 0)
            result_data[spreadsheet_id]["urls"][url]["metatag_editor_cost"] = {
                "api_requests": 1 if cost_value > 0 else 0,
                "cost": round(cost_value, 6),
                "currency": "USD"
            }
            total_cost += cost_value
            failed += 1
        else:
            # Успешный результат
            result_data[spreadsheet_id]["urls"][url]["reviewed_metatags"] = {
                "h1": result.get("h1"),
                "title": result.get("title"),
                "description": result.get("description"),
                "changes": result.get("changes", []),
                "original": result.get("original", {}),
                "cost": result.get("cost", 0)
            }
            
            # Добавляем стоимость редактирования (единый формат)
            result_data[spreadsheet_id]["urls"][url]["metatag_editor_cost"] = {
                "api_requests": 1,  # Один запрос к LLM на URL
                "cost": round(result.get("cost", 0), 6),
                "currency": "USD"
            }
            
            successful += 1
            total_cost += result.get("cost", 0)
            
            if len(result.get("changes", [])) > 0:
                changed += 1
    
    logger.info("Результаты пакетной проверки:")
    logger.info(f"- Успешно проверено: {successful}")
    logger.info(f"- Исправлено: {changed}")
    logger.info(f"- Без изменений: {successful - changed}")
    logger.info(f"- Пропущено: {skipped}")
    logger.info(f"- Ошибок: {failed}")
    logger.info(f"- Общая стоимость: ${total_cost:.6f}")
    
    if failed > 0:
        logger.warning("Не удалось проверить:")
        for spreadsheet_id, url in url_mapping:
            reviewed = result_data[spreadsheet_id]["urls"][url].get("reviewed_metatags", {})
            if reviewed.get("error"):
                logger.info(f"  - {url}: {reviewed.get('error', 'Unknown error')}")
    
    return result_data


def save_batch_results(
    results: Dict,
    output_path: str = "jsontests/metatag_editor_batch_results.json"
) -> None:
    """
    Сохраняет результаты пакетной проверки в JSON файл
    
    Args:
        results: Словарь с результатами проверки
        output_path: Путь для сохранения файла
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в {output_path}")


if __name__ == "__main__":
    """
    Тестовый запуск пакетной проверки и исправления
    """
    async def test():
        # Определяем пути относительно корня проекта
        project_root = Path(__file__).parent.parent
        input_file = project_root / "jsontests" / "metagenerator_batch_results.json"
        output_file = project_root / "jsontests" / "metatag_editor_batch_results.json"
        
        # Загружаем данные
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Запускаем пакетную проверку
        results = await review_metatags_batch(
            data=data,
            model="claude-sonnet-4-5-20250929",
            max_concurrent=50,  # 50 одновременных запросов
            max_retries=3,      # 3 попытки на каждый URL
            max_title_length=90,
            max_description_length=170
        )
        
        # Сохраняем результаты
        save_batch_results(results, str(output_file))
    
    asyncio.run(test())
