"""
Модуль для обработки URL с лемматизацией метатегов конкурентов
"""
import json
import sys
import os
from typing import Dict
from pathlib import Path

# Добавляем путь к модулю lemmatizer
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lemmatizer import find_common_words
from logger_config import get_lemmatizer_logger

logger = get_lemmatizer_logger()


def process_urls_with_lemmatization(
    data: Dict,
    h1_min_frequency_percent: float = 0.15,
    title_min_frequency_percent: float = 0.15,
    description_min_frequency_percent: float = 0.15,
    max_competitors: int = 5
) -> Dict:
    """
    Обрабатывает словарь с URL, извлекает title, description и h1 конкурентов из filtered_urls,
    лемматизирует их и добавляет результаты обратно в словарь.
    
    ВАЖНО: Приоритет отдается конкурентам с тем же типом страницы, что и основной URL.
    Конкуренты с ошибками парсинга пропускаются.
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {queries: [{filtered_urls: [...]}]}}}}
        h1_min_frequency_percent: Минимальный процент фраз для фильтрации редких слов H1 (по умолчанию 0.15 = 15%)
        title_min_frequency_percent: Минимальный процент фраз для фильтрации редких слов Title (по умолчанию 0.15 = 15%)
        description_min_frequency_percent: Минимальный процент фраз для фильтрации редких слов Description (по умолчанию 0.15 = 15%)
        max_competitors: Максимальное количество конкурентов для анализа (по умолчанию 5)
    
    Returns:
        Обновленный словарь с добавленными полями lemmatized_title_words, lemmatized_description_words и lemmatized_h1_words
    """
    result_data = {}
    
    for spreadsheet_id, spreadsheet_info in data.items():
        result_data[spreadsheet_id] = {"urls": {}}
        urls_dict = spreadsheet_info.get('urls', {})
        
        for url, url_data in urls_dict.items():
            # Копируем исходные данные
            result_data[spreadsheet_id]["urls"][url] = url_data.copy()
            
            # Определяем тип основного URL
            main_page_classification = url_data.get('page_classification', {})
            main_page_type = main_page_classification.get('page_type') if main_page_classification else None
            
            # Извлекаем filtered_urls из queries
            queries = url_data.get('queries', [])
            
            # Разделяем конкурентов на две группы: с тем же типом и с другими типами
            same_type_competitors = []  # Приоритет
            other_competitors = []      # Резерв
            
            for query_item in queries:
                if isinstance(query_item, dict):
                    filtered_urls = query_item.get('filtered_urls', [])
                    
                    for item in filtered_urls:
                        if isinstance(item, dict):
                            # Пропускаем конкурентов с ошибками
                            if 'error' in item or 'parsing_error' in item:
                                continue
                            
                            # Проверяем наличие метатегов
                            competitor_meta = item.get('competitor_meta', {})
                            if not competitor_meta:
                                continue
                            
                            # Проверяем наличие хотя бы одного метатега
                            has_meta = (
                                competitor_meta.get('title') or 
                                competitor_meta.get('description') or 
                                competitor_meta.get('h1')
                            )
                            if not has_meta:
                                continue
                            
                            # Проверяем тип страницы конкурента
                            page_classification = item.get('page_classification', {})
                            page_type = page_classification.get('page_type') if page_classification else None
                            
                            # Распределяем по группам
                            if main_page_type and page_type == main_page_type:
                                same_type_competitors.append(item)
                            else:
                                other_competitors.append(item)
            
            # Логируем количество найденных конкурентов
            if same_type_competitors or other_competitors:
                logger.debug(
                    f"{url}: найдено конкурентов с тем же типом={len(same_type_competitors)}, "
                    f"с другими типами={len(other_competitors)}"
                )
            
            # Формируем итоговый список: сначала приоритетные, потом остальные
            competitors_to_analyze = same_type_competitors[:max_competitors]
            if len(competitors_to_analyze) < max_competitors:
                remaining = max_competitors - len(competitors_to_analyze)
                competitors_to_analyze.extend(other_competitors[:remaining])
            
            # Извлекаем метатеги из выбранных конкурентов
            titles = []
            descriptions = []
            h1s = []
            
            for item in competitors_to_analyze:
                competitor_meta = item.get('competitor_meta', {})
                if competitor_meta.get('title'):
                    titles.append(competitor_meta['title'])
                if competitor_meta.get('description'):
                    descriptions.append(competitor_meta['description'])
                if competitor_meta.get('h1'):
                    h1s.append(competitor_meta['h1'])
            
            competitors_count = len(competitors_to_analyze)
            same_type_count = len([c for c in competitors_to_analyze if c in same_type_competitors])
            
            # Лемматизируем
            lemmatized_title_words = find_common_words(
                titles,
                min_frequency_percent=title_min_frequency_percent
            ) if titles else []
            
            lemmatized_description_words = find_common_words(
                descriptions,
                min_frequency_percent=description_min_frequency_percent
            ) if descriptions else []
            
            lemmatized_h1_words = find_common_words(
                h1s,
                min_frequency_percent=h1_min_frequency_percent
            ) if h1s else []
            
            # Добавляем результаты
            result_data[spreadsheet_id]["urls"][url]["lemmatized_title_words"] = lemmatized_title_words
            result_data[spreadsheet_id]["urls"][url]["lemmatized_description_words"] = lemmatized_description_words
            result_data[spreadsheet_id]["urls"][url]["lemmatized_h1_words"] = lemmatized_h1_words
            
            logger.info(
                f"[OK] {url}: "
                f"конкурентов={competitors_count} (того же типа={same_type_count}), "
                f"title words={len(lemmatized_title_words)}, "
                f"desc words={len(lemmatized_description_words)}, "
                f"h1 words={len(lemmatized_h1_words)}"
            )
    
    return result_data


def save_results_to_json(results: Dict, filename: str = "jsontests/lemmatizer_processor_results.json") -> None:
    """
    Сохраняет результаты в JSON файл
    
    Args:
        results: Словарь с результатами
        filename: Путь к файлу для сохранения
    """
    import os
    
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в файл: {filename}")


if __name__ == "__main__":
    """
    Тестовый запуск лемматизации метатегов конкурентов
    
    Используется файл после классификации страниц (batch_page_classification_results.json),
    где уже есть competitor_meta и page_classification для конкурентов.
    
    Приоритет отдается конкурентам с тем же типом страницы, что и основной URL.
    """
    # Определяем пути относительно корня проекта
    project_root = Path(__file__).parent.parent
    input_file = project_root / "jsontests" / "batch_page_classification_results.json"
    output_file = project_root / "jsontests" / "lemmatizer_processor_results.json"
    
    logger.info(f"Загрузка данных из {input_file}")
    
    # Загружаем данные
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Обрабатываем
    logger.info("Начало лемматизации метатегов конкурентов")
    results = process_urls_with_lemmatization(
        data=data,
        h1_min_frequency_percent=0.75,  # Фильтрация редких слов H1 (20%)
        title_min_frequency_percent=0.75,  # Фильтрация редких слов Title (25%)
        description_min_frequency_percent=0.75,  # Фильтрация редких слов Description (25%)
        max_competitors=5  # Максимум 5 конкурентов для анализа
    )
    
    # Сохраняем
    save_results_to_json(results, str(output_file))
    logger.info("Лемматизация завершена")
