"""
Модуль для обновления листа Data в Google Sheets с отсортированными запросами по частотности

Логика работы:
1. Читает текущие данные из листа Data
2. Для URL из словарика с частотностью - сортирует запросы по frequency (по убыванию)
3. Для URL, которых нет в словарике - оставляет как есть
4. Обновляет все данные одним batch запросом
"""
import json
import os
import sys
from typing import Dict, List, Optional
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import get_sheets_reader_logger

logger = get_sheets_reader_logger()


def col_index_to_letter(col_idx: int) -> str:
    """
    Конвертирует индекс колонки (0-based) в буквенную нотацию Google Sheets
    
    Args:
        col_idx: Индекс колонки (0 = A, 1 = B, ..., 25 = Z, 26 = AA, ...)
    
    Returns:
        str: Буквенная нотация (A, B, ..., Z, AA, AB, ...)
    
    Examples:
        0 -> A
        1 -> B
        25 -> Z
        26 -> AA
        27 -> AB
    """
    result = ""
    col_idx += 1  # Делаем 1-based для удобства
    
    while col_idx > 0:
        col_idx -= 1
        result = chr(65 + (col_idx % 26)) + result
        col_idx //= 26
    
    return result


def get_sheets_client():
    """
    Создает и возвращает клиент Google Sheets
    
    Returns:
        gspread.Client: Авторизованный клиент
    """
    credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(creds)
    
    return client


def load_spreadsheet_ids() -> List[str]:
    """
    Загружает список ID таблиц из spreadsheets.json
    
    Returns:
        List[str]: Список ID таблиц
    """
    spreadsheets_path = os.path.join(os.path.dirname(__file__), 'spreadsheets.json')
    
    with open(spreadsheets_path, 'r', encoding='utf-8') as f:
        spreadsheet_ids = json.load(f)
    
    return spreadsheet_ids


