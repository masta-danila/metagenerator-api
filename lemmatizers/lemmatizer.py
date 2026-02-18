"""
Модуль для лемматизации (приведения слов к начальной форме) с использованием Yandex Mystem.
"""
from pymystem3 import Mystem
import pymorphy3
from typing import List, Dict
from pathlib import Path


# Глобальные экземпляры (создаются один раз при импорте модуля)
_mystem = None
_morph = None


def _get_mystem() -> Mystem:
    """Получает или создает глобальный экземпляр Mystem"""
    global _mystem
    if _mystem is None:
        _mystem = Mystem()
    return _mystem


def _get_morph() -> pymorphy3.analyzer.MorphAnalyzer:
    """Получает или создает глобальный экземпляр pymorphy3.MorphAnalyzer"""
    global _morph
    if _morph is None:
        _morph = pymorphy3.MorphAnalyzer()
    return _morph


def lemmatize_text(text: str) -> str:
    """
    Приводит все слова в тексте к начальной форме
    
    Args:
        text: Текст для лемматизации
    
    Returns:
        Текст с леммами (через пробел)
    """
    mystem = _get_mystem()
    lemmas = mystem.lemmatize(text)
    # Убираем лишние пробелы и переносы строк
    lemmas = [lemma.strip() for lemma in lemmas if lemma.strip()]
    return ' '.join(lemmas)


def lemmatize_list(texts: List[str]) -> List[str]:
    """
    Лемматизирует список текстов
    
    Args:
        texts: Список текстов для лемматизации
    
    Returns:
        Список лемматизированных текстов
    """
    return [lemmatize_text(text) for text in texts]


def get_lemmas(text: str) -> List[str]:
    """
    Возвращает список лемм для текста
    
    Args:
        text: Текст для лемматизации
    
    Returns:
        Список лемм
    """
    mystem = _get_mystem()
    lemmas = mystem.lemmatize(text)
    return [lemma.strip() for lemma in lemmas if lemma.strip()]


def analyze(text: str) -> List[Dict]:
    """
    Получает подробный морфологический анализ текста
    
    Args:
        text: Текст для анализа
    
    Returns:
        Список словарей с информацией о каждом слове
    """
    mystem = _get_mystem()
    analysis = mystem.analyze(text)
    results = []
    
    for item in analysis:
        if 'analysis' in item and item['analysis']:
            word_info = item['analysis'][0]
            results.append({
                'text': item.get('text', ''),
                'lemma': word_info.get('lex', ''),
                'pos': word_info.get('gr', '').split(',')[0] if word_info.get('gr') else '',
                'grammar': word_info.get('gr', ''),
            })
    
    return results


def lemmatize_queries(queries: List[str]) -> Dict[str, str]:
    """
    Лемматизирует список поисковых запросов
    
    Args:
        queries: Список поисковых запросов
    
    Returns:
        Словарь {оригинальный_запрос: лемматизированный_запрос}
    """
    result = {}
    for query in queries:
        lemmatized = lemmatize_text(query)
        result[query] = lemmatized
    return result


def save_results_to_json(results: Dict, filename: str = "jsontests/lemmatizer_results.json") -> None:
    """
    Сохраняет результаты лемматизации в JSON файл
    
    Args:
        results: Словарь с результатами анализа
        filename: Путь к файлу для сохранения
    """
    import os
    import json
    
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Результаты сохранены в файл: {filename}")


