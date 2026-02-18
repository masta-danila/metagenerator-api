"""
Модуль для проверки и исправления готовых метатегов через LLM
"""
import sys
import os
import json
import asyncio
from typing import List, Dict, Optional
from pathlib import Path

# Добавляем путь к папке llm для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'llm'))

from llm_router import llm_request  # type: ignore


async def review_and_fix_metatags(
    h1: str,
    title: str,
    description: str,
    h1_words: List[str],
    title_words: List[str],
    description_words: List[str],
    company_name: str,
    main_query: str,
    model: str,
    current_h1: str = None,
    h1_variables: Optional[List[str]] = None,
    title_variables: Optional[List[str]] = None,
    description_variables: Optional[List[str]] = None,
    max_title_length: int = None,
    max_description_length: int = None
) -> Dict[str, any]:
    """
    Проверяет и исправляет готовые метатеги на соответствие промпту и наличие ошибок
    
    Args:
        h1: Существующий h1
        title: Существующий title
        description: Существующий description
        h1_words: Список слов для использования в h1
        title_words: Список слов для использования в title
        description_words: Список слов для использования в description
        company_name: Название компании
        main_query: Основной поисковый запрос
        model: Модель LLM для проверки (обязательный параметр)
        current_h1: Текущий H1 страницы (для использования в качестве базы)
        h1_variables: Список переменных Битрикса для h1
        title_variables: Список переменных Битрикса для title
        description_variables: Список переменных Битрикса для description
        max_title_length: Максимальная длина Title в символах (если None, ограничение не указывается)
        max_description_length: Максимальная длина Description в символах (если None, ограничение не указывается)
    
    Returns:
        Словарь с исправленными метатегами и информацией о стоимости
    """
    import random
    
    # Случайный выбор количества слов для H1 (от 2 до 5)
    h1_word_count = random.randint(2, 5)
    selected_h1_words = h1_words[:h1_word_count] if len(h1_words) >= h1_word_count else h1_words
    
    # Формируем промпт для проверки и исправления
    prompt = "Проверь и исправь следующие метатеги на соответствие требованиям и наличие ошибок в тексте.\n\n"
    
    prompt += "ТЕКУЩИЕ МЕТАТЕГИ:\n"
    prompt += f"H1: {h1}\n"
    prompt += f"Title: {title}\n"
    prompt += f"Description: {description}\n\n"
    
    # ========== СЕКЦИЯ 1: H1 ==========
    prompt += "=== СЕКЦИЯ 1: H1 ===\n\n"

    # Требования к H1
    prompt += "Требования к H1:\n"

    if current_h1:
        prompt += f"Слова отсюда должны быть использованы по одному разу: {current_h1}\n\n"

    prompt += f"- отсюда должна быть выделена ключевая СУЩНОСТЬ (главный объект/предмет) и использованы слова, составляющие эту сущность по одному разу: {main_query}\n"
    prompt += f"- эти слова в текущем числе (мн или ед) должны быть использованы по одному разу: {', '.join(selected_h1_words)}\n"
    prompt += "- h1 не должен содержать грамматических ошибок\n"
    prompt += f"- ВАЖНО: НЕ ДОЛЖНО БЫТЬ использовано название компании '{company_name}' или любые его части\n"
    
    if h1_variables and len(h1_variables) > 0:
        prompt += f"- должны быть использованы переменные Битрикса: {', '.join(h1_variables)} (естественным образом)\n"
    
    prompt += "\n"
    
    # ========== СЕКЦИЯ 2: TITLE ==========
    prompt += "=== СЕКЦИЯ 2: TITLE ===\n\n"
    
    # Требования к Title
    prompt += "Требования к Title:\n"
    if max_title_length:
        prompt += f"- МАКСИМАЛЬНАЯ ДЛИНА: {max_title_length} символов (включая пробелы и переменные)\n"
    prompt += f"- основной запрос используй ближе к началу: {main_query}\n"
    prompt += f"- эти слова в текущем числе (мн или ед) должны быть использованы по одному разу: {', '.join(title_words)}\n"
    prompt += "- title должен представлять собой ОДНО осмысленное законченное предложение\n"
    prompt += "- должен быть коммерчески привлекательным и побуждать к действию\n"
    prompt += "- не должно быть использовано : и - (в качестве тире)\n"
    
    if title_variables and len(title_variables) > 0:
        prompt += f"- должны быть использованы переменные Битрикса: {', '.join(title_variables)} (естественным образом)\n"
    
    prompt += f"- должно быть использовано название компании: «{company_name}»\n"
    prompt += "\n"
    
    # ========== СЕКЦИЯ 3: DESCRIPTION ==========
    prompt += "=== СЕКЦИЯ 3: DESCRIPTION ===\n\n"
    
    # Требования к Description
    prompt += "Требования к Description:\n"
    if max_description_length:
        prompt += f"- МАКСИМАЛЬНАЯ ДЛИНА: {max_description_length} символов (включая пробелы и переменные)\n"
    prompt += f"- основной запрос используй ближе к началу: {main_query}\n"
    prompt += f"- эти слова в текущем числе (мн или ед) должны быть использованы по одному разу: {', '.join(description_words)}\n"
    prompt += "- description должен представлять собой одно или несколько осмысленных законченных предложений\n"
    
    if description_variables and len(description_variables) > 0:
        prompt += f"- должны быть использованы переменные Битрикса: {', '.join(description_variables)} (естественным образом)\n"
    
    prompt += f"- должно быть использовано название компании: «{company_name}»\n"
    prompt += "\n===\n\n"
    
    prompt += "ЗАДАЧА:\n"
    prompt += "1. Проверь каждый метатег на соответствие требованиям\n"
    prompt += "2. Проверь на грамматические, орфографические и пунктуационные ошибки\n"
    prompt += "3. Исправь найденные проблемы\n"
    prompt += "4. Если метатег соответствует всем требованиям и не содержит ошибок, оставь его без изменений\n\n"
    
    prompt += 'Верни результат СТРОГО в формате ЕДИНСТВЕННОГО JSON (без дополнительного текста):\n'
    prompt += '{"h1": "исправленный h1", "title": "исправленный title", "description": "исправленное description", "changes": ["список изменений, если были"]}\n'
    prompt += 'В одном ответе СТРОГО один JSON!\n'
    prompt += 'Если изменений не было, верни пустой список changes.'
    
    # Запускаем синхронный llm_request в executor
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: llm_request(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
    )
    
    content = response.get("content", "").strip()
    cost = response.get("cost", 0.0)
    
    # Парсим JSON ответ
    try:
        # Убираем markdown code blocks если есть
        if content.startswith("```"):
            # Находим первую и последнюю строку с ```
            lines = content.split('\n')
            start_idx = 0
            end_idx = len(lines)
            
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    start_idx = i + 1
                    break
            
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip().startswith("```"):
                    end_idx = i
                    break
            
            content = '\n'.join(lines[start_idx:end_idx])
        
        result = json.loads(content)
        
        return {
            "h1": result.get("h1", h1),
            "title": result.get("title", title),
            "description": result.get("description", description),
            "changes": result.get("changes", []),
            "cost": cost
        }
    
    except json.JSONDecodeError as e:
        return {
            "error": f"Ошибка парсинга JSON: {str(e)}",
            "raw_content": content,
            "h1": h1,
            "title": title,
            "description": description,
            "changes": [],
            "cost": cost
        }


