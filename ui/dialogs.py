from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDateTimeEdit, QPushButton, QLabel
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import QCheckBox

class ReminderDialog(QDialog):
    def __init__(self, initial_text=""):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.layout = QVBoxLayout(self)

        self.text_input = QLineEdit(initial_text)
        self.time_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(300))  # +5 мин по дефолту
        self.time_input.setCalendarPopup(True)

        self.cb_gui = QCheckBox("На компьютер (HUD)")
        self.cb_gui.setChecked(True)
        self.cb_tg = QCheckBox("В Telegram")


        self.save_btn = QPushButton("ЗАФИКСИРОВАТЬ")
        self.save_btn.clicked.connect(self.accept)

        self.layout.addWidget(QLabel("СУТЬ:"))
        self.layout.addWidget(self.text_input)
        self.layout.addWidget(QLabel("ВРЕМЯ:"))
        self.layout.addWidget(self.time_input)
        self.layout.addWidget(self.cb_gui)
        self.layout.addWidget(self.cb_tg)
        self.layout.addWidget(self.save_btn)

    def get_data(self):
        return {
            "text": self.text_input.text(),
            "time": self.time_input.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "to_gui": self.cb_gui.isChecked(),
            "to_tg": self.cb_tg.isChecked()
        }