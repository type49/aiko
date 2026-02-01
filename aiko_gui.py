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
from utils.logger import logger  # Твой логгер


class WindowManager:
    @staticmethod
    def get_reminder_input(initial_text=""):
        logger.info(f"UI: Открытие диалога напоминания. Текст: '{initial_text}'")
        dialog = ReminderDialog(initial_text)
        if dialog.exec():
            data = dialog.get_data()
            logger.info(f"UI: Пользователь ввел данные: {data}")
            return data
        logger.info("UI: Диалог напоминания отменен пользователем.")
        return None, None


class AikoApp(QObject):
    def __init__(self):
        super().__init__()
        logger.info("GUI: Запуск интерфейса...")
        self.ctx = AikoContext()
        self.signals = AikoSignals()

        # Проброс сигналов в контекст
        self.ctx.ui_log = self.signals.display_message.emit
        self.ctx.ui_open_reminder = self.signals.open_reminder.emit
        self.ctx.ui_status = self.update_tray_icon

        # Подключаем обработчики сигналов в GUI
        self.signals.display_message.connect(self.receive_message)
        self.signals.open_reminder.connect(self._handle_reminder_ui)

        # Инициализация ядра
        self.core = AikoCore(self.ctx)

        # UI компоненты
        self.popup = PopupNotification()
        self.tray = QSystemTrayIcon()
        self._init_tray()

        logger.info("GUI: Все компоненты инициализированы. Запуск рабочего потока Ядра.")
        threading.Thread(target=self.core.run, daemon=True, name="CoreThread").start()

    def _init_tray(self):
        self.update_tray_icon("idle")
        menu = QMenu()
        menu.addAction("Выход", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.show()
        logger.debug("GUI: Системный трей готов.")

    def update_tray_icon(self, status):
        """Логгируем только важные смены состояний, чтобы не спамить в DEBUG"""
        logger.debug(f"GUI: Обновление иконки трея -> {status}")
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
        logger.info("GUI: Получен сигнал на открытие планировщика.")
        content, dt = WindowManager.get_reminder_input(text)
        if content and dt:
            if self.core.add_scheduler_task("reminder", content, dt):
                logger.info("GUI: Задача успешно передана в Ядро.")
                self.receive_message(f"Задача зафиксирована на {dt}", "success")

    def receive_message(self, text, msg_type):
        """Фиксация всех всплывающих уведомлений в логе"""
        logger.info(f"HUD: [{msg_type.upper()}] {text}")
        self.popup.add_item(text, msg_type)

    def quit_app(self):
        logger.warning("GUI: Запрошено завершение приложения.")
        self.ctx.is_running = False
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    try:
        aiko_instance = AikoApp()
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"GUI: Критическая ошибка при запуске: {e}", exc_info=True)