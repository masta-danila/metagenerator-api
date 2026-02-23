"""
Конфигурация API
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # API настройки
    API_TITLE: str = "Metagenerator API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "API для автоматической генерации SEO метатегов"
    
    # API ключи (через переменные окружения)
    API_KEYS: str = "test-api-key-123,another-key-456"  # Через запятую
    
    # Redis настройки
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    
    # Celery настройки
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600  # 1 час максимум на задачу
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def get_valid_api_keys(self) -> set[str]:
        """Возвращает множество валидных API ключей"""
        return set(key.strip() for key in self.API_KEYS.split(',') if key.strip())


# Глобальный экземпляр настроек
settings = Settings()
