import time
from pathlib import Path
from typing import Optional
from utils.config_manager import aiko_cfg
from utils.db_manager import db
from utils.logger import logger


class AikoContext:
    def __init__(self):
        # --- Системные состояния ---
        self.is_running = True
        self.state = "init"  # init, idle, active, processing
        self.last_input_source = "mic"  # mic, tg, gui
        self.signals = None  # Сюда прилетят сигналы из GUI

        # --- Менеджеры (Присваиваются в main.py) ---
        self.ui_manager = None  # PopupNotification instance

        # --- Состояние активации (Для ActivationService) ---
        self.last_activation_time = 0.0
        self.active_window = aiko_cfg.get("trigger.active_window", 5.0)
        self.post_command_window = aiko_cfg.get("trigger.post_command_window", 3.0)

        # --- Конфигурация ресурсов ---
        self.model_path = Path(aiko_cfg.get("stt-model.path", "models/base"))
        self.device_id = aiko_cfg.get("audio.device_id", 1)

        # --- Коллбеки для GUI ---
        self.ui_status = lambda status: None
        self.ui_audio_status = lambda is_ok, msg: None

    def ui_output(self, text: str, level: str = "info", priority: Optional[str] = None):
        """Централизованный вывод в UI уведомления."""
        if self.ui_manager:
            # Наш PopupNotification принимает msg_type, что логически равно level
            self.ui_manager.add_item(text, msg_type=level, priority=priority)
        else:
            # Если менеджер еще не проброшен, дублируем критику в лог
            logger.warning(f"CTX_FALLBACK: [{level.upper()}] {text}")

    def set_input_source(self, source: str):
        """Фиксирует, откуда пришла команда (нужно для reply)."""
        if source in ["mic", "tg", "gui"]:
            self.last_input_source = source
            logger.debug(f"CTX: Источник ввода установлен на {source}")

    def open_ui(self, name: str, *args, **kwargs):
        """Универсальный вызов любого окна через сигналы Qt."""
        if self.signals:
            payload = {"name": name, "args": args, "kwargs": kwargs}
            self.signals.show_window.emit(payload)
        else:
            logger.warning(f"CTX: Попытка открыть {name}, когда GUI не активен.")

    def broadcast(self, text: str, ui=True, tg=True, window=None, priority: Optional[str] = None, **kwargs):
        """Вещание на все активные фронты (UI, Telegram, Окна)."""
        # Поддержка обоих имен аргумента для совместимости
        msg_type = kwargs.get("msg_type", kwargs.get("level", "info"))

        if ui:
            self.ui_output(text, level=msg_type, priority=priority)

        if window:
            self.open_ui(window, text, **kwargs)

        if tg:
            # Добавляем визуальный префикс для ТГ в зависимости от типа
            prefix = "⚠️ " if priority in ["warning", "critical"] else "📢 "
            db.add_tg_message(f"{prefix}{text}")

        logger.info(f"BROADCAST [{msg_type.upper()}]: {text}")

    def reply(self, text: str, level: str = "info", priority: Optional[str] = None, to_all: bool = False):
        """Умный ответ: отправляет сообщение в канал-источник запроса."""
        # 1. Ответ в GUI
        if self.last_input_source in ["mic", "gui"] or to_all:
            self.ui_output(text, level, priority)

        # 2. Ответ в Telegram
        if self.last_input_source == "tg" or to_all:
            db.add_tg_message(text)