import time
from pathlib import Path
from utils.config_manager import aiko_cfg
from utils.db_manager import db
from utils.logger import logger

class AikoContext:
    def __init__(self):
        self.is_running = True
        self.state = "init"  # init, idle, active, processing
        self.last_input_source = "mic"  # mic, tg, gui
        self.signals = None

        # --- Состояние активации (Для ActivationService) ---
        self.last_activation_time = 0.0
        self.active_window = aiko_cfg.get("trigger.active_window", 5.0)
        self.post_command_window = aiko_cfg.get("trigger.post_command_window", 3.0)

        # --- Конфигурация ресурсов ---
        self.model_path = Path(aiko_cfg.get("stt-model.path", "models/base"))
        self.device_id = aiko_cfg.get("audio.device_id", 1)

        # --- Мосты (Callbacks) с безопасными заглушками ---
        self.ui_output = lambda text, level="info", priority="low": None
        self.ui_status = lambda status: None
        self.ui_audio_status = lambda is_ok, msg: None

    def set_input_source(self, source: str):
        """Фиксирует, откуда пришла команда (нужно для reply)."""
        if source in ["mic", "tg", "gui"]:
            self.last_input_source = source
            logger.debug(f"CTX: Источник ввода установлен на {source}")

    def open_ui(self, name, *args, **kwargs):
        """Универсальный вызов любого окна одной строкой."""
        if self.signals:
            payload = {"name": name, "args": args, "kwargs": kwargs}
            self.signals.show_window.emit(payload)
        else:
            logger.warning(f"CTX: Попытка открыть {name}, когда GUI не активен.")

    def broadcast(self, text, ui=True, tg=True, window=None, priority=None, **kwargs):
        """Вещание на все активные фронты."""
        level = kwargs.get("level", "info")
        if ui: self.ui_output(text, level, priority)
        if window: self.open_ui(window, text, **kwargs)
        if tg: db.add_tg_message(f"📢 {text}")
        logger.info(f"BROADCAST: {text}")

    def reply(self, text, level="info", priority=None, to_all=False):
        """Умный ответ: туда, откуда пришел запрос."""

        # 1. Ответ в GUI (если это голос 'mic', само приложение 'gui' или принудительно 'to_all')
        if self.last_input_source in ["mic", "gui"] or to_all:
            self.ui_output(text, level, priority)

        # 2. Ответ в Telegram
        if self.last_input_source == "tg" or to_all:
            db.add_tg_message(text)