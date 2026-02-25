"""
Модуль для получения частотности запросов через XMLRiver Wordstat API
"""

import os
import asyncio
import json
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv
import httpx
import sys

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import get_search_logger

logger = get_search_logger()

# Загружаем переменные окружения
load_dotenv()

# API endpoint для Wordstat
WORDSTAT_API_URL = "http://xmlriver.com/wordstat/new/json"


def get_api_credentials() -> dict:
    """Получает API credentials из переменных окружения"""
    user_id = os.getenv("XMLRIVER_USER_ID")
    api_key = os.getenv("XMLRIVER_API_KEY")
    if not user_id or not api_key:
        raise ValueError("XMLRIVER_USER_ID и XMLRIVER_API_KEY должны быть заданы в .env")
    return {"user": user_id, "key": api_key}


async def get_query_frequency(
    query: str,
    regions: Optional[int] = None,
    device: str = "desktop",
    exact_match: bool = True,
    max_retries: int = 3,
) -> Dict[str, any]:
    """
    Получает частотность запроса через XMLRiver Wordstat API.
    
    Частота берется из поля "totalValue" в ответе основной вкладки Wordstat.
    
    Args:
        query: Поисковый запрос
        regions: ID региона Яндекса (None = все регионы, 213 = Москва)
        device: Устройство (desktop, phone, tablet)
        exact_match: Если True (по умолчанию) - добавляет кавычки и ! перед каждым словом
                     для точной частотности ("!входные !двери").
                     Если False - запрос передается как есть (широкая частотность).
        max_retries: Количество повторных попыток при ошибках
        
    Returns:
        Словарь с ключами:
        - query: исходный запрос
        - frequency: частотность запроса (totalValue)
        - error: текст ошибки (если есть)
        - api_requests: количество фактических запросов к API (для подсчета стоимости)
        
    Пример:
        exact_match=True: "входные двери" → "!входные !двери" → частота ≈1500 (точная)
        exact_match=False: "входные двери" → "входные двери" → частота ≈120000 (широкая)
    """
    # Получаем credentials
    credentials = get_api_credentials()
    
    # Подготавливаем запрос
    if exact_match:
        # "Чистый" запрос: добавляем кавычки и ! перед каждым словом
        # "входные двери" -> "!входные !двери"
        # Оператор ! фиксирует словоформу, кавычки - точное соответствие
        words = query.split()
        clean_words = ["!" + word for word in words]
        prepared_query = '"' + " ".join(clean_words) + '"'
    else:
        # "Грязный" запрос: передаем как есть
        prepared_query = query
    
    # НЕ кодируем вручную - httpx сделает это автоматически
    # Формируем параметры запроса (БЕЗ pagetype - используем основную вкладку)
    params = {
        "user": credentials["user"],
        "key": credentials["key"],
        "query": prepared_query,  # передаем как есть, httpx закодирует
    }
    
    # Добавляем опциональные параметры
    if regions is not None:
        params["regions"] = regions
    
    if device:
        params["device"] = device
    
    # Делаем запрос с повторными попытками
    api_requests = 0  # Счетчик фактических запросов к API
    
    for attempt in range(max_retries):
        try:
            logger.info(f"[Попытка {attempt + 1}/{max_retries}] Запрос частотности: {query} (подготовлен: {prepared_query})")
            
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.get(WORDSTAT_API_URL, params=params)
                response.raise_for_status()
                
                # Парсим JSON ответ
                data = response.json()
                
                # Проверяем на ошибки API
                if "error" in data:
                    error_code = data.get("error_code", "unknown")
                    error_message = data.get("error", "Unknown error")
                    logger.error(f"[ERROR] XMLRiver API ошибка {error_code}: {error_message}")
                    # При ошибке API деньги не снимаются - НЕ увеличиваем api_requests
                    
                    # Если это последняя попытка - возвращаем ошибку
                    if attempt == max_retries - 1:
                        return {
                            "query": query,
                            "frequency": None,
                            "error": f"API Error {error_code}: {error_message}",
                            "api_requests": api_requests
                        }
                    # Иначе ждем и повторяем попытку
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                
                # Извлекаем totalValue (частоту)
                # В ответе API это поле называется "totalValue" (с маленькой буквы)
                frequency = data.get("totalValue")
                
                if frequency is not None:
                    # Успешный запрос - увеличиваем счетчик (деньги списались)
                    api_requests += 1
                    logger.info(f"[OK] Частотность '{query}': {frequency}")
                    return {
                        "query": query,
                        "frequency": int(frequency) if frequency else 0,
                        "error": None,
                        "api_requests": api_requests
                    }
                else:
                    logger.warning(f"[WARNING] totalValue не найден в ответе для запроса: {query}")
                    # totalValue не найден - вероятно ошибка, НЕ увеличиваем api_requests
                    
                    # Если это последняя попытка - возвращаем ошибку
                    if attempt == max_retries - 1:
                        return {
                            "query": query,
                            "frequency": None,
                            "error": "totalValue not found in response",
                            "api_requests": api_requests
                        }
                    # Иначе ждем и повторяем попытку
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                
        except httpx.TimeoutException:
            # При timeout деньги не снимаются - НЕ увеличиваем api_requests
            logger.error(f"[ERROR] Таймаут при запросе частотности: {query}")
            if attempt == max_retries - 1:
                return {
                    "query": query,
                    "frequency": None,
                    "error": "Request timeout",
                    "api_requests": api_requests
                }
            await asyncio.sleep(2 * (attempt + 1))
            
        except httpx.HTTPStatusError as e:
            # При HTTP ошибке деньги не снимаются - НЕ увеличиваем api_requests
            logger.error(f"[ERROR] HTTP ошибка {e.response.status_code} для запроса: {query}")
            if attempt == max_retries - 1:
                return {
                    "query": query,
                    "frequency": None,
                    "error": f"HTTP {e.response.status_code}",
                    "api_requests": api_requests
                }
            await asyncio.sleep(2 * (attempt + 1))
            
        except json.JSONDecodeError as e:
            # При ошибке парсинга JSON деньги не снимаются - НЕ увеличиваем api_requests
            logger.error(f"[ERROR] Ошибка парсинга JSON для запроса '{query}': {e}")
            if attempt == max_retries - 1:
                return {
                    "query": query,
                    "frequency": None,
                    "error": "JSON decode error",
                    "api_requests": api_requests
                }
            await asyncio.sleep(2 * (attempt + 1))
            
        except Exception as e:
            # При неожиданной ошибке деньги не снимаются - НЕ увеличиваем api_requests
            logger.error(f"[ERROR] Неожиданная ошибка для запроса '{query}': {e}")
            if attempt == max_retries - 1:
                return {
                    "query": query,
                    "frequency": None,
                    "error": str(e),
                    "api_requests": api_requests
                }
            await asyncio.sleep(2 * (attempt + 1))
    
    # Если все попытки неудачны
    return {
        "query": query,
        "frequency": None,
        "error": "All retry attempts failed",
        "api_requests": api_requests
    }




if __name__ == "__main__":
    """
    Тестовый запуск - получает частотность для одного запроса
    """
    async def test():
        # Тестовый запрос
        test_query = "теплообменник для вентиляции"
        
        logger.info(f"Тест сбора частотности для запроса: {test_query}")
        logger.info(f"Регион: 213 (Москва)")
        logger.info(f"Устройство: desktop")
        logger.info(f"Режим: exact_match=True (точная частотность)")
        
        # Получаем точную частотность
        result = await get_query_frequency(
            query=test_query,
            regions=213,
            device="",
            exact_match=True  # "!входные !двери" -> ~1500
        )
        
        # Выводим результаты
        logger.info("РЕЗУЛЬТАТ:")
        
        query = result["query"]
        frequency = result["frequency"]
        error = result.get("error")
        
        if error:
            logger.error(f"{query}: ОШИБКА - {error}")
        else:
            logger.info(f"Запрос: {query}")
            logger.info(f"Частота: {frequency:,}")
        
        # Сохраняем в JSON
        project_root = Path(__file__).parent.parent
        output_file = project_root / "jsontests" / "wordstat_frequency_result.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Результат сохранен в файл: {output_file}")
    
    asyncio.run(test())
