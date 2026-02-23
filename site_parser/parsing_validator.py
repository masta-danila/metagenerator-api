"""
Модуль валидации качества парсинга filtered_urls

Проверяет:
1. Наличие данных (запросов, filtered_urls)
2. Процент успешно спарсенных URL выше минимального порога
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import setup_logger

logger = setup_logger('parsing_validator', 'logs/parsing_validator.log')


def _count_urls_in_queries(queries: List[Dict]) -> Tuple[int, int]:
    """
    Подсчитывает успешные и неудачные URL в списке запросов
    
    Args:
        queries: Список запросов с filtered_urls
    
    Returns:
        (successful_count, failed_count)
    """
    successful = 0
    failed = 0
    
    for query in queries:
        if not isinstance(query, dict):
            continue
        
        for filtered_item in query.get('filtered_urls', []):
            if not isinstance(filtered_item, dict):
                continue
            
            # Успешный URL = есть html_structure и нет error
            if 'html_structure' in filtered_item and 'error' not in filtered_item:
                successful += 1
            elif 'error' in filtered_item:
                failed += 1
    
    return successful, failed


def _get_total_filtered_urls(queries: List[Dict]) -> int:
    """
    Подсчитывает общее количество filtered_urls в запросах
    
    Args:
        queries: Список запросов
    
    Returns:
        Общее количество filtered_urls
    """
    total = 0
    for query in queries:
        if not isinstance(query, dict):
            continue
        total += len(query.get('filtered_urls', []))
    
    return total


def validate_parsing_quality(
    data: Dict,
    min_success_rate: float = 0.7
) -> Dict:
    """
    Проверяет качество парсинга filtered_urls
    
    Args:
        data: Словарь после шага 6 (step6_html_parsed.json)
        min_success_rate: Минимальный процент успешно спарсенных URL (0.0-1.0)
    
    Returns:
        {
            "valid": True/False,
            "total_main_urls": int,
            "total_queries": int,
            "total_filtered_urls": int,  # Общее количество filtered_urls
            "successful_urls": int,
            "failed_urls": int,
            "success_rate": float,  # Процент успешных от общего количества
            "issues": List[str]
        }
    """
    issues = []
    total_main_urls = 0
    total_queries = 0
    total_filtered_urls = 0
    total_successful = 0
    total_failed = 0
    
    # Проверка 1: Есть ли данные вообще
    if not data:
        issues.append("Данные пустые")
        return {
            "valid": False,
            "total_main_urls": 0,
            "total_queries": 0,
            "total_filtered_urls": 0,
            "successful_urls": 0,
            "failed_urls": 0,
            "success_rate": 0.0,
            "issues": issues
        }
    
    # Проходим по всем spreadsheet
    for spreadsheet_id, sheet_info in data.items():
        urls_dict = sheet_info.get('urls', {})
        
        # Проходим по всем основным URL
        for main_url, url_data in urls_dict.items():
            total_main_urls += 1
            queries = url_data.get('queries', [])
            queries_count = len(queries)
            total_queries += queries_count
            
            # Проверка 2: Количество запросов
            if queries_count == 0:
                issues.append(f"Main URL {main_url}: нет запросов")
            
            # Подсчет успешных и неудачных URL
            successful, failed = _count_urls_in_queries(queries)
            total_successful += successful
            total_failed += failed
            total_filtered_urls += _get_total_filtered_urls(queries)
    
    # Проверка 3: Процент успеха (от фактического количества filtered_urls)
    if total_filtered_urls == 0:
        issues.append("Нет filtered_urls для проверки")
        success_rate = 0.0
    else:
        # Процент от ФАКТИЧЕСКОГО количества filtered_urls
        success_rate = total_successful / total_filtered_urls
        
        if success_rate < min_success_rate:
            issues.append(
                f"Процент успешного парсинга {success_rate:.1%} "
                f"ниже требуемого {min_success_rate:.1%} "
                f"(успешных {total_successful} из {total_filtered_urls} фактических)"
            )
    
    # Итоговый результат
    valid = len(issues) == 0
    
    # Логирование результатов
    logger.info("РЕЗУЛЬТАТЫ ВАЛИДАЦИИ ПАРСИНГА")
    logger.info(f"Основных URL: {total_main_urls}")
    logger.info(f"Всего запросов: {total_queries}")
    logger.info(f"Всего filtered_urls: {total_filtered_urls}")
    logger.info(f"Успешно спарсено: {total_successful}")
    logger.info(f"С ошибками: {total_failed}")
    logger.info(f"Процент успеха: {success_rate:.1%} (минимум: {min_success_rate:.1%})")
    logger.info(f"Статус: {'✓ ПРОЙДЕНА' if valid else '✗ НЕ ПРОЙДЕНА'}")
    
    if not valid:
        logger.warning(f"ПРИЧИНЫ НЕПРОЙДЕННОЙ ВАЛИДАЦИИ ({len(issues)}):")
        for i, issue in enumerate(issues[:20], 1):  # Показываем первые 20
            logger.warning(f"{i}. {issue}")
        if len(issues) > 20:
            logger.warning(f"... и еще {len(issues) - 20} проблем")
    
    return {
        "valid": valid,
        "total_main_urls": total_main_urls,
        "total_queries": total_queries,
        "total_filtered_urls": total_filtered_urls,
        "successful_urls": total_successful,
        "failed_urls": total_failed,
        "success_rate": success_rate,
        "issues": issues
    }


def get_failed_urls_summary(data: Dict, limit: int = 50) -> List[Dict]:
    """
    Возвращает список URL с ошибками и причинами
    
    Args:
        data: Словарь после шага 6
        limit: Максимальное количество URL в результате
    
    Returns:
        Список словарей с информацией об ошибках
    """
    failed_urls = []
    
    for spreadsheet_id, sheet_info in data.items():
        urls_dict = sheet_info.get('urls', {})
        
        for main_url, url_data in urls_dict.items():
            for query_idx, query in enumerate(url_data.get('queries', [])):
                if not isinstance(query, dict):
                    continue
                
                query_text = query.get('query', f'запрос #{query_idx+1}')
                
                for filtered_item in query.get('filtered_urls', []):
                    if not isinstance(filtered_item, dict):
                        continue
                    
                    if 'error' in filtered_item:
                        failed_urls.append({
                            "main_url": main_url,
                            "query": query_text,
                            "filtered_url": filtered_item.get('url', 'unknown'),
                            "error": filtered_item['error']
                        })
                        
                        if len(failed_urls) >= limit:
                            return failed_urls
    
    return failed_urls


def get_main_urls_stats(data: Dict) -> List[Dict]:
    """
    Статистика по каждому main_url отдельно
    
    Args:
        data: Словарь после шага 6
    
    Returns:
        Список статистик по каждому main_url
    """
    stats = []
    
    for spreadsheet_id, sheet_info in data.items():
        sheet_name = sheet_info.get('name', spreadsheet_id)
        urls_dict = sheet_info.get('urls', {})
        
        for main_url, url_data in urls_dict.items():
            queries = url_data.get('queries', [])
            queries_count = len(queries)
            
            successful, failed = _count_urls_in_queries(queries)
            total_filtered = _get_total_filtered_urls(queries)
            
            success_rate = successful / total_filtered if total_filtered > 0 else 0.0
            
            stats.append({
                "spreadsheet": sheet_name,
                "main_url": main_url,
                "queries_count": queries_count,
                "total_filtered_urls": total_filtered,
                "successful_urls": successful,
                "failed_urls": failed,
                "success_rate": success_rate
            })
    
    return stats


if __name__ == "__main__":
    """
    Пример использования - проверка файла step6_html_parsed.json
    """
    # Загружаем данные
    test_file = Path(__file__).parent.parent / "jsontests" / "step7_html_reparsed.json"
    
    if not test_file.exists():
        print("Error: File not found")
        sys.exit(1)
    
    with open(test_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Параметры валидации
    min_success = 0.6  # 70%
    
    # Валидация
    result = validate_parsing_quality(
        data=data,
        min_success_rate=min_success
    )
    
    # Вывод результата (с отладочной информацией)
    print(f"Основных URL: {result['total_main_urls']}")
    print(f"Всего запросов: {result['total_queries']}")
    print(f"Всего filtered_urls: {result['total_filtered_urls']}")
    print(f"Успешных URL: {result['successful_urls']}")
    print(f"С ошибками: {result['failed_urls']}")
    print(f"Процент: {result['success_rate']:.1%}")
    print(f"Валидация: {result['valid']}")
    
    if result['issues']:
        print(f"\nПроблемы ({len(result['issues'])}):")
        for issue in result['issues'][:5]:  # Показываем первые 5
            print(f"  - {issue}")
    
    sys.exit(0 if result['valid'] else 1)
