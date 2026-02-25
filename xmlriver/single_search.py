"""
Простая функция для выполнения одиночного запроса к XMLRiver API.
Возвращает сырой XML ответ без парсинга.
"""

import os
import asyncio
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import httpx
import sys

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import get_search_logger

logger = get_search_logger()

# Загружаем переменные окружения из корня проекта
load_dotenv()

# API endpoint
API_URL = "http://xmlriver.com/search_yandex/xml"


def get_api_credentials() -> dict:
    """Получает API credentials из переменных окружения"""
    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")
    if not user_id or not api_key:
        raise ValueError("XMLRIVER_USER_ID и XMLRIVER_API_KEY должны быть заданы в .env")
    return {"user": user_id, "key": api_key}


async def search_yandex(
    query: str,
    region: int = 213,
    groupby: int = 10,
    page: int = 0,
    device: str = "mobile",
    domain: str = "ru",
    lang: str = "ru",
    max_retries: int = 3,
    retry_delay: int = 10,
    query_index: int = None,
    total_queries: int = None,
    outer_retry_attempt: int = None,
    outer_max_retries: int = None,
) -> dict:
    """
    Выполняет поиск в Яндексе через XMLRiver API.
    Возвращает сырой XML ответ.
    
    Args:
        query: Поисковый запрос
        region: ID региона Яндекса (213 = Москва, 2 = Санкт-Петербург)
        groupby: ТОП позиций для сбора (10, 20, 30...)
        page: Страница выдачи (0, 1, 2...)
        device: Устройство (desktop, tablet, mobile)
        domain: Домен Яндекса (ru, com, ua, com.tr, by, kz)
        lang: Язык (ru, uk, en...)
        max_retries: Максимальное количество повторных попыток
        retry_delay: Задержка между попытками в секундах
        query_index: Номер текущего запроса (для логов)
        total_queries: Общее количество запросов (для логов)
        outer_retry_attempt: Номер текущей попытки внешнего цикла (для логов)
        outer_max_retries: Максимальное количество попыток внешнего цикла (для логов)
    
    Returns:
        Словарь с ключами:
        - success: bool, успешен ли запрос
        - data: str, XML ответ от API или None при ошибке
        - error: str, текст ошибки или None при успехе
        - api_requests: int, количество фактических запросов к API
    """
    credentials = get_api_credentials()
    
    # Подготовка параметров запроса
    params = {
        "user": credentials["user"],
        "key": credentials["key"],
        "query": query,
        "lr": region,
        "groupby": groupby,
        "page": page,
        "device": device,
        "domain": domain,
        "lang": lang,
    }
    
    # Формируем префикс для логов
    log_prefix = ""
    if query_index is not None and total_queries is not None:
        log_prefix = f"[QUERY {query_index}/{total_queries}]"
    
    # Формируем информацию о попытке для логов
    if outer_retry_attempt is not None and outer_max_retries is not None:
        attempt_info = f"[ATTEMPT {outer_retry_attempt + 1}/{outer_max_retries}]"
        logger.info(f"{log_prefix}{attempt_info}[REQUEST] XMLRiver: query='{query}', lr={region}, device={device}")
    else:
        attempt_info = None  # Будет вычисляться динамически
        logger.info(f"{log_prefix}[REQUEST] XMLRiver: query='{query}', lr={region}, device={device}")
    
    logger.debug(f"{log_prefix}[DEBUG] Full params: {params}")
    
    api_requests = 0  # Счетчик фактических запросов к API
    
    for attempt in range(max_retries):
        try:
            # XMLRiver требует таймаут минимум 60 секунд (максимальное время ответа)
            # Устанавливаем 90 секунд для надежности
            timeout = httpx.Timeout(90.0, connect=10.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(API_URL, params=params)
            
            logger.debug(f"{log_prefix}[DEBUG] XMLRiver response: status_code={response.status_code}, length={len(response.text)}")
            
            # Обработка 429 (Too Many Requests)
            if response.status_code == 429:
                # При rate limit деньги не снимаются - НЕ увеличиваем api_requests
                wait_time = 60 * (attempt + 1)
                current_attempt = attempt_info if attempt_info else f"[ATTEMPT {attempt + 1}/{max_retries}]"
                logger.warning(f"{log_prefix}{current_attempt}[WARN] Rate limit (429). Ожидание {wait_time} сек...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"{log_prefix}[ERROR] Превышено максимальное количество попыток при rate limit")
                    return {
                        "success": False,
                        "data": None,
                        "error": "Rate limit exceeded",
                        "api_requests": api_requests
                    }
            
            response.raise_for_status()
            # Успешный запрос - увеличиваем счетчик (деньги списались)
            api_requests += 1
            return {
                "success": True,
                "data": response.text,
                "error": None,
                "api_requests": api_requests
            }
        
        except httpx.TimeoutException as e:
            # При timeout деньги не снимаются - НЕ увеличиваем api_requests
            current_attempt = attempt_info if attempt_info else f"[ATTEMPT {attempt + 1}/{max_retries}]"
            logger.error(f"{log_prefix}{current_attempt}[ERROR] Таймаут запроса: {e}")
            if attempt < max_retries - 1:
                logger.info(f"{log_prefix}[RETRY] Повторная попытка через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "data": None,
                "error": "Request timeout",
                "api_requests": api_requests
            }
        
        except httpx.HTTPStatusError as e:
            # При HTTP ошибке деньги не снимаются - НЕ увеличиваем api_requests
            current_attempt = attempt_info if attempt_info else f"[ATTEMPT {attempt + 1}/{max_retries}]"
            logger.error(f"{log_prefix}{current_attempt}[ERROR] HTTP {e.response.status_code}: {e}")
            logger.error(f"{log_prefix}[ERROR] Response: {e.response.text[:200]}")
            if attempt < max_retries - 1:
                logger.info(f"{log_prefix}[RETRY] Повторная попытка через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "data": None,
                "error": f"HTTP {e.response.status_code}",
                "api_requests": api_requests
            }
        
        except httpx.RequestError as e:
            current_attempt = attempt_info if attempt_info else f"[ATTEMPT {attempt + 1}/{max_retries}]"
            logger.error(f"{log_prefix}{current_attempt}[ERROR] Ошибка HTTP запроса: {type(e).__name__}")
            logger.error(f"{log_prefix}[ERROR] Детали: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"{log_prefix}[RETRY] Повторная попытка через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "data": None,
                "error": f"Request error: {str(e)}",
                "api_requests": api_requests
            }
        
        except Exception as e:
            current_attempt = attempt_info if attempt_info else f"[ATTEMPT {attempt + 1}/{max_retries}]"
            logger.error(f"{log_prefix}{current_attempt}[ERROR] Неожиданная ошибка: {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"{log_prefix}[RETRY] Повторная попытка через {retry_delay} секунд...")
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "data": None,
                "error": f"Unexpected error: {str(e)}",
                "api_requests": api_requests
            }
    
    return {
        "success": False,
        "data": None,
        "error": "All retry attempts failed",
        "api_requests": api_requests
    }


if __name__ == "__main__":
    """
    Простой тест - выполняет один запрос и выводит результат
    """
    import sys
    
    # Тестовый запрос
    test_query = "теплообменник для нагрева воды" if len(sys.argv) < 2 else sys.argv[1]
    
    logger.info(f"[TEST] Запуск теста для запроса: '{test_query}'")
    
    async def test():
        result = await search_yandex(
            query=test_query,
            region=213,
            groupby=10,
            device="mobile",
            domain="ru",
            lang="ru",
        )
        
        logger.info(f"[TEST] API запросов: {result['api_requests']}")
        
        if result['success'] and result['data']:
            xml_result = result['data']
            logger.info(f"[TEST] Получен XML ({len(xml_result)} символов)")
            logger.info(f"[TEST] Первые 500 символов: {xml_result[:500]}")
            
            # Сохраняем в файл для анализа
            output_file = Path(__file__).parent.parent / "jsontests" / "single_search_result.xml"
            output_file.parent.mkdir(exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(xml_result)
            logger.info(f"[TEST] XML сохранен в: {output_file}")
        else:
            logger.error(f"[TEST] Не удалось получить результат: {result.get('error', 'Unknown error')}")
    
    asyncio.run(test())
