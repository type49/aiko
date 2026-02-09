from dataclasses import dataclass
from typing import Optional
import sys
import math

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QObject, Signal, QPoint, Property, \
    QSequentialAnimationGroup, QParallelAnimationGroup
from PySide6.QtGui import QPainter, QColor, QFont, QPainterPath, QLinearGradient, QRadialGradient
from PySide6.QtCore import QRectF, QPointF


# ============ ЦВЕТОВАЯ СХЕМА ============
class NotificationColors:
    """Все цвета нотификации в одном месте"""
    # Основные цвета градиента (голубые оттенки)
    GRADIENT_COLOR_1 = QColor(30, 120, 180)  # Светло-голубой
    GRADIENT_COLOR_2 = QColor(20, 90, 150)  # Средний голубой
    GRADIENT_COLOR_3 = QColor(15, 70, 130)  # Темно-голубой

    # Цвета для анимации (сдвиг яркости)
    ANIMATION_BRIGHTNESS_SHIFT = 0  # Насколько меняется яркость при анимации

    # Блик
    HIGHLIGHT_COLOR_START = QColor(255, 255, 255, 40)
    HIGHLIGHT_COLOR_END = QColor(255, 255, 255, 0)

    # Текст
    TEXT_COLOR = "white"

    # Тень
    SHADOW_COLOR = QColor(0, 0, 0, 60)
    SHADOW_BLUR_RADIUS = 20
    SHADOW_OFFSET_X = 0
    SHADOW_OFFSET_Y = 4


@dataclass
class NotificationConfig:
    """Настройки нотификации"""
    max_width: int = 700
    min_width: int = 300
    padding: int = 12
    font_size: int = 12
    display_duration: int = 3000
    animation_duration: int = 600