def update_data_sheet_with_frequency(
    spreadsheet_id: str,
    frequency_data: Dict,
    client: Optional[gspread.Client] = None
) -> Dict:
    """
    Обновляет лист Data в таблице, сортируя запросы по частотности
    
    Обновляет две колонки:
    - Querries: запросы (отсортированные по убыванию частотности)
    - Demand: частотности (соответствующие запросам)
    
    Args:
        spreadsheet_id: ID таблицы Google Sheets
        frequency_data: Словарь с данными частотности из wordstat_batch_result.json
        client: Клиент gspread (если None - создается новый)
    
    Returns:
        Dict: Статистика обновления
    """
    if client is None:
        client = get_sheets_client()
    
    try:
        # Открываем таблицу
        spreadsheet = client.open_by_key(spreadsheet_id)
        logger.info(f"Открыта таблица: {spreadsheet.title}")
        
        # Получаем лист Data
        try:
            data_sheet = spreadsheet.worksheet('Data')
        except gspread.exceptions.WorksheetNotFound:
            logger.warning(f"Лист 'Data' не найден в таблице {spreadsheet.title}")
            return {
                'spreadsheet_id': spreadsheet_id,
                'spreadsheet_title': spreadsheet.title,
                'error': 'Data sheet not found'
            }
        
        # Получаем все данные листа
        all_values = data_sheet.get_all_values()
        
        if not all_values:
            logger.warning(f"Лист Data пуст в таблице {spreadsheet.title}")
            return {
                'spreadsheet_id': spreadsheet_id,
                'spreadsheet_title': spreadsheet.title,
                'error': 'Data sheet is empty'
            }
        
        # Первая строка - заголовки
        headers = all_values[0]
        
        # Находим индексы нужных колонок
        try:
            url_idx = headers.index('URL') if 'URL' in headers else headers.index('url')
            queries_idx = headers.index('Querries') if 'Querries' in headers else headers.index('querries')
            demand_idx = headers.index('Demand') if 'Demand' in headers else None
            cost_idx = headers.index('Cost') if 'Cost' in headers else None
        except ValueError as e:
            logger.error(f"Не найдена обязательная колонка: {e}")
            return {
                'spreadsheet_id': spreadsheet_id,
                'spreadsheet_title': spreadsheet.title,
                'error': f'Required column not found: {e}'
            }
        
        if demand_idx is None:
            logger.warning(f"Колонка 'Demand' не найдена в таблице {spreadsheet.title}, частотность не будет обновлена")
        
        # Проверяем наличие колонки Cost, если нет - создаем
        if cost_idx is None:
            logger.info(f"Колонка 'Cost' не найдена в таблице {spreadsheet.title}, создаем...")
            # Добавляем заголовок в следующую свободную колонку
            cost_idx = len(headers)
            cost_col_letter = col_index_to_letter(cost_idx)
            data_sheet.update(f'{cost_col_letter}1', [['Cost']])
            
            # Делаем заголовок жирным
            data_sheet.format(f'{cost_col_letter}1', {
                'textFormat': {
                    'bold': True
                }
            })
            
            logger.info(f"Колонка 'Cost' создана: {cost_col_letter}")
        else:
            logger.info(f"Колонка 'Cost' найдена в таблице {spreadsheet.title}")
        
        # Получаем данные частотности для этой таблицы
        urls_with_frequency = frequency_data.get(spreadsheet_id, {}).get('urls', {})
        
        # Шаг 1: Группируем строки по URL
        url_rows = {}  # {url: [list of row indices]}
        
        for row_idx, row in enumerate(all_values[1:], start=2):  # start=2 т.к. индексация в Google Sheets с 1 и +1 заголовок
            if len(row) <= url_idx:
                continue
            
            url = row[url_idx].strip()
            if not url:
                continue
            
            if url not in url_rows:
                url_rows[url] = []
            url_rows[url].append(row_idx)
        
        # Подготавливаем batch update
        updates = []
        stats = {
            'total_rows': len(all_values) - 1,  # Без заголовка
            'urls_updated': 0,
            'urls_skipped': 0,
            'rows_updated': 0,
        }
        
        # Шаг 2: Обрабатываем каждый URL
        for url, row_indices in url_rows.items():
            # Проверяем, есть ли этот URL в словарике с частотностью
            if url not in urls_with_frequency:
                stats['urls_skipped'] += 1
                continue
            
            url_data = urls_with_frequency[url]
            queries_with_freq = url_data.get('queries', [])
            
            if not queries_with_freq:
                stats['urls_skipped'] += 1
                continue
            
            # Сортируем запросы по frequency (по убыванию)
            # None или 0 идут в конец
            sorted_queries = sorted(
                queries_with_freq,
                key=lambda x: (x.get('frequency') or 0, x.get('query', '')),
                reverse=True
            )
            
            # Заполняем существующие строки отсортированными запросами
            for i, row_idx in enumerate(row_indices):
                if i < len(sorted_queries):
                    query_item = sorted_queries[i]
                    query_text = query_item.get('query', '')
                    frequency = query_item.get('frequency')
                    wordstat_cost = query_item.get('wordstat_cost', 0)
                    
                    # Обновляем колонку Querries
                    queries_col_letter = col_index_to_letter(queries_idx)
                    queries_cell_range = f'{queries_col_letter}{row_idx}'
                    
                    updates.append({
                        'range': queries_cell_range,
                        'values': [[query_text]]
                    })
                    
                    # Обновляем колонку Demand (если она есть)
                    if demand_idx is not None:
                        demand_col_letter = col_index_to_letter(demand_idx)
                        demand_cell_range = f'{demand_col_letter}{row_idx}'
                        frequency_text = str(frequency) if frequency is not None else ''
                        
                        updates.append({
                            'range': demand_cell_range,
                            'values': [[frequency_text]]
                        })
                    
                    # Обновляем колонку Cost ТОЛЬКО если есть данные по стоимости
                    # Если wordstat_cost отсутствует или равен 0 - оставляем существующее значение в таблице
                    if cost_idx is not None and wordstat_cost is not None and wordstat_cost > 0:
                        cost_col_letter = col_index_to_letter(cost_idx)
                        cost_cell_range = f'{cost_col_letter}{row_idx}'
                        cost_text = str(wordstat_cost)
                        
                        updates.append({
                            'range': cost_cell_range,
                            'values': [[cost_text]]
                        })
                    
                    stats['rows_updated'] += 1
            
            stats['urls_updated'] += 1
            logger.debug(f"Обновление {url}: {len(row_indices)} строк, {len(sorted_queries)} запросов")
        
        # Применяем все обновления одним batch запросом
        if updates:
            logger.info(f"Применение {len(updates)} обновлений к листу Data...")
            
            # Формируем список обновляемых колонок
            updated_columns = ['Querries']
            if demand_idx is not None:
                updated_columns.append('Demand')
            if cost_idx is not None:
                updated_columns.append('Cost')
            
            logger.info(f"Обновляются колонки: {', '.join(updated_columns)}")
            data_sheet.batch_update(updates)
            logger.info(f"Успешно обновлено {len(updates)} ячеек")
        else:
            logger.info("Нет обновлений для применения")
        
        return {
            'spreadsheet_id': spreadsheet_id,
            'spreadsheet_title': spreadsheet.title,
            'stats': stats,
            'updates_applied': len(updates)
        }
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении таблицы {spreadsheet_id}: {e}")
        return {
            'spreadsheet_id': spreadsheet_id,
            'error': str(e)
        }


