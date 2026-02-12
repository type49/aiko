import sys
import os
import json
import random
from datetime import datetime
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QIcon, QPainter, QBrush, QColor, QPainterPath, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QLineEdit, QPushButton, QLabel, QHBoxLayout,
                               QScrollArea, QFrame, QGraphicsDropShadowEffect)
from llama_cpp import Llama
from core.global_context import ctx
import utils.audio_player
from utils.audio_player import audio_manager


# --- МЕНЕДЖЕР ИСТОРИИ ---
class HistoryManager:
    def __init__(self, history_file="data/chat_history.json"):
        self.history_file = history_file
        self.system_prompt = {
            "role": "system",
            "content": """Ты Айко — дерзкая AI-девушка. Говори о себе в женском роде. 
Отвечай КОРОТКО (1-2 предложения). Будь остроумной, используй легкую иронию. 
Называй пользователя "киса" иногда. НЕ повторяйся. НЕ используй нумерованные списки."""
        }

    def load_history(self):
        """Загрузить историю из файла"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    messages = data.get('messages', [])

                    # Проверяем на глюки в истории
                    for msg in messages:
                        content = msg.get('content', '')
                        if any(x in content.lower() for x in ['шаг:', 'пункт!', 'истина в любом', 'твой выбор:']):
                            print("⚠️ Обнаружена глючная история! Очищаю...")
                            self.clear_history()
                            return [self.system_prompt]

                    # Всегда добавляем системный промпт в начало
                    return [self.system_prompt] + messages
            except Exception as e:
                print(f"⚠️ Ошибка загрузки истории: {e}")
                return [self.system_prompt]
        return [self.system_prompt]

    def save_history(self, history):
        """Сохранить историю в файл (без системного промпта)"""
        try:
            # Сохраняем все кроме системного промпта
            messages_to_save = [msg for msg in history if msg['role'] != 'system']

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'messages': messages_to_save,
                    'last_updated': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def clear_history(self):
        """Очистить историю"""
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
            print("✅ История очищена")


# --- ПОТОК ГЕНЕРАЦИИ (ИСПРАВЛЕННЫЙ) ---
class AikoWorker(QThread):
    finished = Signal(str)

    def __init__(self, model, history):
        super().__init__()
        self.model = model
        self.history = history
        self.user_input = ""

    def run(self):
        try:
            # БЕРЕМ ТОЛЬКО ПОСЛЕДНИЕ 4 ПАРЫ СООБЩЕНИЙ (не больше!)
            system_msg = next((msg for msg in self.history if msg['role'] == 'system'), None)
            recent_history = [msg for msg in self.history if msg['role'] != 'system']

            # Ограничиваем до 4 последних пар (8 сообщений)
            recent_history = recent_history[-8:] if len(recent_history) > 8 else recent_history

            # МАКСИМАЛЬНО ПРОСТОЙ ПРОМПТ
            messages = []

            if system_msg:
                messages.append(f"System: {system_msg['content']}\n")

            for msg in recent_history:
                role = "User" if msg['role'] == 'user' else "Aiko"
                messages.append(f"{role}: {msg['content']}")

            messages.append(f"User: {self.user_input}")
            messages.append("Aiko:")

            full_prompt = "\n".join(messages)

            # ДЕБАГ - выводим промпт
            print("\n" + "=" * 60)
            print("ПРОМПТ (последние 300 символов):")
            print(full_prompt[-300:])
            print("=" * 60 + "\n")

            # МИНИМАЛЬНЫЕ ПАРАМЕТРЫ (самые безопасные)
            res = self.model(
                full_prompt,
                max_tokens=100,  # Урезал для стабильности
                temperature=0.8,
                top_p=0.9,
                top_k=30,
                repeat_penalty=1.3,  # Против зацикливания
                stop=["User:", "user:", "System:"],
                echo=False,
                stream=False
            )

            answer = res["choices"][0]["text"].strip()

            # ЧИСТИМ ОТВЕТ от мусора
            # Убираем повторяющиеся строки
            lines = answer.split('\n')
            unique_lines = []
            seen = set()

            for line in lines:
                clean_line = line.strip()
                if clean_line and clean_line not in seen and len(unique_lines) < 3:
                    unique_lines.append(clean_line)
                    seen.add(clean_line)

            answer = ' '.join(unique_lines)

            # Обрезаем если слишком длинный
            if len(answer) > 200:
                answer = answer[:200].rsplit(' ', 1)[0] + "..."

            # Если пустой или мусор
            if not answer or len(answer) < 3:
                fallback_responses = [
                    "Хм, что-то я задумалась...",
                    "Секунду, мысли собираю 🤔",
                    "Эм... переспроши?",
                    "Сорри, отвлеклась на секунду"
                ]
                answer = random.choice(fallback_responses)

            print(f"✅ ОТВЕТ: {answer}\n")
            self.finished.emit(answer)

        except Exception as e:
            print(f"❌ ОШИБКА ГЕНЕРАЦИИ: {e}")
            self.finished.emit("Ой, что-то пошло не так... Давай попробуем ещё раз?")


class ModelLoader(QThread):
    """Поток для асинхронной загрузки модели LLM"""
    finished = Signal(object)  # Передаем загруженную модель
    progress = Signal(str)  # Сообщения о прогрессе

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path

    def run(self):
        """Загрузка модели в фоновом потоке"""
        try:
            self.progress.emit("Загрузка модели...")

            from llama_cpp import Llama

            llm = Llama(
                model_path=self.model_path,
                n_threads=2,
                n_ctx=1024,
                verbose=False
            )

            self.progress.emit("Модель загружена!")
            self.finished.emit(llm)

        except Exception as e:
            self.progress.emit(f"Ошибка загрузки: {e}")
            self.finished.emit(None)


# --- КРУГЛАЯ АВАТАРКА ---
class AvatarLabel(QLabel):
    def __init__(self, image_path, size=40):
        super().__init__()
        self.setFixedSize(size, size)
        target = QPixmap(size, size)
        target.fill(Qt.GlobalColor.transparent)

        if os.path.exists(image_path):
            p = QPixmap(image_path).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                           Qt.TransformationMode.SmoothTransformation)
        else:
            # Создаем простую заглушку
            p = QPixmap(size, size)
            p.fill(QColor(100, 100, 150))

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, p)
        painter.end()
        self.setPixmap(target)


# --- ОБЛАЧКО СООБЩЕНИЯ С ХВОСТИКОМ ---
class ChatBubble(QWidget):
    def __init__(self, text, timestamp, is_user=True):
        super().__init__()
        self.text = text
        self.timestamp = timestamp
        self.is_user = is_user

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(0)

        # Создаем контейнер для текста и времени
        bubble_container = QWidget()
        bubble_container.setStyleSheet("background: transparent;")
        bubble_layout = QVBoxLayout(bubble_container)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        bubble_layout.setSpacing(2)

        # Текст сообщения
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_label.setFont(QFont("Segoe UI", 10))

        bg_color = "rgba(0, 120, 254, 255)" if is_user else "rgba(43, 43, 43, 255)"
        text_color = "white"

        text_label.setStyleSheet(f"""
            background-color: {bg_color};
            color: {text_color};
            border-radius: 12px;
            padding: 8px 12px;
        """)

        # Время отправки
        time_label = QLabel(timestamp)
        time_label.setFont(QFont("Segoe UI", 8))
        time_label.setStyleSheet("""
            color: rgba(255, 255, 255, 100);
            background: transparent;
            padding: 2px 12px 4px 12px;
        """)

        if is_user:
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        bubble_layout.addWidget(text_label)
        bubble_layout.addWidget(time_label)

        if is_user:
            layout.addStretch()
            layout.addWidget(bubble_container)
        else:
            layout.addWidget(bubble_container)
            layout.addStretch()

    def paintEvent(self, event):
        """Рисуем хвостик у сообщения"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.is_user:
            # Хвостик справа (синий)
            painter.setBrush(QColor(0, 120, 254))
            painter.setPen(Qt.PenStyle.NoPen)

            path = QPainterPath()
            x = self.width() - 20
            y = 12

            path.moveTo(x, y)
            path.lineTo(x + 8, y + 5)
            path.lineTo(x, y + 10)
            path.closeSubpath()

            painter.drawPath(path)
        else:
            # Хвостик слева (серый)
            painter.setBrush(QColor(43, 43, 43))
            painter.setPen(Qt.PenStyle.NoPen)

            path = QPainterPath()
            x = 20
            y = 12

            path.moveTo(x, y)
            path.lineTo(x - 8, y + 5)
            path.lineTo(x, y + 10)
            path.closeSubpath()

            painter.drawPath(path)

        super().paintEvent(event)