class ModernNotification(QWidget):
    """Современный нотификатор"""

    def __init__(self, text: str, config: Optional[NotificationConfig] = None):
        super().__init__()
        self.text = text
        self.config = config or NotificationConfig()
        self._opacity = 0.0
        self._y_offset = 0.0
        self._gradient_shift = 0.0

        self._setup_window()
        self._create_ui()
        self._setup_animations()

    def _setup_window(self):
        """Настройка окна"""
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def _create_ui(self):
        """UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.config.padding, self.config.padding, self.config.padding, self.config.padding)

        # Текст
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)

        font = QFont("Segoe UI", self.config.font_size)
        self.label.setFont(font)
        self.label.setStyleSheet(f"QLabel {{ background: transparent; color: {NotificationColors.TEXT_COLOR}; }}")

        layout.addWidget(self.label)

        # Правильный расчет размера с учетом переноса
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(font)

        # Максимальная ширина текста (без padding)
        max_text_width = self.config.max_width - self.config.padding * 2

        # Рассчитываем реальную высоту с переносами
        text_rect = fm.boundingRect(
            0, 0,
            max_text_width, 10000,
            Qt.TextWordWrap | Qt.AlignCenter,
            self.text
        )

        # Ширина: или по тексту, или максимум
        text_width = min(text_rect.width(), max_text_width)
        width = max(text_width + self.config.padding * 2, self.config.min_width)

        # Высота: точно по тексту + padding
        height = text_rect.height() + self.config.padding * 2

        self.setFixedSize(int(width), int(height))

        # Тень для глубины
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(NotificationColors.SHADOW_BLUR_RADIUS)
        shadow.setColor(NotificationColors.SHADOW_COLOR)
        shadow.setOffset(NotificationColors.SHADOW_OFFSET_X, NotificationColors.SHADOW_OFFSET_Y)
        self.setGraphicsEffect(shadow)

    def _get_opacity(self):
        return self._opacity

    def _set_opacity(self, value):
        self._opacity = value
        self.update()

    opacity = Property(float, _get_opacity, _set_opacity)

    def _get_y_offset(self):
        return self._y_offset

    def _set_y_offset(self, value):
        self._y_offset = value
        self._update_position()

    y_offset = Property(float, _get_y_offset, _set_y_offset)

    def _get_gradient_shift(self):
        return self._gradient_shift

    def _set_gradient_shift(self, value):
        self._gradient_shift = value
        self.update()

    gradient_shift = Property(float, _get_gradient_shift, _set_gradient_shift)

    def _update_position(self):
        """Обновляем позицию на основе offset"""
        if hasattr(self, '_target_x') and hasattr(self, '_base_y'):
            self.move(self._target_x, int(self._base_y + self._y_offset))

    def _setup_animations(self):
        """Настройка анимаций"""
        # Появление
        self.show_group = QParallelAnimationGroup()

        # Fade in
        self.fade_in = QPropertyAnimation(self, b"opacity")
        self.fade_in.setDuration(self.config.animation_duration)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

        # Slide up
        self.slide_in = QPropertyAnimation(self, b"y_offset")
        self.slide_in.setDuration(self.config.animation_duration)
        self.slide_in.setStartValue(100.0)
        self.slide_in.setEndValue(0.0)
        self.slide_in.setEasingCurve(QEasingCurve.OutBack)

        self.show_group.addAnimation(self.fade_in)
        self.show_group.addAnimation(self.slide_in)

        # Скрытие
        self.hide_group = QParallelAnimationGroup()

        # Fade out
        self.fade_out = QPropertyAnimation(self, b"opacity")
        self.fade_out.setDuration(self.config.animation_duration)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InCubic)

        # Slide down
        self.slide_out = QPropertyAnimation(self, b"y_offset")
        self.slide_out.setDuration(self.config.animation_duration)
        self.slide_out.setStartValue(0.0)
        self.slide_out.setEndValue(100.0)
        self.slide_out.setEasingCurve(QEasingCurve.InBack)

        self.hide_group.addAnimation(self.fade_out)
        self.hide_group.addAnimation(self.slide_out)

        # Пульсация градиента
        self.gradient_anim = QPropertyAnimation(self, b"gradient_shift")
        self.gradient_anim.setDuration(3000)
        self.gradient_anim.setStartValue(0.0)
        self.gradient_anim.setKeyValueAt(0.5, 1.0)
        self.gradient_anim.setEndValue(0.0)
        self.gradient_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.gradient_anim.setLoopCount(-1)

    def paintEvent(self, event):
        """Рисуем красивое уведомление с органичным градиентом и плавным затуханием"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Применяем opacity
        painter.setOpacity(self._opacity)

        rect = self.rect()

        # Скругленный прямоугольник как основа
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 26, 26)

        # Заливаем базовым цветом
        painter.fillPath(path, NotificationColors.GRADIENT_COLOR_2)

        # Создаем несколько радиальных градиентов в случайных позициях
        # для органичного эффекта
        painter.setClipPath(path)  # Обрезаем по скругленному прямоугольнику

        shift = int(self._gradient_shift * NotificationColors.ANIMATION_BRIGHTNESS_SHIFT)

        # Градиент 1 - левый верхний угол
        gradient1 = QRadialGradient(
            QPointF(rect.width() * 0.2, rect.height() * 0.3),
            rect.width() * 0.6
        )
        color1 = QColor(
            NotificationColors.GRADIENT_COLOR_1.red() + shift,
            NotificationColors.GRADIENT_COLOR_1.green() + shift,
            NotificationColors.GRADIENT_COLOR_1.blue() + shift,
            NotificationColors.GRADIENT_COLOR_1.alpha()
        )
        gradient1.setColorAt(0, color1)
        gradient1.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillPath(path, gradient1)

        # Градиент 2 - правый нижний
        gradient2 = QRadialGradient(
            QPointF(rect.width() * 0.8, rect.height() * 0.7),
            rect.width() * 0.5
        )
        color2 = QColor(
            NotificationColors.GRADIENT_COLOR_3.red() + shift,
            NotificationColors.GRADIENT_COLOR_3.green() + shift,
            NotificationColors.GRADIENT_COLOR_3.blue() + shift,
            NotificationColors.GRADIENT_COLOR_3.alpha()
        )
        gradient2.setColorAt(0, color2)
        gradient2.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillPath(path, gradient2)

        # Градиент 3 - центр (пульсирующий)
        gradient3 = QRadialGradient(
            QPointF(rect.width() * 0.5, rect.height() * 0.5),
            rect.width() * 0.4 * (1 + self._gradient_shift * 0.3)  # Изменяется размер
        )
        color3 = QColor(
            NotificationColors.GRADIENT_COLOR_1.red() + shift * 2,
            NotificationColors.GRADIENT_COLOR_1.green() + shift * 2,
            NotificationColors.GRADIENT_COLOR_1.blue() + shift * 2,
            150
        )
        gradient3.setColorAt(0, color3)
        gradient3.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillPath(path, gradient3)

        # Легкий блик сверху
        painter.setClipping(False)
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(QRectF(rect), 26, 26)

        highlight = QLinearGradient(0, 0, 0, rect.height() * 0.5)
        highlight.setColorAt(0, NotificationColors.HIGHLIGHT_COLOR_START)
        highlight.setColorAt(1, NotificationColors.HIGHLIGHT_COLOR_END)
        painter.fillPath(highlight_path, highlight)

        # НОВОЕ: Плавное затухание по краям (fade mask)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)

        fade_margin = 30  # Ширина зоны затухания по краям

        # Затухание слева
        left_fade = QLinearGradient(0, 0, fade_margin, 0)
        left_fade.setColorAt(0, QColor(0, 0, 0, 0))
        left_fade.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(0, 0, fade_margin, rect.height(), left_fade)

        # Затухание справа
        right_fade = QLinearGradient(rect.width() - fade_margin, 0, rect.width(), 0)
        right_fade.setColorAt(0, QColor(0, 0, 0, 255))
        right_fade.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(rect.width() - fade_margin, 0, fade_margin, rect.height(), right_fade)

        # Затухание сверху
        top_fade = QLinearGradient(0, 0, 0, fade_margin)
        top_fade.setColorAt(0, QColor(0, 0, 0, 0))
        top_fade.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(0, 0, rect.width(), fade_margin, top_fade)

        # Затухание снизу
        bottom_fade = QLinearGradient(0, rect.height() - fade_margin, 0, rect.height())
        bottom_fade.setColorAt(0, QColor(0, 0, 0, 255))
        bottom_fade.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(0, rect.height() - fade_margin, rect.width(), fade_margin, bottom_fade)
    def show_notification(self):
        """Показать уведомление"""
        screen = QApplication.primaryScreen().availableGeometry()

        # Позиция по центру экрана
        self._target_x = (screen.width() - self.width()) // 2
        self._base_y = screen.height() - self.height() - 12

        self.move(self._target_x, int(self._base_y + 100))
        self.show()

        # Запускаем анимацию появления
        self.show_group.start()

        # Запускаем пульсацию градиента
        self.gradient_anim.start()

        # Автоматически скрываем
        QTimer.singleShot(self.config.display_duration, self.hide_notification)

    def hide_notification(self):
        """Скрыть уведомление"""
        self.gradient_anim.stop()
        self.hide_group.finished.connect(self._cleanup)
        self.hide_group.start()

    def _cleanup(self):
        self.close()
        self.deleteLater()