def update_all_data_sheets(frequency_data: Dict) -> Dict:
    """
    Обновляет листы Data во всех таблицах из spreadsheets.json
    
    Args:
        frequency_data: Словарь с данными частотности из wordstat_batch_result.json
    
    Returns:
        Dict: Общая статистика обновлений
    """
    # Создаем клиент один раз для всех таблиц
    client = get_sheets_client()
    
    # Загружаем список таблиц
    spreadsheet_ids = load_spreadsheet_ids()
    
    logger.info(f"Начало обновления {len(spreadsheet_ids)} таблиц...")
    
    results = []
    total_stats = {
        'total_spreadsheets': len(spreadsheet_ids),
        'successful_updates': 0,
        'failed_updates': 0,
        'total_urls_updated': 0,
        'total_urls_skipped': 0,
    }
    
    for spreadsheet_id in spreadsheet_ids:
        logger.info(f"Обработка таблицы: {spreadsheet_id}")
        
        result = update_data_sheet_with_frequency(
            spreadsheet_id=spreadsheet_id,
            frequency_data=frequency_data,
            client=client
        )
        
        results.append(result)
        
        if 'error' in result:
            total_stats['failed_updates'] += 1
            logger.error(f"Ошибка: {result['error']}")
        else:
            total_stats['successful_updates'] += 1
            if 'stats' in result:
                total_stats['total_urls_updated'] += result['stats']['urls_updated']
                total_stats['total_urls_skipped'] += result['stats']['urls_skipped']
            logger.info(f"Обновлено URL: {result.get('stats', {}).get('urls_updated', 0)}")
            logger.info(f"Пропущено URL: {result.get('stats', {}).get('urls_skipped', 0)}")
    
    logger.info("ИТОГОВАЯ СТАТИСТИКА")
    logger.info(f"Всего таблиц: {total_stats['total_spreadsheets']}")
    logger.info(f"Успешно обновлено: {total_stats['successful_updates']}")
    logger.info(f"Ошибок: {total_stats['failed_updates']}")
    logger.info(f"Всего URL обновлено: {total_stats['total_urls_updated']}")
    logger.info(f"Всего URL пропущено: {total_stats['total_urls_skipped']}")
    
    return {
        'results': results,
        'total_stats': total_stats
    }


if __name__ == "__main__":
    """
    Тестовый запуск - загружает данные из wordstat_batch_result.json
    и обновляет листы Data во всех таблицах
    
    Использование:
        python gsheets/data_updater.py
    """
    # Загружаем данные с частотностью
    project_root = Path(__file__).parent.parent
    input_file = project_root / "jsontests" / "wordstat_batch_result.json"
    
    logger.info(f"Загрузка данных из: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        frequency_data = json.load(f)
    
    logger.info("ЗАПУСК ОБНОВЛЕНИЯ ЛИСТОВ DATA")
    
    # Обновляем все таблицы
    result = update_all_data_sheets(frequency_data)
    
    logger.info("ОБНОВЛЕНИЕ ЗАВЕРШЕНО")
