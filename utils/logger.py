import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ============================================================
# FORMATTERS
# ============================================================

class ColorFormatter(logging.Formatter):
    """Специальный форматтер для раскрашивания логов в консоли."""
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

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


# ============================================================
# UI HANDLER (SAFE & THROTTLED)
# ============================================================

class ToastHandler(logging.Handler):
    """Потокобезопасный хэндлер с защитой от спама для Qt уведомлений."""

    def __init__(self, notification_manager, interval=5.0):
        super().__init__()
        self.manager = notification_manager
        self.interval = interval
        self._last_messages = {}  # {msg: timestamp}
        self._max_cache = 100

    def emit(self, record):
        try:
            # Текст сообщения без системных метаданных для UI
            msg = record.getMessage()
            now = time.time()

            # Дросселирование (Throttling) идентичных сообщений
            if msg in self._last_messages:
                if now - self._last_messages[msg] < self.interval:
                    return

            # Очистка кеша при переполнении
            if len(self._last_messages) > self._max_cache:
                self._last_messages.clear()

            self._last_messages[msg] = now

            # Отправка в менеджер (add_item уже защищен сигналом в PopupNotification)
            if record.levelno >= logging.CRITICAL:
                self.manager.add_item(msg, msg_type="error", priority="critical")
            elif record.levelno >= logging.ERROR:
                self.manager.add_item(msg, msg_type="error")
            elif record.levelno >= logging.WARNING:
                self.manager.add_item(msg, msg_type="info", priority="warning", lifetime=4000)

        except Exception:
            self.handleError(record)


# ============================================================
# SETUP FUNCTIONS
# ============================================================

def setup_logger(name="AIKO"):
    """Инициализация базового логгера (Консоль + Файл)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorFormatter())
    console_handler.setLevel(logging.INFO)

    # 2. File Handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "aiko.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s', '%Y-%m-%d %H:%M:%S'
    ))
    file_handler.setLevel(logging.DEBUG)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def register_ui_logger(notification_manager):
    """Связывает логгер с UI. Вызывать строго ПОСЛЕ инициализации PopupNotification."""
    logger = logging.getLogger("AIKO")

    ui_handler = ToastHandler(notification_manager)
    ui_handler.setLevel(logging.WARNING)  # Ловим WARNING и выше

    # Форматтер для UI (только суть, без дат)
    ui_formatter = logging.Formatter('%(message)s')
    ui_handler.setFormatter(ui_formatter)

    logger.addHandler(ui_handler)
    logger.info("UI Logger registered successfully.")


# Глобальный объект для импорта
logger = setup_logger()