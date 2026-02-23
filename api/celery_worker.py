"""
Celery worker с задачами
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Добавляем корневую папку проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "gsheets"))

from api.celery_config import celery_app
from gsheets.sheets_reader import process_specific_spreadsheets  # type: ignore
from gsheets.data_updater import update_all_data_sheets  # type: ignore
from gsheets.sheets_updater import update_all_spreadsheets  # type: ignore
from metagenerator_pipeline import run_metagenerator_pipeline
from logger_config import get_pipeline_logger

logger = get_pipeline_logger()


@celery_app.task(bind=True, name="metagenerator.process_spreadsheets")
def process_spreadsheets_task(
    self,
    spreadsheet_ids: list[str],
    enable_classification: bool = False,
    enable_metatag_editor: bool = False
):
    """
    Celery задача для обработки таблиц и генерации метатегов
    
    Args:
        self: Celery task instance (bind=True)
        spreadsheet_ids: Список ID Google таблиц
        enable_classification: Включить классификацию страниц
        enable_metatag_editor: Включить проверку метатегов
        
    Returns:
        dict: Результат выполнения
    """
    task_id = self.request.id
    logger.info(f"[TASK {task_id}] Начало обработки {len(spreadsheet_ids)} таблиц")
    
    try:
        # Обновляем статус: "Чтение Google Sheets"
        self.update_state(
            state='PROGRESS',
            meta={'progress': 'MAIN: ШАГ 1/4: Чтение данных из Google Sheets'}
        )
        
        # Шаг 1: Чтение конкретных Google Sheets (только запрошенные таблицы)
        logger.info(f"[TASK {task_id}] MAIN: ШАГ 1/4: Чтение данных из Google Sheets")
        logger.info(f"[TASK {task_id}] Запрошено таблиц: {len(spreadsheet_ids)}")
        
        data = process_specific_spreadsheets(spreadsheet_ids)
        
        if not data:
            raise ValueError(f"Ни одна из таблиц {spreadsheet_ids} не найдена или не содержит URL для обработки")
        
        logger.info(f"[TASK {task_id}] Загружено {len(data)} таблиц с данными")
        
        # Обновляем статус: "Основная обработка"
        self.update_state(
            state='PROGRESS',
            meta={'progress': 'MAIN: ШАГ 2/4: Основная обработка данных (metagenerator_pipeline)'}
        )
        
        # Шаг 2: Основная обработка данных через pipeline
        logger.info(f"[TASK {task_id}] MAIN: ШАГ 2/4: Основная обработка данных")
        
        # Запускаем async функцию в sync контексте Celery
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            data = loop.run_until_complete(
                run_metagenerator_pipeline(
                    data=data,
                    enable_classification=enable_classification,
                    enable_metatag_editor=enable_metatag_editor
                )
            )
        finally:
            loop.close()
        
        logger.info(f"[TASK {task_id}] Pipeline завершен успешно")
        
        # Обновляем статус: "Обновление Data листа"
        self.update_state(
            state='PROGRESS',
            meta={'progress': 'MAIN: ШАГ 3/4: Обновление листа Data в Google Sheets'}
        )
        
        # Шаг 3: Обновление листа Data
        logger.info(f"[TASK {task_id}] MAIN: ШАГ 3/4: Обновление листа Data")
        data_update_stats = update_all_data_sheets(frequency_data=data)
        
        # Обновляем статус: "Обновление Meta листа"
        self.update_state(
            state='PROGRESS',
            meta={'progress': 'MAIN: ШАГ 4/4: Обновление листа Meta в Google Sheets'}
        )
        
        # Шаг 4: Обновление листа Meta
        logger.info(f"[TASK {task_id}] MAIN: ШАГ 4/4: Обновление листа Meta")
        meta_update_stats = update_all_spreadsheets(
            data=data,
            sheet_name="Meta"
        )
        
        logger.info(f"[TASK {task_id}] Обработка завершена успешно")
        
        # Возвращаем результат
        return {
            "status": "completed",
            "spreadsheet_ids": spreadsheet_ids,
            "data_update": data_update_stats.get('total_stats', {}),
            "meta_update": meta_update_stats,
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[TASK {task_id}] Ошибка: {str(e)}", exc_info=True)
        # Celery автоматически пометит задачу как FAILURE
        raise
