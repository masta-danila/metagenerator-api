#!/usr/bin/env python3
"""
Тест антидетект браузера
Проверяет работу undetected-chromedriver на известных сайтах детекции ботов
"""
import undetected_chromedriver as uc
import time
import ssl
import urllib.request

# Временно отключаем проверку SSL для загрузки ChromeDriver
ssl._create_default_https_context = ssl._create_unverified_context

def test_antidetect():
    """Проверка антидетекта на нескольких сайтах"""
    
    print("🧪 Тест антидетект браузера\n")
    
    # Создаем драйвер с минимальными настройками
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = uc.Chrome(
        options=options,
        version_main=None,
        headless=False,  # Видимый режим для проверки
        use_subprocess=True
    )
    
    try:
        # Тест 1: Простая проверка - Google
        print("1️⃣ Проверка подключения - Google...")
        driver.get("https://www.google.com/")
        time.sleep(3)
        print("   ✅ Google загружен")
        
        # Тест 2: Яндекс
        print("\n2️⃣ Проверка - Яндекс...")
        driver.get("https://ya.ru/")
        time.sleep(3)
        print("   ✅ Яндекс загружен")
        
        # Тест 3: Реальный сайт - vseinstrumenti.ru
        print("\n3️⃣ ГЛАВНЫЙ ТЕСТ - vseinstrumenti.ru...")
        driver.get("https://www.vseinstrumenti.ru/category/gidravlicheskie-telezhki-2082/")
        time.sleep(5)
        
        # Проверяем что получили
        page_source = driver.page_source
        page_title = driver.title
        
        print(f"\n   📄 Заголовок страницы: {page_title}")
        print(f"   📏 Размер HTML: {len(page_source)} символов")
        
        # Анализируем содержимое
        if "Access denied" in page_source or "Access Denied" in page_source:
            print("   ❌ БЛОКИРОВКА! Сайт показывает 'Access Denied'")
        elif "captcha" in page_source.lower():
            print("   ⚠️  Обнаружена CAPTCHA - сайт подозревает бота")
        elif "blocked" in page_source.lower():
            print("   ❌ БЛОКИРОВКА! Найдено слово 'blocked'")
        elif len(page_source) > 50000:
            print("   ✅✅✅ УСПЕШНО! Получена полная страница")
            print("   🎉 Антидетект работает отлично!")
        elif len(page_source) > 10000:
            print("   ✅ Страница загружена, но возможно не полностью")
        else:
            print(f"   ❌ Подозрительно мало HTML - возможна блокировка")
        
        print("\n✅ Тест завершен. Визуально проверьте страницу в браузере.")
        input("Нажмите Enter для закрытия браузера...")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    finally:
        driver.quit()
        print("🔒 Браузер закрыт")

if __name__ == "__main__":
    test_antidetect()
