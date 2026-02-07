from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QLabel,
    QGraphicsOpacityEffect, QApplication, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QObject, QEasingCurve
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QGraphicsBlurEffect
from PySide6.QtMultimedia import QSoundEffect
from utils.audio_player import audio_manager


# ============================================================
# CONFIG (можно вынести в общий конфиг приложения)
# ============================================================

@dataclass
class ToastConfig:
    """Настройки тостов"""
    max_width_ratio: float = 0.45
    min_width: int = 220
    spacing: int = 6
    border_radius: int = 14
    font_size: int = 13
    fade_duration: int = 280
    slide_duration: int = 280
    auto_hide_delay: int = 30000
    reposition_duration: int = 200


# ============================================================
# STYLES (легко менять темы)
# ============================================================

class ToastStyles:
    """Централизованные стили для тостов"""

    ACCENTS = {
        "info": "#0A84FF",
        "success": "#30D158",
        "error": "#FF453A",
        "cmd": "#FFD60A",
    }

    PRIORITIES = {
        "warning": {
            "bar_color": "#FF375F",
            "bg_color": "rgba(40,20,20,0.85)",
            "sound": None
        },
        "critical": {
            "bar_color": "#FF3B30",
            "bg_color": "rgba(60,0,0,0.95)",
            "sound": None
        }
    }

    @classmethod
    def get_colors(cls, msg_type: str, priority: Optional[str] = None):
        """Получить цвета для тоста"""
        accent = cls.ACCENTS.get(msg_type, cls.ACCENTS["info"])

        if priority and priority in cls.PRIORITIES:
            prio = cls.PRIORITIES[priority]
            return {
                "accent": accent,
                "bar": prio["bar_color"],
                "bg": prio["bg_color"],
                "sound": prio.get("sound")
            }

        return {
            "accent": accent,
            "bar": accent,
            "bg": "rgba(28,28,30,0.72)",
            "sound": None
        }


# ============================================================
# TOAST ITEM
# ============================================================

