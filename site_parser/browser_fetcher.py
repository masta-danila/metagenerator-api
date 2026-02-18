"""
Модуль для получения HTML кода страниц через браузер

Упрощенная версия из yamparser, адаптированная для получения HTML
"""

import os
import sys
import time
import warnings
import logging
import subprocess
from typing import Optional
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настраиваем логирование
try:
    from logger_config import get_browser_fetcher_logger
    logger = get_browser_fetcher_logger()
except ImportError:
    logger = logging.getLogger(__name__)

# Подавляем предупреждения
warnings.filterwarnings('ignore', message='pkg_resources is deprecated')
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Подавляем логи selenium-wire, urllib3, webdriver-manager
logging.getLogger('seleniumwire').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('hpack').setLevel(logging.ERROR)
logging.getLogger('WDM').setLevel(logging.ERROR)

# Пробуем импортировать seleniumwire для прокси
try:
    from seleniumwire import webdriver as wiredriver
    SELENIUMWIRE_AVAILABLE = True
except ImportError:
    SELENIUMWIRE_AVAILABLE = False
    wiredriver = None

# Импортируем proxy manager
try:
    from .proxy_manager import ProxyManager
    PROXY_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from proxy_manager import ProxyManager
        PROXY_MANAGER_AVAILABLE = True
    except ImportError:
        PROXY_MANAGER_AVAILABLE = False
        ProxyManager = None


