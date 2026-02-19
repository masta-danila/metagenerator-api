"""
Модуль для автоматического обхода антибот защит и капч

Поддерживаемые защиты:
- Antibot Cloud (кнопка "I'm not a robot")
- Cloudflare Challenge (в будущем)
- reCAPTCHA (в будущем)
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AntibotSolver:
    """Решатель антибот защит для Selenium WebDriver"""
    
    def __init__(self, driver):
        """
        Args:
            driver: экземпляр Selenium WebDriver
        """
        self.driver = driver
    
    def detect_protection(self, html: str) -> Optional[str]:
        """
        Определяет тип защиты на странице
        
        Args:
            html: HTML код страницы
            
        Returns:
            Тип защиты ('antibot_cloud', 'cloudflare', None)
        """
        html_lower = html.lower()
        
        # Antibot Cloud (ПРИОРИТЕТ - проверяем первым)
        if 'antiprotectbot' in html_lower or "i'm not a robot" in html_lower:
            return 'antibot_cloud'
        
        # Cloudflare Challenge (ТОЛЬКО специфичные маркеры)
        if '<title>just a moment' in html_lower or 'checking your browser' in html_lower:
            return 'cloudflare'
        
        return None
    
    def solve_antibot_cloud(self, max_wait: int = 15) -> bool:
        """
        Обход Antibot Cloud защиты
        
        Antibot Cloud показывает несколько кнопок "I'm not a robot" с одинаковым текстом,
        но разными случайными классами. Видимая кнопка определяется через CSS (display:none).
        
        Args:
            max_wait: максимальное время ожидания прохождения (секунд)
            
        Returns:
            True если защита пройдена, False если нет
        """
        try:
            logger.info("Обход Antibot Cloud защиты...")
            
            # Ждем 5 секунд чтобы JS отрендерил кнопки
            time.sleep(5)
            
            # Находим кнопку по тексту и кликаем на видимую (без display:none)
            js_click = """
            // Находим все div с текстом "I'm not a robot" или "Я не робот"
            var allDivs = document.querySelectorAll('div');
            var buttons = [];
            
            for(var i=0; i<allDivs.length; i++) {
                var text = allDivs[i].textContent.trim();
                if (text === "I'm not a robot" || text === "Я не робот") {
                    buttons.push(allDivs[i]);
                }
            }
            
            if (buttons.length === 0) return 0;
            
            // Выбираем видимую кнопку (без display:none)
            for(var i=0; i<buttons.length; i++) {
                var style = window.getComputedStyle(buttons[i]);
                if (style.display !== 'none' && buttons[i].offsetParent !== null) {
                    buttons[i].click();
                    return 1;
                }
            }
            
            // Если не нашли видимую - кликаем первую
            if (buttons.length > 0) {
                buttons[0].click();
                return 1;
            }
            
            return 0;
            """
            
            result = self.driver.execute_script(js_click)
            
            if not result or result == 0:
                logger.warning("Не удалось найти кнопку Antibot Cloud")
                return False
            
            logger.info(f"Кликнули на кнопку Antibot Cloud")
            
            # Ждем прохождения защиты (обычно 3 секунды)
            time.sleep(3)
            
            # Проверяем что защита прошла
            html = self.driver.page_source
            if self.detect_protection(html) == 'antibot_cloud':
                logger.warning("Antibot Cloud не прошла с первого раза, ждем еще...")
                # Ждем еще немного
                for i in range(5):
                    time.sleep(1)
                    html = self.driver.page_source
                    if self.detect_protection(html) != 'antibot_cloud':
                        logger.info(f"Antibot Cloud пройдена через {i + 1} дополнительных секунд")
                        return True
                
                logger.error(f"Antibot Cloud НЕ пройдена за {max_wait} секунд")
                return False
            
            logger.info("Antibot Cloud успешно пройдена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обходе Antibot Cloud: {e}")
            return False
    
    def solve_cloudflare(self, max_wait: int = 30) -> bool:
        """
        Обход Cloudflare Challenge
        
        Cloudflare обычно проходится автоматически через undetected-chromedriver,
        просто нужно подождать.
        
        Args:
            max_wait: максимальное время ожидания (секунд)
            
        Returns:
            True если защита пройдена, False если нет
        """
        try:
            logger.info("Обнаружена Cloudflare, ожидаем автоматического прохождения...")
            
            for i in range(max_wait):
                time.sleep(1)
                html = self.driver.page_source
                
                if self.detect_protection(html) != 'cloudflare':
                    logger.info(f"Cloudflare пройдена за {i + 1} секунд")
                    return True
            
            logger.error(f"Cloudflare НЕ пройдена за {max_wait} секунд")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при обходе Cloudflare: {e}")
            return False
    
    def solve(self, html: str, max_wait: int = 15) -> bool:
        """
        Автоматически определяет и обходит защиту
        
        Args:
            html: HTML код страницы
            max_wait: максимальное время ожидания (секунд)
            
        Returns:
            True если защита пройдена или не обнаружена, False если не удалось пройти
        """
        protection_type = self.detect_protection(html)
        
        if not protection_type:
            # Нет защиты
            return True
        
        logger.info(f"Обнаружена защита: {protection_type}")
        
        if protection_type == 'antibot_cloud':
            return self.solve_antibot_cloud(max_wait)
        elif protection_type == 'cloudflare':
            return self.solve_cloudflare(max_wait)
        else:
            logger.warning(f"Неизвестный тип защиты: {protection_type}")
            return False