# --- ГЛАВНОЕ ОКНО ---
class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aiko Messenger")

        # Менеджер истории
        self.history_manager = HistoryManager()

        # Геометрия окна - левый нижний угол
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.panel_width = int(screen_geo.width() * 0.2)  # 20% ширины экрана
        self.panel_height = int(screen_geo.height() * 0.7)  # 70% высоты

        self.visible_x = screen_geo.x()
        self.hidden_x = screen_geo.x() - self.panel_width
        self.visible_y = screen_geo.y() + screen_geo.height() - self.panel_height

        self.resize(self.panel_width, self.panel_height)
        self.move(self.visible_x, self.visible_y)
        self.is_hidden = False

        # Убираем стандартные элементы Windows, но оставляем обычное окно (не поверх всех)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )

        # Прозрачный фон для скругленных краев
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
        """)

        # Инициализация LLM
        # ИСПРАВЛЕНИЕ: Асинхронная загрузка модели
        self.llm = None  # Пока модель не загружена
        self.model_loading = True

        model_path = "../AiKo/models/qwen2.5-3b-instruct.Q8_0.gguf"
        if os.path.exists(model_path):
            # Создаем поток загрузки
            self.model_loader = ModelLoader(model_path)
            self.model_loader.finished.connect(self._on_model_loaded)
            self.model_loader.progress.connect(self._on_model_progress)
            self.model_loader.start()

            print("📄 Запущена загрузка модели в фоне...")
        else:
            self.model_loading = False
            print(f"⚠️ Модель не найдена: {model_path}")

        # Загружаем историю
        self.history = self.history_manager.load_history()
        self.message_count = len([m for m in self.history if m['role'] != 'system']) // 2

        self.central = QWidget()
        self.central.setStyleSheet("""
            QWidget {
                background: #0f0f0f;
                border-radius: 12px;
            }
        """)
        self.setCentralWidget(self.central)
        self.main_layout = QVBoxLayout(self.central)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # --- HEADER (ВЕРХНЯЯ ПАНЕЛЬ) ---
        self.header = QFrame()
        self.header.setFixedHeight(70)
        self.header.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a; 
                border-bottom: 1px solid #2a2a2a;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 10, 15, 10)

        # Аватарка
        avatar_path = "assets/images/aiko_avatar.png"
        self.avatar = AvatarLabel(avatar_path, 45)
        header_layout.addWidget(self.avatar)

        # Имя и Статус
        name_status_layout = QVBoxLayout()
        name_status_layout.setSpacing(2)

        self.name_label = QLabel("Айко")
        self.name_label.setFont(QFont("Segoe UI Semibold", 14))
        self.name_label.setStyleSheet("color: white; border: none;")

        self.status_label = QLabel("онлайн")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: #00ff00; border: none;")

        name_status_layout.addWidget(self.name_label)
        name_status_layout.addWidget(self.status_label)
        name_status_layout.addStretch()

        header_layout.addLayout(name_status_layout)
        header_layout.addStretch()

        # Кнопка перезагрузки модели
        self.reset_button = QPushButton("🔄")
        self.reset_button.setFixedSize(35, 35)
        self.reset_button.clicked.connect(self.reset_model)
        self.reset_button.setToolTip("Перезагрузить модель")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: rgba(255, 255, 255, 120);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 17px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(100, 200, 255, 180);
                color: white;
                border: 1px solid rgba(100, 200, 255, 200);
            }
        """)

        # Кнопка очистки истории
        self.clear_button = QPushButton("🗑")
        self.clear_button.setFixedSize(35, 35)
        self.clear_button.clicked.connect(self.clear_chat_history)
        self.clear_button.setToolTip("Очистить историю")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: rgba(255, 255, 255, 120);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 17px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255, 150, 0, 180);
                color: white;
                border: 1px solid rgba(255, 150, 0, 200);
            }
        """)

        # Кнопка сворачивания
        self.minimize_button = QPushButton("−")
        self.minimize_button.setFixedSize(35, 35)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: rgba(255, 255, 255, 120);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 17px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 20);
                color: white;
                border: 1px solid rgba(255, 255, 255, 30);
            }
        """)

        # Кнопка закрытия (с анимацией уезжания)
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(35, 35)
        self.close_button.clicked.connect(self.close_with_animation)
        self.close_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: rgba(255, 255, 255, 120);
                border: 1px solid rgba(255, 255, 255, 15);
                border-radius: 17px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(255, 80, 80, 180);
                color: white;
                border: 1px solid rgba(255, 80, 80, 200);
            }
        """)

        header_layout.addWidget(self.reset_button)
        header_layout.addSpacing(5)
        header_layout.addWidget(self.clear_button)
        header_layout.addSpacing(5)
        header_layout.addWidget(self.minimize_button)
        header_layout.addSpacing(5)
        header_layout.addWidget(self.close_button)
        self.main_layout.addWidget(self.header)

        # --- ЗОНА ЧАТА ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: #0f0f0f; border: none;")

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: #0f0f0f;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(3)
        self.chat_layout.addStretch()

        self.scroll.setWidget(self.chat_container)
        self.main_layout.addWidget(self.scroll)

        # --- ВВОД (FOOTER) ---
        self.footer = QFrame()
        self.footer.setStyleSheet("""
            QFrame {
                background: #1a1a1a; 
                padding: 10px; 
                border-top: 1px solid #2a2a2a;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(10, 10, 10, 10)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Напиши мне что-нибудь...")
        self.input_field.setFont(QFont("Segoe UI", 10))
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: #2b2b2b; 
                color: white; 
                border-radius: 20px; 
                padding: 10px 15px; 
                border: 1px solid #3a3a3a;
            }
        """)
        self.input_field.returnPressed.connect(self.send)

        self.btn = QPushButton("➤")
        self.btn.setFixedSize(40, 40)
        self.btn.setFont(QFont("Segoe UI", 16))
        self.btn.setStyleSheet("""
            QPushButton {
                background: #0078fe; 
                color: white; 
                border-radius: 20px;
            }
            QPushButton:hover {
                background: #0066dd;
            }
            QPushButton:pressed {
                background: #0055cc;
            }
        """)
        self.btn.clicked.connect(self.send)

        footer_layout.addWidget(self.input_field)
        footer_layout.addWidget(self.btn)
        self.main_layout.addWidget(self.footer)

        # Worker и Таймер (worker создастся после загрузки модели)

        self.typing_timer = QTimer()
        self.typing_timer.timeout.connect(self.animate_typing)
        self.typing_dots = 0

        # Восстанавливаем историю в UI
        self.restore_chat_history()

    def _on_model_progress(self, message):
        """Обработка сообщений о прогрессе загрузки"""
        print(f"[ModelLoader] {message}")
        # Обновляем статус в GUI
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)

    def _on_model_loaded(self, llm):
        """Вызывается когда модель загружена"""
        self.llm = llm
        self.model_loading = False

        if llm:
            print("✅ Модель загружена успешно!")
            if hasattr(self, 'status_label'):
                self.status_label.setText("онлайн")
                self.status_label.setStyleSheet("color: #00ff00; border: none;")
        else:
            print("❌ Ошибка загрузки модели")
            if hasattr(self, 'status_label'):
                self.status_label.setText("офлайн")
                self.status_label.setStyleSheet("color: #ff0000; border: none;")


    def _on_model_progress(self, message):
        """Обработка прогресса загрузки модели"""
        print(f"[ModelLoader] {message}")
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            if "Загрузка" in message:
                self.status_label.setStyleSheet("color: #FFA500; border: none;")

    def _on_model_loaded(self, llm):
        """Вызывается когда модель загружена"""
        self.llm = llm
        self.model_loading = False

        if llm:
            print("✅ Модель загружена успешно!")

            # ВАЖНО: Создаем worker после загрузки модели
            self.worker = AikoWorker(self.llm, self.history)
            self.worker.finished.connect(self.receive)

            if hasattr(self, 'status_label'):
                self.status_label.setText("онлайн")
                self.status_label.setStyleSheet("color: #00ff00; border: none;")
        else:
            print("❌ Ошибка загрузки модели")
            if hasattr(self, 'status_label'):
                self.status_label.setText("офлайн")
                self.status_label.setStyleSheet("color: #ff0000; border: none;")
    def reset_model(self):
        """Перезагрузка модели (TODO: сделать асинхронной)"""
        print("🔄 Перезагрузка модели...")

        # Устанавливаем флаг загрузки
        self.model_loading = True
        if hasattr(self, 'status_label'):
            self.status_label.setText("Перезагрузка...")
            self.status_label.setStyleSheet("color: #FFA500; border: none;")

        if self.llm:
            del self.llm

        model_path = "../AiKo/models/qwen2.5-3b-instruct.Q8_0.gguf"

        # Пока синхронно (TODO: переделать на ModelLoader)
        self.llm = Llama(
            model_path=model_path,
            n_threads=2,
            n_ctx=1024,
            verbose=False
        )

        if self.llm:
            self.worker = AikoWorker(self.llm, self.history)
            self.worker.finished.connect(self.receive)
            self.model_loading = False
            if hasattr(self, 'status_label'):
                self.status_label.setText("онлайн")
                self.status_label.setStyleSheet("color: #00ff00; border: none;")

        print("✅ Модель перезагружена")

    def restore_chat_history(self):
        """Восстановить сообщения из истории в интерфейс"""
        for msg in self.history:
            if msg['role'] == 'user':
                self.add_bubble(msg['content'], msg.get('timestamp', ''), True, play_sound=False)
            elif msg['role'] == 'assistant':
                self.add_bubble(msg['content'], msg.get('timestamp', ''), False, play_sound=False)

        # Прокручиваем вниз после загрузки
        QTimer.singleShot(100, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))

    def clear_chat_history(self):
        """Очистить всю историю чата"""
        # Очищаем UI
        while self.chat_layout.count() > 1:  # Оставляем stretch
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Очищаем историю
        self.history_manager.clear_history()
        self.history = self.history_manager.load_history()
        self.message_count = 0

        # Обновляем worker
        if self.llm:
            self.worker.history = self.history

        print("✅ История чата очищена")

    def close_with_animation(self):
        """Закрытие с анимацией уезжания влево"""
        # Сохраняем историю перед закрытием
        self.history_manager.save_history(self.history)

        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        current_y = self.pos().y()
        self.animation.setEndValue(QPoint(self.hidden_x, current_y))
        self.animation.finished.connect(self.close)
        self.animation.start()

    def animate_typing(self):
        self.typing_dots = (self.typing_dots + 1) % 4
        self.status_label.setText("печатает" + "." * self.typing_dots)
        self.status_label.setStyleSheet("color: #aaa; font-style: italic; font-size: 12px; border: none;")

    def send(self):
        """Отправка сообщения пользователя"""
        text = self.input_field.text().strip()
        if not text:
            return

        # ИСПРАВЛЕНИЕ: Проверяем загружается ли модель
        if self.model_loading:
            self.add_message("Модель еще загружается, подождите...", False)
            return

        if not self.llm:
            self.add_message("Модель не загружена. Перезагрузите окно.", False)
            return

        timestamp = self.get_timestamp()
        self.add_bubble(text, timestamp, True)

        # Добавляем в историю с временной меткой
        self.history.append({
            "role": "user",
            "content": text,
            "timestamp": timestamp
        })

        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.typing_timer.start(400)
        self.worker.user_input = text
        self.worker.history = self.history  # Обновляем историю в worker
        self.worker.start()

    def receive(self, answer):
        self.typing_timer.stop()
        self.status_label.setText("онлайн")
        self.status_label.setStyleSheet("color: #00ff00; font-size: 10px; border: none;")

        timestamp = self.get_timestamp()
        self.add_bubble(answer, timestamp, False)

        # Добавляем в историю с временной меткой
        self.history.append({
            "role": "assistant",
            "content": answer,
            "timestamp": timestamp
        })

        # Автоочистка старых сообщений (оставляем последние 20 пар + системный промпт)
        self.message_count += 1
        if self.message_count > 20:
            system = next((msg for msg in self.history if msg['role'] == 'system'), None)
            non_system = [msg for msg in self.history if msg['role'] != 'system']
            self.history = [system] + non_system[-40:]  # 40 = 20 пар
            self.message_count = 20

        # Сохраняем историю после каждого ответа
        self.history_manager.save_history(self.history)

        self.input_field.setEnabled(True)
        self.input_field.setFocus()

    def add_bubble(self, text, timestamp, is_user, play_sound=True):
        if play_sound:
            if not is_user:
                audio_manager.play.message()
            else:
                audio_manager.play.message_send()

        bubble = ChatBubble(text, timestamp, is_user)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50,
                          lambda: self.scroll.verticalScrollBar().setValue(
                              self.scroll.verticalScrollBar().maximum()))

    def get_timestamp(self):
        """Возвращает текущее время в формате HH:MM"""
        return datetime.now().strftime("%H:%M")

    def paintEvent(self, event):
        """Рисуем скругленное окно с тенью"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Тень
        for i in range(4):
            shadow_opacity = 40 - i * 8
            painter.setBrush(QColor(0, 0, 0, shadow_opacity))
            painter.setPen(Qt.PenStyle.NoPen)
            shadow_rect = self.rect().adjusted(-i, -i, i, i)
            painter.drawRoundedRect(shadow_rect, 12, 12)

        # Основной фон - темный
        painter.setBrush(QColor(15, 15, 15, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Aiko Messenger")

    window = ChatWindow()
    window.show()
    sys.exit(app.exec())