if __name__ == "__main__":
    """Тестирование редактора метатегов"""
    
    async def test():
        print("\nТест редактора метатегов\n")
        print("=" * 80)
        
        # Загружаем данные с готовыми метатегами
        input_file = "jsontests/step12_generated_metatags.json"
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Выбираем случайный URL для теста
        import random
        sheet_id = list(data.keys())[0]
        urls = data[sheet_id]["urls"]
        url = random.choice(list(urls.keys()))
        url_data = urls[url]
        
        print(f"\nВыбран случайный URL: {url}\n")
        
        # Извлекаем параметры
        generated = url_data.get("generated_metatags", {})
        h1 = generated.get("h1", "")
        title = generated.get("title", "")
        description = generated.get("description", "")
        
        h1_words = url_data.get("lemmatized_h1_words", [])
        title_words = url_data.get("lemmatized_title_words", [])
        description_words = url_data.get("lemmatized_description_words", [])
        company_name = url_data.get("company_name", "")
        queries = url_data.get("queries", [])
        
        # Определяем основной запрос
        if queries:
            if isinstance(queries[0], dict):
                main_query = queries[0].get("query", "")
            else:
                main_query = queries[0]
        else:
            main_query = ""
        
        h1_variables = url_data.get("variables_h1", [])
        title_variables = url_data.get("variables_title", [])
        description_variables = url_data.get("variables_description", [])
        
        # Извлекаем текущий H1 страницы
        current_meta = url_data.get("current_meta", {})
        current_h1 = current_meta.get("h1", "") if current_meta else ""
        
        print("ИСХОДНЫЕ МЕТАТЕГИ:")
        print(f"H1: {h1}")
        print(f"Title: {title}")
        print(f"Description: {description}")
        print()
        
        print("Параметры проверки:")
        print(f"  Основной запрос: {main_query}")
        print(f"  Компания: {company_name}")
        print(f"  Текущий H1: {current_h1 if current_h1 else 'Не найден'}")
        print(f"  H1 words: {h1_words}")
        print(f"  Title words: {title_words}")
        print(f"  Description words: {description_words}")
        print()
        
        # Проверка и исправление
        print("Отправка запроса на проверку и исправление...\n")
        
        import time
        start_time = time.time()
        
        result = await review_and_fix_metatags(
            h1=h1,
            title=title,
            description=description,
            h1_words=h1_words,
            title_words=title_words,
            description_words=description_words,
            company_name=company_name,
            main_query=main_query,
            model="claude-sonnet-4-5-20250929",
            current_h1=current_h1,
            h1_variables=h1_variables,
            title_variables=title_variables,
            description_variables=description_variables,
            max_title_length=90,
            max_description_length=170
        )
        
        elapsed = time.time() - start_time
        
        print("=" * 80)
        print("ИСПРАВЛЕННЫЕ МЕТАТЕГИ:")
        print("=" * 80)
        print(f"\nH1: {result.get('h1', 'ОШИБКА')}")
        print(f"\nTitle: {result.get('title', 'ОШИБКА')}")
        print(f"\nDescription: {result.get('description', 'ОШИБКА')}")
        
        changes = result.get('changes', [])
        if changes:
            print(f"\nВнесенные изменения:")
            for i, change in enumerate(changes, 1):
                print(f"  {i}. {change}")
        else:
            print(f"\nИзменения не требуются - метатеги соответствуют требованиям")
        
        print(f"\nСтоимость: ${result.get('cost', 0.0):.6f}")
        print(f"Время выполнения: {elapsed:.2f}s")
        print()
        
        if "error" in result:
            print(f"ОШИБКА: {result['error']}")
            if "raw_content" in result:
                print(f"Сырой ответ: {result['raw_content'][:500]}")
        
        print("=" * 80)
    
    asyncio.run(test())
