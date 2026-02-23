"""
Авторизация через API ключи
"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from api.config import settings

# Header для API ключа
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Проверяет валидность API ключа
    
    Args:
        api_key: API ключ из заголовка X-API-Key
        
    Returns:
        str: Валидный API ключ
        
    Raises:
        HTTPException: Если ключ невалидный
    """
    valid_keys = settings.get_valid_api_keys()
    
    if api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key
