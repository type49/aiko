import atexit
import json
import sys
import threading
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QObject, Qt, QDateTime
import asyncio

from services.telegram.bot import AikoTelegramService
from ui.reminder import ReminderManager, ReminderCreateDialog, AlarmWindow
from ui.signals import AikoSignals
from ui.notifications import PopupNotification
from ui.settings import SettingsWindow

from aiko_core import AikoCore, AikoContext
from ui.tray import AikoTray
from utils.logger import logger
from utils.lifecycle import lifecycle


class AikoApp(QObject):
    def __init__(self, ctx, core):
        super().__init__()
        self.ctx = ctx
        self.core = core
        self.signals = AikoSignals()

        # Состояния окон
        self.active_alarms = []
        self.manager_win = None
        self.settings_win = None

        # Инициализация визуальных компонентов
        self.popup = PopupNotification()
        self.tray = AikoTray(self)

        self._bind_context()
        self._connect_signals()
        logger.info("GUI: Интерфейс успешно инициализирован.")

    def _bind_context(self):
        self.ctx.ui_log = self.signals.display_message.emit
        self.ctx.ui_open_reminder = self.signals.open_reminder.emit
        self.ctx.ui_status = self.tray.update_icon # Напрямую в трей
        self.ctx.ui_audio_status = self.signals.audio_status_changed.emit
        self.ctx.ui_show_alarm = self.signals.show_alarm.emit

    def _connect_signals(self):
        self.signals.display_message.connect(self.receive_message)
        self.signals.open_reminder.connect(self._handle_reminder_ui)
        self.signals.audio_status_changed.connect(self._handle_audio_status_change)
        self.signals.show_alarm.connect(self._handle_alarm_display)

    # --- Методы управления окнами ---
    def _handle_reminder_ui(self, text):
        dialog = ReminderCreateDialog(text)
        if dialog.exec():
            self.receive_message("Напоминалка сохранена", "success")

    def _handle_alarm_display(self, data):
        alarm = AlarmWindow(data, on_close_callback=lambda obj: self.active_alarms.remove(obj))
        geo = QApplication.primaryScreen().geometry()
        alarm.move((geo.width() - alarm.width()) // 2, (geo.height() - alarm.height()) // 2)
        self.active_alarms.append(alarm)
        alarm.show()

    def show_reminder_manager(self):
        if not self.manager_win:
            self.manager_win = ReminderManager()
        self.manager_win.refresh_list()
        self.manager_win.show()

    def show_settings(self):
        self.settings_win = SettingsWindow()
        self.settings_win.settings_saved.connect(self._on_settings_updated)
        self.settings_win.show()

    def _on_settings_updated(self):
        self.receive_message("Настройки обновлены", "info")
        if hasattr(self.core, 'restart_audio_capture'):
            self.core.restart_audio_capture()

    def _handle_audio_status_change(self, is_ok, message):
        if is_ok:
            self.core.set_state("idle")
            self.receive_message("Микрофон подключен", "success")
        else:
            self.core.set_state("blocked")
            self.receive_message(f"Ошибка аудио: {message}", "error")


    def receive_message(self, text, msg_type):
        self.popup.add_item(text, msg_type)

    def quit_app(self):
        self.ctx.is_running = False
        QApplication.quit()