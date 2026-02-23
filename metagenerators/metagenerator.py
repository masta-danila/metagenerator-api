"""
Метагенератор - модуль для генерации SEO-текстов (H1, Title, Description) через LLM.
"""
import sys
import os
import json
import asyncio
from typing import List, Dict
from pathlib import Path

# Добавляем путь к папке llm для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'llm'))

from llm_router import llm_request  # type: ignore


async def generate_seo_texts(
    title_words: List[str],
    description_words: List[str],
    h1_words: List[str],
    company_name: str,
    main_query: str = None,
    h1_variables: List[str] = None,
    title_variables: List[str] = None,
    description_variables: List[str] = None,
    example_titles: List[str] = None,
    example_descriptions: List[str] = None,
    example_h1s: List[str] = None,
    current_h1: str = None,
    max_title_length: int = None,
    max_description_length: int = None,
    use_main_query_in_h1: bool = True,
    use_main_query_in_title: bool = True,
    use_main_query_in_description: bool = True,
    model: str = "claude-sonnet-4-5-20250929"
) -> Dict[str, str]:
    """
    Генерирует H1, Title и Description через LLM
    
    Args:
        title_words: Список слов для использования в title
        description_words: Список слов для использования в description
        h1_words: Список слов для использования в h1
        company_name: Название компании
        main_query: Основной поисковый запрос для title и description (если None, берется первое слово из title_words)
        h1_variables: Список переменных Битрикса для h1 (например, ["#PRICE#", "#NAME#"])
        title_variables: Список переменных Битрикса для title (например, ["#PRICE#", "#NAME#"])
        description_variables: Список переменных Битрикса для description
        example_titles: Примеры title от конкурентов (для ознакомления)
        example_descriptions: Примеры description от конкурентов (для ознакомления)
        example_h1s: Примеры h1 от конкурентов (для ознакомления)
        current_h1: Текущий H1 страницы (для использования в качестве базы при генерации)
        max_title_length: Максимальная длина Title в символах (если None, ограничение не указывается в промпте)
        max_description_length: Максимальная длина Description в символах (если None, ограничение не указывается в промпте)
        use_main_query_in_h1: Использовать ли основной запрос в требованиях к H1 (по умолчанию True)
        use_main_query_in_title: Использовать ли основной запрос в требованиях к Title (по умолчанию True)
        use_main_query_in_description: Использовать ли основной запрос в требованиях к Description (по умолчанию True)
        model: Модель LLM для генерации
    
    Returns:
        Словарь с ключами: h1, title, description, cost
    """
    # Определяем основной запрос
    if main_query is None:
        main_query = title_words[0] if title_words else ""
    
    # Случайный выбор количества слов для H1 (от 2 до 5)
    import random
    h1_word_count = random.randint(2, 5)
    selected_h1_words = h1_words[:h1_word_count] if len(h1_words) >= h1_word_count else h1_words
    
    # Формируем промпт с разделением на секции
    prompt = "Напиши h1, title и description для страницы сайта.\n\n"
    
    # ========== СЕКЦИЯ 1: H1 ==========
    prompt += "=== СЕКЦИЯ 1: H1 ===\n\n"
    
    # Примеры H1
    if example_h1s:
        prompt += "Примеры H1 от конкурентов (для ознакомления):\n"
        for i, h1 in enumerate(example_h1s[:3], 1):
            prompt += f"  {i}. {h1}\n"
        prompt += "\n"
    
    # Текущий H1 (если есть)
    if current_h1:
        prompt += f"Текущий H1 на странице прими за базу с использованием всех его слов: {current_h1}\n\n"
    
    # Требования к H1
    prompt += "Требования к H1:\n"
    if use_main_query_in_h1:
        prompt += f"- из основного запроса выдели ключевую СУЩНОСТЬ (главный объект/предмет) и используй слова, составляющие эту сущность по одному разу: {main_query}\n"
    prompt += f"- используй все слова в текущем числе (мн или ед) по одному разу: {', '.join(selected_h1_words)}\n"
    prompt += "- если удается обойтись приведенными выше словами (h1 выглядит логично и понятно), то не выдумывай и не добавляй новых слов\n"
    prompt += f"- ВАЖНО: ЗАПРЕЩЕНО использовать название компании '{company_name}' или любые его части\n"
    prompt += "- старайся обходиться без :\n"
    
    if h1_variables and len(h1_variables) > 0:
        prompt += f"- используй переменные Битрикса: {', '.join(h1_variables)} (естественным образом)\n"
    
    prompt += "\n"
    
    # ========== СЕКЦИЯ 2: TITLE ==========
    prompt += "=== СЕКЦИЯ 2: TITLE ===\n\n"
    
    # Примеры Title
    if example_titles:
        prompt += "Примеры Title от конкурентов (для ознакомления):\n"
        for i, title in enumerate(example_titles[:3], 1):
            prompt += f"  {i}. {title}\n"
        prompt += "\n"
    
    # Требования к Title
    prompt += "Требования к Title:\n"
    if max_title_length:
        prompt += f"- МАКСИМАЛЬНАЯ ДЛИНА: {max_title_length} символов (включая пробелы и переменные)\n"
    if use_main_query_in_title:
        prompt += f"- основной запрос используй ближе к началу: {main_query}\n"
    prompt += f"- используй все слова в том числе (мн или ед) как они даны тут по одному разу: {', '.join(title_words)}\n"
    prompt += "- title должен представлять собой ОДНО осмысленное законченное предложение\n"
    prompt += "- должен быть коммерчески привлекательным и побуждать к действию\n"
    prompt += "- старайся обходиться без : и -\n"
    
    if title_variables and len(title_variables) > 0:
        prompt += f"- используй переменные Битрикса: {', '.join(title_variables)} (естественным образом)\n"
    
    prompt += f"- используй название компании: «{company_name}»\n"
    prompt += "\n"
    
    # ========== СЕКЦИЯ 3: DESCRIPTION ==========
    prompt += "=== СЕКЦИЯ 3: DESCRIPTION ===\n\n"
    
    # Примеры Description
    if example_descriptions:
        prompt += "Примеры Description от конкурентов (для ознакомления):\n"
        for i, desc in enumerate(example_descriptions[:3], 1):
            prompt += f"  {i}. {desc}\n"
        prompt += "\n"
    
    # Требования к Description
    prompt += "Требования к Description:\n"
    if max_description_length:
        prompt += f"- МАКСИМАЛЬНАЯ ДЛИНА: {max_description_length} символов (включая пробелы и переменные)\n"
    if use_main_query_in_description:
        prompt += f"- основной запрос используй ближе к началу: {main_query}\n"
    prompt += f"- используй все слова в том числе (мн или ед) как они даны тут по одному разу: {', '.join(description_words)}\n"
    prompt += "- description должен представлять собой одно или несколько осмысленных законченных предложений\n"
    
    if description_variables and len(description_variables) > 0:
        prompt += f"- используй переменные Битрикса: {', '.join(description_variables)} (естественным образом)\n"
    
    prompt += f"- используй название компании: «{company_name}»\n"
    prompt += "\n===\n"
    prompt += """

Верни результат СТРОГО в формате ЕДИНСТВЕННОГО JSON (без дополнительного текста):
{
  "h1": "текст h1",
  "title": "текст title",
  "description": "текст description"
В одном ответе СТРОГО один JSON!
}"""
    
    # Запускаем синхронный llm_request в executor
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: llm_request(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
    )
    
    # Парсим ответ
    content = response.get("content", "{}")
    
    try:
        result = json.loads(content)
        return {
            "h1": result.get("h1", ""),
            "title": result.get("title", ""),
            "description": result.get("description", ""),
            "cost": response.get("cost", 0)
        }
    except json.JSONDecodeError:
        # Если не удалось распарсить JSON, возвращаем пустой результат
        return {
            "h1": "",
            "title": "",
            "description": "",
            "cost": response.get("cost", 0),
            "error": "Failed to parse LLM response",
            "raw_content": content
        }


