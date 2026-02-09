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

        # --- НОВОЕ: Централизованные состояния ---
        self.microphone_enabled = True  # Состояние микрофона
        self.focus_mode_active = False  # Состояние режима концентрации

        # Коллбеки для оповещения GUI об изменениях состояния
        self._state_change_callbacks = []

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

    # ========== НОВЫЕ МЕТОДЫ: Управление состоянием ==========

    def register_state_callback(self, callback):
        """Регистрирует коллбек для оповещения об изменении состояния"""
        if callback not in self._state_change_callbacks:
            self._state_change_callbacks.append(callback)
            logger.debug("CTX: Зарегистрирован callback для состояния")

    def _notify_state_change(self, state_name: str, new_value: bool):
        """Оповещает все зарегистрированные коллбеки об изменении состояния"""
        for callback in self._state_change_callbacks:
            try:
                callback(state_name, new_value)
            except Exception as e:
                logger.error(f"CTX: Ошибка в callback: {e}")

    def get_microphone_should_listen(self):
        """
        Проверяет, должен ли микрофон обрабатывать звук
        Используется в Core для пропуска обработки когда микрофон "выключен"
        """
        return self.microphone_enabled

    def set_microphone_state(self, enabled: bool, source: str = "unknown"):
        """
        Централизованное управление микрофоном

        Args:
            enabled: True - включить, False - выключить
            source: Источник команды (gui, voice, system)
        """
        if self.microphone_enabled == enabled:
            logger.debug(f"CTX: Микрофон уже в состоянии {enabled}, пропуск")
            return False

        self.microphone_enabled = enabled
        logger.info(f"CTX: Микрофон {'включен' if enabled else 'выключен'} [{source}]")

        # Оповещаем GUI
        self._notify_state_change("microphone", enabled)

        return True

    def set_focus_mode(self, active: bool, source: str = "unknown"):
        """
        Централизованное управление режимом концентрации

        Args:
            active: True - включить, False - выключить
            source: Источник команды (gui, voice, system)
        """
        if self.focus_mode_active == active:
            logger.debug(f"CTX: Режим концентрации уже в состоянии {active}, пропуск")
            return False

        self.focus_mode_active = active
        logger.info(f"CTX: Режим концентрации {'включен' if active else 'выключен'} [{source}]")

        # Оповещаем GUI
        self._notify_state_change("focus_mode", active)

        return True

    # ========== СУЩЕСТВУЮЩИЕ МЕТОДЫ ==========

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

    def broadcast(self, text, ui=True, tg=True, window=None, priority=None, message=False, duration=None, **kwargs):
        """
        Вещание на все активные фронты.

        Args:
            text: Текст сообщения
            ui: Показывать в UI (обычное уведомление или центральное сообщение)
            tg: Отправлять в Telegram
            window: Открыть окно с указанным именем
            priority: Приоритет уведомления ("warning", "critical")
            message: Показать как центральное сообщение от ассистента (вместо бокового уведомления)
            duration: Длительность показа в мс (только для message=True)
            **kwargs: Дополнительные параметры
        """
        level = kwargs.get("level", "info")

        if ui:
            if message:
                # Центральное сообщение от ассистента
                self.ui_output(text, level, priority, message=True, duration=duration)
            else:
                # Обычное боковое уведомление
                self.ui_output(text, level, priority, message=False)

        if window:
            self.open_ui(window, text, **kwargs)

        if tg:
            prefix = "🤖 " if message else "📢 "
            db.add_tg_message(f"{prefix}{text}")

        log_msg = f"[MSG] {text}" if message else f"[BROADCAST] {text}"
        logger.info(log_msg)

    def reply(self, text, level="info", priority=None, to_all=False, message=False, duration=None):
        """
        Умный ответ: туда, откуда пришел запрос.

        Args:
            text: Текст ответа
            level: Уровень сообщения ("info", "success", "error")
            priority: Приоритет ("warning", "critical")
            to_all: Отправить во все каналы
            message: Показать как центральное сообщение от ассистента
            duration: Длительность показа в мс (только для message=True)
        """
        # 1. Ответ в GUI (если это голос 'mic', само приложение 'gui' или принудительно 'to_all')
        if self.last_input_source in ["mic", "gui"] or to_all:
            self.ui_output(text, level, priority, message=message, duration=duration)

        # 2. Ответ в Telegram
        if self.last_input_source == "tg" or to_all:
            prefix = "🤖 " if message else ""
            db.add_tg_message(f"{prefix}{text}")