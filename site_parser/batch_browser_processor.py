"""
Батчевый процессор для повторного парсинга URL с ошибками через браузер (Selenium)

Используется как второй проход после batch_html_processor.py:
1. Извлекает URL с ошибками парсинга из результатов первого прохода
2. Повторно парсит их через browser_fetcher (Selenium + JavaScript)
3. Обновляет данные, заменяя ошибки на успешные результаты
"""
import json
import sys
import copy
import time
import threading
from typing import Dict, List, Set, Optional
from pathlib import Path
from collections import defaultdict

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import get_html_parser_logger
from site_parser.browser_fetcher import BrowserFetcher

logger = get_html_parser_logger()


def extract_failed_urls(data: Dict) -> Dict:
    """
    Извлекает все URL с ошибками парсинга из результатов первого прохода
    
    Args:
        data: Словарь структуры {spreadsheet_id: {urls: {url: {...}}}}
    
    Returns:
        Словарь с URL, которые не удалось спарсить:
        {
            'main_urls': {url: [locations]},
            'filtered_urls': {url: [locations]}
        }
    """
    failed_urls = {
        'main_urls': defaultdict(list),
        'filtered_urls': defaultdict(list)
    }
    
    for spreadsheet_id, sheet_info in data.items():
        urls_dict = sheet_info.get('urls', {})
        
        for main_url, url_data in urls_dict.items():
            # Проверяем основной URL на наличие ошибки
            if 'parsing_error' in url_data:
                failed_urls['main_urls'][main_url].append({
                    'spreadsheet_id': spreadsheet_id,
                    'main_url': main_url,
                    'error': url_data['parsing_error']
                })
                logger.debug(f"Found failed main_url: {main_url}")
            
            # Проверяем filtered_urls в каждом query
            for query_idx, query in enumerate(url_data.get('queries', [])):
                if not isinstance(query, dict):
                    continue
                    
                for filtered_item in query.get('filtered_urls', []):
                    if isinstance(filtered_item, dict) and 'error' in filtered_item:
                        url = filtered_item.get('url', '')
                        if url:
                            failed_urls['filtered_urls'][url].append({
                                'spreadsheet_id': spreadsheet_id,
                                'main_url': main_url,
                                'query_idx': query_idx,
                                'error': filtered_item['error']
                            })
                            logger.debug(f"Found failed filtered_url: {url}")
    
    return failed_urls


# Домены с очень сильной защитой - можно пропускать или требуют residential прокси
# ВНИМАНИЕ: vseinstrumenti.ru работает если НЕ использовать эмуляцию!
PROBLEMATIC_DOMAINS = [
    # 'vseinstrumenti.ru',  # Отключено - работает в простом режиме
    # Добавьте другие проблемные домены сюда
]