def save_results_to_json(results: Dict, filename: str = "jsontests/seo_texts_results.json", silent: bool = False) -> None:
    """
    Сохраняет результаты генерации в JSON файл
    
    Args:
        results: Словарь с результатами
        filename: Путь к файлу для сохранения
        silent: Не выводить сообщение о сохранении
    """
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    if not silent:
        print(f"\n✓ Результаты генерации сохранены в файл: {filename}")
        print(f"  Для проверки и выбора лучшего варианта запустите: arsenkin/metatag_checker.py")


if __name__ == "__main__":
    """
    Тест генерации SEO-текстов - выбирает случайный URL из lemmatizer_processor_results.json
    и генерирует H1, Title, Description через LLM
    """
    import random
    
    async def test():
        try:
            # Определяем пути относительно корня проекта
            project_root = Path(__file__).parent.parent
            input_file = project_root / "jsontests" / "step11_lemmatized.json"
            output_file = project_root / "jsontests" / "metagenerator_test_results.json"
            
            # Загружаем данные из lemmatizer_processor_results.json
            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Собираем все URL из всех spreadsheet
            all_urls = []
            for spreadsheet_id, spreadsheet_info in data.items():
                urls_dict = spreadsheet_info.get('urls', {})
                for url in urls_dict.keys():
                    all_urls.append((spreadsheet_id, url))
            
            if not all_urls:
                print("В данных не найдено ни одного URL")
                return
            
            # Выбираем случайный URL
            spreadsheet_id, target_url = random.choice(all_urls)
            url_data = data[spreadsheet_id]['urls'][target_url]
            
            # Извлекаем данные
            company_name = url_data.get("company_name", "Ворота нам")
            queries_list = url_data.get("queries", [])
            
            # Берем основной запрос из первого query
            if queries_list and isinstance(queries_list[0], dict):
                main_query = queries_list[0].get("query", "ворота")
            else:
                main_query = "ворота"
            
            # Переменные Битрикса
            h1_variables = url_data.get("variables_h1", [])
            title_variables = url_data.get("variables_title", [])
            description_variables = url_data.get("variables_description", [])
            
            # Извлекаем текущий H1 страницы
            current_meta = url_data.get("current_meta", {})
            current_h1 = current_meta.get("h1", "") if current_meta else ""
            
            # Определяем тип основного URL
            main_page_classification = url_data.get('page_classification', {})
            main_page_type = main_page_classification.get('page_type') if main_page_classification else None
            
            # Собираем примеры от конкурентов с приоритетом по типу страницы
            same_type_examples = {'titles': [], 'descriptions': [], 'h1s': []}
            other_examples = {'titles': [], 'descriptions': [], 'h1s': []}
            
            for query_item in queries_list:
                if isinstance(query_item, dict):
                    filtered_urls = query_item.get('filtered_urls', [])
                    for item in filtered_urls:
                        if isinstance(item, dict) and 'competitor_meta' in item:
                            # Пропускаем конкурентов с ошибками
                            if 'error' in item or 'parsing_error' in item:
                                continue
                            
                            competitor_meta = item['competitor_meta']
                            if not competitor_meta:
                                continue
                            
                            # Определяем тип конкурента
                            page_classification = item.get('page_classification', {})
                            page_type = page_classification.get('page_type') if page_classification else None
                            
                            # Выбираем группу для добавления
                            is_same_type = (main_page_type and page_type == main_page_type)
                            target = same_type_examples if is_same_type else other_examples
                            
                            # Добавляем в соответствующую группу
                            if competitor_meta.get('title'):
                                target['titles'].append(competitor_meta['title'])
                            if competitor_meta.get('description'):
                                target['descriptions'].append(competitor_meta['description'])
                            if competitor_meta.get('h1'):
                                target['h1s'].append(competitor_meta['h1'])
            
            # Формируем итоговые списки примеров: сначала с тем же типом, потом остальные
            example_titles = same_type_examples['titles'][:3]
            if len(example_titles) < 3:
                example_titles.extend(other_examples['titles'][:3 - len(example_titles)])
            
            example_descriptions = same_type_examples['descriptions'][:3]
            if len(example_descriptions) < 3:
                example_descriptions.extend(other_examples['descriptions'][:3 - len(example_descriptions)])
            
            example_h1s = same_type_examples['h1s'][:3]
            if len(example_h1s) < 3:
                example_h1s.extend(other_examples['h1s'][:3 - len(example_h1s)])
            
            # Импортируем функцию лемматизации
            sys.path.insert(0, str(project_root / "lemmatizers"))
            from lemmatizer import find_common_words  # type: ignore
            
            # Извлекаем слова из ЭТИХ ЖЕ примеров, которые показываем в промпте
            h1_words = find_common_words(
                example_h1s,
                min_frequency_percent=0.75
            ) if example_h1s else []
            
            title_words = find_common_words(
                example_titles,
                min_frequency_percent=0.75
            ) if example_titles else []
            
            description_words = find_common_words(
                example_descriptions,
                min_frequency_percent=0.75
            ) if example_descriptions else []
            
            print(f"\nВыбран случайный URL: {target_url}")
            print(f"Тип страницы: {main_page_type if main_page_type else 'Не определен'}")
            print(f"Текущий H1: {current_h1 if current_h1 else 'Не найден'}")
            
            print(f"\n{'='*80}")
            print("ИЗВЛЕЧЕННЫЕ СЛОВА ИЗ ПРИМЕРОВ:")
            print(f"{'='*80}")
            print(f"\nH1 words: {h1_words}")
            print(f"Title words: {title_words}")
            print(f"Description words: {description_words}")
            
            print(f"\n{'='*80}")
            print("ПАРАМЕТРЫ ГЕНЕРАЦИИ:")
            print(f"{'='*80}")
            print(f"Основной запрос: {main_query}")
            print(f"Компания: {company_name}")
            print(f"H1 variables: {h1_variables}")
            print(f"Title variables: {title_variables}")
            print(f"Description variables: {description_variables}")
            
            print(f"\n{'='*80}")
            print("Отправка запроса в LLM...")
            print(f"{'='*80}")
            
            # Генерируем SEO-тексты
            seo_texts = await generate_seo_texts(
                title_words=title_words,
                description_words=description_words,
                h1_words=h1_words,
                company_name=company_name,
                main_query=main_query,
                h1_variables=h1_variables,
                title_variables=title_variables,
                description_variables=description_variables,
                example_titles=example_titles,
                example_descriptions=example_descriptions,
                example_h1s=example_h1s,
                current_h1=current_h1,
                max_title_length=80,
                max_description_length=150,
                use_main_query_in_h1=True,
                use_main_query_in_title=True,
                use_main_query_in_description=True,
                model="claude-sonnet-4-5-20250929"
            )
            
            # Добавляем метаданные
            seo_texts["metadata"] = {
                "url": target_url,
                "h1_words": h1_words,
                "title_words": title_words,
                "description_words": description_words,
                "company_name": company_name,
                "main_query": main_query,
                "h1_variables": h1_variables,
                "title_variables": title_variables,
                "description_variables": description_variables,
                "examples_count": {
                    "h1": len(example_h1s),
                    "title": len(example_titles),
                    "description": len(example_descriptions)
                }
            }
            
            # Сохраняем результат
            save_results_to_json(seo_texts, str(output_file), silent=False)
            
            # Выводим результаты
            print("\n" + "="*80)
            print("РЕЗУЛЬТАТЫ:")
            print("="*80)
            print(f"\nH1: {seo_texts.get('h1', '')}")
            print(f"\nTitle: {seo_texts.get('title', '')}")
            print(f"\nDescription: {seo_texts.get('description', '')}")
            print(f"\nСтоимость: ${seo_texts.get('cost', 0):.6f}")
            
            if "error" in seo_texts:
                print(f"\nОшибка: {seo_texts['error']}")
                if "raw_content" in seo_texts:
                    print(f"\nСырой ответ LLM:\n{seo_texts['raw_content']}")
            
        except FileNotFoundError as e:
            print(f"Файл не найден: {e}")
        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test())
