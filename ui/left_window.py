import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer, QDateTime, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QFont, QPainter, QColor
import psutil
import subprocess
import platform


class EdgeButton(QWidget):
    """Тонкая вертикальная кнопка-вкладка на краю экрана"""

    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen_geo = QApplication.primaryScreen().availableGeometry()
        button_width = 5
        button_height = 100
        x = screen_geo.x()
        y = screen_geo.y() + (screen_geo.height() - button_height) // 2

        self.setGeometry(x, y, button_width, button_height)
        self.is_hovered = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.is_hovered:
            painter.setBrush(QColor(255, 255, 255, 100))
        else:
            painter.setBrush(QColor(255, 255, 255, 50))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 2, 2)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_window.toggle_visibility()


class LiquidGlassWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Геометрия с учетом панели задач
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.panel_width = int(screen_geo.width() * 0.2)
        height = screen_geo.height()
        self.visible_x = screen_geo.x()
        self.hidden_x = screen_geo.x() - self.panel_width
        y = screen_geo.y()

        self.setGeometry(self.visible_x, y, self.panel_width, height)
        self.is_hidden = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setup_ui()

        # Создаем кнопку-вкладку
        self.edge_button = EdgeButton(self)
        self.edge_button.hide()

        # Таймер для обновления данных
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)

        # Инициализация переменных для сети
        self.last_net_bytes = None
        self.last_net_sent = None
        self.last_net_recv = None

        # Первое обновление данных
        self.update_data()

    def toggle_visibility(self):
        """Плавное скрытие/показ панели"""
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        current_y = self.pos().y()

        if self.is_hidden:
            # Показываем панель
            self.animation.setEndValue(QPoint(self.visible_x, current_y))
            self.hide_button.setText("◂")
            self.is_hidden = False
            self.edge_button.hide()
        else:
            # Скрываем панель
            self.animation.setEndValue(QPoint(self.hidden_x, current_y))
            self.hide_button.setText("▸")
            self.is_hidden = True
            self.edge_button.show()

        self.animation.start()

    def toggle_expand(self):
        """Раскрытие/скрытие дополнительной системной информации"""
        if self.expandable_container.isVisible():
            # Скрываем
            self.expandable_container.hide()
            self.expand_button.setText("⌄")
        else:
            # Показываем
            self.expandable_container.show()
            self.expand_button.setText("⌃")

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 30, 25, 30)
        main_layout.setSpacing(0)

        # ===== КНОПКА СКРЫТИЯ =====
        hide_btn_container = QWidget()
        hide_btn_container.setStyleSheet("background: transparent;")
        hide_btn_layout = QHBoxLayout(hide_btn_container)
        hide_btn_layout.setContentsMargins(0, 0, 0, 20)
        hide_btn_layout.setSpacing(0)

        hide_btn_layout.addStretch()

        self.hide_button = QPushButton("◂")
        self.hide_button.setFixedSize(40, 40)
        self.hide_button.clicked.connect(self.toggle_visibility)
        self.hide_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 15);
                color: rgba(255, 255, 255, 120);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 25);
                color: rgba(255, 255, 255, 180);
                border: 1px solid rgba(255, 255, 255, 35);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 35);
            }
        """)

        hide_btn_layout.addWidget(self.hide_button)
        main_layout.addWidget(hide_btn_container)

        # ===== ВРЕМЯ И ДАТА =====
        time_container = QWidget()
        time_container.setStyleSheet("background: transparent;")
        time_layout = QVBoxLayout(time_container)
        time_layout.setContentsMargins(0, 0, 0, 35)
        time_layout.setSpacing(5)

        # Время
        self.time_label = QLabel("11:42")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI Light", 72, QFont.Weight.Light)
        self.time_label.setFont(font)
        self.time_label.setStyleSheet("""
            color: rgba(255, 255, 255, 220);
            background: transparent;
            letter-spacing: -2px;
        """)

        # День недели и дата
        self.date_label = QLabel("FRI 19")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_font = QFont("Segoe UI Semibold", 18, QFont.Weight.DemiBold)
        self.date_label.setFont(date_font)
        self.date_label.setStyleSheet("""
            color: rgba(255, 255, 255, 180);
            background: transparent;
            letter-spacing: 3px;
        """)

        # Полная дата
        self.full_date_label = QLabel("JANUARY")
        self.full_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        month_font = QFont("Segoe UI", 12, QFont.Weight.Normal)
        self.full_date_label.setFont(month_font)
        self.full_date_label.setStyleSheet("""
            color: rgba(255, 255, 255, 140);
            background: transparent;
            letter-spacing: 2px;
        """)

        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.date_label)
        time_layout.addWidget(self.full_date_label)

        main_layout.addWidget(time_container)

        # Разделитель
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(255, 255, 255, 0),
                stop:0.5 rgba(255, 255, 255, 40),
                stop:1 rgba(255, 255, 255, 0));
        """)
        main_layout.addWidget(separator)
        main_layout.addSpacing(30)

        # ===== СИСТЕМНАЯ ИНФОРМАЦИЯ =====

        # Заголовок секции
        sys_header = QLabel("SYSTEM")
        sys_header.setFont(QFont("Segoe UI Semibold", 11, QFont.Weight.DemiBold))
        sys_header.setStyleSheet("""
            color: rgba(180, 180, 200, 160);
            background: transparent;
            letter-spacing: 3px;
            padding-bottom: 15px;
        """)
        main_layout.addWidget(sys_header)

        # CPU (всегда видим)
        self.cpu_label = self.create_info_row("CPU", "0%")
        main_layout.addLayout(self.cpu_label)
        main_layout.addSpacing(12)

        # Сеть (всегда видима)
        self.net_label = self.create_info_row("NET", "0 KB/s")
        main_layout.addLayout(self.net_label)
        main_layout.addSpacing(12)

        # Контейнер для раскрывающихся элементов
        self.expandable_container = QWidget()
        self.expandable_container.setStyleSheet("background: transparent;")
        self.expandable_layout = QVBoxLayout(self.expandable_container)
        self.expandable_layout.setContentsMargins(0, 0, 0, 0)
        self.expandable_layout.setSpacing(12)

        # Upload/Download
        self.upload_label = self.create_info_row("UPLOAD", "0 KB/s")
        self.expandable_layout.addLayout(self.upload_label)

        self.download_label = self.create_info_row("DOWNLOAD", "0 KB/s")
        self.expandable_layout.addLayout(self.download_label)

        # GPU (если доступно)
        self.gpu_label = self.create_info_row("GPU", "N/A")
        self.expandable_layout.addLayout(self.gpu_label)

        # RAM Pressure / Swap
        self.ram_label = self.create_info_row("RAM", "0 GB")
        self.expandable_layout.addLayout(self.ram_label)

        self.swap_label = self.create_info_row("SWAP", "0%")
        self.expandable_layout.addLayout(self.swap_label)

        # Температура
        self.temp_label = self.create_info_row("TEMP", "--°C")
        self.expandable_layout.addLayout(self.temp_label)

        self.expandable_container.hide()  # Изначально скрыт
        main_layout.addWidget(self.expandable_container)

        # Кнопка раскрытия/скрытия
        expand_btn_layout = QHBoxLayout()
        expand_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.expand_button = QPushButton("⌄")
        self.expand_button.setFixedSize(30, 30)
        self.expand_button.clicked.connect(self.toggle_expand)
        self.expand_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: rgba(255, 255, 255, 100);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 20);
                color: rgba(255, 255, 255, 150);
                border: 1px solid rgba(255, 255, 255, 25);
            }
        """)

        expand_btn_layout.addStretch()
        expand_btn_layout.addWidget(self.expand_button)
        expand_btn_layout.addStretch()

        main_layout.addLayout(expand_btn_layout)

        main_layout.addStretch()

        # ===== БЫСТРЫЕ ДЕЙСТВИЯ =====
        main_layout.addSpacing(20)

        quick_header = QLabel("QUICK ACTIONS")
        quick_header.setFont(QFont("Segoe UI Semibold", 11, QFont.Weight.DemiBold))
        quick_header.setStyleSheet("""
            color: rgba(180, 180, 200, 160);
            background: transparent;
            letter-spacing: 3px;
            padding-bottom: 15px;
        """)
        main_layout.addWidget(quick_header)

        # Кнопки быстрых действий
        quick_buttons_layout = QHBoxLayout()
        quick_buttons_layout.setSpacing(10)

        # Task Manager
        taskmgr_btn = self.create_quick_button("📊", "Task Manager")
        taskmgr_btn.clicked.connect(self.open_task_manager)
        quick_buttons_layout.addWidget(taskmgr_btn)

        # Settings
        settings_btn = self.create_quick_button("⚙️", "Settings")
        settings_btn.clicked.connect(self.open_settings)
        quick_buttons_layout.addWidget(settings_btn)

        # Terminal
        terminal_btn = self.create_quick_button("💻", "Terminal")
        terminal_btn.clicked.connect(self.open_terminal)
        quick_buttons_layout.addWidget(terminal_btn)

        main_layout.addLayout(quick_buttons_layout)
        main_layout.addSpacing(20)

        self.setLayout(main_layout)

    def create_info_row(self, label_text, value_text):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setFont(QFont("Segoe UI", 10))
        label.setStyleSheet("""
            color: rgba(160, 160, 180, 140);
            background: transparent;
            letter-spacing: 1px;
        """)

        value = QLabel(value_text)
        value.setFont(QFont("Segoe UI Semibold", 11, QFont.Weight.DemiBold))
        value.setStyleSheet("""
            color: rgba(240, 240, 255, 200);
            background: transparent;
        """)
        value.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(value)

        # Сохраняем ссылку на value для обновления
        setattr(self, f"{label_text.lower()}_value", value)

        return layout

    def has_battery(self):
        """Проверка наличия батареи"""
        try:
            battery = psutil.sensors_battery()
            return battery is not None
        except:
            return False

    def create_quick_button(self, icon, tooltip):
        """Создание кнопки быстрого действия"""
        btn = QPushButton(icon)
        btn.setFixedSize(50, 50)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 12);
                color: rgba(255, 255, 255, 140);
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 10px;
                font-size: 20px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 22);
                border: 1px solid rgba(255, 255, 255, 30);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 30);
            }
        """)
        return btn

    def open_task_manager(self):
        """Открыть диспетчер задач"""
        if platform.system() == 'Windows':
            subprocess.Popen('taskmgr', shell=True)
        else:
            subprocess.Popen(['gnome-system-monitor'])

    def open_settings(self):
        """Открыть настройки системы"""
        if platform.system() == 'Windows':
            subprocess.Popen('ms-settings:', shell=True)
        else:
            subprocess.Popen(['gnome-control-center'])

    def open_terminal(self):
        """Открыть терминал"""
        if platform.system() == 'Windows':
            subprocess.Popen('wt', shell=True)  # Windows Terminal
        else:
            subprocess.Popen(['gnome-terminal'])

    def update_data(self):
        """Обновление данных с оптимизацией"""
        try:
            # Обновление времени и даты
            now = QDateTime.currentDateTime()
            self.time_label.setText(now.toString("HH:mm"))
            self.date_label.setText(now.toString("ddd dd").upper())
            self.full_date_label.setText(now.toString("MMMM").upper())

            # CPU
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_value.setText(f"{cpu_percent:.1f}%")

            # Сеть - общий трафик
            net_io = psutil.net_io_counters()
            if self.last_net_bytes is None:
                self.last_net_bytes = net_io.bytes_sent + net_io.bytes_recv
                self.last_net_sent = net_io.bytes_sent
                self.last_net_recv = net_io.bytes_recv
                self.net_value.setText("0 KB/s")
                self.upload_value.setText("0 KB/s")
                self.download_value.setText("0 KB/s")
            else:
                current_bytes = net_io.bytes_sent + net_io.bytes_recv
                current_sent = net_io.bytes_sent
                current_recv = net_io.bytes_recv

                bytes_per_sec = (current_bytes - self.last_net_bytes) / 2
                upload_per_sec = (current_sent - self.last_net_sent) / 2
                download_per_sec = (current_recv - self.last_net_recv) / 2

                self.last_net_bytes = current_bytes
                self.last_net_sent = current_sent
                self.last_net_recv = current_recv

                # Общая сеть
                if bytes_per_sec < 1024:
                    self.net_value.setText(f"{bytes_per_sec:.0f} B/s")
                elif bytes_per_sec < 1024 ** 2:
                    self.net_value.setText(f"{bytes_per_sec / 1024:.1f} KB/s")
                else:
                    self.net_value.setText(f"{bytes_per_sec / (1024 ** 2):.1f} MB/s")

                # Upload
                if upload_per_sec < 1024:
                    self.upload_value.setText(f"{upload_per_sec:.0f} B/s")
                elif upload_per_sec < 1024 ** 2:
                    self.upload_value.setText(f"{upload_per_sec / 1024:.1f} KB/s")
                else:
                    self.upload_value.setText(f"{upload_per_sec / (1024 ** 2):.1f} MB/s")

                # Download
                if download_per_sec < 1024:
                    self.download_value.setText(f"{download_per_sec:.0f} B/s")
                elif download_per_sec < 1024 ** 2:
                    self.download_value.setText(f"{download_per_sec / 1024:.1f} KB/s")
                else:
                    self.download_value.setText(f"{download_per_sec / (1024 ** 2):.1f} MB/s")

            # GPU - пробуем nvidia-smi
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
                )
                if result.returncode == 0 and result.stdout.strip():
                    gpu_usage = result.stdout.strip()
                    self.gpu_value.setText(f"{gpu_usage}%")
                else:
                    self.gpu_value.setText("N/A")
            except:
                self.gpu_value.setText("N/A")

            # RAM
            ram = psutil.virtual_memory()
            ram_used = ram.used / (1024 ** 3)
            ram_percent = ram.percent
            self.ram_value.setText(f"{ram_used:.1f} GB ({ram_percent:.0f}%)")

            # SWAP
            swap = psutil.swap_memory()
            self.swap_value.setText(f"{swap.percent:.1f}%")

            # Температура - пробуем разные методы
            temp_found = False

            # Метод 1: nvidia-smi для GPU температуры
            if not temp_found:
                try:
                    result = subprocess.run(
                        ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'],
                        capture_output=True,
                        text=True,
                        timeout=1,
                        creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        gpu_temp = result.stdout.strip()
                        if gpu_temp.replace('.', '').isdigit():
                            self.temp_value.setText(f"{gpu_temp}°C")
                            temp_found = True
                except:
                    pass

            # Метод 2: psutil sensors (Linux)
            if not temp_found and hasattr(psutil, 'sensors_temperatures'):
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            if entries and entries[0].current > 0:
                                temp_value = entries[0].current
                                self.temp_value.setText(f"{temp_value:.0f}°C")
                                temp_found = True
                                break
                except:
                    pass

            if not temp_found:
                self.temp_value.setText("--°C")

        except Exception as e:
            print(f"Error updating data: {e}")

    def paintEvent(self, event):
        """Рисуем черную полупрозрачную панель с тенью"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Тень
        for i in range(4):
            shadow_opacity = 40 - i * 8
            painter.setBrush(QColor(0, 0, 0, shadow_opacity))
            painter.setPen(Qt.PenStyle.NoPen)
            shadow_rect = self.rect().adjusted(-i, -i, i, i)
            painter.drawRect(shadow_rect)

        # Основной фон - черный полупрозрачный
        painter.setBrush(QColor(0, 0, 0, 220))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        # Тонкая граница справа
        painter.setPen(QColor(255, 255, 255, 10))
        painter.drawLine(
            self.width() - 1, 0,
            self.width() - 1, self.height()
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiquidGlassWindow()
    window.show()
    sys.exit(app.exec())