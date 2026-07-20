import json
import logging
from pathlib import Path

def setup_logging(log_file: str = "parser.log"):
    """Настройка логирования"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def ensure_directories():
    """Создание необходимых папок"""
    Path("sessions").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)

def load_json_file(file_path: str, default=None):
    """Загрузка JSON файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default or {}

def save_json_file(file_path: str, data):
    """Сохранение JSON файла"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)