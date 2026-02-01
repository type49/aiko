import sys
import threading
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QObject, Qt

# ИМПОРТЫ ИЗ НАШЕЙ ПАПКИ UI
from ui.signals import AikoSignals
from ui.notifications import PopupNotification
from ui.dialogs import ReminderDialog

from aiko_core import AikoCore, AikoContext

class WindowManager:
    @staticmethod
    def get_reminder_input(initial_text=""):
        dialog = ReminderDialog(initial_text)
        if dialog.exec():
            return dialog.get_data()
        return None, None

class AikoApp(QObject):
    def __init__(self):
        super().__init__()
        self.ctx = AikoContext()
        self.signals = AikoSignals() # Создаем сигналы ТУТ

        # Проброс сигналов в контекст
        self.ctx.ui_log = self.signals.display_message.emit
        self.ctx.ui_open_reminder = self.signals.open_reminder.emit
        self.ctx.ui_status = self.update_tray_icon

        # Подключаем обработчики сигналов в GUI
        self.signals.display_message.connect(self.receive_message)
        self.signals.open_reminder.connect(self._handle_reminder_ui)

        self.core = AikoCore(self.ctx)
        self.popup = PopupNotification()
        self.tray = QSystemTrayIcon()
        self._init_tray()

        threading.Thread(target=self.core.run, daemon=True).start()

    def _init_tray(self):
        self.update_tray_icon("idle")
        menu = QMenu()
        menu.addAction("Выход", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def update_tray_icon(self, status):
        colors = {"idle": "#00FFCC", "active": "#FF0000", "blocked": "#000000", "off": "#555555"}
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(colors.get(status, "#00FFCC")))
        p.drawEllipse(12, 12, 40, 40)
        p.end()
        self.tray.setIcon(QIcon(pixmap))

    def _handle_reminder_ui(self, text):
        content, dt = WindowManager.get_reminder_input(text)
        if content and dt:
            if self.core.add_scheduler_task("reminder", content, dt):
                self.receive_message(f"Задача зафиксирована на {dt}", "success")

    def receive_message(self, text, msg_type):
        self.popup.add_item(text, msg_type)

    def quit_app(self):
        self.ctx.is_running = False
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    aiko_instance = AikoApp()
    sys.exit(app.exec())