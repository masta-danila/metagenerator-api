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

from api.celery_config import celery_app
from metagenerator_pipeline import run_metagenerator_pipeline
from logger_config import get_pipeline_logger

logger = get_pipeline_logger()


@celery_app.task(bind=True, name="metagenerator.process_pipeline")
def process_pipeline_task(
    self,
    data: dict,
    enable_classification: bool = False,
    enable_metatag_editor: bool = False
):
    """
    Celery задача для обработки данных через metagenerator_pipeline
    
    Args:
        self: Celery task instance (bind=True)
        data: Словарь с данными из Google Sheets
        enable_classification: Включить классификацию страниц
        enable_metatag_editor: Включить проверку метатегов
        
    Returns:
        dict: Обработанные данные (очищенные от промежуточной информации)
    """
    task_id = self.request.id
    
    # Подсчитываем количество URL (data = {url: {...}})
    total_urls = len(data)
    
    logger.info(f"[TASK {task_id}] Начало обработки: {total_urls} URL")
    
    try:
        # Обновляем статус: задача выполняется
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 'Обработка данных...',
                'started_at': datetime.now().isoformat()
            }
        )
        
        # Обертываем данные в структуру таблицы (pipeline ожидает {spreadsheet_id: {urls: {...}}})
        wrapped_data = {
            "API_REQUEST": {
                "urls": data
            }
        }
        
        # Запускаем metagenerator_pipeline
        logger.info(f"[TASK {task_id}] Запуск metagenerator_pipeline")
        
        # Запускаем async функцию в sync контексте Celery
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_data = loop.run_until_complete(
                run_metagenerator_pipeline(
                    data=wrapped_data,
                    enable_classification=enable_classification,
                    enable_metatag_editor=enable_metatag_editor
                )
            )
        finally:
            loop.close()
        
        # Разворачиваем обратно (убираем уровень таблицы)
        if "API_REQUEST" in result_data and "urls" in result_data["API_REQUEST"]:
            result_data = result_data["API_REQUEST"]["urls"]
        
        # Очищаем от исходных входных данных (оставляем только результаты обработки)
        cleaned_data = {}
        for url, url_data in result_data.items():
            cleaned_url_data = {}
            
            # Оставляем только поля с результатами обработки
            result_fields = [
                'generated_metatags',
                'wordstat_cost',
                'yandex_search_cost',
                'metageneration_cost',
                'classification_cost',
                'metatag_editor_cost',
            ]
            
            for field in result_fields:
                if field in url_data:
                    cleaned_url_data[field] = url_data[field]
            
            cleaned_data[url] = cleaned_url_data
        
        logger.info(f"[TASK {task_id}] Pipeline завершен успешно")
        
        # Возвращаем обработанные данные
        return {
            "status": "completed",
            "data": cleaned_data,  # Только результаты обработки
            "completed_at": datetime.now().isoformat(),
            "urls_processed": len(cleaned_data)
        }
        
    except Exception as e:
        logger.error(f"[TASK {task_id}] Ошибка: {str(e)}", exc_info=True)
        # Celery автоматически пометит задачу как FAILURE
        raise
