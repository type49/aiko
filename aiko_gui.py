import importlib
import re
from typing import Dict, Optional
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QObject, Qt, Slot
from utils.logger import logger


class AikoApp(QObject):
    def __init__(self, ctx, core):
        super().__init__()
        self.ctx = ctx
        self.core = core
        self._windows: Dict[str, QWidget] = {}

        # 1. Загружаем сигналы
        from ui.signals import AikoSignals
        self.signals = AikoSignals()
        self.ctx.signals = self.signals


        # 2. Компоненты (сначала создаем, потом биндим!)

        from ui.tray import AikoTray
        self.popup = ctx.ui_manager
        self.tray = AikoTray(self)

        # 3. Настройка связей
        self._bind_context()
        self._connect_signals()

        logger.info("GUI: Система управления интерфейсами стабилизирована.")

    def _bind_context(self):
        """Проброс управления в глобальный контекст ctx."""
        self.ctx.ui_output = self._handle_ui_output
        self.ctx.open_ui = self.open_ui
        self.ctx.ui_status = self.tray.update_icon
        self.ctx.ui_audio_status = self.signals.audio_status_changed.emit

    def _connect_signals(self):
        """Внутренняя шина сигналов Qt."""
        self.signals.show_window.connect(self._universal_loader)
        # self.signals.display_message.connect(self.receive_message)
        self.signals.display_message.connect(self.popup.add_item)

        self.signals.audio_status_changed.connect(self._handle_audio_status_change)

    def open_ui(self, name: str, *args, **kwargs):
        """Публичный метод вызова окон: ctx.open_ui(...)"""
        payload = {"name": name, "args": args, "kwargs": kwargs}
        self.signals.show_window.emit(payload)

    @Slot(object)
    def _universal_loader(self, cmd):
        """Роутер: загружает, регистрирует и удерживает окна в памяти."""
        try:
            # Парсинг команды
            name, args, kwargs = self._parse_command(cmd)
            if not name: return

            # Если окно живо — просто поднимаем его
            if self._try_activate_window(name):
                return

            # Создание нового инстанса
            window = self._create_window_instance(name, *args, **kwargs)
            if window:
                self._register_and_show(name, window)

        except Exception as e:
            logger.error(f"GUI Error: Критический сбой роутера: {e}", exc_info=True)

    def _parse_command(self, cmd):
        if isinstance(cmd, str): return cmd, [], {}
        if isinstance(cmd, dict):
            return cmd.get("name"), cmd.get("args", []), cmd.get("kwargs", {})
        return None, [], {}

    def _try_activate_window(self, name: str) -> bool:
        if name in self._windows:
            try:
                w = self._windows[name]
                w.show()
                w.activateWindow()
                w.raise_()
                return True
            except RuntimeError:
                del self._windows[name]
        return False

    def _create_window_instance(self, name: str, *args, **kwargs) -> Optional[QWidget]:
        try:
            # Нормализация имени файла (на случай опечаток)
            clean_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower().replace("__", "_")
            module = importlib.import_module(f"ui.{clean_name}")

            # Имя класса из имени файла (stats_window -> StatsWindow)
            class_name = "".join(word.capitalize() for word in clean_name.split("_"))
            window_class = getattr(module, class_name)

            # Создаем окно без принудительного parent (чтобы не ломать твои __init__)
            return window_class(*args, **kwargs)
        except Exception as e:
            logger.error(f"GUI: Ошибка сборки окна '{name}': {e}")
            return None

    def _register_and_show(self, name: str, window: QWidget):
        """Финальная регистрация окна в памяти."""
        self._windows[name] = window
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.destroyed.connect(lambda: self._windows.pop(name, None))

        window.show()
        self._center_window(window)
        logger.debug(f"GUI: Окно {name} зарегистрировано. Активных окон: {len(self._windows)}")

    def _center_window(self, widget: QWidget):
        screen = QApplication.primaryScreen().availableGeometry()
        widget.move((screen.width() - widget.width()) // 2, (screen.height() - widget.height()) // 2)

    def _handle_ui_output(self, text, level="info", priority=None):
        print("UI OUTPUT EMIT:", text, level, priority)
        self.signals.display_message.emit(str(text), level, priority)

    def _handle_audio_status_change(self, is_ok, message):
        self.core.set_state("idle" if is_ok else "blocked")
        self._handle_ui_output(message, "success" if is_ok else "error")
        self.tray.update_icon(is_ok)

    def quit_app(self):
        self.ctx.is_running = False
        QApplication.quit()