def parse_url_with_browser(
    url: str,
    use_proxy: bool = False,
    proxy_manager = None,
    max_retries: int = 2,
    wait_time: int = 3,
    min_html_length: int = 100,
    device_type: str = "desktop",
    visible: bool = False,
    skip_problematic: bool = False
) -> Dict:
    """
    Синхронная функция для парсинга URL через браузер с повторными попытками
    
    Args:
        url: URL для парсинга
        use_proxy: использовать ли прокси
        proxy_manager: экземпляр ProxyManager
        max_retries: Максимальное количество попыток
        wait_time: Время ожидания загрузки JavaScript
        min_html_length: Минимальная длина HTML для валидного результата
        device_type: "mobile" или "desktop"
        visible: показывать ли браузер визуально (для отладки)
        skip_problematic: пропускать ли домены с сильной защитой
    
    Returns:
        Словарь с результатом парсинга
    """
    # Проверяем не находится ли домен в списке проблемных
    if skip_problematic:
        for domain in PROBLEMATIC_DOMAINS:
            if domain in url:
                logger.warning(f"[SKIP] Пропускаем URL с сильной защитой: {url}")
                return {
                    'url': url,
                    'error': f'Skipped: {domain} requires residential proxies or CAPTCHA solving'
                }
    
    for attempt in range(max_retries):
        fetcher = None
        try:
            logger.info(f"[BROWSER {attempt + 1}/{max_retries}] Парсинг: {url}")
            
            # Создаем новый браузер для каждой попытки
            fetcher = BrowserFetcher(
                device_type=device_type,
                visible=visible,
                use_proxy=use_proxy,
                proxy_manager=proxy_manager
            )
            
            if not fetcher.start():
                raise Exception("Не удалось запустить браузер")
            
            # ПРОСТАЯ загрузка - как в debug_vseinstrumenti.py (БЕЗ эмуляции!)
            html = fetcher.fetch_html(url, wait_time=wait_time, clean_html=True, min_html_length=min_html_length, emulate_user=False)
            
            # Закрываем браузер (как в debug - без лишних задержек)
            fetcher.close()
            fetcher = None
            
            if not html:
                raise Exception(f"HTML не получен (None)")
            
            if len(html) < min_html_length:
                raise Exception(f"HTML слишком короткий: {len(html)} < {min_html_length} символов")
            
            logger.info(f"[BROWSER OK] {url} ({len(html)} символов)")
            return {
                'url': url,
                'html_structure': html
            }
                
        except Exception as e:
            logger.error(f"[BROWSER ОШИБКА] Попытка {attempt + 1} для {url}: {str(e)}")
            
            # Принудительно закрываем браузер в случае ошибки
            if fetcher:
                try:
                    fetcher.close()
                except:
                    pass
            
            if attempt == max_retries - 1:
                return {
                    'url': url,
                    'error': f'Browser fetch failed: {str(e)}'
                }
            
            # Увеличиваем задержку с каждой попыткой
            time.sleep(3 * (attempt + 1))
    
    return {
        'url': url,
        'error': 'Unknown error - no result returned'
    }


