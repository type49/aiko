from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt

class AikoTray(QSystemTrayIcon):
    def __init__(self, app_instance):
        super().__init__()
        self.is_active = None  # Состояние неопределенности
        self.app = app_instance
        self._init_menu()
        self.update_icon("init")
        self.show()

    def _init_menu(self):
        menu = QMenu()
        menu.addAction("Менеджер напоминалок", self.app.show_reminder_manager)
        menu.addAction("Настройки", self.app.show_settings)
        menu.addSeparator()
        menu.addAction("Выход", self.app.quit_app)
        self.setContextMenu(menu)

    def update_icon(self, status):
        colors = {
            "idle": "#00FFCC",
            "active": "#FF0000",
            "blocked": "#000000",
            "init": "#555555",
        }
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(colors.get(status, "#555555")))
        p.drawEllipse(12, 12, 40, 40)
        p.end()
        self.setIcon(QIcon(pixmap))