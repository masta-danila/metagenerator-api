"""
Модуль для получения HTML через браузер - ТОЧНАЯ КОПИЯ debug_vseinstrumenti.py
"""
import time
import ssl
import sys
import logging
from typing import Optional
from pathlib import Path

import undetected_chromedriver as uc

# Отключаем SSL проверку для загрузки драйвера
ssl._create_default_https_context = ssl._create_unverified_context

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настраиваем логирование
try:
    from logger_config import get_browser_fetcher_logger
    logger = get_browser_fetcher_logger()
except ImportError:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)


class BrowserFetcher:
    """Класс для получения HTML через браузер - на основе debug_vseinstrumenti.py"""
    
    def __init__(self, device_type: str = "desktop", visible: bool = False, use_proxy: bool = False, proxy_manager = None):
        """
        Args:
            device_type: "desktop" или "mobile"
            visible: показывать браузер (True) или headless (False)
            use_proxy: ИГНОРИРУЕТСЯ
            proxy_manager: ИГНОРИРУЕТСЯ
        """
        self.device_type = device_type
        self.visible = visible
        self.driver = None
    
    def start(self) -> bool:
        """Запуск браузера - ТОЧНАЯ КОПИЯ debug_vseinstrumenti.py"""
        try:
            logger.info(f"Запуск браузера ({self.device_type}, {'visible' if self.visible else 'headless'})...")
            
            # ТОЧНО КАК В DEBUG
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
            # ТОЧНО КАК В DEBUG
            self.driver = uc.Chrome(
                options=options,
                version_main=None,
                headless=not self.visible
            )
            
            logger.info("Браузер успешно запущен")
            return True
        except Exception as e:
            error_msg = str(e).split('\n')[0]
            logger.error(f"Ошибка запуска браузера: {type(e).__name__}: {error_msg}")
            return False
    
    def fetch_html(self, url: str, wait_time: int = 5, clean_html: bool = False, min_html_length: int = 100, emulate_user: bool = False) -> Optional[str]:
        """Получить HTML - ТОЧНАЯ КОПИЯ debug_vseinstrumenti.py"""
        if not self.driver:
            logger.error("Браузер не запущен. Вызовите start() сначала.")
            return None
        
        try:
            logger.info(f"Загружаем: {url}")
            
            # ТОЧНО КАК В DEBUG
            self.driver.get(url)
            time.sleep(wait_time)
            html = self.driver.page_source
            
            if not html:
                logger.error("HTML не получен (None)")
                return None
            
            # Проверка длины
            if len(html) < min_html_length:
                logger.error(f"HTML слишком короткий: {len(html)} < {min_html_length} символов")
                return None
            
            logger.info(f"HTML получен ({len(html)} символов)")
            return html
        except Exception as e:
            error_msg = str(e).split('\n')[0]
            logger.error(f"Ошибка загрузки: {type(e).__name__}: {error_msg}")
            return None
    
    def close(self):
        """Закрыть браузер"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Браузер закрыт")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии браузера: {e}")
            finally:
                self.driver = None


if __name__ == "__main__":
    """Тест"""
    print("Тест BrowserFetcher\n")
    
    fetcher = BrowserFetcher(device_type="desktop", visible=True)
    
    if not fetcher.start():
        print("ОШИБКА: Не запустился")
        exit(1)
    
    print("Браузер запущен\n")
    
    url = "https://www.vseinstrumenti.ru/category/gidravlicheskie-telezhki-2082/"
    print(f"Загружаем: {url}\n")
    
    html = fetcher.fetch_html(url, wait_time=5, min_html_length=2000)
    
    if html:
        print(f"HTML получен: {len(html)} символов")
        
        # Проверяем title
        html_lower = html.lower()
        if "<title>" in html_lower:
            title_start = html_lower.find("<title>") + 7
            title_end = html_lower.find("</title>", title_start)
            if title_end > title_start:
                title = html[title_start:title_end]
                print(f"\nTitle: {title[:150]}\n")
        
        # Проверки детекта
        if "access denied" in html_lower or "доступ запрещен" in html_lower:
            print("ДЕТЕКТ: Access Denied")
        elif "just a moment" in html_lower:
            print("ДЕТЕКТ: Cloudflare")
        elif "captcha" in html_lower[:5000]:  # Проверяем только начало
            print("ДЕТЕКТ: CAPTCHA")
        elif "гидравлическ" in html_lower or "telezhki" in html_lower:
            print("УСПЕХ: НЕТ ДЕТЕКТА - контент есть!")
        else:
            print("ВНИМАНИЕ: Неизвестный контент")
    else:
        print("ОШИБКА: Не получен")
    
    input("\nEnter...")
    fetcher.close()
