"""
Пример использования Metagenerator API
Полный workflow: чтение Sheets → API обработка → обновление Sheets
"""
import requests
import time
import sys
from pathlib import Path

# Добавляем корневую папку проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gsheets.sheets_reader import process_all_spreadsheets
from gsheets.data_updater import update_all_data_sheets
from gsheets.sheets_updater import update_all_spreadsheets


# Настройки API
API_URL = "http://localhost:8000"
API_KEY = "7V%bbNhdyACGreVqbWrQHfCoWEc99**XVN1WMwZs6"  # Замените на ваш API ключ из .env


def main():
    """Основной workflow"""
    
    print("=" * 80)
    print("METAGENERATOR API - ПРИМЕР ИСПОЛЬЗОВАНИЯ")
    print("=" * 80)
    
    # ШАГ 1: Чтение данных из Google Sheets
    print("\n[1/4] Чтение данных из Google Sheets...")
    try:
        data = process_all_spreadsheets()
        
        if not data:
            print("❌ Ошибка: Не найдено ни одной таблицы для обработки")
            return
        
        tables_count = len(data)
        urls_count = sum(len(sheet_info.get('urls', {})) for sheet_info in data.values())
        
        print(f"✅ Загружено: {tables_count} таблиц, {urls_count} URL")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении Sheets: {e}")
        return
    
    # ШАГ 2: Отправка задачи в API
    print("\n[2/4] Отправка задачи в API...")
    try:
        response = requests.post(
            f"{API_URL}/process",
            headers={"X-API-Key": API_KEY},
            json={
                "data": data,
                "enable_classification": False,  # Включить при необходимости
                "enable_metatag_editor": False   # Включить при необходимости
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Ошибка API: {response.status_code}")
            print(response.text)
            return
        
        task_info = response.json()
        task_id = task_info["task_id"]
        
        print(f"✅ Задача создана: {task_id}")
        print(f"   Статус: {task_info['status']}")
        print(f"   Сообщение: {task_info['message']}")
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удается подключиться к API по адресу {API_URL}")
        print("   Убедитесь, что сервер запущен (./start_api.sh)")
        return
    except Exception as e:
        print(f"❌ Ошибка при отправке задачи: {e}")
        return
    
    # ШАГ 3: Ожидание выполнения задачи
    print("\n[3/4] Ожидание выполнения задачи...")
    print("(Это может занять несколько минут)")
    
    last_progress = None
    dots = 0
    
    while True:
        try:
            status_response = requests.get(
                f"{API_URL}/status/{task_id}",
                headers={"X-API-Key": API_KEY},
                timeout=10
            )
            
            if status_response.status_code != 200:
                print(f"\n❌ Ошибка при проверке статуса: {status_response.status_code}")
                return
            
            status_data = status_response.json()
            current_status = status_data["status"]
            
            # Завершено успешно
            if current_status == "completed":
                print("\n✅ Задача завершена успешно!")
                result_data = status_data["result"]["data"]
                
                stats = status_data["result"]
                print(f"   Обработано таблиц: {stats.get('tables_processed', 0)}")
                print(f"   Обработано URL: {stats.get('urls_processed', 0)}")
                
                break
            
            # Ошибка
            elif current_status == "failed":
                print(f"\n❌ Задача завершилась с ошибкой:")
                print(f"   {status_data.get('error', 'Неизвестная ошибка')}")
                return
            
            # В процессе
            else:
                progress = status_data.get("progress", "обработка...")
                
                # Выводим прогресс, если он изменился
                if progress != last_progress:
                    if last_progress is not None:
                        print()  # Новая строка после точек
                    print(f"   {progress}", end="", flush=True)
                    last_progress = progress
                    dots = 0
                else:
                    # Анимация точек
                    print(".", end="", flush=True)
                    dots += 1
                    if dots >= 50:
                        print()
                        dots = 0
            
            time.sleep(5)  # Проверяем каждые 5 секунд
            
        except Exception as e:
            print(f"\n❌ Ошибка при проверке статуса: {e}")
            return
    
    # ШАГ 4: Обновление Google Sheets с результатами
    print("\n[4/4] Обновление Google Sheets...")
    try:
        # Обновляем Data лист
        print("   Обновление Data листа...", end="", flush=True)
        update_all_data_sheets(frequency_data=result_data)
        print(" ✅")
        
        # Обновляем Meta лист
        print("   Обновление Meta листа...", end="", flush=True)
        update_all_spreadsheets(data=result_data, sheet_name="Meta")
        print(" ✅")
        
        print("\n" + "=" * 80)
        print("🎉 ВСЕ ГОТОВО! Данные успешно обновлены в Google Sheets")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Ошибка при обновлении Sheets: {e}")
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