def reparse_failed_urls_with_browser(
    data: Dict,
    max_concurrent: int = 3,
    max_retries: int = 2,
    wait_time: int = 3,
    use_proxy: bool = False,
    proxy_manager = None,
    min_html_length: int = 100,
    device_type: str = "desktop",
    visible: bool = False,
    skip_problematic: bool = True
) -> Dict:
    """
    Повторно парсит URL с ошибками через браузер (Selenium) используя многопоточность
    
    Args:
        data: Словарь с результатами первого прохода (из batch_html_processor)
        max_concurrent: Максимальное количество одновременных браузеров (рекомендуется 2-5)
        max_retries: Максимальное количество попыток при ошибках
        wait_time: Время ожидания загрузки JavaScript (секунды)
        use_proxy: использовать ли прокси
        proxy_manager: экземпляр ProxyManager (опционально)
        min_html_length: Минимальная длина HTML для валидного результата
        device_type: "mobile" или "desktop" - тип устройства для эмуляции
        visible: показывать ли браузер визуально (для отладки)
        skip_problematic: пропускать ли домены с очень сильной защитой (по умолчанию True)
    
    Returns:
        Обновленный словарь с исправленными данными
    """
    logger.info("ПОВТОРНЫЙ ПАРСИНГ URL С ОШИБКАМИ ЧЕРЕЗ БРАУЗЕР (SELENIUM)")
    
    # Автоматически загружаем прокси если use_proxy=True но proxy_manager=None
    if use_proxy and proxy_manager is None:
        proxy_file = Path(__file__).parent / "proxy.txt"
        if proxy_file.exists():
            try:
                from proxy_manager import ProxyManager
                proxy_manager = ProxyManager()
                if proxy_manager.proxies:
                    logger.info(f"Автоматически загружено {len(proxy_manager.proxies)} прокси из {proxy_file}")
                else:
                    logger.warning("proxy.txt пустой - работаем без прокси")
                    use_proxy = False
            except Exception as e:
                logger.warning(f"Не удалось загрузить прокси: {e}")
                logger.info("Работаем без прокси")
                use_proxy = False
        else:
            logger.info("proxy.txt не найден - работаем без прокси")
            use_proxy = False
    
    logger.info(f"- Макс. одновременных браузеров: {max_concurrent}")
    logger.info(f"- Попыток на URL: {max_retries}")
    logger.info(f"- Ожидание загрузки JS: {wait_time}s")
    logger.info(f"- Минимальная длина HTML: {min_html_length} символов")
    logger.info(f"- Тип устройства: {device_type}")
    logger.info(f"- Режим браузера: {'Видимый' if visible else 'Headless'}")
    if use_proxy and proxy_manager:
        logger.info(f"- Используются прокси: {len(proxy_manager.proxies)} доступно")
    else:
        logger.info(f"- Прокси: НЕ используются")
    
    # Шаг 1: Извлекаем URL с ошибками
    logger.info("[ШАГ 1] Поиск URL с ошибками парсинга...")
    failed_urls = extract_failed_urls(data)
    
    main_failed_count = len(failed_urls['main_urls'])
    filtered_failed_count = len(failed_urls['filtered_urls'])
    total_failed = main_failed_count + filtered_failed_count
    
    logger.info(f"Найдено URL с ошибками:")
    logger.info(f"  - Основных URL (main_url): {main_failed_count}")
    logger.info(f"  - Filtered URLs: {filtered_failed_count}")
    logger.info(f"  - ВСЕГО уникальных: {total_failed}")
    
    if total_failed == 0:
        logger.info("Нет URL для повторного парсинга! Все URL успешно спарсены.")
        return data
    
    # Шаг 2: Собираем все уникальные URL
    all_failed_urls = list(set(failed_urls['main_urls'].keys()) | set(failed_urls['filtered_urls'].keys()))
    logger.info(f"[ШАГ 2] Подготовка к повторному парсингу {len(all_failed_urls)} уникальных URL...")
    
    # Показываем примеры URL с ошибками
    logger.info("Примеры URL с ошибками:")
    for i, url in enumerate(all_failed_urls[:5], 1):
        error = None
        if url in failed_urls['main_urls']:
            error = failed_urls['main_urls'][url][0].get('error', 'Unknown error')
        elif url in failed_urls['filtered_urls']:
            error = failed_urls['filtered_urls'][url][0].get('error', 'Unknown error')
        
        logger.info(f"  {i}. {url[:80]}...")
        logger.info(f"     Ошибка: {error[:100]}")
    
    if len(all_failed_urls) > 5:
        logger.info(f"  ... и еще {len(all_failed_urls) - 5} URL")
    
    # Шаг 3: Создаем батчи для параллельной обработки
    def chunks(lst, n):
        """Разделить список на батчи по n элементов"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    
    url_batches = list(chunks(all_failed_urls, max(1, len(all_failed_urls) // max_concurrent)))
    
    # Шаг 4: Запускаем повторный парсинг через браузер с многопоточностью
    logger.info(f"[ШАГ 3] Запуск повторного парсинга через Selenium (потоков: {len(url_batches)})...")
    logger.info(f"ВНИМАНИЕ: Браузер медленнее httpx в ~3-5 раз, наберитесь терпения...")
    
    results = []
    results_lock = threading.Lock()
    
    def process_batch(batch, worker_id):
        """Обработка батча URL в отдельном потоке"""
        logger.info(f"Поток {worker_id}: Начало обработки {len(batch)} URL")
        
        for url in batch:
            result = parse_url_with_browser(
                url=url,
                use_proxy=use_proxy,
                proxy_manager=proxy_manager,
                max_retries=max_retries,
                wait_time=wait_time,
                min_html_length=min_html_length,
                device_type=device_type,
                visible=visible,
                skip_problematic=skip_problematic
            )
            
            with results_lock:
                results.append(result)
        
        logger.info(f"Поток {worker_id}: Завершено")
    
    threads = []
    delay_between_threads = 2  # Задержка между запуском потоков (секунды)
    
    for i, batch in enumerate(url_batches, 1):
        thread = threading.Thread(target=process_batch, args=(batch, i))
        threads.append(thread)
        thread.start()
        
        # Даем время на инициализацию браузера перед запуском следующего
        if i < len(url_batches):
            logger.info(f"Ждем {delay_between_threads}с перед запуском следующего потока...")
            time.sleep(delay_between_threads)
    
    # Ждем завершения всех потоков
    for thread in threads:
        thread.join()
    
    # Шаг 5: Создаем маппинг URL -> результат
    parsed_data = {result['url']: result for result in results}
    
    # Шаг 6: Подсчитываем статистику
    success_count = sum(1 for r in results if 'error' not in r)
    failed_count = sum(1 for r in results if 'error' in r)
    success_rate = (success_count / len(results) * 100) if results else 0
    
    logger.info(f"[ШАГ 4] Результаты повторного парсинга:")
    logger.info(f"  Успешно исправлено: {success_count}")
    logger.info(f"  Снова ошибка: {failed_count}")
    logger.info(f"  Успешность: {success_rate:.1f}%")
    
    # Показываем какие URL все еще с ошибками
    if failed_count > 0:
        logger.warning(f"URL, которые все еще с ошибками:")
        still_failed = [r for r in results if 'error' in r]
        for i, r in enumerate(still_failed[:5], 1):
            logger.warning(f"  {i}. {r['url'][:80]}...")
            logger.warning(f"     Ошибка: {r['error'][:100]}")
        if len(still_failed) > 5:
            logger.warning(f"  ... и еще {len(still_failed) - 5} URL")
    
    # Шаг 7: Обновляем исходные данные
    logger.info(f"[ШАГ 5] Обновление данных...")
    result_data = copy.deepcopy(data)
    
    main_urls_fixed = 0
    filtered_urls_fixed = 0
    
    # Обновляем main_urls
    for url, locations in failed_urls['main_urls'].items():
        new_data = parsed_data.get(url)
        if new_data:
            for loc in locations:
                sid = loc['spreadsheet_id']
                murl = loc['main_url']
                
                if 'error' not in new_data:
                    # Дополнительная проверка длины HTML перед записью
                    html_length = len(new_data.get('html_structure', ''))
                    if html_length < min_html_length:
                        logger.warning(f"HTML слишком короткий для записи ({html_length} < {min_html_length}): {url}")
                        result_data[sid]['urls'][murl]['parsing_error'] = f"Browser: HTML too short ({html_length} < {min_html_length})"
                    else:
                        # Успех - добавляем HTML и удаляем ошибку
                        result_data[sid]['urls'][murl]['html_structure'] = new_data['html_structure']
                        result_data[sid]['urls'][murl].pop('parsing_error', None)
                        main_urls_fixed += 1
                        logger.debug(f"Исправлен main_url: {url}")
                else:
                    # Снова ошибка - обновляем текст ошибки
                    result_data[sid]['urls'][murl]['parsing_error'] = f"Browser: {new_data['error']}"
                    logger.debug(f"Ошибка повторилась для main_url: {url}")
    
    # Обновляем filtered_urls
    for url, locations in failed_urls['filtered_urls'].items():
        new_data = parsed_data.get(url)
        if new_data:
            for loc in locations:
                sid = loc['spreadsheet_id']
                murl = loc['main_url']
                qidx = loc['query_idx']
                
                # Находим и обновляем элемент в filtered_urls
                filtered_list = result_data[sid]['urls'][murl]['queries'][qidx]['filtered_urls']
                for item in filtered_list:
                    if isinstance(item, dict) and item.get('url') == url:
                        if 'error' not in new_data:
                            # Дополнительная проверка длины HTML перед записью
                            html_length = len(new_data.get('html_structure', ''))
                            if html_length < min_html_length:
                                logger.warning(f"HTML слишком короткий для записи ({html_length} < {min_html_length}): {url}")
                                item['error'] = f"Browser: HTML too short ({html_length} < {min_html_length})"
                            else:
                                # Успех - добавляем HTML и удаляем ошибку
                                item['html_structure'] = new_data['html_structure']
                                item.pop('error', None)
                                filtered_urls_fixed += 1
                                logger.debug(f"Исправлен filtered_url: {url}")
                        else:
                            # Снова ошибка - обновляем текст ошибки
                            item['error'] = f"Browser: {new_data['error']}"
                            logger.debug(f"Ошибка повторилась для filtered_url: {url}")
                        break
    
    logger.info(f"Обновлено записей:")
    logger.info(f"  - Main URLs: {main_urls_fixed}")
    logger.info(f"  - Filtered URLs: {filtered_urls_fixed}")
    logger.info(f"  - ВСЕГО: {main_urls_fixed + filtered_urls_fixed}")
    
    logger.info(f"ПОВТОРНЫЙ ПАРСИНГ ЗАВЕРШЕН")
    
    return result_data


def save_results(
    results: Dict,
    output_path: str = "jsontests/batch_html_reparsed_results.json"
) -> None:
    """
    Сохраняет результаты повторного парсинга в JSON файл
    
    Args:
        results: Словарь с обновленными результатами
        output_path: Путь для сохранения файла
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Результаты сохранены в {output_path}")


