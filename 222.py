import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtCore import Qt, QTimer, QDateTime, QRectF, QPoint
from PySide6.QtGui import QPainter, QColor, QPixmap, QPainterPath

try:
    myappid = 'strategy.advisor.adaptive.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass


class BlurWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ (БАЗОВЫЕ) ---
        # Расчет scale_factor относительно Full HD (1920)
        screen_geometry = QApplication.primaryScreen().geometry()
        self.scale_factor = screen_geometry.width() / 1920.0

        # Размеры теперь умножаются на коэффициент
        self.content_width = int(1000 * self.scale_factor)
        self.content_height = int(600 * self.scale_factor)
        self.margin = int(15 * self.scale_factor)
        self.character_overflow = int(200 * self.scale_factor)

        self.window_width = self.content_width
        self.window_height = self.content_height + self.character_overflow

        self.setFixedSize(self.window_width, self.window_height)

        # Загрузка персонажа
        self.character_pixmap = None
        char_path = os.path.join(os.path.dirname(__file__), 'ai.png')
        if os.path.exists(char_path):
            self.character_pixmap = QPixmap(char_path)

        self.init_ui()
        self.position_to_bottom_right()

    def position_to_bottom_right(self):
        """Привязка к правому нижнему углу рабочего стола"""
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = screen_geo.x() + screen_geo.width() - self.width()
        y = screen_geo.y() + screen_geo.height() - self.height()
        self.move(x, y)

    def init_ui(self):
        # Координаты для левого верхнего угла плашки
        # Учитываем character_overflow, чтобы часы были внутри черной области
        base_x = self.margin + int(40 * self.scale_factor)
        base_y = self.character_overflow + self.margin + int(40 * self.scale_factor)

        # Часы
        self.time_label = QLabel("00:00", self)
        font_size_time = int(52 * self.scale_factor)
        self.time_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {font_size_time}px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        self.time_label.move(base_x, base_y)

        # Дата
        self.date_label = QLabel("", self)
        font_size_date = int(15 * self.scale_factor)
        self.date_label.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 180);
                font-size: {font_size_date}px;
                background: transparent;
            }}
        """)
        # Смещение даты чуть ниже часов
        self.date_label.move(base_x, base_y + int(65 * self.scale_factor))

        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)
        self.update_time()

    def update_time(self):
        current = QDateTime.currentDateTime()
        self.time_label.setText(current.toString("hh:mm"))
        self.date_label.setText(current.toString("dddd MM/dd"))
        self.time_label.adjustSize()  # Чтобы текст не обрезался при смене шрифта
        self.date_label.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Геометрия фона
        content_x = self.margin
        content_y = self.character_overflow + self.margin
        content_w = self.content_width - 2 * self.margin
        content_h = self.content_height - 2 * self.margin

        content_rect = QRectF(content_x, content_y, content_w, content_h)
        radius = 30 * self.scale_factor

        clip_path = QPainterPath()
        clip_path.addRoundedRect(content_rect, radius, radius)

        # 1. Тень (адаптивная глубина)
        painter.save()
        for i in range(12):
            opacity = 50 - i * 4
            painter.setBrush(QColor(0, 0, 0, opacity))
            painter.setPen(Qt.NoPen)
            expand = i * 0.5 * self.scale_factor
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                content_rect.adjusted(-expand, -expand, expand, expand),
                radius + expand, radius + expand
            )
            painter.drawPath(shadow_path)
        painter.restore()

        # 2. Фон
        painter.save()
        painter.setClipPath(clip_path)
        painter.fillRect(content_rect, QColor(0, 0, 0, 160))
        painter.restore()

        # 3. Персонаж (строго вправо)
        if self.character_pixmap and not self.character_pixmap.isNull():
            # Масштабируем картинку под текущую высоту окна
            scaled_pixmap = self.character_pixmap.scaledToHeight(
                self.window_height,
                Qt.SmoothTransformation
            )

            char_x = self.window_width - scaled_pixmap.width()
            char_y = 0

            painter.drawPixmap(char_x, char_y, scaled_pixmap)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    widget = BlurWidget()
    widget.show()

    sys.exit(app.exec())