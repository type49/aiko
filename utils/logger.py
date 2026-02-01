import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(name="AIKO"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Формат: Дата Время [Уровень] Модуль: Сообщение
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', '%Y-%m-%d %H:%M:%S')

    # 1. Лог в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 2. Лог в файл (макс 5МБ, храним 3 последних)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(log_dir / "aiko.log", maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()