class BrowserFetcher:
    """
    Класс для получения HTML кода страниц через браузер Chrome
    """
    
    def __init__(
        self,
        device_type: str = "desktop",
        visible: bool = False,
        use_proxy: bool = False,
        proxy_manager: Optional['ProxyManager'] = None
    ):
        """
        Инициализация браузера
        
        Args:
            device_type: "mobile" или "desktop"
            visible: показывать окно браузера (True) или запускать скрыто (False).
                    Если True - браузер не закрывается автоматически, ждет ручного закрытия.
            use_proxy: использовать ли прокси
            proxy_manager: экземпляр ProxyManager (опционально)
        """
        self.device_type = device_type
        self.visible = visible
        self.use_proxy = use_proxy
        self.proxy_manager = proxy_manager
        self.driver = None
        self.current_proxy = None
        
    def _create_options(self) -> Options:
        """Создание опций для Chrome"""
        options = Options()
        
        # Стратегия загрузки страницы: eager - ждем только DOM, не ждем все ресурсы
        options.page_load_strategy = 'eager'
        
        # Базовые настройки
        if not self.visible:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        
        # Подавляем логи и предупреждения Chrome
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-logging")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Отключаем WebRTC для предотвращения утечки IP
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-webrtc-hw-encoding")
        options.add_argument("--disable-webrtc-hw-decoding")
        
        # Отключаем предупреждения SSL
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--allow-running-insecure-content")
        
        # Настройка мобильной эмуляции
        if self.device_type == "mobile":
            device_width, device_height = 390, 844  # iPhone 13
            mobile_emulation = {
                "deviceMetrics": {
                    "width": device_width,
                    "height": device_height,
                    "pixelRatio": 3.0
                },
                "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
            }
            options.add_experimental_option("mobileEmulation", mobile_emulation)
            options.add_argument(f"--window-size=500,994")
        else:
            # Desktop user agent
            options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        return options
    
    def start(self) -> bool:
        """
        Запуск браузера
        
        Returns:
            True если браузер успешно запущен
        """
        try:
            logger.info(f"Запуск браузера ({self.device_type}, {'visible' if self.visible else 'headless'})...")
            
            # Если нужен прокси
            if self.use_proxy and self.proxy_manager and PROXY_MANAGER_AVAILABLE:
                if not SELENIUMWIRE_AVAILABLE:
                    logger.error("selenium-wire не установлен. Установите: pip install selenium-wire")
                    return False
                
                # Получаем прокси
                self.current_proxy = self.proxy_manager.get_random_proxy()
                if not self.current_proxy:
                    logger.error("Нет доступных прокси")
                    return False
                
                # Настраиваем прокси
                chrome_options, proxy_options = self.proxy_manager.configure_seleniumwire_proxy(self.current_proxy)
                
                # Добавляем наши настройки
                options = self._create_options()
                for arg in options.arguments:
                    if not any(arg.startswith(existing_arg.split('=')[0]) for existing_arg in chrome_options.arguments):
                        chrome_options.add_argument(arg)
                
                for option_name, option_value in options.experimental_options.items():
                    chrome_options.add_experimental_option(option_name, option_value)
                
                # Создаем драйвер с прокси (подавляем логи chromedriver)
                service = Service(
                    ChromeDriverManager(cache_valid_range=7).install(),  # Обновляет раз в неделю
                    log_output=os.devnull
                )
                self.driver = wiredriver.Chrome(
                    service=service,
                    options=chrome_options,
                    seleniumwire_options=proxy_options
                )
                
            else:
                # Создаем драйвер без прокси (подавляем логи chromedriver)
                options = self._create_options()
                service = Service(
                    ChromeDriverManager(cache_valid_range=7).install(),  # Обновляет раз в неделю
                    log_output=os.devnull
                )
                self.driver = webdriver.Chrome(
                    service=service,
                    options=options
                )
            
            # Убираем признаки автоматизации
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            # Устанавливаем таймауты (увеличены для работы с прокси)
            self.driver.set_page_load_timeout(60)  # 60 секунд для полной загрузки
            self.driver.implicitly_wait(15)  # 15 секунд для поиска элементов
            
            logger.info("Браузер успешно запущен")
            return True
            
        except Exception as e:
            # Выводим только краткое описание ошибки (без stacktrace)
            error_msg = str(e).split('\n')[0]
            logger.error(f"Ошибка запуска браузера: {type(e).__name__}: {error_msg}")
            return False
    
    def fetch_html(self, url: str, wait_time: int = 2, clean_html: bool = False, min_html_length: int = 100) -> Optional[str]:
        """
        Получить HTML код страницы
        
        Args:
            url: URL страницы
            wait_time: время ожидания после загрузки (секунды)
            clean_html: применить ли очистку HTML (удалить классы, id, стили и т.д.)
            min_html_length: минимальная длина HTML (символов) для валидного результата
        
        Returns:
            HTML код страницы или None при ошибке
        """
        if not self.driver:
            logger.error("Браузер не запущен. Вызовите start() сначала.")
            return None
        
        html = None
        try:
            logger.info(f"Загружаем: {url}")
            self.driver.get(url)
            
        except Exception as e:
            # Если таймаут - это нормально, страница может быть загружена частично
            error_type = type(e).__name__
            if 'Timeout' in error_type:
                logger.warning(f"Таймаут загрузки страницы, но попробуем получить HTML")
            else:
                error_msg = str(e).split('\n')[0]
                logger.error(f"Ошибка загрузки: {error_type}: {error_msg}")
                return None
        
        # Пытаемся получить HTML несколько раз (Chrome может крашнуться с прокси)
        for attempt in range(3):
            try:
                # Ждем загрузки JavaScript (только на первой попытке)
                if attempt == 0:
                    time.sleep(wait_time)
                else:
                    time.sleep(0.5)
                
                # Получаем HTML
                html = self.driver.page_source
                
                # Если получили - выходим из цикла
                if html:
                    break
                    
            except Exception as e:
                error_type = type(e).__name__
                # Если окно закрылось - прерываем попытки
                if 'NoSuchWindow' in error_type or 'window already closed' in str(e):
                    logger.error(f"Окно браузера закрылось (попытка {attempt + 1}/3)")
                    if attempt < 2:
                        logger.info("Пробуем еще раз...")
                        continue
                    return None
                else:
                    error_msg = str(e).split('\n')[0]
                    logger.error(f"Ошибка получения HTML: {error_type}: {error_msg}")
                    if attempt < 2:
                        continue
                    return None
        
        if not html:
            logger.error("Не удалось получить HTML после 3 попыток")
            return None
        
        try:
            # Применяем очистку если требуется
            if clean_html:
                try:
                    from .html_cleaner import compress_html_for_classification
                except ImportError:
                    from html_cleaner import compress_html_for_classification
                html = compress_html_for_classification(html)
            
            # Проверяем минимальную длину HTML
            if len(html) < min_html_length:
                logger.error(f"HTML слишком короткий: {len(html)} < {min_html_length} символов")
                return None
            
            logger.info(f"HTML получен ({len(html)} символов)")
            return html
            
        except Exception as e:
            error_msg = str(e).split('\n')[0]
            logger.error(f"Ошибка обработки HTML: {type(e).__name__}: {error_msg}")
            return None
    
    def wait_for_manual_close(self):
        """
        Ожидание ручного закрытия браузера
        Используется когда браузер виден (visible=True)
        """
        if not self.driver:
            return
        
        logger.info("Браузер останется открытым")
        logger.info("Закройте окно браузера вручную для завершения")
        
        try:
            # Проверяем каждую секунду, закрыт ли браузер
            while True:
                try:
                    # Попытка получить текущий URL - если браузер закрыт, будет исключение
                    _ = self.driver.current_url
                    time.sleep(1)
                except Exception:
                    # Браузер был закрыт пользователем
                    logger.info("Браузер закрыт пользователем")
                    break
        except KeyboardInterrupt:
            logger.info("Прервано пользователем (Ctrl+C)")
        finally:
            self.driver = None
    
    def close(self):
        """Закрыть браузер"""
        if self.driver:
            # Если браузер виден - ждем закрытия браузера пользователем
            if self.visible:
                self.wait_for_manual_close()
            else:
                # Скрытый браузер - закрываем автоматически
                try:
                    self.driver.quit()
                    logger.info("Браузер закрыт")
                except Exception as e:
                    logger.error(f"Ошибка закрытия браузера: {e}")
                finally:
                    self.driver = None
                    
                    # Принудительно прибиваем все оставшиеся процессы
                    try:
                        # Для macOS
                        subprocess.run(['killall', '-9', 'chromedriver'], 
                                     stderr=subprocess.DEVNULL, 
                                     stdout=subprocess.DEVNULL)
                        subprocess.run(['killall', '-9', 'Google Chrome'], 
                                     stderr=subprocess.DEVNULL, 
                                     stdout=subprocess.DEVNULL)
                        
                        # Для Linux
                        subprocess.run(['killall', '-9', 'chromium'], 
                                     stderr=subprocess.DEVNULL, 
                                     stdout=subprocess.DEVNULL)
                        subprocess.run(['killall', '-9', 'chrome'], 
                                     stderr=subprocess.DEVNULL, 
                                     stdout=subprocess.DEVNULL)
                        
                        logger.debug("Принудительная очистка браузерных процессов завершена")
                    except Exception as e:
                        logger.debug(f"Не удалось выполнить killall: {e}")
    
    def __enter__(self):
        """Поддержка контекстного менеджера"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие при выходе из контекста"""
        self.close()


