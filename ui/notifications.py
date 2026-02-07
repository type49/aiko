from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QLabel,
    QGraphicsOpacityEffect, QApplication, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QObject, QEasingCurve, Property, Signal
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
    auto_hide_delay: int = 5000
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
# PROGRESS BAR WIDGET
# ============================================================

class ProgressBar(QWidget):
    """Прогресс-бар внизу тоста"""

    def __init__(self, color: str, duration: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self._progress = 1.0
        self._color = color
        self._duration = duration

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                opacity: 0.3;
            }}
        """)

    def get_progress(self):
        return self._progress

    def set_progress(self, value):
        self._progress = value
        self.update()

    progress = Property(float, get_progress, set_progress)

    def start_animation(self):
        """Запуск анимации уменьшения"""
        if self._duration <= 0:
            return

        self.anim = QPropertyAnimation(self, b"progress")
        self.anim.setDuration(self._duration)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Linear)
        self.anim.start()

    def paintEvent(self, event):
        """Отрисовка с учётом прогресса"""
        from PySide6.QtGui import QPainter, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Парсим цвет
        color = QColor(self._color)
        color.setAlphaF(0.3)
        painter.fillRect(0, 0, int(self.width() * self._progress), self.height(), color)


# ============================================================
# TOAST ITEM
# ============================================================

class ToastItem(QWidget):
    """Визуальный компонент уведомления"""

    def __init__(self, text: str, msg_type: str, priority: Optional[str],
                 config: ToastConfig, manager, lifetime: Optional[int] = None):
        super().__init__()

        self.text = text
        self.msg_type = msg_type
        self.priority = priority
        self.config = config
        self.manager = manager
        self.final_pos = QPoint(0, 0)
        self.lifetime = lifetime if lifetime is not None else self.config.auto_hide_delay
        self._is_hiding = False  # Флаг для предотвращения повторного показа

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

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container
        self.container = QFrame()
        self.container.setObjectName("toast")
        self.container.setStyleSheet(f"""
            QFrame#toast {{
                background-color: {colors['bg']};
                border-top-left-radius: {self.config.border_radius}px;
                border-top-right-radius: {self.config.border_radius}px;
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

        # Progress bar
        self.progress_bar = ProgressBar(colors['bar'], self.lifetime)

        # Add to main layout
        main_layout.addWidget(self.container)
        main_layout.addWidget(self.progress_bar)

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
        self.progress_bar.setFixedWidth(target_width)
        self.label.adjustSize()
        self.container.adjustSize()
        self.adjustSize()

    def _setup_animations(self):
        """Настройка анимаций"""
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(self.config.fade_duration)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.slide_anim = QPropertyAnimation(self, b"pos")
        self.slide_anim.setDuration(self.config.slide_duration)
        self.slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Отдельная анимация для скрытия
        self.hide_slide_anim = QPropertyAnimation(self, b"pos")
        self.hide_slide_anim.setDuration(self.config.slide_duration)
        self.hide_slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.hide_slide_anim.finished.connect(self._destroy)

    def _play_sound(self):
        """Воспроизведение звука с защитой от бесконечного цикла"""
        # 1. Если это ошибка — молчим. Безопасность превыше всего.
        if self.msg_type == "error" or self.priority == "critical":
            return

        # 2. Пытаемся проиграть звук уведомления
        try:
            # Используем проверку существования файла в самом аудио-менеджере,
            # но здесь просто глушим ошибку.
            audio_manager.play.notify()
        except Exception:
            # Печатаем в консоль напрямую.
            # НЕ ВЫЗЫВАЙ logger.error здесь, иначе снова пойдет рекурсия!
            print("LOG: [Toast] Notification sound file missing, skipping sound.")

    def reposition(self, index: int, animated: bool = False):
        """Установка позиции тоста"""
        if self._is_hiding:  # Не перемещаем тост, который скрывается
            return

        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.height(), self.height()

        x = screen.right() - self.width()
        y = screen.bottom() - ((self.height() + self.config.spacing) * (index + 1)) - 12
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
        if self._is_hiding:  # Не анимируем перемещение для скрывающегося тоста
            return

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

        # Start progress bar animation
        if self.lifetime > 0:
            self.progress_bar.start_animation()

        # Auto-hide
        if self.lifetime > 0:  # Если 0, можно сделать уведомление вечным
            QTimer.singleShot(self.lifetime, self.hide_toast)

    def hide_toast(self):
        """Скрытие с анимацией уезжания вправо"""
        if self._is_hiding:  # Предотвращаем повторное скрытие
            return

        self._is_hiding = True
        screen = QApplication.primaryScreen().availableGeometry()

        # Останавливаем все текущие анимации перемещения
        if hasattr(self, '_move_anim'):
            self._move_anim.stop()
        self.slide_anim.stop()

        # Анимация уезжания вправо
        self.hide_slide_anim.setStartValue(self.pos())
        self.hide_slide_anim.setEndValue(QPoint(screen.right() + 50, self.pos().y()))
        self.hide_slide_anim.start()

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
    _request_toast = Signal(str, str, object, object)
    def __init__(self, config: Optional[ToastConfig] = None):
        super().__init__()
        self.config = config or ToastConfig()
        self.active_toasts = []
        self._filters = []
        self._click_handlers = {}  # type -> handler
        self._request_toast.connect(self._internal_create_toast)

    def add_filter(self, filter_func: Callable[[str], bool]):
        """Добавить фильтр для игнорирования уведомлений"""
        self._filters.append(filter_func)

    def set_click_handler(self, msg_type: str, handler: Callable):
        """Установить обработчик для типа сообщений"""
        self._click_handlers[msg_type] = handler

    def add_item(self, text: str, msg_type: str = "info",
                 priority: Optional[str] = None,
                 lifetime: Optional[int] = None):
        """Показать уведомление"""
        # 1. Проверка фильтров
        if any(f(text) for f in self._filters):
            return

        # # 2. Создание тоста с пробросом lifetime
        # toast = ToastItem(
        #     text=text,
        #     msg_type=msg_type,
        #     priority=priority,
        #     config=self.config,
        #     manager=self,
        #     lifetime=lifetime
        # )
        #
        # # 3. Добавление в начало списка.
        # # Новые уведомления будут иметь индекс 0 и рисоваться в самой нижней позиции.
        # self.active_toasts.insert(0, toast)
        #
        # # 4. Сначала рассчитываем позиции для всех, потом показываем новый
        # self._reposition_all(animated=True)
        # toast.show_toast()
        self._request_toast.emit(text, msg_type, priority, lifetime)

    def _internal_create_toast(self, text, msg_type, priority, lifetime):
        """
        ОПАСНЫЙ метод. Работает ТОЛЬКО в GUI-потоке.
        Сюда мы попадаем через сигнал.
        """
        # 4. Вот теперь создаем виджет — это безопасно, т.к. сигнал перенес нас в GUI-поток
        toast = ToastItem(
            text=text,
            msg_type=msg_type,
            priority=priority,
            config=self.config,
            manager=self,
            lifetime=lifetime
        )

        self.active_toasts.insert(0, toast)
        self._reposition_all(animated=True)
        toast.show_toast()

    def remove_item(self, item: ToastItem):
        """Удалить тост из списка активных"""
        if item in self.active_toasts:
            self.active_toasts.remove(item)
            # Анимированно подтягиваем оставшиеся тосты на свободные места
            self._reposition_all(animated=True)

    def _reposition_all(self, animated: bool):
        """Обновить позиции всех тостов согласно их индексу в списке"""
        for i, toast in enumerate(self.active_toasts):
            toast.reposition(i, animated=animated)

    def handle_click(self, toast: ToastItem):
        """Обработка клика по тосту"""
        if toast.msg_type in self._click_handlers:
            self._click_handlers[toast.msg_type](toast.text, toast.priority)
            toast.hide_toast()  # Закрываем после обработки клика
            return

        # Логирование (замени на logger при необходимости)
        print(f"[Toast] {toast.msg_type} clicked: {toast.text}")

    def clear_all(self):
        """Закрыть все уведомления"""
        # Используем срез [:], так как оригинальный список будет меняться при удалении
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
    notifications.add_item("Успешно выполнено", "success", lifetime=2000)
    notifications.add_item("Внимание!", "info", priority="warning")
    notifications.add_item("Критическая ошибка!", "error")
    notifications.add_item("Команда выполнена", "cmd", priority="critical", lifetime=0)

    app.exec()