if __name__ == "__main__":
    """
    Тестовый запуск повторного парсинга через браузер
    """
    def test():
        import subprocess
        import platform
        
        # Убиваем старые процессы Chrome и ChromeDriver
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["killall", "-9", "Google Chrome"], stderr=subprocess.DEVNULL)
                subprocess.run(["killall", "-9", "chromedriver"], stderr=subprocess.DEVNULL)
                logger.info("Убиты старые процессы Chrome и ChromeDriver")
            elif platform.system() == "Linux":
                subprocess.run(["pkill", "-9", "-f", "chrome"], stderr=subprocess.DEVNULL)
                subprocess.run(["pkill", "-9", "-f", "chromedriver"], stderr=subprocess.DEVNULL)
                logger.info("Убиты старые процессы Chrome и ChromeDriver")
        except Exception as e:
            logger.warning(f"Не удалось убить старые процессы: {e}")
        
        # Определяем пути относительно корня проекта
        project_root = Path(__file__).parent.parent
        input_file = project_root / "jsontests" / "step6_html_parsed.json"
        output_file = project_root / "jsontests" / "step7_html_reparsed.json"
        
        # Проверяем наличие входного файла
        if not input_file.exists():
            logger.error(f"Входной файл не найден: {input_file}")
            logger.error("Сначала запустите batch_html_processor.py")
            return
        
        # Загружаем данные с результатами первого прохода
        logger.info(f"Загрузка данных из {input_file}")
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Проверяем наличие proxy.txt
        proxy_file = Path(__file__).parent / "proxy.txt"
        use_proxy = False
        proxy_manager = None
        
        if proxy_file.exists():
            try:
                from proxy_manager import ProxyManager
                proxy_manager = ProxyManager()
                if proxy_manager.proxies:
                    use_proxy = True
                    logger.info(f"Используем прокси: {len(proxy_manager.proxies)} доступно")
            except Exception as e:
                logger.warning(f"Не удалось загрузить прокси: {e}")
        else:
            logger.info("Файл proxy.txt не найден - работаем без прокси")
        
        # Запускаем повторный парсинг через браузер
        results = reparse_failed_urls_with_browser(
            data=data,
            max_concurrent=10,         # 10 браузеров параллельно
            max_retries=2,             # 2 попытки на каждый URL
            wait_time=5,               # 5 сек ожидания после загрузки
            use_proxy=use_proxy,       # Используем прокси если есть proxy.txt
            proxy_manager=proxy_manager,  # Передаем менеджер прокси
            min_html_length=2000,      # Минимальная длина HTML в символах
            device_type="desktop",     # Тип устройства для эмуляции
            visible=True,              # Видимый режим (headless детектируется)
            skip_problematic=False     # НЕ пропускаем
        )
        
        # Сохраняем результаты
        save_results(results, str(output_file))
        
        logger.info(f"ГОТОВО!")
    
    test()