def fetch_html_simple(
    url: str,
    device_type: str = "desktop",
    visible: bool = False,
    wait_time: int = 2,
    use_proxy: bool = False,
    proxy_manager: Optional['ProxyManager'] = None,
    clean_html: bool = False,
    min_html_length: int = 100
) -> Optional[str]:
    """
    Упрощенная функция для получения HTML одной страницы
    
    Args:
        url: URL страницы
        device_type: "mobile" или "desktop"
        visible: показывать окно браузера (True) или запускать скрыто (False).
                Если True - браузер не закрывается автоматически.
        wait_time: время ожидания после загрузки (секунды)
        use_proxy: использовать ли прокси
        proxy_manager: экземпляр ProxyManager (опционально)
        clean_html: применить ли очистку HTML (удалить классы, id, стили и т.д.)
        min_html_length: минимальная длина HTML (символов) для валидного результата
    
    Returns:
        HTML код страницы или None при ошибке
    
    Example:
        html = fetch_html_simple("https://example.com")
        if html:
            logger.info(f"Получено {len(html)} символов")
    """
    with BrowserFetcher(
        device_type=device_type, 
        visible=visible, 
        use_proxy=use_proxy, 
        proxy_manager=proxy_manager
    ) as fetcher:
        return fetcher.fetch_html(url, wait_time=wait_time, clean_html=clean_html, min_html_length=min_html_length)


if __name__ == "__main__":
    """
    Пример использования с сохранением в JSON
    
    Использование:
        python browser_fetcher.py                   # скрытый режим
        python browser_fetcher.py https://site.com  # указать URL
    """
    import json
    from datetime import datetime
    
    # Получаем URL из аргументов или используем тестовый
    url = sys.argv[1] if len(sys.argv) > 1 else "https://sn22.ru/catalog/payanye-teploobmenniki/_ridan/"
    
    logger.info(f"Получение HTML со страницы: {url}")
    
    # Настройка прокси
    use_proxy = False
    proxy_manager = None
    proxy_file = Path(__file__).parent / "proxy.txt"
    
    if proxy_file.exists() and PROXY_MANAGER_AVAILABLE:
        logger.info("Найден файл proxy.txt - используем прокси")
        use_proxy = True
        proxy_manager = ProxyManager()
    elif proxy_file.exists():
        logger.warning("ProxyManager недоступен - работаем без прокси")
    else:
        logger.info("Файл proxy.txt не найден - работаем без прокси")
    
    # Получаем HTML
    html = fetch_html_simple(
        url,
        visible=False,  # False = headless режим (без окна)
        use_proxy=use_proxy,
        proxy_manager=proxy_manager,
        clean_html=True,
        min_html_length=100
    )
    
    # Подготовка результата
    if html:
        logger.info(f"Успешно! Получено {len(html)} символов (очищенный HTML)")
        logger.debug(f"Начало HTML:\n{html[:300]}...")
        result = {
            "url": url,
            "html": html,
            "html_length": len(html),
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
    else:
        logger.error("Ошибка получения HTML")
        result = {
            "url": url,
            "html": None,
            "html_length": 0,
            "timestamp": datetime.now().isoformat(),
            "status": "error"
        }
    
    # Сохранение в JSON
    output_dir = Path(__file__).parent.parent / "jsontests"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "browser_fetch_result.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результат сохранен: {output_file}")
