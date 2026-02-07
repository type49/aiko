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

        menu.addAction("Тест Статистики", lambda: self.app.ctx.open_ui(
            "stats_window",  # Имя файла
            "v1.0.4",  # arg[0]
            "Active",  # arg[1]
            cpu="12%",  # kwarg: cpu
            ram="4.2GB",  # kwarg: ram
            temp=45,  # kwarg: temp
            status="Normal"  # kwarg: status
        ))
        menu.addAction("Настройки", lambda: self.app.ctx.open_ui("settings_window"))
        menu.addAction("Задачи", lambda: self.app.ctx.open_ui("reminder"))

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