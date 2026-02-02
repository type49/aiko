import sounddevice as sd
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QFormLayout,
                               QLineEdit, QComboBox, QSlider, QPushButton, QLabel, QHBoxLayout)
from PySide6.QtCore import Qt, Signal
from utils.config_manager import aiko_cfg
from utils.logger import logger


class SettingsWindow(QWidget):
    # Сигнал для уведомления системы об изменениях
    settings_saved = Signal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("AiKo — Параметры системы")
        self.setFixedSize(450, 550)
        self.init_ui()
        logger.info("SettingsWindow: Окно настроек инициализировано.")

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- ТАБ 1: ОСНОВНЫЕ НАСТРОЙКИ ---
        self.general_tab = QWidget()
        self.setup_general_tab()
        self.tabs.addTab(self.general_tab, "Основные")

        # --- ТАБ 2: ТЕЛЕГРАМ (ЗАГОТОВКА) ---
        self.tg_tab = QWidget()
        tg_layout = QVBoxLayout(self.tg_tab)
        tg_label = QLabel("Модуль интеграции с Telegram находится в разработке.")
        tg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tg_layout.addWidget(tg_label)
        tg_layout.addStretch()
        self.tabs.addTab(self.tg_tab, "Telegram")

        layout.addWidget(self.tabs)

        # Нижняя панель кнопок
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Применить")
        self.save_btn.setFixedHeight(35)
        self.save_btn.clicked.connect(self.save_settings)

        self.close_btn = QPushButton("Отмена")
        self.close_btn.setFixedHeight(35)
        self.close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def setup_general_tab(self):
        layout = QFormLayout(self.general_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Имя ассистента
        self.name_input = QLineEdit(aiko_cfg.get("bot.name", "Айко"))
        layout.addRow("Имя ассистента:", self.name_input)

        # 2. Выбор микрофона
        self.mic_box = QComboBox()
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    self.mic_box.addItem(f"{i}: {dev['name']}", i)

            current_mic = aiko_cfg.get("audio.device_index", 0)
            index = self.mic_box.findData(current_mic)
            self.mic_box.setCurrentIndex(index if index != -1 else 0)
        except Exception as e:
            logger.error(f"SettingsWindow: Ошибка загрузки списка аудио-устройств: {e}")
            layout.addRow(QLabel("Ошибка загрузки микрофонов"), self.mic_box)

        layout.addRow("Устройство ввода:", self.mic_box)

        # 3. Общая громкость
        vol_layout = QHBoxLayout()
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        current_vol = int(aiko_cfg.get("audio.master_volume", 0.7) * 100)
        self.vol_slider.setValue(current_vol)

        self.vol_label = QLabel(f"{current_vol}%")
        self.vol_slider.valueChanged.connect(lambda v: self.vol_label.setText(f"{v}%"))

        vol_layout.addWidget(self.vol_slider)
        vol_layout.addWidget(self.vol_label)
        layout.addRow("Громкость системы:", vol_layout)

    def save_settings(self):
        """Вызывается ТОЛЬКО при нажатии кнопки 'Применить'"""
        logger.info("SettingsWindow: Пользователь нажал 'Применить'.")

        # Считываем данные из интерфейса
        new_name = self.name_input.text()
        new_mic_idx = self.mic_box.currentData()
        new_vol = self.vol_slider.value() / 100

        # Обновляем конфиг в памяти
        aiko_cfg.set("bot.name", new_name)
        aiko_cfg.set("audio.device_index", new_mic_idx)
        aiko_cfg.set("audio.master_volume", new_vol)

        # Сохраняем физически
        if aiko_cfg.save():
            logger.info(f"SettingsWindow: Конфиг сохранен (Vol: {new_vol}, Mic: {new_mic_idx})")
            self.settings_saved.emit()  # Уведомляем систему
            self.close()

    def reject_settings(self):
        """Вызывается при нажатии 'Отмена'"""
        logger.info("SettingsWindow: Изменения отменены пользователем.")
        self.close()  # Просто закрываем, метод save_settings не вызывается