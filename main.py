"""
Полный цикл генерации метатегов из Google Sheets

Выполняет 4 основных шага:
1. Чтение данных из Google Sheets
2. Основная обработка через metagenerator_pipeline (10 внутренних шагов)
3. Обновление листа Data в Google Sheets частотностью
4. Обновление листа Meta в Google Sheets метатегами
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
from data_updater import update_all_data_sheets  # type: ignore
from sheets_updater import update_all_spreadsheets  # type: ignore
from logger_config import get_pipeline_logger
from metagenerator_pipeline import run_metagenerator_pipeline

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
    logger.info("MAIN: ШАГ 1/4: Чтение данных из Google Sheets")
    data = process_all_spreadsheets()
    save_step_results(data, "step1_sheets_data.json")
    
    # Шаг 2: Основная обработка данных через metagenerator_pipeline
    logger.info("MAIN: ШАГ 2/4: Основная обработка данных (metagenerator_pipeline)")
    try:
        data = await run_metagenerator_pipeline(
            data=data,
            enable_classification=False,  # Классификация страниц (шаг 8)
            enable_metatag_editor=False   # Проверка метатегов (шаг 11)
        )
        save_step_results(data, "step11_pipeline_result.json")
    except RuntimeError as e:
        logger.error(f"  ✗ Пайплайн прерван: {e}")
        return False  # Прерываем выполнение
    except Exception as e:
        logger.error(f"  ✗ Ошибка в пайплайне: {e}")
        return False
    
    # Шаг 3: Обновление листа Data в Google Sheets (частотность)
    logger.info("MAIN: ШАГ 3/4: Обновление листа Data в Google Sheets частотностью")
    data_update_stats = update_all_data_sheets(frequency_data=data)
    save_step_results(data_update_stats, "step12_data_update_stats.json")
    
    # Шаг 4: Обновление листа Meta в Google Sheets (метатеги)
    logger.info("MAIN: ШАГ 4/4: Обновление листа Meta в Google Sheets метатегами")
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
