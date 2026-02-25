"""
Pydantic модели для API
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class TaskRequest(BaseModel):
    """Запрос на создание задачи обработки данных через metagenerator_pipeline"""
    
    data: Dict[str, Any] = Field(
        ...,
        description="Словарь с URL и их данными (структура: {url: {queries, company_name, region, ...}})"
    )
    
    enable_classification: bool = Field(
        default=False,
        description="Включить классификацию страниц через LLM (pipeline шаг 7)"
    )
    
    enable_metatag_editor: bool = Field(
        default=False,
        description="Включить проверку и исправление метатегов через LLM (pipeline шаг 10)"
    )


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
        description="Результат выполнения (только для completed)"
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
