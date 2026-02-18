#!/usr/bin/env python3
"""
Отладка vseinstrumenti.ru - смотрим ЧТО именно блокирует
"""
import undetected_chromedriver as uc
import time
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

def debug_vseinstrumenti():
    """Проверяем что показывает vseinstrumenti.ru"""
    
    print("🔍 Отладка vseinstrumenti.ru\n")
    
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = uc.Chrome(
        options=options,
        version_main=None,
        headless=False
    )
    
    try:
        # Сначала главная
        print("1️⃣ Заходим на главную vseinstrumenti.ru...")
        driver.get("https://www.vseinstrumenti.ru/")
        time.sleep(5)
        
        html = driver.page_source
        title = driver.title
        
        print(f"   📄 Title: {title}")
        print(f"   📏 HTML size: {len(html)} символов")
        
        # Проверяем признаки блокировки
        if "Access denied" in html or "Access Denied" in html:
            print("   ❌ ACCESS DENIED!")
        elif "Just a moment" in html or "Checking your browser" in html:
            print("   🔄 Cloudflare проверяет браузер...")
        elif "captcha" in html.lower():
            print("   🤖 CAPTCHA обнаружена")
        elif "ray id" in html.lower() or "cloudflare" in html.lower():
            print("   ☁️ Cloudflare активна")
        elif len(html) < 10000:
            print(f"   ⚠️ Подозрительно мало HTML")
        else:
            print("   ✅ Главная загружена нормально")
        
        print("\n   Оставляю браузер открытым - проверьте визуально что показывает сайт!")
        print("   Посмотрите есть ли:")
        print("     - Капча")
        print("     - Cloudflare challenge")
        print("     - Access Denied")
        print("     - Обычная страница")
        
        input("\n   Нажмите Enter когда проверите...")
        
        # Теперь категория
        print("\n2️⃣ Переходим в категорию...")
        driver.get("https://www.vseinstrumenti.ru/category/gidravlicheskie-telezhki-2082/")
        time.sleep(5)
        
        html2 = driver.page_source
        title2 = driver.title
        
        print(f"   📄 Title: {title2}")
        print(f"   📏 HTML size: {len(html2)} символов")
        
        if "Access denied" in html2 or "Access Denied" in html2:
            print("   ❌ ACCESS DENIED на категории!")
        elif "Just a moment" in html2:
            print("   🔄 Cloudflare снова проверяет...")
        elif "captcha" in html2.lower():
            print("   🤖 CAPTCHA на категории")
        elif len(html2) > 50000:
            print("   ✅ Категория загружена успешно!")
        else:
            print(f"   ⚠️ Мало HTML - возможна блокировка")
        
        # Сохраняем HTML для анализа
        with open("/tmp/vseinstrumenti_debug.html", "w", encoding="utf-8") as f:
            f.write(html2)
        print("\n   💾 HTML сохранен в /tmp/vseinstrumenti_debug.html")
        
        print("\n   Снова оставляю браузер - проверьте что видите!")
        input("   Нажмите Enter для выхода...")
        
    finally:
        driver.quit()
        print("\n🔒 Браузер закрыт")

if __name__ == "__main__":
    debug_vseinstrumenti()
