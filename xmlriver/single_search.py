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
    user_id = os.getenv("XMLRIVER_USER_ID", "8834")
    api_key = os.getenv("XMLRIVER_API_KEY", "e5a50999a40533aa928bb89be21e53c1ebd93ef2")
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
    
    logger.info(f"[REQUEST] XMLRiver: query='{query}', lr={region}, device={device}")
    logger.debug(f"[DEBUG] Full params: {params}")
    
    api_requests = 0  # Счетчик фактических запросов к API
    
    for attempt in range(max_retries):
        try:
            # XMLRiver требует таймаут минимум 60 секунд (максимальное время ответа)
            # Устанавливаем 90 секунд для надежности
            timeout = httpx.Timeout(90.0, connect=10.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(API_URL, params=params)
            
            logger.debug(f"[DEBUG] XMLRiver response: status_code={response.status_code}, length={len(response.text)}")
            
            # Обработка 429 (Too Many Requests)
            if response.status_code == 429:
                # При rate limit деньги не снимаются - НЕ увеличиваем api_requests
                wait_time = 60 * (attempt + 1)
                logger.warning(f"[WARN] Rate limit (429). Попытка {attempt + 1}/{max_retries}. Ожидание {wait_time} сек...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"[ERROR] Превышено максимальное количество попыток при rate limit")
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
            logger.error(f"[ERROR] search_yandex: таймаут запроса (попытка {attempt + 1}/{max_retries}) - {e}")
            if attempt < max_retries - 1:
                logger.info(f"[RETRY] Повторная попытка через 10 секунд...")
                await asyncio.sleep(10)
                continue
            return {
                "success": False,
                "data": None,
                "error": "Request timeout",
                "api_requests": api_requests
            }
        
        except httpx.HTTPStatusError as e:
            # При HTTP ошибке деньги не снимаются - НЕ увеличиваем api_requests
            logger.error(f"[ERROR] search_yandex: HTTP ошибка {e.response.status_code} (попытка {attempt + 1}/{max_retries}) - {e}")
            logger.error(f"[ERROR] Response content: {e.response.text[:200]}")
            if attempt < max_retries - 1:
                logger.info(f"[RETRY] Повторная попытка через 10 секунд...")
                await asyncio.sleep(10)
                continue
            return {
                "success": False,
                "data": None,
                "error": f"HTTP {e.response.status_code}",
                "api_requests": api_requests
            }
        
        except httpx.RequestError as e:
            logger.error(f"[ERROR] search_yandex: ошибка HTTP запроса (попытка {attempt + 1}/{max_retries})")
            logger.error(f"[ERROR] Тип ошибки: {type(e).__name__}")
            logger.error(f"[ERROR] Детали: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"[RETRY] Повторная попытка через 10 секунд...")
                await asyncio.sleep(10)
                continue
            return {
                "success": False,
                "data": None,
                "error": f"Request error: {str(e)}",
                "api_requests": api_requests
            }
        
        except Exception as e:
            logger.error(f"[ERROR] search_yandex: неожиданная ошибка (попытка {attempt + 1}/{max_retries}) - {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"[RETRY] Повторная попытка через 10 секунд...")
                await asyncio.sleep(10)
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
