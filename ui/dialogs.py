from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDateTimeEdit, QPushButton, QLabel
from PySide6.QtCore import Qt, QDateTime


class ReminderDialog(QDialog):
    def __init__(self, initial_text=""):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.layout = QVBoxLayout(self)
        self.text_input = QLineEdit(initial_text)
        self.time_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(60))
        self.time_input.setCalendarPopup(True)
        self.save_btn = QPushButton("ЗАФИКСИРОВАТЬ")
        self.save_btn.clicked.connect(self.accept)

        self.layout.addWidget(QLabel("Суть:"))
        self.layout.addWidget(self.text_input)
        self.layout.addWidget(self.time_input)
        self.layout.addWidget(self.save_btn)

        self.setStyleSheet("""
            QDialog { background: #1a1a1a; color: #00FFCC; border: 1px solid #00FFCC; }
            QLineEdit, QDateTimeEdit { background: #252525; color: white; border: 1px solid #333; padding: 5px; }
            QPushButton { background: #00FFCC; color: #000; font-weight: bold; padding: 8px; border: none; }
        """)

    def get_data(self):
        return self.text_input.text(), self.time_input.dateTime().toString("yyyy-MM-dd HH:mm:ss")