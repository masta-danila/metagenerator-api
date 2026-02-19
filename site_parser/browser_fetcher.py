"""
Модуль для получения HTML через браузер - на основе debug_vseinstrumenti.py + прокси
"""
import time
import ssl
import sys
import logging
from typing import Optional
from pathlib import Path

import undetected_chromedriver as uc

# Импортируем решатель антибот защит и клинер HTML
try:
    from .antibot_solver import AntibotSolver
    from .html_cleaner import compress_html_for_classification
except ImportError:
    from antibot_solver import AntibotSolver
    from html_cleaner import compress_html_for_classification

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
            use_proxy: использовать прокси (через --proxy-server)
            proxy_manager: менеджер прокси (должен иметь метод get_random_proxy())
        """
        self.device_type = device_type
        self.visible = visible
        self.use_proxy = use_proxy
        self.proxy_manager = proxy_manager
        self.driver = None
        self.current_proxy = None
    
    def start(self) -> bool:
        """Запуск браузера с опциональным прокси через Chrome расширение"""
        try:
            logger.info(f"Запуск браузера ({self.device_type}, {'visible' if self.visible else 'headless'})...")
            
            # Базовые опции - как в debug
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
            # Добавляем прокси если нужно
            if self.use_proxy and self.proxy_manager:
                self.current_proxy = self.proxy_manager.get_random_proxy()
                if not self.current_proxy:
                    logger.error("Не удалось получить прокси из proxy_manager")
                    return False
                
                proxy_host = self.current_proxy['ip']
                proxy_port = self.current_proxy['port']
                proxy_str = f"{proxy_host}:{proxy_port}"
                
                # ВАЖНО: Chrome расширения НЕ работают с прокси авторизацией в undetected-chromedriver
                # Поэтому используем простой --proxy-server БЕЗ авторизации
                
                if self.current_proxy.get('username') and self.current_proxy.get('password'):
                    logger.warning(f"ВНИМАНИЕ: Прокси {proxy_str} требует авторизацию, но undetected-chromedriver её НЕ поддерживает!")
                    logger.warning("Работаем БЕЗ прокси. Используйте прокси без авторизации (формат IP:PORT)")
                    # НЕ используем прокси с авторизацией
                    self.driver = uc.Chrome(
                        options=options,
                        version_main=None,
                        headless=not self.visible
                    )
                else:
                    # Прокси БЕЗ авторизации - простой --proxy-server
                    options.add_argument(f"--proxy-server={proxy_str}")
                    logger.info(f"Используем прокси: {proxy_str}")
                    
                    # Используем undetected-chromedriver
                    self.driver = uc.Chrome(
                        options=options,
                        version_main=None,
                        headless=not self.visible
                    )
            else:
                # БЕЗ прокси - чистый undetected-chromedriver
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
        """Получить HTML с ожиданием антибот проверок (Antibot Cloud, Cloudflare и др.)"""
        if not self.driver:
            logger.error("Браузер не запущен. Вызовите start() сначала.")
            return None
        
        try:
            logger.info(f"Загружаем: {url}")
            
            # Загружаем страницу
            self.driver.get(url)
            
            # Для антибот защиты нужно больше времени
            initial_wait = max(wait_time, 8)  # минимум 8 секунд
            time.sleep(initial_wait)
            
            # Проверяем и обходим антибот защиты через AntibotSolver
            html = self.driver.page_source
            
            if html:
                # Используем AntibotSolver - он автоматически определит и обойдет защиту
                solver = AntibotSolver(self.driver)
                solver.solve(html, max_wait=15)
                
                # Получаем финальный HTML после обхода защит
                html = self.driver.page_source
            
            if not html:
                logger.error("HTML не получен (None)")
                return None
            
            # Проверка длины
            if len(html) < min_html_length:
                logger.error(f"HTML слишком короткий: {len(html)} < {min_html_length} символов")
                return None
            
            # Очистка HTML если требуется
            if clean_html:
                logger.info(f"Очистка HTML ({len(html)} символов)...")
                html = compress_html_for_classification(html)
                logger.info(f"HTML очищен ({len(html)} символов)")
            
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
    """Тест с прокси"""
    print("Тест BrowserFetcher С ПРОКСИ\n")
    
    # Загружаем прокси
    proxy_file = Path(__file__).parent / "proxy.txt"
    use_proxy = False
    proxy_manager = None
    
    if proxy_file.exists():
        try:
            # Импортируем ProxyManager
            try:
                from proxy_manager import ProxyManager
            except ImportError:
                sys.path.insert(0, str(Path(__file__).parent))
                from proxy_manager import ProxyManager
            
            proxy_manager = ProxyManager()
            if proxy_manager.proxies:
                use_proxy = True
                print(f"Загружено {len(proxy_manager.proxies)} прокси из {proxy_file}\n")
            else:
                print("proxy.txt пустой - работаем БЕЗ прокси\n")
        except Exception as e:
            print(f"Ошибка загрузки прокси: {e}")
            print("Работаем БЕЗ прокси\n")
    else:
        print("proxy.txt не найден - работаем БЕЗ прокси\n")
    
    # Создаем fetcher С ПРОКСИ
    fetcher = BrowserFetcher(
        device_type="desktop", 
        visible=True,
        use_proxy=use_proxy,
        proxy_manager=proxy_manager
    )
    
    if not fetcher.start():
        print("ОШИБКА: Не запустился")
        exit(1)
    
    print("Браузер запущен\n")
    
    # Показываем какой прокси используется
    if fetcher.current_proxy:
        print(f"Используется прокси: {fetcher.current_proxy['ip']}:{fetcher.current_proxy['port']}\n")
    else:
        print("Работаем БЕЗ прокси (direct connection)\n")
    
    url = "https://ekb.deltainzhiniring.ru/avtoservis/domkratyi/transmissionnyie/"
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
        elif "captcha" in html_lower[:5000]:
            print("ДЕТЕКТ: CAPTCHA")
        elif "гидравлическ" in html_lower or "telezhki" in html_lower:
            print("УСПЕХ: НЕТ ДЕТЕКТА - контент есть!")
        else:
            print("ВНИМАНИЕ: Неизвестный контент")
    else:
        print("ОШИБКА: Не получен")
    
    input("\nНажмите Enter для закрытия...")
    fetcher.close()
    print("Готово!")
