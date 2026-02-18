"""
Модуль для парсинга сайтов
"""
from .html_parser import parse_for_ml, save_to_json
from .meta_extractor import extract_meta, extract_meta_from_dict
from .batch_meta_processor import extract_meta_from_filtered_urls, save_results

__all__ = [
    'parse_for_ml',
    'save_to_json',
    'extract_meta',
    'extract_meta_from_dict',
    'extract_meta_from_filtered_urls',
    'save_results',
]
