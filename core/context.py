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
        self.core = None  # Ссылка на AikoCore (для доступа к audio)

        # --- НОВОЕ: Централизованные состояния ---
        self.microphone_enabled = True  # Состояние микрофона
        self.focus_mode_active = False  # Состояние режима концентрации

        # --- UI СТАТУС (для трея и других UI элементов) ---
        # Возможные значения: "init", "idle", "active", "blocked", "mute"
        self.ui_status_value = "init"
        self._ui_status_callbacks = []  # Коллбеки для обновления UI (трей, окна и т.д.)

        # Коллбеки для оповещения GUI об изменениях состояния
        self._state_change_callbacks = []

        # --- Состояние активации (Для ActivationService) ---
        self.last_activation_time = 0.0
        self.active_window = aiko_cfg.get("trigger.active_window", 5.0)
        self.post_command_window = aiko_cfg.get("trigger.post_command_window", 3.0)

        # --- Конфигурация ресурсов ---
        self.model_path = Path(aiko_cfg.get("stt-model.path", "models/base"))
        self.device_id = aiko_cfg.get("audio.device_id", 1)

        # --- Коллбеки для GUI (DEPRECATED - используйте set_ui_status) ---
        self.ui_status = lambda status: None
        self.ui_audio_status = lambda is_ok, msg: None

    # ========== UI СТАТУС (ЦЕНТРАЛИЗОВАННЫЙ) ==========

    def register_ui_status_callback(self, callback):
        """
        Регистрирует коллбек для получения обновлений UI статуса.
        Используется треем, окнами и другими UI элементами.

        Коллбек вызывается как: callback(status: str)
        где status один из: "init", "idle", "active", "blocked", "mute"
        """
        if callback not in self._ui_status_callbacks:
            self._ui_status_callbacks.append(callback)
            logger.debug("CTX: Зарегистрирован UI status callback")
            # Сразу отправляем текущий статус
            callback(self.ui_status_value)

    def set_ui_status(self, new_status: str, source: str = "unknown"):
        """
        Централизованная установка UI статуса.
        БЕЗОПАСНО: Автоматически оповещает все UI элементы через Qt сигналы.

        Args:
            new_status: Один из: "init", "idle", "active", "blocked", "mute"
            source: Источник изменения (для логирования)
        """
        valid_statuses = ["init", "idle", "active", "blocked", "mute"]
        if new_status not in valid_statuses:
            logger.warning(f"CTX: Некорректный UI статус '{new_status}', игнорирую")
            return False

        if self.ui_status_value == new_status:
            logger.debug(f"CTX: UI статус уже '{new_status}', пропуск")
            return False

        old_status = self.ui_status_value
        self.ui_status_value = new_status
        logger.info(f"CTX: UI статус изменен: {old_status} → {new_status} [{source}]")

        # КРИТИЧНО: Используем сигналы вместо прямых вызовов
        if self.signals:
            # Отправляем через Qt сигнал (безопасно из любого потока)
            self.signals.ui_status_changed.emit(new_status)
        else:
            # Fallback для прямых вызовов (только если сигналы не инициализированы)
            for callback in self._ui_status_callbacks:
                try:
                    callback(new_status)
                except Exception as e:
                    logger.error(f"CTX: Ошибка в UI status callback: {e}")

        return True

    # ========== УПРАВЛЕНИЕ СОСТОЯНИЯМИ ==========

    def register_state_callback(self, callback):
        """Регистрирует коллбек для оповещения об изменении состояния"""
        if callback not in self._state_change_callbacks:
            self._state_change_callbacks.append(callback)
            logger.debug("CTX: Зарегистрирован callback для состояния")

    def _notify_state_change(self, state_name: str, new_value: bool):
        """Оповещает все зарегистрированные коллбеки об изменении состояния"""
        # КРИТИЧНО: Используем Qt сигналы для безопасного межпоточного вызова
        if self.signals:
            # Отправляем через сигнал (безопасно из любого потока)
            self.signals.state_changed.emit(state_name, new_value)
        else:
            # Fallback для прямого вызова (только если в том же потоке)
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
        Физически включает/выключает аудиопоток

        Args:
            enabled: True - включить, False - выключить
            source: Источник команды (gui, voice, system, hardware_conflict, audio_error)
        """
        if self.microphone_enabled == enabled:
            logger.debug(f"CTX: Микрофон уже в состоянии {enabled}, пропуск")
            return False

        self.microphone_enabled = enabled
        logger.info(f"CTX: Микрофон {'включен' if enabled else 'выключен'} [{source}]")

        # ФИЗИЧЕСКОЕ управление потоком через core.audio
        if self.core and hasattr(self.core, 'audio'):
            if enabled:
                # Включаем поток
                success = self.core.audio.start_stream()
                if not success:
                    logger.error("CTX: Не удалось запустить аудиопоток")
                    self.microphone_enabled = False  # Откатываем состояние
                    return False
            else:
                # Выключаем поток
                self.core.audio.stop_stream()

        # Обновляем UI статус
        if not enabled:
            self.set_ui_status("blocked", source=f"mic_disabled_{source}")
        else:
            # Возвращаемся в idle, если не было других причин для blocked
            if self.ui_status_value == "blocked":
                self.set_ui_status("idle", source=f"mic_enabled_{source}")

        # Оповещаем GUI о изменении состояния микрофона
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

    def ui_output(self, text: str, level: str = "info", priority: Optional[str] = None, message: bool = False, duration: int = None):
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