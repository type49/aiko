from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt
from utils.logger import logger


class AikoTray(QSystemTrayIcon):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.current_status = "init"

        # КРИТИЧЕСКИ ВАЖНО: Устанавливаем иконку ПЕРЕД show()
        self._create_icon("init")

        # Инициализируем меню
        self._init_menu()

        # Подключаем сигнал клика ПЕРЕД show()
        self.activated.connect(self.on_tray_activated)

        # Показываем трей ТОЛЬКО ПОСЛЕ установки иконки и подключения сигнала
        self.show()

        print(f"Tray shown: {self.isVisible()}")
        print(f"Icon is null: {self.icon().isNull()}")

        # Подписываемся на обновления UI статуса через ctx ПОСЛЕ show()
        self.app.ctx.register_ui_status_callback(self.update_icon)

        logger.info("Tray: Инициализирован.")

    def _create_icon(self, status: str):
        """Создает и устанавливает иконку для заданного статуса"""
        colors = {
            "init": "#555555",
            "idle": "#00FFCC",
            "active": "#FF0000",
            "blocked": "#000000",
            "mute": "#FFA500",
        }

        color = colors.get(status, "#555555")

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(12, 12, 40, 40)
        painter.end()

        self.setIcon(QIcon(pixmap))

        tooltips = {
            "init": "Айко - Инициализация...",
            "idle": "Айко - Готова к работе",
            "active": "Айко - Слушаю...",
            "blocked": "Айко - Микрофон отключен",
            "mute": "Айко - Режим тишины",
        }
        self.setToolTip(tooltips.get(status, "Айко"))

    def _init_menu(self):
        menu = QMenu()

        menu.addAction("Главная", lambda: self.app.ctx.open_ui("aiko_window"))
        menu.addAction("Задачи", lambda: self.app.ctx.open_ui("reminder"))
        menu.addAction("Тест Статистики", lambda: self.app.ctx.open_ui(
            "stats_window",
            "v1.0.4",
            "Active",
            cpu="12%",
            ram="4.2GB",
            temp=45,
            status="Normal"
        ))

        menu.addSeparator()

        menu.addAction("[Test] Init", lambda: self.app.ctx.set_ui_status("init", "tray_test"))
        menu.addAction("[Test] Idle", lambda: self.app.ctx.set_ui_status("idle", "tray_test"))
        menu.addAction("[Test] Active", lambda: self.app.ctx.set_ui_status("active", "tray_test"))
        menu.addAction("[Test] Blocked", lambda: self.app.ctx.set_ui_status("blocked", "tray_test"))
        menu.addAction("[Test] Mute", lambda: self.app.ctx.set_ui_status("mute", "tray_test"))

        menu.addSeparator()
        menu.addAction("Выход", self.app.quit_app)

        self.setContextMenu(menu)

    def update_icon(self, status: str):
        """
        Обновляет иконку трея в зависимости от статуса.
        Вызывается автоматически через callback system из ctx.
        """
        if self.current_status == status:
            return

        self.current_status = status
        self._create_icon(status)
        logger.debug(f"Tray: Иконка обновлена на '{status}'")

    def on_tray_activated(self, reason):
        """Обработчик кликов по трею"""
        print(f"=== TRAY CLICKED ===")
        print(f"Reason: {reason}")

        # Открываем окно на любой клик (одинарный или двойной)
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            print("Opening aiko_window...")
            self.app.ctx.open_ui("aiko_window")
        else:
            print(f"Ignored reason: {reason}")