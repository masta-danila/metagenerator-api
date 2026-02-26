"""
Pydantic модели для API
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class TaskRequest(BaseModel):
    """
    Запрос на создание задачи обработки данных через metagenerator_pipeline
    
    Структура поля data:
    {
        "URL страницы": {
            "queries": [{"query": "текст запроса"}, ...],  # Список поисковых запросов
            "company_name": "Название компании",            # Название компании для контекста
            "region": 213,                                  # ID региона Яндекса (213 = Москва)
            "variables_h1": [],                             # Переменные для H1 (опционально)
            "variables_title": [],                          # Переменные для Title (опционально)
            "variables_description": []                     # Переменные для Description (опционально)
        }
    }
    """
    
    data: Dict[str, Any] = Field(
        ...,
        description="Словарь URL -> данные страницы (queries, company_name, region, variables)",
        json_schema_extra={
            "example": {
                "https://example.com/": {
                    "queries": [
                        {"query": "купить товар"},
                        {"query": "товар цена"}
                    ],
                    "company_name": "Моя Компания",
                    "region": 213,
                    "variables_h1": [],
                    "variables_title": [],
                    "variables_description": []
                },
                "https://example.com/services/": {
                    "queries": [
                        {"query": "услуги компании"}
                    ],
                    "company_name": "Моя Компания",
                    "region": 213,
                    "variables_h1": [],
                    "variables_title": [],
                    "variables_description": []
                }
            }
        }
    )
    
    enable_classification: bool = Field(
        default=False,
        description="Включить классификацию страниц через LLM (определение типа: коммерческая/информационная)"
    )
    
    enable_metatag_editor: bool = Field(
        default=False,
        description="Включить проверку и исправление метатегов через LLM после генерации"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "https://example.com/": {
                        "queries": [
                            {"query": "купить товар"},
                            {"query": "товар цена"}
                        ],
                        "company_name": "Моя Компания",
                        "region": 213,
                        "variables_h1": [],
                        "variables_title": [],
                        "variables_description": []
                    },
                    "https://example.com/services/": {
                        "queries": [
                            {"query": "услуги компании"},
                            {"query": "заказать услугу"}
                        ],
                        "company_name": "Моя Компания",
                        "region": 213,
                        "variables_h1": [],
                        "variables_title": [],
                        "variables_description": []
                    }
                },
                "enable_classification": False,
                "enable_metatag_editor": False
            }
        }


class TaskResponse(BaseModel):
    """Ответ при создании задачи"""
    
    task_id: str = Field(
        ...,
        description="Уникальный ID задачи",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    
    status: str = Field(
        ...,
        description="Статус задачи: queued, processing, completed, failed",
        example="queued"
    )
    
    created_at: str = Field(
        ...,
        description="Время создания задачи (ISO 8601)",
        example="2026-02-23T15:30:00"
    )
    
    message: str = Field(
        default="Задача создана и добавлена в очередь",
        description="Информационное сообщение"
    )
    
    urls_count: int = Field(
        ...,
        description="Количество URL для обработки"
    )


class TaskStatus(BaseModel):
    """Статус выполнения задачи"""
    
    task_id: str = Field(
        ...,
        description="ID задачи"
    )
    
    status: str = Field(
        ...,
        description="Статус: queued, processing, completed, failed",
        example="processing"
    )
    
    progress: Optional[str] = Field(
        default=None,
        description="Текущий прогресс (например, 'PIPELINE: ШАГ 3/10')",
        example="PIPELINE: ШАГ 5/10: Валидация качества парсинга"
    )
    
    created_at: Optional[str] = Field(
        default=None,
        description="Время создания задачи"
    )
    
    started_at: Optional[str] = Field(
        default=None,
        description="Время начала обработки"
    )
    
    completed_at: Optional[str] = Field(
        default=None,
        description="Время завершения"
    )
    
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Результат выполнения (только для completed)",
        json_schema_extra={
            "example": {
                "status": "completed",
                "data": {
                    "https://example.com/": {
                        "generated_metatags": {
                            "h1": "Купить товар - Моя Компания",
                            "title": "Купить товар по выгодной цене | Моя Компания",
                            "description": "Купить товар от Моя Компания. Лучшие цены и качество."
                        },
                        "wordstat_cost": {
                            "api_requests": 2,
                            "cost": 0.05,
                            "currency": "RUB"
                        },
                        "yandex_search_cost": {
                            "api_requests": 2,
                            "cost": 0.05,
                            "currency": "RUB"
                        },
                        "metageneration_cost": {
                            "api_requests": 1,
                            "cost": 0.006,
                            "currency": "USD"
                        },
                        "classification_cost": {
                            "api_requests": 0,
                            "cost": 0,
                            "currency": ""
                        },
                        "metatag_editor_cost": {
                            "api_requests": 0,
                            "cost": 0,
                            "currency": ""
                        }
                    }
                },
                "completed_at": "2026-02-24T15:30:00",
                "urls_processed": 1
            }
        }
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Сообщение об ошибке (только для failed)"
    )
    
    class Config:
        # Не включать в ответ поля со значением None
        exclude_none = True


class HealthResponse(BaseModel):
    """Ответ health check эндпоинта"""
    
    status: str = Field(
        default="healthy",
        description="Статус сервиса"
    )
    
    version: str = Field(
        ...,
        description="Версия API"
    )
    
    redis_connected: bool = Field(
        ...,
        description="Подключение к Redis"
    )
    
    celery_workers: int = Field(
        ...,
        description="Количество активных Celery workers"
    )
