# -*- coding: utf-8 -*-
import threading
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

        # --- Thread-safe состояния ---
        self._state_lock = threading.RLock()
        self.microphone_enabled = True
        self.focus_mode_active = False

        # Сохранение предыдущего состояния для восстановления
        self._previous_ui_status = "init"

        # --- UI СТАТУС (для трея и других UI элементов) ---
        # Возможные значения: "init", "idle", "active", "blocked", "mute"
        self.ui_status_value = "init"
        self._ui_status_callbacks = []

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
        # ИСПРАВЛЕНИЕ: ui_status теперь может быть переопределен извне
        # но по умолчанию использует внутренний механизм
        self._external_ui_status = None
        self._external_ui_audio_status = None

    @property
    def ui_status(self):
        """Геттер для ui_status - возвращает внешний обработчик если есть"""
        if self._external_ui_status:
            return self._external_ui_status
        return lambda status: self.set_ui_status(status, source="legacy_ui_status")

    @ui_status.setter
    def ui_status(self, callback):
        """Сеттер для ui_status - сохраняет внешний обработчик"""
        self._external_ui_status = callback

    @property
    def ui_audio_status(self):
        """Геттер для ui_audio_status"""
        return self._external_ui_audio_status if self._external_ui_audio_status else lambda is_ok, msg: None

    @ui_audio_status.setter
    def ui_audio_status(self, callback):
        """Сеттер для ui_audio_status"""
        self._external_ui_audio_status = callback

    # ========== UI СТАТУС (ЦЕНТРАЛИЗОВАННЫЙ) ==========

    def register_ui_status_callback(self, callback):
        """Регистрирует коллбек для получения обновлений UI статуса."""
        if callback not in self._ui_status_callbacks:
            self._ui_status_callbacks.append(callback)
            logger.debug("CTX: Зарегистрирован UI status callback")
            # Сразу отправляем текущий статус
            callback(self.ui_status_value)

    def set_ui_status(self, new_status: str, source: str = "unknown"):
        """
        Централизованная установка UI статуса.

        ИСПРАВЛЕНО: Максимальная защита от передачи некорректных типов в Qt Signal
        """
        # ДИАГНОСТИКА: Логируем все входящие вызовы
        logger.debug(
            f"CTX: set_ui_status вызван с: new_status={repr(new_status)} (type={type(new_status).__name__}), source={source}")

        # ЗАЩИТА 1: Проверка на None
        if new_status is None:
            logger.error(f"CTX: ❌ new_status is None! source=[{source}]")
            return False

        # ЗАЩИТА 2: Проверка типа
        if not isinstance(new_status, str):
            logger.error(
                f"CTX: ❌ new_status не является str! type={type(new_status).__name__}, value={repr(new_status)}, source=[{source}]")
            try:
                new_status = str(new_status)
                logger.warning(f"CTX: Принудительная конвертация в str: {repr(new_status)}")
            except Exception as e:
                logger.error(f"CTX: Не удалось конвертировать в str: {e}")
                return False

        # ЗАЩИТА 3: Проверка валидности значения
        valid_statuses = ["init", "idle", "active", "blocked", "mute"]
        if new_status not in valid_statuses:
            logger.warning(f"CTX: ⚠️ Некорректный UI статус '{new_status}' (не в {valid_statuses}), source=[{source}]")
            return False

        # Проверка дубликата
        if self.ui_status_value == new_status:
            logger.debug(f"CTX: UI статус уже '{new_status}', пропуск")
            return False

        old_status = self.ui_status_value

        # Сохраняем предыдущий статус для возможности восстановления
        if old_status not in ["blocked", "mute"]:
            self._previous_ui_status = old_status

        self.ui_status_value = new_status
        logger.info(f"CTX: ✓ UI статус изменен: {old_status} → {new_status} [{source}]")

        # ЗАЩИТА 4: Явная конвертация перед emit (на всякий случай)
        safe_status = str(new_status)

        # ЗАЩИТА 5: Финальная проверка перед emit
        if not isinstance(safe_status, str):
            logger.error(
                f"CTX: ❌ КРИТИЧЕСКАЯ ОШИБКА: safe_status не str после конвертации! type={type(safe_status).__name__}")
            return False

        # Используем сигналы вместо прямых вызовов
        if self.signals:
            try:
                logger.debug(f"CTX: Отправка сигнала ui_status_changed.emit('{safe_status}')")
                self.signals.ui_status_changed.emit(safe_status)
                logger.debug(f"CTX: ✓ Сигнал ui_status_changed успешно отправлен")
            except (RuntimeError, TypeError) as e:
                logger.error(f"CTX: ❌ Ошибка при emit сигнала: {type(e).__name__}: {e}")
        else:
            # Fallback на callback'и
            logger.debug("CTX: signals не установлен, используем callbacks")
            for callback in self._ui_status_callbacks[:]:
                try:
                    callback(safe_status)
                except RuntimeError:
                    try:
                        self._ui_status_callbacks.remove(callback)
                    except ValueError:
                        pass
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
        """
        Оповещает все зарегистрированные коллбеки об изменении состояния

        ИСПРАВЛЕНО: Максимальная защита от передачи некорректных типов
        """
        # ДИАГНОСТИКА
        logger.debug(
            f"CTX: _notify_state_change вызван с: state_name={repr(state_name)} (type={type(state_name).__name__}), new_value={repr(new_value)} (type={type(new_value).__name__})")

        # ЗАЩИТА 1: Проверка state_name
        if state_name is None:
            logger.error(f"CTX: ❌ state_name is None!")
            return

        if not isinstance(state_name, str):
            logger.error(
                f"CTX: ❌ state_name не является str! type={type(state_name).__name__}, value={repr(state_name)}")
            try:
                state_name = str(state_name)
                logger.warning(f"CTX: Принудительная конвертация state_name в str: {repr(state_name)}")
            except Exception as e:
                logger.error(f"CTX: Не удалось конвертировать state_name: {e}")
                return

        # ЗАЩИТА 2: Проверка new_value
        if new_value is None:
            logger.error(f"CTX: ❌ new_value is None! state_name={state_name}")
            return

        if not isinstance(new_value, bool):
            logger.error(
                f"CTX: ❌ new_value не является bool! type={type(new_value).__name__}, value={repr(new_value)}, state_name={state_name}")
            try:
                new_value = bool(new_value)
                logger.warning(f"CTX: Принудительная конвертация new_value в bool: {new_value}")
            except Exception as e:
                logger.error(f"CTX: Не удалось конвертировать new_value: {e}")
                return

        # ЗАЩИТА 3: Явная конвертация
        safe_name = str(state_name)
        safe_value = bool(new_value)

        # ЗАЩИТА 4: Финальная проверка
        if not isinstance(safe_name, str) or not isinstance(safe_value, bool):
            logger.error(
                f"CTX: ❌ КРИТИЧЕСКАЯ ОШИБКА после конвертации! safe_name type={type(safe_name).__name__}, safe_value type={type(safe_value).__name__}")
            return

        if self.signals:
            try:
                logger.debug(f"CTX: Отправка сигнала state_changed.emit('{safe_name}', {safe_value})")
                self.signals.state_changed.emit(safe_name, safe_value)
                logger.debug(f"CTX: ✓ Сигнал state_changed успешно отправлен")
            except (RuntimeError, TypeError) as e:
                logger.error(f"CTX: ❌ Ошибка при emit сигнала state_changed: {type(e).__name__}: {e}")
        else:
            logger.debug("CTX: signals не установлен, используем callbacks")
            for callback in self._state_change_callbacks[:]:
                try:
                    callback(safe_name, safe_value)
                except RuntimeError:
                    try:
                        self._state_change_callbacks.remove(callback)
                    except ValueError:
                        pass
                except Exception as e:
                    logger.error(f"CTX: Ошибка в callback для {state_name}: {e}")

    def get_microphone_should_listen(self):
        """Проверяет, должен ли микрофон обрабатывать звук (Thread-safe)"""
        with self._state_lock:
            return self.microphone_enabled

    def set_microphone_state(self, enabled: bool, source: str = "unknown"):
        """Централизованное управление микрофоном (Thread-safe)"""
        logger.debug(
            f"CTX: set_microphone_state вызван с: enabled={repr(enabled)} (type={type(enabled).__name__}), source={source}")

        # ВАЛИДАЦИЯ: enabled должен быть bool
        if not isinstance(enabled, bool):
            logger.warning(f"CTX: set_microphone_state получил не bool: {type(enabled).__name__}, конвертирую")
            enabled = bool(enabled)

        with self._state_lock:
            if self.microphone_enabled == enabled:
                logger.debug(f"CTX: Микрофон уже в состоянии {enabled}, пропуск")
                return False

            self.microphone_enabled = enabled
            logger.info(f"CTX: Микрофон {'включен' if enabled else 'выключен'} [{source}]")

            # ФИЗИЧЕСКОЕ управление потоком через core.audio
            if self.core and hasattr(self.core, 'audio'):
                if enabled:
                    self.core.audio.start_stream()
                else:
                    self.core.audio.stop_stream()

            # Умное восстановление UI статуса
            if not enabled:
                self.set_ui_status("blocked", source=f"mic_disabled_{source}")
            else:
                if self.ui_status_value == "blocked":
                    restore_status = self._previous_ui_status if self._previous_ui_status != "blocked" else "idle"
                    self.set_ui_status(restore_status, source=f"mic_enabled_{source}")

            # Оповещаем GUI о изменении состояния микрофона
            self._notify_state_change("microphone", enabled)

            return True

    def set_focus_mode(self, active: bool, source: str = "unknown"):
        """Централизованное управление режимом концентрации (Thread-safe)"""
        logger.debug(
            f"CTX: set_focus_mode вызван с: active={repr(active)} (type={type(active).__name__}), source={source}")

        # ВАЛИДАЦИЯ: active должен быть bool
        if not isinstance(active, bool):
            logger.warning(f"CTX: set_focus_mode получил не bool: {type(active).__name__}, конвертирую")
            active = bool(active)

        with self._state_lock:
            if self.focus_mode_active == active:
                logger.debug(f"CTX: Режим концентрации уже в состоянии {active}, пропуск")
                return False

            self.focus_mode_active = active
            logger.info(f"CTX: Режим концентрации {'включен' if active else 'выключен'} [{source}]")

            # Оповещаем GUI
            self._notify_state_change("focus_mode", active)

            return True

    # ========== СУЩЕСТВУЮЩИЕ МЕТОДЫ ==========

    def ui_output(self, text: str, level: str = "info", priority: Optional[str] = None,
                  message: bool = False, duration: int = None, play_sound: bool = True):
        """
        Централизованный вывод в UI уведомления.

        ИСПРАВЛЕНИЕ: Теперь корректно работает с ui_manager
        """
        if self.ui_manager:
            # Напрямую вызываем ui_manager.add_item с правильными параметрами
            self.ui_manager.add_item(
                text=text,
                msg_type=level,
                priority=priority,
                play_sound=play_sound
            )
        else:
            logger.warning(f"CTX_FALLBACK: [{level.upper()}] {text}")

    def set_input_source(self, source: str):
        """Фиксирует, откуда пришла команда."""
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

    def broadcast(self, text, ui=True, tg=True, window=None, priority=None, message=False,
                  duration=None, play_sound=True, **kwargs):
        """Вещание на все активные фронты."""
        text = str(text) if text is not None else ""
        level = kwargs.get("level", "info")

        if ui:
            self.ui_output(text, level, priority, message=message, duration=duration, play_sound=play_sound)

        if window:
            self.open_ui(window, text, **kwargs)

        if tg:
            prefix = "🤖 " if message else "📢 "
            safe_text = text
            if "_" in text or "*" in text:
                if "Закрыто программ" in text:
                    parts = text.split("):")
                    if len(parts) > 1:
                        safe_text = f"{parts[0]}):\n`{parts[1].strip()}`"
                    else:
                        safe_text = f"`{text}`"
            db.add_tg_message(f"{prefix}{safe_text}")

        log_msg = f"[MSG] {text}" if message else f"[BROADCAST] {text}"
        logger.info(log_msg)

    def reply(self, text, level="info", priority=None, to_all=False, message=False,
              duration=None, play_sound=True):
        """Умный ответ: туда, откуда пришел запрос."""
        if self.last_input_source in ["mic", "gui"] or to_all:
            self.ui_output(text, level, priority, message=message, duration=duration, play_sound=play_sound)

        if self.last_input_source == "tg" or to_all:
            prefix = "🤖 " if message else ""
            db.add_tg_message(f"{prefix}{text}")