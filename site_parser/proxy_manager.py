"""
Менеджер прокси для работы с selenium-wire
Адаптировано из yamparser
"""

import random
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple
from selenium.webdriver.chrome.options import Options


class ProxyManager:
    """Менеджер прокси серверов с поддержкой seleniumwire"""
    
    def __init__(self, proxy_file: str = None):
        """
        Инициализация менеджера прокси
        
        Args:
            proxy_file: путь к файлу с прокси
                       По умолчанию ищет proxy.txt в папке site_parser/
                       Формат: IP:PORT или IP:PORT:USERNAME:PASSWORD (одна строка - один прокси)
        """
        # Если путь не указан, используем proxy.txt из папки browser
        if proxy_file is None:
            proxy_file = Path(__file__).parent / "proxy.txt"
        
        self.proxy_file = str(proxy_file)
        self.proxies = []
        self.current_index = 0
        self.lock = threading.Lock()
        
        # Загружаем прокси при инициализации
        self.load_proxies()
    
    def load_proxies(self) -> None:
        """Загрузить прокси из файла"""
        try:
            with open(self.proxy_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            self.proxies = []
            skipped_lines = 0
            
            for line_num, line in enumerate(lines, 1):
                original_line = line
                line = line.strip()
                
                if not line or line.startswith('#'):  # Игнорируем комментарии
                    continue
                
                proxy = self.parse_proxy_line(line)
                if proxy:
                    self.proxies.append(proxy)
                else:
                    skipped_lines += 1
                    print(f"Строка {line_num} пропущена (неверный формат): {original_line.strip()}")
            
            print(f"Загружено {len(self.proxies)} прокси из {self.proxy_file}")
            if skipped_lines > 0:
                print(f"Пропущено {skipped_lines} строк с неверным форматом")
            
            if not self.proxies:
                print("Прокси не найдены")
        
        except FileNotFoundError:
            print(f"Файл {self.proxy_file} не найден")
            print("Создайте файл proxy.txt с прокси в формате:")
            print("   IP:PORT (без авторизации)")
            print("   IP:PORT:USERNAME:PASSWORD (с авторизацией)")
            print("   Пример: 192.168.1.1:8080")
            print("   Пример: 192.168.1.1:8080:user:pass")
            self.proxies = []
        
        except Exception as e:
            print(f"Ошибка загрузки прокси: {e}")
            self.proxies = []
    
    def parse_proxy_line(self, line: str) -> Optional[Dict]:
        """
        Парсинг строки прокси в формате: 
        - IP:PORT (без авторизации)
        - IP:PORT:USERNAME:PASSWORD (с авторизацией)
        """
        try:
            line = line.strip()
            parts = line.split(':')
            
            if len(parts) == 2:
                # ip:port (без авторизации)
                return {
                    'ip': parts[0],
                    'port': parts[1],
                    'username': None,
                    'password': None
                }
            elif len(parts) == 4:
                # ip:port:username:password (с авторизацией)
                return {
                    'ip': parts[0],
                    'port': int(parts[1]),
                    'username': parts[2],
                    'password': parts[3],
                    'protocol': 'http'
                }
            else:
                print(f"Неверный формат прокси '{line}' (ожидается IP:PORT или IP:PORT:USERNAME:PASSWORD)")
                return None
        
        except Exception as e:
            print(f"Ошибка парсинга прокси '{line}': {e}")
            return None
    
    def get_next_proxy(self) -> Optional[Dict]:
        """
        Получить следующий прокси из списка (ротация)
        
        Returns:
            Словарь с данными прокси или None если нет прокси
        """
        with self.lock:
            if not self.proxies:
                return None
            
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
    
    def get_random_proxy(self) -> Optional[Dict]:
        """
        Получить случайный прокси из списка
        
        Returns:
            Словарь с данными прокси или None если нет прокси
        """
        if not self.proxies:
            return None
        
        return random.choice(self.proxies)
    
    def get_httpx_proxy_url(self, proxy: Dict) -> str:
        """
        Формирует proxy URL для httpx
        
        Args:
            proxy: Словарь с данными прокси (ip, port, username, password, protocol)
        
        Returns:
            str: Proxy URL в формате protocol://username:password@ip:port
        """
        protocol = proxy.get('protocol', 'http')
        username = proxy['username']
        password = proxy['password']
        ip = proxy['ip']
        port = proxy['port']
        
        return f"{protocol}://{username}:{password}@{ip}:{port}"
    
    def configure_seleniumwire_proxy(self, proxy: Dict) -> Tuple[Options, Optional[Dict]]:
        """
        Настройка прокси для seleniumwire
        
        Args:
            proxy: словарь с данными прокси
            
        Returns:
            Кортеж (chrome_options, seleniumwire_options)
        """
        # Настройки Chrome
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Отключаем WebRTC для предотвращения утечки IP
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-webrtc-hw-encoding")
        options.add_argument("--disable-webrtc-hw-decoding")
        
        # Отключаем предупреждения SSL
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--allow-running-insecure-content")
        
        if not proxy:
            print("Прокси не используется")
            return options, None
        
        # Настройки прокси для seleniumwire
        proxy_options = {
            'proxy': {
                'http': f"http://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}",
                'https': f"http://{proxy['username']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}",
                'no_proxy': 'localhost,127.0.0.1'
            },
            'suppress_connection_errors': False,
            'verify_ssl': False
        }
        
        print(f"Настроен прокси: {proxy['ip']}:{proxy['port']}")
        return options, proxy_options
    
    def get_stats(self) -> Dict:
        """
        Получить статистику по прокси
        
        Returns:
            Словарь со статистикой
        """
        return {
            'total_proxies': len(self.proxies),
            'current_index': self.current_index
        }
