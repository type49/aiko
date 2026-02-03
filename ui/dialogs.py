from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QDateTimeEdit, QPushButton, QLabel, QCheckBox,
                               QComboBox, QSpinBox, QFrame, QGridLayout)
from PySide6.QtCore import Qt, QDateTime, QTimer


class ReminderDialog(QDialog):
    def __init__(self, initial_text=""):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; color: #00FFCC; border: 2px solid #00FFCC; }
            QLineEdit, QDateTimeEdit, QComboBox, QSpinBox { 
                background: #252525; color: white; border: 1px solid #333; padding: 5px; 
            }
            QPushButton { background: #00FFCC; color: #000; font-weight: bold; padding: 8px; border: none; }
            QPushButton#extra_btn { background: #333; color: #00FFCC; border: 1px solid #00FFCC; }
            QLabel { color: #00FFCC; font-size: 10pt; }
            QCheckBox { color: white; }
        """)

        # Основные поля
        self.text_input = QLineEdit(initial_text)
        self.time_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(300))
        self.time_input.setCalendarPopup(True)

        # Каналы связи
        self.cb_gui = QCheckBox("На компьютер (HUD)")
        self.cb_gui.setChecked(True)
        self.cb_tg = QCheckBox("В Telegram")

        # --- СЕКЦИЯ ПОВТОРОВ ---
        self.repeat_type = QComboBox()
        self.repeat_type.addItems(["Один раз", "Каждые N часов", "Ежедневно", "По дням недели"])

        # Виджет для "Каждые N часов"
        self.hours_box = QFrame()
        h_layout = QHBoxLayout(self.hours_box)
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.spin_hours = QSpinBox()
        self.spin_hours.setRange(1, 168)  # до недели
        h_layout.addWidget(QLabel("Интервал (ч):"))
        h_layout.addWidget(self.spin_hours)
        self.hours_box.hide()

        # Виджет для выбора дней недели
        self.days_box = QFrame()
        d_layout = QGridLayout(self.days_box)
        self.day_checks = []
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for i, day in enumerate(days):
            cb = QCheckBox(day)
            d_layout.addWidget(cb, i // 4, i % 4)
            self.day_checks.append(cb)
        self.days_box.hide()

        # --- СЕКЦИЯ КОМАНД (Задел на будущее) ---
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Команды через ; (напр. volume 0; pc_sleep)")

        # Кнопки
        self.save_btn = QPushButton("ЗАФИКСИРОВАТЬ")
        self.save_btn.clicked.connect(self.accept)

        # Сборка UI
        self.layout.addWidget(QLabel("СУТЬ:"))
        self.layout.addWidget(self.text_input)
        self.layout.addWidget(QLabel("ПЕРВЫЙ ЗАПУСК / ВРЕМЯ:"))
        self.layout.addWidget(self.time_input)

        self.layout.addWidget(QLabel("ПОВТОР:"))
        self.layout.addWidget(self.repeat_type)
        self.layout.addWidget(self.hours_box)
        self.layout.addWidget(self.days_box)

        self.layout.addWidget(QLabel("КАНАЛЫ:"))
        h_box = QHBoxLayout()
        h_box.addWidget(self.cb_gui)
        h_box.addWidget(self.cb_tg)
        self.layout.addLayout(h_box)

        self.layout.addWidget(QLabel("КОМАНДЫ:"))
        self.layout.addWidget(self.command_input)

        self.layout.addWidget(self.save_btn)

        # Логика переключения интерфейса
        self.repeat_type.currentIndexChanged.connect(self._toggle_repeat_ui)

    def _toggle_repeat_ui(self):
        mode = self.repeat_type.currentText()
        self.hours_box.setVisible(mode == "Каждые N часов")
        self.days_box.setVisible(mode == "По дням недели")
        self.adjustSize()

    def get_data(self):
        # Собираем список активных дней
        active_days = [cb.text() for cb in self.day_checks if cb.isChecked()]

        return {
            "text": self.text_input.text(),
            "time": self.time_input.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "to_gui": self.cb_gui.isChecked(),
            "to_tg": self.cb_tg.isChecked(),
            "priority": "normal",  # Пока дефолт
            "repeat": {
                "type": self.repeat_type.currentText(),
                "interval_hours": self.spin_hours.value() if self.repeat_type.currentText() == "Каждые N часов" else 0,
                "days": active_days
            },
            "auto_commands": [c.strip() for c in self.command_input.text().split(";") if c.strip()]
        }


class AlarmWindow(QDialog):
    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.data = task_data
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 250)

        self.layout = QVBoxLayout(self)
        self.main_frame = QFrame()
        self.main_frame.setObjectName("AlarmFrame")
        self.main_frame.setStyleSheet("""
            QFrame#AlarmFrame { background: #1a1a1a; border: 2px solid #00FFCC; border-radius: 10px; }
            QLabel { color: #00FFCC; font-size: 12pt; }
            QPushButton { padding: 8px; font-weight: bold; border-radius: 4px; }
            #BtnDone { background: #00FFCC; color: #000; }
            #BtnSnooze { background: #333; color: #00FFCC; border: 1px solid #00FFCC; }
            QSpinBox { background: #252525; color: white; border: 1px solid #333; padding: 3px; }
        """)

        frame_layout = QVBoxLayout(self.main_frame)

        # Текст задачи
        self.label = QLabel(self.data.get('text', 'Напоминание!'))
        self.label.setWordWrap(True)
        frame_layout.addWidget(self.label)

        # Блок откладывания
        snooze_layout = QHBoxLayout()
        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(1, 1440)  # от 1 минуты до суток
        self.spin_minutes.setValue(5)  # дефолт 5 мин
        self.btn_snooze = QPushButton("ОТЛОЖИТЬ НА (мин):")
        self.btn_snooze.setObjectName("BtnSnooze")

        snooze_layout.addWidget(self.btn_snooze)
        snooze_layout.addWidget(self.spin_minutes)
        frame_layout.addLayout(snooze_layout)

        # Кнопка выполнения
        self.btn_done = QPushButton("ВЫПОЛНЕНО / ЗАКРЫТЬ")
        self.btn_done.setObjectName("BtnDone")
        frame_layout.addWidget(self.btn_done)

        self.layout.addWidget(self.main_frame)

