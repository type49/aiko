import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QDateTimeEdit, QPushButton, QLabel, QCheckBox,
                               QComboBox, QSpinBox, QFrame, QGridLayout,
                               QMainWindow, QWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QApplication)
from PySide6.QtCore import Qt, QDateTime
from utils.db_manager import db
from utils.logger import logger


class ReminderCreateDialog(QDialog):
    """Окно создания: Само сохраняет задачу в БД"""

    def __init__(self, initial_text="", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog { background: #1a1a1a; color: #00FFCC; border: 2px solid #00FFCC; }
            QLineEdit, QDateTimeEdit, QComboBox, QSpinBox { 
                background: #252525; color: white; border: 1px solid #333; padding: 5px; 
            }
            QPushButton { background: #00FFCC; color: #000; font-weight: bold; padding: 8px; border: none; }
            QLabel { color: #00FFCC; }
        """)

        layout = QVBoxLayout(self)
        self.text_input = QLineEdit(initial_text)
        self.time_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(300))
        self.time_input.setCalendarPopup(True)

        self.repeat_type = QComboBox()
        self.repeat_type.addItems(["Один раз", "Каждые N часов", "По дням недели"])

        # Блоки настроек (Hours/Days)
        self.hours_box = QFrame()
        h_layout = QHBoxLayout(self.hours_box)
        self.spin_hours = QSpinBox()
        self.spin_hours.setRange(1, 168)
        h_layout.addWidget(QLabel("Интервал (ч):"))
        h_layout.addWidget(self.spin_hours)
        self.hours_box.hide()

        self.days_box = QFrame()
        d_layout = QGridLayout(self.days_box)
        self.day_checks = []
        for i, day in enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]):
            cb = QCheckBox(day)
            d_layout.addWidget(cb, i // 4, i % 4)
            self.day_checks.append(cb)
        self.days_box.hide()

        # Кнопки
        btn_box = QHBoxLayout()
        self.save_btn = QPushButton("ЗАФИКСИРОВАТЬ")
        self.cancel_btn = QPushButton("ОТМЕНА")
        self.cancel_btn.setStyleSheet("background: #333; color: #00FFCC;")

        layout.addWidget(QLabel("СУТЬ НАПОМИНАЛКИ:"))
        layout.addWidget(self.text_input)
        layout.addWidget(QLabel("ВРЕМЯ ПЕРВОГО ЗАПУСКА:"))
        layout.addWidget(self.time_input)
        layout.addWidget(QLabel("ПОВТОРЕНИЕ:"))
        layout.addWidget(self.repeat_type)
        layout.addWidget(self.hours_box)
        layout.addWidget(self.days_box)

        btn_box.addWidget(self.cancel_btn)
        btn_box.addWidget(self.save_btn)
        layout.addLayout(btn_box)

        self.save_btn.clicked.connect(self.handle_save)
        self.cancel_btn.clicked.connect(self.reject)
        self.repeat_type.currentIndexChanged.connect(self._update_ui)

    def _update_ui(self):
        mode = self.repeat_type.currentText()
        self.hours_box.setVisible(mode == "Каждые N часов")
        self.days_box.setVisible(mode == "По дням недели")
        self.adjustSize()

    def handle_save(self):
        """Логика сохранения вынесена из GUI сюда"""
        active_days = [cb.text() for cb in self.day_checks if cb.isChecked()]
        data = {
            "text": self.text_input.text(),
            "time": self.time_input.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "repeat": {
                "type": self.repeat_type.currentText(),
                "interval": self.spin_hours.value(),
                "days": active_days
            },
            "to_gui": True, "to_tg": False
        }
        if db.add_task("reminder", data, data['time']):
            logger.info(f"Reminders: Задача сохранена в БД: {data['text']}")
            self.accept()


class AlarmWindow(QDialog):
    def __init__(self, data, on_close_callback=None): # Добавлен аргумент
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(400, 220)
        self.data = data
        self.on_close = on_close_callback # Сохраняем колбэк

        layout = QVBoxLayout(self)
        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame { background: #1a1a1a; border: 2px solid #FF0000; border-radius: 10px; }
            QLabel { color: #00FFCC; font-size: 14pt; font-weight: bold; border: none; }
            QPushButton { padding: 10px; font-weight: bold; border-radius: 5px; border: none; }
            #BtnDone { background: #00FFCC; color: #000; }
            #BtnSnooze { background: #333; color: #00FFCC; border: 1px solid #00FFCC; }
            QSpinBox { background: #252525; color: white; border: 1px solid #333; }
        """)

        f_layout = QVBoxLayout(self.frame)
        self.label = QLabel(data.get('text', 'НАПОМИНАНИЕ!'))
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)

        snooze_layout = QHBoxLayout()
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 1440)
        self.spin_min.setValue(5)
        self.btn_snooze = QPushButton("ОТЛОЖИТЬ НА (МИН)")
        self.btn_snooze.setObjectName("BtnSnooze")
        snooze_layout.addWidget(self.btn_snooze)
        snooze_layout.addWidget(self.spin_min)

        self.btn_done = QPushButton("ВЫПОЛНЕНО / ЗАКРЫТЬ")
        self.btn_done.setObjectName("BtnDone")

        f_layout.addWidget(self.label)
        f_layout.addLayout(snooze_layout)
        f_layout.addWidget(self.btn_done)
        layout.addWidget(self.frame)

        # Привязываем методы
        self.btn_done.clicked.connect(self.handle_done)
        self.btn_snooze.clicked.connect(self.handle_snooze)

    def handle_done(self):
        self.close_and_cleanup()

    def handle_snooze(self):
        new_time = QDateTime.currentDateTime().addSecs(self.spin_min.value() * 60).toString("yyyy-MM-dd HH:mm:ss")
        if db.add_task("reminder", self.data, new_time):
            logger.info(f"Reminders: Отложено на {self.spin_min.value()} мин.")
        self.close_and_cleanup()

    def close_and_cleanup(self):
        # Вызываем колбэк перед закрытием, чтобы AikoApp удалил ссылку из списка
        if self.on_close:
            self.on_close(self)
        self.close()
        self.deleteLater()


class ReminderManager(QMainWindow):
    """Менеджер: Полный контроль списка"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AiKo | Менеджер напоминалок")
        self.resize(700, 450)
        self.setStyleSheet("QMainWindow { background: #1a1a1a; }")

        self.central = QWidget()
        self.setCentralWidget(self.central)
        layout = QVBoxLayout(self.central)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "ВРЕМЯ", "СУТЬ"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { background: #252525; color: white; gridline-color: #333; }
            QHeaderView::section { background: #333; color: #00FFCC; padding: 5px; }
        """)

        self.btn_refresh = QPushButton("ОБНОВИТЬ СПИСОК")
        self.btn_delete = QPushButton("УДАЛИТЬ ВЫБРАННОЕ")
        self.btn_delete.setStyleSheet("background: #550000; color: white;")

        layout.addWidget(self.table)
        layout.addWidget(self.btn_refresh)
        layout.addWidget(self.btn_delete)

        self.btn_refresh.clicked.connect(self.refresh_list)
        self.btn_delete.clicked.connect(self.delete_reminder)
        self.refresh_list()

    def refresh_list(self):
        self.table.setRowCount(0)
        items = db.get_all_scheduler_tasks()
        for r_id, payload, exec_at, _ in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            try:
                text = json.loads(payload).get('text', '---')
            except:
                text = payload
            self.table.setItem(row, 0, QTableWidgetItem(str(r_id)))
            self.table.setItem(row, 1, QTableWidgetItem(exec_at))
            self.table.setItem(row, 2, QTableWidgetItem(text))

    def delete_reminder(self):
        row = self.table.currentRow()
        if row >= 0:
            r_id = self.table.item(row, 0).text()
            if db.delete_task(r_id): self.refresh_list()