class ToastItem(QWidget):
    """Визуальный компонент уведомления"""

    def __init__(self, text: str, msg_type: str, priority: Optional[str], config: ToastConfig, manager):
        super().__init__()

        self.text = text
        self.msg_type = msg_type
        self.priority = priority
        self.config = config
        self.manager = manager
        self.final_pos = QPoint(0, 0)

        self._setup_window()
        self._create_ui()
        self._setup_animations()
        self._play_sound()

    def _setup_window(self):
        """Настройка окна"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _create_ui(self):
        """Создание интерфейса"""
        colors = ToastStyles.get_colors(self.msg_type, self.priority)

        # Container
        self.container = QFrame(self)
        self.container.setObjectName("toast")
        self.container.setStyleSheet(f"""
            QFrame#toast {{
                background-color: {colors['bg']};
                border-top-left-radius: {self.config.border_radius}px;
                border-bottom-left-radius: {self.config.border_radius}px;
            }}
            QLabel {{
                color: #F2F2F7;
                font-family: -apple-system, BlinkMacSystemFont,
                             "SF Pro Text", "Segoe UI Variable", sans-serif;
                font-size: {self.config.font_size}px;
            }}
        """)

        # Blur
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(24)
        blur.setBlurHints(QGraphicsBlurEffect.PerformanceHint)
        self.container.setGraphicsEffect(blur)

        # Layout
        root = QHBoxLayout(self.container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Accent bar
        self.accent_bar = QFrame()
        self.accent_bar.setFixedWidth(3)
        self.accent_bar.setStyleSheet(f"""
            background-color: {colors['bar']};
            border-top-left-radius: {self.config.border_radius}px;
            border-bottom-left-radius: {self.config.border_radius}px;
        """)

        # Label
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(14, 10, 14, 10)
        content.addWidget(self.label)

        root.addWidget(self.accent_bar)
        root.addLayout(content)

        # Size calculation
        self._calculate_size()

        # Opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

    def _calculate_size(self):
        """Вычисление размеров"""
        screen = QApplication.primaryScreen().availableGeometry()
        max_width = int(screen.width() * self.config.max_width_ratio)

        fm = QFontMetrics(self.label.font())
        text_width = fm.horizontalAdvance(self.text)
        target_width = min(max(text_width + 40, self.config.min_width), max_width)

        self.label.setFixedWidth(target_width - 40)
        self.container.setFixedWidth(target_width)
        self.label.adjustSize()
        self.container.adjustSize()
        self.setFixedSize(self.container.sizeHint())

    def _setup_animations(self):
        """Настройка анимаций"""
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(self.config.fade_duration)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.slide_anim = QPropertyAnimation(self, b"pos")
        self.slide_anim.setDuration(self.config.slide_duration)
        self.slide_anim.setEasingCurve(QEasingCurve.OutCubic)

    def _play_sound(self):
        """Воспроизведение звука"""
        colors = ToastStyles.get_colors(self.msg_type, self.priority)
        sound_file = colors.get("sound")
        audio_manager.play.notify()

    def reposition(self, index: int, animated: bool = False):
        """Установка позиции тоста"""
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()

        x = screen.right() - w
        y = screen.bottom() - ((h + self.config.spacing) * (index + 1)) - 12
        new_pos = QPoint(x, y)

        if not self.isVisible():
            # Начальная позиция со смещением
            self.final_pos = new_pos
            self.move(x + 14, y)
        elif animated:
            # Анимированное перемещение
            self.final_pos = new_pos
            self._animate_move(new_pos)
        else:
            self.final_pos = new_pos

    def _animate_move(self, new_pos: QPoint):
        """Плавное перемещение"""
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(self.config.reposition_duration)
        anim.setStartValue(self.pos())
        anim.setEndValue(new_pos)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._move_anim = anim  # Сохраняем ссылку

    def show_toast(self):
        """Показ с анимацией"""
        self.show()

        # Fade in
        self.fade_anim.setDirection(QPropertyAnimation.Forward)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        # Slide in
        self.slide_anim.setStartValue(self.pos())
        self.slide_anim.setEndValue(self.final_pos)
        self.slide_anim.start()

        # Auto-hide
        QTimer.singleShot(self.config.auto_hide_delay, self.hide_toast)

    def hide_toast(self):
        """Скрытие с анимацией"""
        self.fade_anim.setDirection(QPropertyAnimation.Backward)
        self.fade_anim.finished.connect(self._destroy)
        self.fade_anim.start()

    def _destroy(self):
        """Удаление тоста"""
        if self.manager:
            self.manager.remove_item(self)
        self.deleteLater()

    def mousePressEvent(self, event):
        """Обработка кликов"""
        if event.button() == Qt.RightButton:
            self.hide_toast()
        elif event.button() == Qt.LeftButton and self.manager:
            self.manager.handle_click(self)


# ============================================================
# NOTIFICATION MANAGER
# ============================================================

class PopupNotification(QObject):
    """Менеджер уведомлений"""

    def __init__(self, config: Optional[ToastConfig] = None):
        super().__init__()
        self.config = config or ToastConfig()
        self.active_toasts = []
        self._filters = []
        self._click_handlers = {}  # type -> handler

    def add_filter(self, filter_func: Callable[[str], bool]):
        """Добавить фильтр для игнорирования уведомлений"""
        self._filters.append(filter_func)

    def set_click_handler(self, msg_type: str, handler: Callable):
        """Установить обработчик для типа сообщений"""
        self._click_handlers[msg_type] = handler

    def add_item(self, text: str, msg_type: str = "info", priority: Optional[str] = None):
        """Показать уведомление"""
        # Проверка фильтров
        if any(f(text) for f in self._filters):
            return

        toast = ToastItem(
            text=text,
            msg_type=msg_type,
            priority=priority,
            config=self.config,
            manager=self
        )

        self.active_toasts.append(toast)
        self._reposition_all(animated=False)
        toast.show_toast()

    def remove_item(self, item: ToastItem):
        """Удалить тост из списка"""
        if item in self.active_toasts:
            self.active_toasts.remove(item)
            self._reposition_all(animated=True)

    def _reposition_all(self, animated: bool):
        """Обновить позиции всех тостов"""
        for i, toast in enumerate(self.active_toasts):
            toast.reposition(i, animated=animated)

    def handle_click(self, toast: ToastItem):
        """Обработка клика по тосту"""
        # Кастомный обработчик
        if toast.msg_type in self._click_handlers:
            self._click_handlers[toast.msg_type](toast.text, toast.priority)
            return

        # Дефолтная обработка
        print(f"[Toast] {toast.msg_type} clicked: {toast.text}")

        if toast.priority == "critical":
            print("  → Critical action")
        elif toast.priority == "warning":
            print("  → Warning action")

    def clear_all(self):
        """Закрыть все уведомления"""
        for toast in self.active_toasts[:]:
            toast.hide_toast()


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    app = QApplication([])

    # Создание менеджера
    notifications = PopupNotification()

    # Добавление фильтра
    notifications.add_filter(lambda text: text.startswith("Слышу:"))


    # Кастомный обработчик для cmd
    def handle_cmd(text, priority):
        print(f"Execute command: {text} (priority: {priority})")


    notifications.set_click_handler("cmd", handle_cmd)

    # Использование (как у вас в ctx.reply)
    notifications.add_item("Простое уведомление", "info")
    notifications.add_item("Успешно выполнено", "success")
    notifications.add_item("Внимание!", "info", priority="warning")
    notifications.add_item("Критическая ошибка!", "error", priority="critical")
    notifications.add_item("Команда выполнена", "cmd", priority="critical")

    app.exec()