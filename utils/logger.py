import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class ColorFormatter(logging.Formatter):
    """Специальный форматтер для раскрашивания логов в консоли."""

    # ANSI escape codes для цветов
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    # Шаблон сообщения
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, self.date_format)
        return formatter.format(record)


def setup_logger(name="AIKO"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Стандартный форматтер для файла (без цветов)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', '%Y-%m-%d %H:%M:%S')

    # 1. Лог в консоль (Цветной)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())  # Используем наш новый класс
    console_handler.setLevel(logging.INFO)

    # 2. Лог в файл (макс 5МБ, храним 3 последних)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "aiko.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Очищаем старые хэндлеры, если они были (защита от дублирования при перезагрузке)
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Создаем глобальный объект логгера
logger = setup_logger()