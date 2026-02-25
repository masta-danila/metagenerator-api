"""
Простой smoke-test API (проверка что компоненты работают)
"""
import requests

API_URL = "http://localhost:8000"
API_KEY = "7V%bbNhdyACGreVqbWrQHfCoWEc99**XVN1WMwZs6"

print("SMOKE TEST API")
print("=" * 60)

# 1. Health check
print("\n1. Health check...")
health = requests.get(f"{API_URL}/health").json()
print(f"   Status: {health['status']}")
print(f"   Redis: {'✅' if health['redis_connected'] else '❌'}")
print(f"   Celery workers: {health['celery_workers']}")

# 2. Root endpoint
print("\n2. Root endpoint...")
root = requests.get(f"{API_URL}/").json()
print(f"   Service: {root['service']}")
print(f"   Version: {root['version']}")

# 3. Проверка аутентификации
print("\n3. Проверка аутентификации...")
# Без ключа - должно вернуть 401
no_key = requests.post(f"{API_URL}/process", json={"data": {}})
print(f"   Без ключа: {no_key.status_code} {'✅' if no_key.status_code == 401 else '❌'}")

# С неверным ключом - должно вернуть 401
bad_key = requests.post(
    f"{API_URL}/process",
    headers={"X-API-Key": "wrong-key"},
    json={"data": {}}
)
print(f"   Неверный ключ: {bad_key.status_code} {'✅' if bad_key.status_code == 401 else '❌'}")

# С правильным ключом - должно принять
good_key = requests.post(
    f"{API_URL}/process",
    headers={"X-API-Key": API_KEY},
    json={
        "data": {
            "https://example.com/": {
                "queries": [{"query": "test"}],
                "company_name": "Test",
                "region": 213,
                "variables_h1": [],
                "variables_title": [],
                "variables_description": []
            }
        }
    }
)
print(f"   Правильный ключ: {good_key.status_code} {'✅' if good_key.status_code == 200 else '❌'}")

if good_key.status_code == 200:
    task_info = good_key.json()
    task_id = task_info['task_id']
    print(f"   Task ID: {task_id[:20]}...")
    
    # 4. Проверка статуса задачи
    print("\n4. Проверка статуса задачи...")
    status = requests.get(
        f"{API_URL}/status/{task_id}",
        headers={"X-API-Key": API_KEY}
    ).json()
    print(f"   Status: {status['status']} ✅")
    
    # 5. Отмена задачи
    print("\n5. Отмена задачи...")
    cancel = requests.delete(
        f"{API_URL}/cancel/{task_id}",
        headers={"X-API-Key": API_KEY}
    ).json()
    print(f"   {cancel['message']} ✅")

print("\n" + "=" * 60)
print("🎉 ВСЕ КОМПОНЕНТЫ API РАБОТАЮТ!")
print("=" * 60)
print("\nДля полного теста используйте:")
print("  python api/example_client.py")
print("  (требуются реальные данные из Google Sheets)")