def find_common_words(queries: List[str], min_frequency_percent: float = 0.15) -> List[str]:
    """
    Находит самые частотные слова и возвращает их в им.п. с сохранением наиболее частого числа (ед./мн.)
    
    Args:
        queries: Список поисковых запросов/фраз
        min_frequency_percent: Минимальный процент фраз (0.0-1.0), в которых должно встречаться слово
                              Например, 0.15 = минимум 15% фраз (по умолчанию 0.15)
    
    Returns:
        Список всех слов, которые встречаются в минимум min_frequency_percent фраз,
        отсортированных по убыванию частоты, в им.п. с наиболее частым числом.
        Исключаются предлоги, союзы, частицы и слова с частотой меньше min_frequency_percent
    """
    if not queries:
        return []
    
    # Части речи, которые НЕ нужны (служебные части речи + глаголы)
    # PR = предлог, CONJ = союз, PART = частица, INTJ = междометие, V = глагол
    # Глаголы исключаем, т.к. синтез с nomn превращает их в причастия
    exclude_pos = {'PR', 'CONJ', 'PART', 'INTJ', 'V'}
    
    mystem = _get_mystem()
    morph = _get_morph()
    
    # Словарь для подсчета вхождений каждой комбинации (лемма, число) в фразы
    word_number_phrase_count = {}  # {(лемма, число): количество фраз}
    
    # Обрабатываем каждую фразу
    for query in queries:
        # Получаем морфологический анализ
        analysis = mystem.analyze(query)
        
        # Собираем леммы с числом для текущей фразы
        lemmas_in_phrase = set()  # {(лемма, число)}
        
        for item in analysis:
            if 'analysis' in item and item['analysis']:
                word_info = item['analysis'][0]
                lemma = word_info.get('lex', '').strip()
                grammar = word_info.get('gr', '')
                
                # Определяем часть речи (первая часть до запятой)
                pos = grammar.split(',')[0].split('=')[0] if grammar else ''
                
                # Определяем число из грамматики
                number = 'sing'  # по умолчанию единственное
                if 'мн' in grammar:
                    number = 'plur'
                elif 'ед' in grammar:
                    number = 'sing'
                
                # Фильтруем:
                # 1. Исключаем служебные части речи
                # 2. Короткие слова (меньше 3 символов)
                # 3. Только слова с буквами
                if (pos not in exclude_pos and 
                    lemma and 
                    len(lemma) >= 3 and 
                    any(c.isalpha() for c in lemma)):
                    lemmas_in_phrase.add((lemma, number))
        
        # Увеличиваем счетчик для каждой уникальной комбинации (лемма, число) в этой фразе
        for lemma_number in lemmas_in_phrase:
            if lemma_number not in word_number_phrase_count:
                word_number_phrase_count[lemma_number] = 0
            word_number_phrase_count[lemma_number] += 1
    
    # Если слов нет, возвращаем пустой список
    if not word_number_phrase_count:
        return []
    
    # Для каждой леммы выбираем наиболее частое число
    lemma_best_form = {}  # {лемма: (число, частота)}
    
    for (lemma, number), count in word_number_phrase_count.items():
        if lemma not in lemma_best_form:
            lemma_best_form[lemma] = (number, count)
        else:
            prev_number, prev_count = lemma_best_form[lemma]
            # Обновляем, если новое число встречается чаще
            # При равенстве предпочитаем множественное число
            if count > prev_count or (count == prev_count and number == 'plur' and prev_number == 'sing'):
                lemma_best_form[lemma] = (number, count)
    
    # Вычисляем минимальный порог на основе процента
    total_queries = len(queries)
    min_count = max(1, int(total_queries * min_frequency_percent))  # минимум 1
    
    # Фильтруем слова с низкой частотой
    filtered = [(lemma, number, count) for lemma, (number, count) in lemma_best_form.items() 
                if count >= min_count]
    
    # Если после фильтрации слов нет, возвращаем пустой список
    if not filtered:
        return []
    
    # Сортируем по убыванию частоты
    sorted_lemmas = sorted(filtered, key=lambda x: x[2], reverse=True)
    
    # Синтезируем формы (им.п. + нужное число) через pymorphy3
    result_words = []
    for lemma, number, count in sorted_lemmas:
        parsed = morph.parse(lemma)[0]
        form = parsed.inflect({number, 'nomn'})  # им.п. + число
        word = form.word if form else lemma
        result_words.append(word)
    
    # Возвращаем все слова, прошедшие порог по частоте, отсортированные по убыванию частоты
    return result_words


if __name__ == "__main__":
    """
    Тестовый запуск - извлекает title из filtered_urls и находит частотные слова
    """
    import json
    
    # Определяем пути относительно корня проекта
    project_root = Path(__file__).parent.parent
    input_file = project_root / "jsontests" / "xmlriver_batch_results_with_meta.json"
    output_file = project_root / "jsontests" / "lemmatizer_results.json"
    
    # Читаем JSON файл
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Извлекаем все title из filtered_urls
    texts = []
    
    for spreadsheet_id, spreadsheet_info in data.items():
        urls_dict = spreadsheet_info.get('urls', {})
        for url, url_data in urls_dict.items():
            filtered_urls = url_data.get('filtered_urls', [])
            for item in filtered_urls:
                # Проверяем, является ли item словарем с метаданными
                if isinstance(item, dict) and 'meta' in item:
                    meta = item['meta']
                    if meta and 'title' in meta and meta['title']:
                        texts.append(meta['title'])
    
    print(f"Найдено текстов: {len(texts)}")
    
    # Находим частотные слова (все слова, встречающиеся в минимум 15% текстов)
    min_frequency_percent = 0.30
    common_words = find_common_words(texts, min_frequency_percent=min_frequency_percent)
    
    print(f"\nВыбрано слов: {len(common_words)}")
    print(f"Частотные слова: {common_words}")
    
    # Сохраняем список слов
    save_results_to_json(common_words, str(output_file))
