"""
Быстрый тест API с минимальными данными
"""
import requests
import time
import json

API_URL = "http://localhost:8000"
API_KEY = "7V%bbNhdyACGreVqbWrQHfCoWEc99**XVN1WMwZs6"  # Первый ключ из .env

# Тестовые данные (2 URL)
# Новая структура: {url: {данные}} без уровня таблиц
test_data = {
    "https://www.advertpro.ru/": {
        "queries": [
            {"query": "продвижение сайтов"},
            {"query": "раскрутка сайтов"}
        ],
        "company_name": "АдвертПро",
        "region": 213,  # Москва
        "variables_h1": [],
        "variables_title": [],
        "variables_description": []
    },
    "https://www.advertpro.ru/services/": {
        "queries": [
            {"query": "услуги продвижения"},
            {"query": "SEO услуги"}
        ],
        "company_name": "АдвертПро",
        "region": 213,  # Москва
        "variables_h1": [],
        "variables_title": [],
        "variables_description": []
    }
}

print("=" * 80)
print("ТЕСТ API - ОБРАБОТКА НЕСКОЛЬКИХ URL")
print("=" * 80)

# 1. Проверка health
print("\n[1/4] Проверка статуса API...")
try:
    health = requests.get(f"{API_URL}/health", timeout=5).json()
    print(f"✅ API работает")
    print(f"   Redis: {'✅' if health['redis_connected'] else '❌'}")
    print(f"   Celery workers: {health['celery_workers']}")
except Exception as e:
    print(f"❌ API не доступен: {e}")
    exit(1)

# 2. Отправка задачи
print("\n[2/4] Отправка тестовой задачи...")
print(f"   URL для обработки: {len(test_data)}")
total_queries = sum(len(url_data.get('queries', [])) for url_data in test_data.values())
print(f"   Всего запросов: {total_queries}")

# Настройки pipeline (можно изменить)
ENABLE_CLASSIFICATION = True  # Классификация страниц через LLM (шаг 7)
ENABLE_METATAG_EDITOR = True  # Проверка и исправление метатегов через LLM (шаг 10)

print(f"   Классификация: {'✅ Включена' if ENABLE_CLASSIFICATION else '❌ Выключена'}")
print(f"   Редактирование метатегов: {'✅ Включено' if ENABLE_METATAG_EDITOR else '❌ Выключено'}")

try:
    response = requests.post(
        f"{API_URL}/process",
        headers={"X-API-Key": API_KEY},
        json={
            "data": test_data,
            "enable_classification": ENABLE_CLASSIFICATION,
            "enable_metatag_editor": ENABLE_METATAG_EDITOR
        },
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.text)
        exit(1)
    
    task_info = response.json()
    task_id = task_info["task_id"]
    
    print(f"✅ Задача создана: {task_id}")
    print(f"   {task_info['message']}")
    
except Exception as e:
    print(f"❌ Ошибка при создании задачи: {e}")
    exit(1)

# 3. Ожидание выполнения
print("\n[3/4] Ожидание выполнения...")
print("(Это может занять несколько минут)")

last_progress = None
start_time = time.time()

while True:
    try:
        status_response = requests.get(
            f"{API_URL}/status/{task_id}",
            headers={"X-API-Key": API_KEY},
            timeout=10
        )
        
        if status_response.status_code != 200:
            print(f"\n❌ Ошибка при проверке статуса: {status_response.status_code}")
            exit(1)
        
        status_data = status_response.json()
        current_status = status_data["status"]
        
        # Завершено
        if current_status == "completed":
            elapsed = int(time.time() - start_time)
            print(f"\n✅ Задача завершена за {elapsed}с!")
            
            result = status_data["result"]
            print(f"   Обработано URL: {result.get('urls_processed', 0)}")
            
            # Показываем краткую сводку
            result_data = result.get("data", {})
            for url, url_data in result_data.items():
                print(f"\n   URL: {url}")
                
                # Классификация
                classification = url_data.get("classification", {})
                if classification:
                    print(f"      Тип страницы: {classification.get('page_type', 'N/A')}")
                    print(f"      Уверенность: {classification.get('confidence', 0):.2%}")
                
                # Метатеги
                metatags = url_data.get("generated_metatags", {})
                if metatags:
                    print(f"      H1: {metatags.get('h1', 'N/A')[:80]}...")
                    print(f"      Title: {metatags.get('title', 'N/A')[:80]}...")
                    print(f"      Description: {metatags.get('description', 'N/A')[:80]}...")
                
                # Стоимость
                total_cost = (
                    url_data.get('wordstat_cost', {}).get('total_rub', 0) +
                    url_data.get('yandex_search_cost', {}).get('total_rub', 0) +
                    url_data.get('metageneration_cost', {}).get('total_rub', 0) +
                    url_data.get('classification_cost', {}).get('total_rub', 0) +
                    url_data.get('metatag_editor_cost', {}).get('total_rub', 0)
                )
                print(f"      Общая стоимость: {total_cost:.2f} ₽")
            
            # Полный ответ API в виде словаря
            print("\n" + "=" * 80)
            print("ПОЛНЫЙ ОТВЕТ API:")
            print("=" * 80)
            print(json.dumps(status_data, indent=2, ensure_ascii=False))
            
            break
        
        # Ошибка
        elif current_status == "failed":
            print(f"\n❌ Задача завершилась с ошибкой:")
            print(f"   {status_data.get('error', 'Неизвестная ошибка')}")
            
            # Полный ответ API при ошибке
            print("\n" + "=" * 80)
            print("ПОЛНЫЙ ОТВЕТ API (ОШИБКА):")
            print("=" * 80)
            print(json.dumps(status_data, indent=2, ensure_ascii=False))
            exit(1)
        
        # В процессе
        else:
            progress = status_data.get("progress", "обработка...")
            
            if progress != last_progress:
                elapsed = int(time.time() - start_time)
                print(f"   [{elapsed}с] {progress}")
                last_progress = progress
        
        time.sleep(3)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        print(f"   Задача {task_id} продолжает выполняться в фоне")
        exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        exit(1)

print("\n" + "=" * 80)
print("🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
print("=" * 80)