class AikoMessages(QObject):
    """Менеджер уведомлений"""
    _request = Signal(str, object)

    def __init__(self, config: Optional[NotificationConfig] = None):
        super().__init__()
        self.config = config or NotificationConfig()
        self.current = None
        self.queue = []
        self._request.connect(self._show)

    def show(self, text: str, duration: Optional[int] = None):
        """Показать уведомление"""
        self._request.emit(text, duration)

    def _show(self, text: str, duration: Optional[int]):
        if self.current is not None:
            self.queue.append((text, duration))
            return

        config = NotificationConfig(
            **{**self.config.__dict__,
               **({"display_duration": duration} if duration else {})}
        )

        self.current = ModernNotification(text, config)
        self.current.destroyed.connect(self._on_closed)
        self.current.show_notification()

    def _on_closed(self):
        self.current = None
        if self.queue:
            text, duration = self.queue.pop(0)
            self._show(text, duration)


def integrate_assistant_messages(aiko_gui, ctx):
    if not hasattr(aiko_gui, 'assistant_msg'):
        aiko_gui.assistant_msg = AikoMessages()

    original_ui_output = ctx.ui_output
    original_broadcast = ctx.broadcast
    original_reply = ctx.reply

    def patched_ui_output(text, level="info", priority=None, message=False, duration=None):
        if message:
            aiko_gui.assistant_msg.show(str(text), duration)
        else:
            original_ui_output(text, level, priority)

    def patched_broadcast(text, ui=True, tg=True, window=None, priority=None, message=False, **kwargs):
        if message and ui:
            duration = kwargs.get('duration')
            aiko_gui.assistant_msg.show(str(text), duration)
        if not message:
            original_broadcast(text, ui, tg, window, priority, **kwargs)
        else:
            if window:
                ctx.open_ui(window, text, **kwargs)
            if tg:
                from utils.db_manager import db
                db.add_tg_message(f"📢 {text}")

    def patched_reply(text, level="info", priority=None, to_all=False, message=False, duration=None):
        if message:
            aiko_gui.assistant_msg.show(str(text), duration)
            if ctx.last_input_source == "tg" or to_all:
                from utils.db_manager import db
                db.add_tg_message(text)
        else:
            original_reply(text, level, priority, to_all)

    ctx.ui_output = patched_ui_output
    ctx.broadcast = patched_broadcast
    ctx.reply = patched_reply


if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = AikoMessages()

    QTimer.singleShot(500, lambda: manager.show("Привет! Я Айко 👋"))
    QTimer.singleShot(4000, lambda: manager.show("Задача выполнена успешно ✓"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))
    QTimer.singleShot(8000, lambda: manager.show("Это более длинное уведомление для проверки"))

    sys.exit(app.exec())