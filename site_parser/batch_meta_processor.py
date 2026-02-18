"""
Batch обработка для извлечения метатегов из сжатой HTML структуры
(HTML уже сжат после parse_for_ml, здесь только извлекаются метатеги)
"""
import json
import sys
from typing import Dict
from pathlib import Path

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from .meta_extractor import extract_meta
    from logger_config import get_batch_meta_logger
    logger = get_batch_meta_logger()
except ImportError:
    # Если запускаем напрямую, используем абсолютные импорты
    from site_parser.meta_extractor import extract_meta
    from logger_config import get_batch_meta_logger
    logger = get_batch_meta_logger()


def extract_meta_from_filtered_urls(data: Dict) -> Dict:
    """
    Извлекает метатеги из сжатой HTML структуры в filtered_urls
    
    ВАЖНО: HTML уже сжат после parse_for_ml, здесь только извлекаются метатеги
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {queries: [{filtered_urls: [...]}]}}}}
    
    Returns:
        Обновленный словарь с добавленными метатегами (title, description, h1)
    """
    logger.info("Начало извлечения метатегов из сжатой HTML структуры")
    
    # Копируем исходные данные
    import copy
    result_data = copy.deepcopy(data)
    
    total_urls = 0
    processed = 0
    with_meta = 0
    errors = 0
    
    main_urls_total = 0
    main_urls_with_meta = 0
    main_urls_errors = 0
    
    for spreadsheet_id, spreadsheet_info in data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        
        for main_url, url_data in urls_dict.items():
            # Копируем html_structure и parsing_error основного URL (если есть)
            if 'html_structure' in url_data:
                result_data[spreadsheet_id]['urls'][main_url]['html_structure'] = url_data['html_structure']
            
            if 'parsing_error' in url_data:
                result_data[spreadsheet_id]['urls'][main_url]['parsing_error'] = url_data['parsing_error']
            
            # Извлекаем метатеги основного URL (если есть HTML и нет ошибки парсинга)
            html_structure = url_data.get('html_structure', '')
            parsing_error = url_data.get('parsing_error')
            
            main_urls_total += 1
            
            if html_structure and not parsing_error:
                try:
                    meta_tags = extract_meta(html_structure)
                    result_data[spreadsheet_id]['urls'][main_url]['current_meta'] = {
                        'title': meta_tags.get('title', ''),
                        'description': meta_tags.get('description', ''),
                        'h1': meta_tags.get('h1', '')
                    }
                    main_urls_with_meta += 1
                    logger.debug(f"[MAIN URL] Извлечены метатеги для {main_url}")
                except Exception as e:
                    logger.error(f"[MAIN URL ERROR] Ошибка извлечения метатегов для {main_url}: {str(e)}")
                    result_data[spreadsheet_id]['urls'][main_url]['current_meta'] = {
                        'title': '',
                        'description': '',
                        'h1': '',
                        'error': str(e)
                    }
                    main_urls_errors += 1
            elif parsing_error:
                logger.debug(f"[MAIN URL SKIP] {main_url}: есть ошибка парсинга")
                main_urls_errors += 1
            else:
                logger.debug(f"[MAIN URL SKIP] {main_url}: нет HTML структуры")
                main_urls_errors += 1
            
            queries = url_data.get('queries', [])
            
            for query_idx, query_item in enumerate(queries):
                if isinstance(query_item, dict):
                    filtered_urls = query_item.get('filtered_urls', [])
                    
                    updated_filtered = []
                    
                    for filtered_url_item in filtered_urls:
                        total_urls += 1
                        
                        if isinstance(filtered_url_item, dict):
                            url = filtered_url_item.get('url', '')
                            html_structure = filtered_url_item.get('html_structure', '')
                            error = filtered_url_item.get('error') or filtered_url_item.get('parsing_error')
                            
                            # Если есть ошибка или нет HTML, пропускаем извлечение метатегов
                            if error or not html_structure:
                                if error:
                                    errors += 1
                                    logger.warning(f"[SKIP] {url}: {error}")
                                
                                # Сохраняем как есть
                                updated_filtered.append(filtered_url_item)
                                processed += 1
                                continue
                            
                            # Извлекаем метатеги (HTML уже сжат после parse_for_ml)
                            try:
                                meta_tags = extract_meta(html_structure)
                                
                                # Добавляем извлеченные метатеги
                                updated_item = {
                                    **filtered_url_item,
                                    'competitor_meta': {
                                        'title': meta_tags.get('title', ''),
                                        'description': meta_tags.get('description', ''),
                                        'h1': meta_tags.get('h1', '')
                                    }
                                }
                                
                                updated_filtered.append(updated_item)
                                with_meta += 1
                                processed += 1
                                
                                if processed % 100 == 0:
                                    logger.info(f"[PROGRESS] Обработано {processed}/{total_urls} URL")
                                
                            except Exception as e:
                                logger.error(f"[ERROR] Ошибка обработки HTML для {url}: {str(e)}")
                                # Сохраняем с ошибкой
                                updated_filtered.append({
                                    **filtered_url_item,
                                    'processing_error': str(e)
                                })
                                errors += 1
                                processed += 1
                        else:
                            # Это строка, а не словарь - пропускаем
                            updated_filtered.append(filtered_url_item)
                            processed += 1
                    
                    # Обновляем filtered_urls в результате
                    result_data[spreadsheet_id]['urls'][main_url]['queries'][query_idx]['filtered_urls'] = updated_filtered
    
    logger.info("Извлечение метатегов завершено:")
    logger.info(f"Основные URL:")
    logger.info(f"- Всего: {main_urls_total}")
    logger.info(f"- С метатегами: {main_urls_with_meta}")
    logger.info(f"- Ошибок/пропущено: {main_urls_errors}")
    logger.info(f"URL конкурентов (filtered_urls):")
    logger.info(f"- Всего: {total_urls}")
    logger.info(f"- Обработано: {processed}")
    logger.info(f"- С метатегами: {with_meta}")
    logger.info(f"- Ошибок: {errors}")
    
    return result_data


def save_results(
    results: Dict,
    output_path: str = "jsontests/batch_meta_extracted_results.json"
) -> None:
    """
    Сохраняет результаты извлечения метатегов в JSON файл
    
    Args:
        results: Словарь с результатами
        output_path: Путь для сохранения файла
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в {output_path}")


if __name__ == "__main__":
    """
    Тестовый запуск извлечения метатегов
    """
    # Определяем пути относительно корня проекта
    project_root = Path(__file__).parent.parent
    input_file = project_root / "jsontests" / "step7_html_reparsed.json"
    output_file = project_root / "jsontests" / "step9_meta_extracted.json"
    
    logger.info(f"Загрузка данных из {input_file}")
    
    # Загружаем данные
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Извлекаем метатеги
    results = extract_meta_from_filtered_urls(data)
    
    # Сохраняем результаты
    save_results(results, str(output_file))
