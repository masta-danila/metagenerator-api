"""
FastAPI приложение для генерации метатегов
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import redis

from api.config import settings
from api.models import TaskRequest, TaskResponse, TaskStatus, HealthResponse
from api.auth import verify_api_key
from api.celery_worker import process_spreadsheets_task
from api.celery_config import celery_app

# Создаем FastAPI приложение
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (для веб-клиентов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшн указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["System"])
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "Metagenerator API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check эндпоинт
    Проверяет статус сервиса, Redis и Celery workers
    """
    # Проверка Redis
    redis_connected = False
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            socket_connect_timeout=2
        )
        r.ping()
        redis_connected = True
    except Exception:
        pass
    
    # Проверка Celery workers
    celery_workers = 0
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        if stats:
            celery_workers = len(stats)
    except Exception:
        pass
    
    return HealthResponse(
        status="healthy" if redis_connected and celery_workers > 0 else "degraded",
        version=settings.API_VERSION,
        redis_connected=redis_connected,
        celery_workers=celery_workers
    )


@app.post("/generate", response_model=TaskResponse, tags=["Tasks"])
async def generate_metatags(
    request: TaskRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Создает задачу на генерацию метатегов
    
    Процесс:
    1. Задача добавляется в очередь Celery
    2. Возвращается task_id для отслеживания статуса
    3. Используйте GET /status/{task_id} для проверки прогресса
    
    Требуется API ключ в заголовке X-API-Key
    """
    try:
        # Отправляем задачу в Celery
        task = process_spreadsheets_task.apply_async(
            kwargs={
                "spreadsheet_ids": request.spreadsheet_ids,
                "enable_classification": request.enable_classification,
                "enable_metatag_editor": request.enable_metatag_editor
            }
        )
        
        return TaskResponse(
            task_id=task.id,
            status="queued",
            created_at=datetime.now().isoformat(),
            message=f"Задача создана для обработки {len(request.spreadsheet_ids)} таблиц"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания задачи: {str(e)}"
        )


@app.get("/status/{task_id}", response_model=TaskStatus, tags=["Tasks"])
async def check_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Проверяет статус выполнения задачи
    
    Возможные статусы:
    - PENDING: Задача в очереди (или не найдена)
    - PROGRESS: Задача выполняется
    - SUCCESS: Задача завершена успешно
    - FAILURE: Ошибка выполнения
    - REVOKED: Задача отменена
    
    Требуется API ключ в заголовке X-API-Key
    """
    try:
        # Получаем результат задачи из Celery
        task_result = celery_app.AsyncResult(task_id)
        
        # Базовый ответ
        response = TaskStatus(
            task_id=task_id,
            status=task_result.state.lower()
        )
        
        # Добавляем дополнительную информацию в зависимости от статуса
        if task_result.state == 'PENDING':
            response.status = "queued"
            response.progress = "Задача в очереди"
            
        elif task_result.state == 'PROGRESS':
            response.status = "processing"
            if task_result.info:
                response.progress = task_result.info.get('progress')
                response.started_at = task_result.info.get('started_at')
                
        elif task_result.state == 'SUCCESS':
            response.status = "completed"
            response.result = task_result.result
            if task_result.result:
                response.completed_at = task_result.result.get('completed_at')
                
        elif task_result.state == 'FAILURE':
            response.status = "failed"
            response.error = str(task_result.info)
            
        elif task_result.state == 'REVOKED':
            response.status = "cancelled"
            response.error = "Задача была отменена"
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса: {str(e)}"
        )


@app.delete("/cancel/{task_id}", tags=["Tasks"])
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Отменяет выполнение задачи
    
    Примечание: Задача будет остановлена, но уже выполненная часть не откатится
    
    Требуется API ключ в заголовке X-API-Key
    """
    try:
        celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Задача отменена"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отмены задачи: {str(e)}"
        )


# Для запуска через uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
