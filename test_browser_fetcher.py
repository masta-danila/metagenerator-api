#!/usr/bin/env python3
"""
Тест BrowserFetcher - проверяем что именно палится
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from site_parser.browser_fetcher import BrowserFetcher

def test_browser_fetcher():
    """Тест BrowserFetcher как в batch_browser_processor"""
    
    print("🧪 Тест BrowserFetcher (как в batch_browser_processor)\n")
    
    test_urls = [
        "https://www.google.com/",
        "https://www.vseinstrumenti.ru/category/gidravlicheskie-telezhki-2082/"
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n{i}️⃣ Тест {i}/{len(test_urls)}: {url}")
        
        fetcher = None
        try:
            # Создаем браузер (как в parse_url_with_browser)
            fetcher = BrowserFetcher(
                device_type="desktop",
                visible=True,  # Видимый режим для проверки
                use_proxy=False,
                proxy_manager=None
            )
            
            print("   🚀 Запускаем браузер...")
            if not fetcher.start():
                print("   ❌ Не удалось запустить браузер")
                continue
            
            print(f"   📄 Загружаем страницу...")
            html = fetcher.fetch_html(url, wait_time=3, clean_html=False, min_html_length=1000)
            
            # Закрываем браузер
            print("   🔒 Закрываем браузер...")
            fetcher.close()
            fetcher = None
            
            # Проверяем результат
            if html:
                print(f"   ✅ Успешно! Получено {len(html)} символов")
                
                # Проверяем на блокировку
                if "Access denied" in html or "Access Denied" in html:
                    print("   ❌ БЛОКИРОВКА! Access Denied")
                elif "captcha" in html.lower():
                    print("   ⚠️  CAPTCHA обнаружена")
                elif len(html) > 50000:
                    print("   ✅✅✅ Отлично! Полная страница загружена")
                else:
                    print(f"   ⚠️  Мало HTML, возможна блокировка")
            else:
                print("   ❌ HTML не получен (None)")
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        finally:
            if fetcher:
                try:
                    fetcher.close()
                except:
                    pass
        
        print("   ⏸️  Нажмите Enter для следующего теста...")
        input()
    
    print("\n✅ Тест завершен")

if __name__ == "__main__":
    test_browser_fetcher()
