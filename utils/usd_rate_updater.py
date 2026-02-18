"""
Модуль для получения актуального курса доллара с наценкой
"""
import json
import httpx
from pathlib import Path
from datetime import datetime, timedelta


def load_pricing_config() -> dict:
    """
    Загружает конфигурацию из config/usd_rate.json
    
    Returns:
        dict: Словарь с конфигурацией
    """
    config_path = Path(__file__).parent.parent / "config" / "usd_rate.json"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_pricing_config(config: dict) -> None:
    """
    Сохраняет конфигурацию в config/usd_rate.json
    
    Args:
        config: Словарь с конфигурацией
    """
    config_path = Path(__file__).parent.parent / "config" / "usd_rate.json"
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def fetch_usd_rate_from_cbr() -> float:
    """
    Получает актуальный курс доллара с API Центробанка РФ
    
    Returns:
        float: Курс USD/RUB или None при ошибке
    
    API: https://www.cbr-xml-daily.ru/daily_json.js
    """
    try:
        response = httpx.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        # Курс доллара находится в Valute.USD.Value
        usd_rate = data.get("Valute", {}).get("USD", {}).get("Value")
        
        if usd_rate:
            return float(usd_rate)
        
    except Exception as e:
        print(f"[WARNING] Не удалось получить курс с API ЦБ РФ: {e}")
    
    return None


def get_usd_rate_with_markup() -> float:
    """
    Получает курс доллара с наценкой
    
    Логика работы:
    1. Проверяет, прошел ли интервал обновления (update_interval_hours)
    2. Если прошел:
       - Запрашивает актуальный курс с API ЦБ РФ
       - Применяет наценку
       - Сохраняет в конфиг
    3. Если не прошел:
       - Возвращает курс с наценкой из конфига
    
    Returns:
        float: Курс USD/RUB с наценкой
    
    Example:
        >>> rate = get_usd_rate_with_markup()
        >>> # Если курс ЦБ = 91.5, наценка 20%, то вернет 109.8
    """
    config = load_pricing_config()
    
    # Проверяем, нужно ли обновлять курс
    last_updated_str = config.get('last_updated', '')
    update_interval_hours = config.get('update_interval_hours', 24)
    
    needs_update = True
    
    if last_updated_str:
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            now = datetime.now()
            time_diff = now - last_updated
            
            # Если прошло меньше интервала - обновление не нужно
            if time_diff < timedelta(hours=update_interval_hours):
                needs_update = False
                print(f"[INFO] Используется кэшированный курс (обновлен {time_diff.total_seconds() / 3600:.1f} часов назад)")
        except (ValueError, AttributeError):
            pass
    
    # Если нужно обновление - запрашиваем с API
    if needs_update:
        fresh_rate = fetch_usd_rate_from_cbr()
        
        if fresh_rate:
            # Обновляем конфиг только с курсом ЦБ
            config['usd_rate'] = fresh_rate
            config['last_updated'] = datetime.now().isoformat()
            
            save_pricing_config(config)
            
            print(f"[INFO] Курс обновлен: {fresh_rate} RUB (ЦБ РФ)")
        else:
            print("[WARNING] Не удалось получить курс с API, используется курс из конфига")
    
    # Вычисляем и возвращаем курс с наценкой
    base_rate = config.get('usd_rate', 91.5)
    markup_percentage = config.get('markup_percentage', 0.0)
    rate_with_markup = base_rate * (1 + markup_percentage / 100)
    
    return round(rate_with_markup, 2)


if __name__ == "__main__":
    """
    Тестовый запуск модуля
    """
    print("=" * 60)
    print("ТЕСТ МОДУЛЯ ПОЛУЧЕНИЯ КУРСА ДОЛЛАРА")
    print("=" * 60)
    
    print("\n1. Загрузка текущей конфигурации...")
    config = load_pricing_config()
    print(f"   Курс ЦБ: {config.get('usd_rate')} RUB")
    print(f"   Наценка: {config.get('markup_percentage')}%")
    print(f"   Последнее обновление: {config.get('last_updated')}")
    print(f"   Интервал обновления: {config.get('update_interval_hours')} часов")
    
    print("\n2. Получение актуального курса с наценкой...")
    rate_with_markup = get_usd_rate_with_markup()
    print(f"   Итоговый курс (ЦБ + {config.get('markup_percentage')}%): {rate_with_markup} RUB")
    
    print("\n" + "=" * 60)
