from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QLabel, QGraphicsOpacityEffect, QApplication
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation
# Шрифты и цвета живут в QtGui!
from PySide6.QtGui import QColor, QFont, QFontMetrics

class PopupNotification(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame()
        self.container.setObjectName("toastContainer")
        self.container.setStyleSheet("""
            QFrame#toastContainer {
                background-color: rgba(20, 20, 20, 0.92);
                border: 1px solid rgba(0, 255, 204, 0.4);
                border-radius: 12px;
            }
            QLabel { color: #e0e0e0; font-family: "Segoe UI Variable", sans-serif; font-size: 14px; background: transparent; }
        """)
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(16, 10, 16, 10)
        self.main_layout.addWidget(self.container)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_fade_out)
        self.fade_anim.finished.connect(lambda: self.hide() if self.opacity_effect.opacity() == 0 else None)

    def add_item(self, text, msg_type="info"):
        if text.startswith("Слышу:"): return
        self.hide_timer.stop()
        self.fade_anim.stop()

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        colors = {"info": "#99f0ff", "cmd": "#ffdd57", "error": "#ff6b6b", "success": "#51cf66"}
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {colors.get(msg_type, '#fff')}; font-weight: 500;")
        self.content_layout.addWidget(label)

        self.reposition(text)
        self.show()
        self.opacity_effect.setOpacity(1.0)
        self.hide_timer.start(5000)

    def reposition(self, text=""):
        screen = QApplication.primaryScreen().availableGeometry()
        max_w, min_w = int(screen.width() * 0.5), 320
        metrics = QFontMetrics(QFont("Segoe UI Variable", 14))
        text_width = metrics.horizontalAdvance(text) + 80
        final_w = max(min_w, min(text_width, max_w))
        rect = metrics.boundingRect(0, 0, final_w - 40, 1000, Qt.AlignCenter | Qt.TextWordWrap, text)
        final_h = rect.height() + 30
        self.setFixedSize(int(final_w), int(final_h))
        self.move((screen.width() - final_w) // 2, screen.bottom() - final_h - 40)

    def start_fade_out(self):
        self.fade_anim.setDuration(600)
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.start()