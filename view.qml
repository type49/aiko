import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QDateTime, QRectF, QPoint, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPixmap, QPainterPath, QTransform

try:
    myappid = 'strategy.advisor.adaptive.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass


class CharacterWidget(QWidget):
    """Отдельный виджет для персонажа с анимациями"""

    def __init__(self, parent=None, character_path=None):
        super().__init__(parent)

        # Делаем виджет прозрачным для фона
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Загрузка изображения персонажа
        self.character_pixmap = None
        if character_path and os.path.exists(character_path):
            self.character_pixmap = QPixmap(character_path)

        def update_mask(self):
            mask = self.pixmap.mask()  # альфа PNG
            self.setMask(mask)
        # --- АНИМАЦИЯ ДЛЯ ПЕРСОНАЖА ---
        # Масштаб персонажа (для эффекта hover)
        # Изначально 0.95 (95%), чтобы при увеличении до 1.0 (100%) не обрезалось
        self._character_scale = 0.95
        self.character_scale_animation = QPropertyAnimation(self, b"character_scale")
        self.character_scale_animation.setDuration(200)
        self.character_scale_animation.setEasingCurve(QEasingCurve.OutCubic)

        # Поворот персонажа (для эффекта клика)
        self._character_rotation = 0.0
        self.character_rotation_animation = QPropertyAnimation(self, b"character_rotation")
        self.character_rotation_animation.setDuration(400)  # Увеличил длительность для плавности
        self.character_rotation_animation.setEasingCurve(QEasingCurve.InOutCubic)  # Плавная кривая вместо Elastic

        # Включаем отслеживание мыши
        self.setMouseTracking(True)

    # --- PROPERTY ДЛЯ АНИМАЦИИ ПЕРСОНАЖА (МАСШТАБ) ---
    def get_character_scale(self):
        return self._character_scale

    def set_character_scale(self, scale):
        self._character_scale = scale
        self.update()  # Перерисовываем виджет

    character_scale = Property(float, get_character_scale, set_character_scale)

    # --- PROPERTY ДЛЯ АНИМАЦИИ ПЕРСОНАЖА (ПОВОРОТ) ---
    def get_character_rotation(self):
        return self._character_rotation

    def set_character_rotation(self, rotation):
        self._character_rotation = rotation
        self.update()  # Перерисовываем виджет

    character_rotation = Property(float, get_character_rotation, set_character_rotation)

    def enterEvent(self, event):
        """При наведении курсора на персонажа - увеличиваем"""
        self.character_scale_animation.stop()
        self.character_scale_animation.setStartValue(self._character_scale)
        self.character_scale_animation.setEndValue(1.0)  # Увеличиваем до 100%
        self.character_scale_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """При уходе курсора с персонажа - уменьшаем"""
        self.character_scale_animation.stop()
        self.character_scale_animation.setStartValue(self._character_scale)
        self.character_scale_animation.setEndValue(0.95)  # Возвращаем к 95%
        self.character_scale_animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """При клике на персонажа - поворачиваем"""
        # ЗАГЛУШКА: Плавно поворачиваем персонажа на 5 градусов и обратно
        self.character_rotation_animation.stop()
        self.character_rotation_animation.setDuration(600)  # Общая длительность
        self.character_rotation_animation.setStartValue(0.0)
        self.character_rotation_animation.setKeyValueAt(0.5, 5.0)  # В середине - максимальный поворот
        self.character_rotation_animation.setEndValue(0.0)  # В конце - возврат
        self.character_rotation_animation.start()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Отрисовка персонажа"""
        if not self.character_pixmap or self.character_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Масштабируем картинку под текущую высоту виджета
        scaled_pixmap = self.character_pixmap.scaledToHeight(
            self.height(),
            Qt.SmoothTransformation
        )

        # Позиция персонажа (справа в виджете)
        char_x = self.width() - scaled_pixmap.width()
        char_y = 0

        # Центр персонажа для трансформаций
        char_center_x = char_x + scaled_pixmap.width() / 2
        char_center_y = char_y + scaled_pixmap.height() / 2

        # Перемещаем точку отсчёта в центр персонажа
        painter.translate(char_center_x, char_center_y)

        # Применяем масштабирование (эффект hover)
        painter.scale(self._character_scale, self._character_scale)

        # Применяем поворот (эффект клика)
        painter.rotate(self._character_rotation)

        # Возвращаем точку отсчёта обратно
        painter.translate(-char_center_x, -char_center_y)

        # Рисуем персонажа с применёнными трансформациями
        painter.drawPixmap(char_x, char_y, scaled_pixmap)


class AnimatedButton(QPushButton):
    """Кнопка с анимацией масштабирования"""

    def __init__(self, parent=None, icon_name=None, base_icon_size=40):
        super().__init__(parent)
        self._scale = 1.0
        self.icon_pixmap = None
        self.base_icon_size = base_icon_size  # Базовый размер иконки

        # Загрузка иконки если указано имя
        if icon_name:
            icon_path = os.path.join(os.path.dirname(__file__), f"./assets/images/icons/{icon_name}.png")
            if os.path.exists(icon_path):
                self.icon_pixmap = QPixmap(icon_path)

        # Анимация масштаба
        self.scale_animation = QPropertyAnimation(self, b"scale")
        self.scale_animation.setDuration(150)
        self.scale_animation.setEasingCurve(QEasingCurve.OutCubic)

    def set_icon(self, icon_name):
        """Установка иконки по имени файла"""
        icon_path = os.path.join(os.path.dirname(__file__), f"{icon_name}.png")
        if os.path.exists(icon_path):
            self.icon_pixmap = QPixmap(icon_path)
            self.update()

    def get_scale(self):
        return self._scale

    def set_scale(self, scale):
        self._scale = scale
        self.update()

    scale = Property(float, get_scale, set_scale)

    def enterEvent(self, event):
        """При наведении увеличиваем до 120%"""
        self.scale_animation.stop()
        self.scale_animation.setStartValue(self._scale)
        self.scale_animation.setEndValue(1.2)
        self.scale_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """При уходе возвращаем к 100%"""
        self.scale_animation.stop()
        self.scale_animation.setStartValue(self._scale)
        self.scale_animation.setEndValue(1.0)
        self.scale_animation.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """При нажатии уменьшаем до 90%"""
        self.scale_animation.stop()
        self.scale_animation.setStartValue(self._scale)
        self.scale_animation.setEndValue(0.9)
        self.scale_animation.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """При отпускании возвращаем к 120% (hover состояние)"""
        self.scale_animation.stop()
        self.scale_animation.setStartValue(self._scale)
        self.scale_animation.setEndValue(1.2)
        self.scale_animation.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Отрисовка с масштабированием от центра"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = self.rect()
        center = rect.center()

        # Рисуем иконку если есть
        if self.icon_pixmap and not self.icon_pixmap.isNull():
            # Вычисляем размер с учетом масштаба от БАЗОВОГО размера
            scaled_size = int(self.base_icon_size * self._scale)

            # Масштабируем иконку
            scaled_icon = self.icon_pixmap.scaled(
                scaled_size, scaled_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Центрируем иконку в виджете
            icon_x = center.x() - scaled_icon.width() // 2
            icon_y = center.y() - scaled_icon.height() // 2
            painter.drawPixmap(icon_x, icon_y, scaled_icon)
        else:
            # Если иконки нет - рисуем белый фон для отладки (базового размера)
            debug_rect_size = int(self.base_icon_size * self._scale)
            debug_rect = QRectF(
                center.x() - debug_rect_size // 2,
                center.y() - debug_rect_size // 2,
                debug_rect_size,
                debug_rect_size
            )

            if "circle" in self.objectName():
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(debug_rect)
            else:
                painter.setBrush(QColor(255, 255, 255))
                painter.setPen(Qt.NoPen)
                painter.drawRect(debug_rect)


class BlurWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ (БАЗОВЫЕ) ---
        # Расчет scale_factor относительно Full HD (1920)
        screen_geometry = QApplication.primaryScreen().geometry()
        self.scale_factor = screen_geometry.width() / 1920.0

        # Размеры теперь умножаются на коэффициент
        self.content_width = int(1000 * self.scale_factor)
        self.content_height = int(600 * self.scale_factor)
        self.margin = int(15 * self.scale_factor)
        self.character_overflow = int(200 * self.scale_factor)

        # Добавляем небольшой запас для анимации персонажа (5% увеличение)
        # Персонаж занимает примерно 30% ширины, 5% от этого = 1.5% от ширины
        animation_margin = int(20 * self.scale_factor)  # Небольшой запас справа и снизу

        self.window_width = self.content_width + animation_margin
        self.window_height = self.content_height + self.character_overflow + animation_margin

        self.setFixedSize(self.window_width, self.window_height)

        # --- СОЗДАНИЕ ВИДЖЕТА ПЕРСОНАЖА ---
        char_path = os.path.join(os.path.dirname(__file__), 'ai.png')
        self.character_widget = CharacterWidget(self, char_path)
        # Размещаем виджет персонажа на всю высоту окна справа
        self.character_widget.setGeometry(
            0,  # x - на всю ширину окна (персонаж сам выровняется вправо внутри)
            0,  # y - сверху
            self.window_width,  # ширина - на всё окно
            self.window_height  # высота - на всё окно
        )
        # Поднимаем персонажа наверх по z-order (чтобы он был поверх всего)
        self.character_widget.raise_()

        # Загрузка стилей
        self.load_styles()

        self.init_ui()
        self.position_to_bottom_right()

    def load_styles(self):
        """Загрузка QSS стилей"""
        style_path = os.path.join(os.path.dirname(__file__), 'styles.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())

    def position_to_bottom_right(self):
        """Привязка к правому нижнему углу рабочего стола"""
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = screen_geo.x() + screen_geo.width() - self.width()
        y = screen_geo.y() + screen_geo.height() - self.height()
        self.move(x, y)

    def init_ui(self):
        # ======================================================================
        # --- ГЛАВНЫЙ ВИДЖЕТ И ЛЭЙАУТ ---
        # ======================================================================

        # Создаём главный виджет-контейнер для всего содержимого
        main_container = QWidget(self)

        # Главный вертикальный лэйаут (всё содержимое сверху вниз)
        main_vertical_layout = QVBoxLayout(main_container)

        # --- НАСТРОЙКА ОТСТУПОВ ГЛАВНОГО ЛЭЙАУТА ---
        # Можно менять эти значения для изменения отступов от краёв черного прямоугольника
        left_margin = self.margin + int(40 * self.scale_factor)  # Отступ слева
        top_margin = self.character_overflow + self.margin + int(15 * self.scale_factor)  # Отступ сверху (уменьшен)
        right_margin = self.margin + int(40 * self.scale_factor)  # Отступ справа
        bottom_margin = self.margin + int(40 * self.scale_factor)  # Отступ снизу

        main_vertical_layout.setContentsMargins(
            left_margin,
            top_margin,
            right_margin,
            bottom_margin
        )

        # Расстояние между секциями (квадратные кнопки и средняя часть)
        vertical_spacing = int(15 * self.scale_factor)  # Можно менять
        main_vertical_layout.setSpacing(vertical_spacing)

        # ======================================================================
        # --- КВАДРАТНЫЕ КНОПКИ ВВЕРХУ (ГОРИЗОНТАЛЬНЫЙ ЛЭЙАУТ) ---
        # ======================================================================

        # Реальный размер иконки (базовый)
        square_icon_size = int(40 * self.scale_factor)

        # Размер виджета с запасом для анимации увеличения на 20%
        square_widget_size = int(square_icon_size * 1.3)  # +30% запас

        # Расстояние между кнопками
        square_spacing = int(16 * self.scale_factor)

        # Создаём горизонтальный лэйаут для квадратных кнопок
        square_buttons_layout = QHBoxLayout()
        square_buttons_layout.setContentsMargins(0, 0, 0, 0)
        square_buttons_layout.setSpacing(square_spacing)

        # --- Первая квадратная кнопка ---
        self.square_button_1 = AnimatedButton(self, "square1", square_icon_size)
        self.square_button_1.setObjectName("square_button")
        self.square_button_1.setFixedSize(square_widget_size, square_widget_size)
        square_buttons_layout.addWidget(self.square_button_1)

        # --- Вторая квадратная кнопка ---
        self.square_button_2 = AnimatedButton(self, "square2", square_icon_size)
        self.square_button_2.setObjectName("square_button")
        self.square_button_2.setFixedSize(square_widget_size, square_widget_size)
        square_buttons_layout.addWidget(self.square_button_2)

        # --- Третья квадратная кнопка ---
        self.square_button_3 = AnimatedButton(self, "square3", square_icon_size)
        self.square_button_3.setObjectName("square_button")
        self.square_button_3.setFixedSize(square_widget_size, square_widget_size)
        square_buttons_layout.addWidget(self.square_button_3)

        # --- Четвёртая квадратная кнопка ---
        self.square_button_4 = AnimatedButton(self, "square4", square_icon_size)
        self.square_button_4.setObjectName("square_button")
        self.square_button_4.setFixedSize(square_widget_size, square_widget_size)
        square_buttons_layout.addWidget(self.square_button_4)

        # --- Пятая квадратная кнопка ---
        self.square_button_5 = AnimatedButton(self, "square5", square_icon_size)
        self.square_button_5.setObjectName("square_button")
        self.square_button_5.setFixedSize(square_widget_size, square_widget_size)
        square_buttons_layout.addWidget(self.square_button_5)

        # Добавляем растяжку справа, чтобы кнопки были прижаты к левому краю
        square_buttons_layout.addStretch()

        # Добавляем лэйаут квадратных кнопок в главный вертикальный лэйаут
        main_vertical_layout.addLayout(square_buttons_layout)

        # ======================================================================
        # --- СРЕДНЯЯ ЧАСТЬ: КРУГЛЫЕ КНОПКИ + ЧАСЫ + ТЕКСТ ---
        # ======================================================================

        # Создаём горизонтальный лэйаут для средней части
        middle_layout = QHBoxLayout()
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(int(20 * self.scale_factor))

        # --- КРУГЛЫЕ КНОПКИ СЛЕВА (ВЕРТИКАЛЬНЫЙ ЛЭЙАУТ) ---

        # Реальный размер иконки (базовый)
        circle_icon_size = int(48 * self.scale_factor)

        # Размер виджета с запасом для анимации увеличения на 20%
        circle_widget_size = int(circle_icon_size * 1.3)  # +30% запас

        # Расстояние между кнопками
        circle_spacing = int(12 * self.scale_factor)

        # Создаём вертикальный лэйаут для круглых кнопок
        circle_buttons_layout = QVBoxLayout()
        circle_buttons_layout.setContentsMargins(0, 0, 0, 0)
        circle_buttons_layout.setSpacing(circle_spacing)

        # --- Первая круглая кнопка ---
        self.circle_button_1 = AnimatedButton(self, "circle1", circle_icon_size)
        self.circle_button_1.setObjectName("circle_button")
        self.circle_button_1.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_1)

        # --- Вторая круглая кнопка ---
        self.circle_button_2 = AnimatedButton(self, "circle2", circle_icon_size)
        self.circle_button_2.setObjectName("circle_button")
        self.circle_button_2.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_2)

        # --- Третья круглая кнопка ---
        self.circle_button_3 = AnimatedButton(self, "circle3", circle_icon_size)
        self.circle_button_3.setObjectName("circle_button")
        self.circle_button_3.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_3)

        # --- Четвёртая круглая кнопка ---
        self.circle_button_4 = AnimatedButton(self, "circle4", circle_icon_size)
        self.circle_button_4.setObjectName("circle_button")
        self.circle_button_4.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_4)

        # --- Пятая круглая кнопка ---
        self.circle_button_5 = AnimatedButton(self, "circle5", circle_icon_size)
        self.circle_button_5.setObjectName("circle_button")
        self.circle_button_5.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_5)

        # --- Шестая круглая кнопка ---
        self.circle_button_6 = AnimatedButton(self, "circle6", circle_icon_size)
        self.circle_button_6.setObjectName("circle_button")
        self.circle_button_6.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_6)

        # --- Седьмая круглая кнопка ---
        self.circle_button_7 = AnimatedButton(self, "circle7", circle_icon_size)
        self.circle_button_7.setObjectName("circle_button")
        self.circle_button_7.setFixedSize(circle_widget_size, circle_widget_size)
        circle_buttons_layout.addWidget(self.circle_button_7)

        # Добавляем растяжку снизу, чтобы кнопки были прижаты к верхнему краю
        circle_buttons_layout.addStretch()

        # Добавляем лэйаут круглых кнопок в средний горизонтальный лэйаут
        middle_layout.addLayout(circle_buttons_layout)

        # --- БЛОК ЧАСОВ И ТЕКСТА (ВЕРТИКАЛЬНЫЙ ЛЭЙАУТ) ---

        # Создаём вертикальный лэйаут для часов и текста
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(int(10 * self.scale_factor))

        # --- БЛОК ЧАСОВ (вертикальный лэйаут) ---
        time_layout = QVBoxLayout()
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(0)

        # Метка времени (часы и минуты)
        self.time_label = QLabel("00:00", self)
        self.time_label.setObjectName("time_label")
        font_size_time = int(52 * self.scale_factor)
        self.time_label.setStyleSheet(f"font-size: {font_size_time}px;")

        # Метка даты (день недели и дата)
        self.date_label = QLabel("Monday 02/09", self)
        self.date_label.setObjectName("date_label")
        font_size_date = int(15 * self.scale_factor)
        self.date_label.setStyleSheet(f"font-size: {font_size_date}px;")

        # Добавляем метки в вертикальный лэйаут
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.date_label)

        # --- БЛОК ТЕКСТОВ (вертикальный лэйаут) ---
        signal_layout = QVBoxLayout()
        signal_layout.setContentsMargins(0, 0, 0, 0)
        signal_layout.setSpacing(0)

        # Размеры шрифтов для текстов сигнала
        signal_title_font_size = int(18 * self.scale_factor)
        signal_text_font_size = int(14 * self.scale_factor)

        # Заголовок сигнала (когда ожидается следующий сигнал)
        self.signal_title = QLabel("Следующий сигнал через два часа три минуты", self)
        self.signal_title.setObjectName("signal_title")
        self.signal_title.setStyleSheet(f"font-size: {signal_title_font_size}px; margin: 0; padding: 0;")

        # Текст сигнала (описание сигнала)
        self.signal_text = QLabel("Текст сигнала", self)
        self.signal_text.setObjectName("signal_text")
        self.signal_text.setStyleSheet(f"font-size: {signal_text_font_size}px; margin: 0; padding: 0;")

        # Добавляем метки в вертикальный лэйаут
        signal_layout.addWidget(self.signal_title, 0, Qt.AlignLeft | Qt.AlignBottom)
        signal_layout.addWidget(self.signal_text, 0, Qt.AlignLeft | Qt.AlignTop)

        # Добавляем блоки часов и текста в общий info лэйаут
        info_layout.addLayout(time_layout)
        info_layout.addSpacing(int(20 * self.scale_factor))  # Отступ между часами и текстом
        info_layout.addLayout(signal_layout)
        info_layout.addStretch()  # Растяжка снизу

        # Добавляем info лэйаут в средний горизонтальный лэйаут
        middle_layout.addLayout(info_layout)

        # Добавляем растяжку справа в среднем лэйауте
        middle_layout.addStretch()

        # Добавляем средний лэйаут в главный вертикальный лэйаут
        main_vertical_layout.addLayout(middle_layout)

        # Добавляем растяжку снизу в главном вертикальном лэйауте
        main_vertical_layout.addStretch()

        # ======================================================================
        # --- ПРИМЕНЯЕМ ГЛАВНЫЙ КОНТЕЙНЕР ---
        # ======================================================================

        # Позиционируем главный контейнер (занимает всю область черного прямоугольника)
        main_container.setGeometry(
            0,
            0,
            self.content_width,
            self.content_height + self.character_overflow
        )

        # ======================================================================
        # --- ТАЙМЕР ДЛЯ ОБНОВЛЕНИЯ ВРЕМЕНИ ---
        # ======================================================================

        # Создаём таймер, который будет срабатывать каждую секунду
        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)  # 1000 миллисекунд = 1 секунда

        # Обновляем время сразу при запуске
        self.update_time()

    def update_time(self):
        """Обновление текущего времени и даты на экране"""
        current = QDateTime.currentDateTime()
        # Устанавливаем время в формате часы:минуты
        self.time_label.setText(current.toString("hh:mm"))
        # Устанавливаем дату в формате день_недели месяц/день
        self.date_label.setText(current.toString("dddd MM/dd"))
        # Подгоняем размер меток под текст
        self.time_label.adjustSize()
        self.date_label.adjustSize()

    def paintEvent(self, event):
        """Отрисовка всего виджета"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # ======================================================================
        # --- ГЕОМЕТРИЯ ФОНА (ЧЕРНАЯ ПАНЕЛЬ) ---
        # ======================================================================

        # Координаты и размеры черной панели
        content_x = self.margin
        content_y = self.character_overflow + self.margin
        content_w = self.content_width - 2 * self.margin
        content_h = self.content_height - 2 * self.margin

        # Прямоугольник для фона
        content_rect = QRectF(content_x, content_y, content_w, content_h)

        # Радиус скругления углов
        radius = 30 * self.scale_factor

        # Создаём путь с закруглёнными углами для клипа
        clip_path = QPainterPath()
        clip_path.addRoundedRect(content_rect, radius, radius)

        # ======================================================================
        # --- 1. ТЕНЬ (МНОГОСЛОЙНАЯ ДЛЯ ГЛУБИНЫ) ---
        # ======================================================================

        painter.save()
        # Рисуем 12 слоёв тени с уменьшающейся прозрачностью
        for i in range(12):
            opacity = 50 - i * 4  # Прозрачность уменьшается с каждым слоем
            painter.setBrush(QColor(0, 0, 0, opacity))
            painter.setPen(Qt.NoPen)

            # Каждый слой немного больше предыдущего
            expand = i * 0.5 * self.scale_factor
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                content_rect.adjusted(-expand, -expand, expand, expand),
                radius + expand, radius + expand
            )
            painter.drawPath(shadow_path)
        painter.restore()

        # ======================================================================
        # --- 2. ЧЕРНЫЙ ФОН С ПРОЗРАЧНОСТЬЮ ---
        # ======================================================================

        painter.save()
        # Ограничиваем рисование областью с закруглёнными углами
        painter.setClipPath(clip_path)
        # Рисуем чёрный полупрозрачный фон
        painter.fillRect(content_rect, QColor(0, 0, 0, 160))
        painter.restore()

        # Персонаж теперь рисуется отдельным виджетом CharacterWidget


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    widget = BlurWidget()
    widget.show()

    sys.exit(app.exec())