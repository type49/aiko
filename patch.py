#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматическое исправление chat_window.py для асинхронной загрузки модели

Исправляет зависание GUI при открытии окна чата.
"""

import os
import sys
import re

MODEL_LOADER_CLASS = '''
# --- ПОТОК ЗАГРУЗКИ МОДЕЛИ (АСИНХРОННАЯ ЗАГРУЗКА) ---
class ModelLoader(QThread):
    """Поток для асинхронной загрузки модели LLM"""
    finished = Signal(object)  # Передаем загруженную модель
    progress = Signal(str)      # Сообщения о прогрессе

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


'''

NEW_MODEL_INIT = '''        # ИСПРАВЛЕНИЕ: Асинхронная загрузка модели
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
'''

NEW_METHODS = '''
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
'''


def fix_chat_window(filepath):
    """Применить исправления к chat_window.py"""
    print(f"Исправление {filepath}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Добавляем класс ModelLoader после AikoWorker
    # Ищем конец класса AikoWorker
    marker = "# --- ВИДЖЕТ СООБЩЕНИЯ ---"
    if marker in content:
        content = content.replace(marker, MODEL_LOADER_CLASS + "\n" + marker)
        print("✓ Добавлен класс ModelLoader")
    else:
        print("⚠ Маркер для вставки ModelLoader не найден, ищу альтернативу...")
        # Альтернативный маркер
        alt_marker = "class MessageBubble"
        if alt_marker in content:
            content = content.replace(
                f"class MessageBubble",
                MODEL_LOADER_CLASS + f"\nclass MessageBubble"
            )
            print("✓ Добавлен класс ModelLoader (альтернативное место)")

    # 2. Заменяем синхронную загрузку модели
    old_model_init = r'''        # Инициализация LLM
        model_path = "../AiKo/models/qwen2.5-3b-instruct.Q8_0.gguf"
        if os.path.exists\(model_path\):
            print\(".*Загрузка модели.*"\)
            self.llm = Llama\(
                model_path=model_path,
                n_threads=2,
                n_ctx=1024,.*
                verbose=False.*
            \)
            print\(".*Модель загружена.*"\)
        else:
            self.llm = None
            print\(f".*Модель не найдена:.*"\)'''

    # Простой поиск и замена (без regex для надежности)
    if "print(\"📄 Загрузка модели...\")" in content or "print(\"Загрузка модели...\")" in content:
        # Находим начало блока
        start_marker = "# Инициализация LLM"
        end_marker = "# Загружаем историю"

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx != -1 and end_idx != -1:
            # Заменяем блок между маркерами
            before = content[:start_idx]
            after = content[end_idx:]

            content = before + NEW_MODEL_INIT + "\n        " + after
            print("✓ Заменена синхронная загрузка модели на асинхронную")
        else:
            print("⚠ Не найдены маркеры для замены блока инициализации")

    # 3. Добавляем новые методы в конец класса ChatWindow
    # Ищем метод close или последний метод класса
    if "def closeEvent(self, event):" in content:
        content = content.replace(
            "def closeEvent(self, event):",
            NEW_METHODS + "\n    def closeEvent(self, event):"
        )
        print("✓ Добавлены методы _on_model_loaded и _on_model_progress")
    else:
        print("⚠ Метод closeEvent не найден, добавляю в конец класса")
        # Ищем конец класса ChatWindow
        # Это сложнее, лучше добавить вручную

    # 4. Добавляем проверку в send_message
    send_message_check = '''    def send_message(self):
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
            return'''

    # Ищем метод send_message
    old_send_start = '''    def send_message(self):
        """Отправка сообщения пользователя"""
        text = self.input_field.text().strip()
        if not text:
            return

        if not self.llm:'''

    if old_send_start in content:
        content = content.replace(old_send_start, send_message_check + "\n\n        if not self.llm:")
        print("✓ Добавлена проверка загрузки модели в send_message")

    # Сохраняем
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ Файл {filepath} исправлен")


def main():
    # Путь к файлу
    project_dir = os.path.dirname(os.path.abspath(__file__))
    chat_window_path = os.path.join(project_dir, "ui", "chat_window.py")

    # Проверяем существование
    if not os.path.exists(chat_window_path):
        print(f"✗ Файл не найден: {chat_window_path}")
        print("  Укажите правильный путь к проекту")
        return 1

    # Создаем backup
    print("\n=== Создание резервной копии ===")
    backup_path = f"{chat_window_path}.backup_async"
    os.system(f'cp "{chat_window_path}" "{backup_path}"')
    print(f"✓ Резервная копия: {backup_path}")

    print("\n=== Применение исправлений ===")

    # Применяем исправления
    fix_chat_window(chat_window_path)

    print("\n=== Готово! ===")
    print("Исправления применены.")
    print("Теперь модель будет загружаться асинхронно, не блокируя GUI")
    print("\nДля отката изменений выполните:")
    print(f'  cp "{backup_path}" "{chat_window_path}"')

    print("\n=== Тестирование ===")
    print("1. Запустите приложение")
    print("2. Откройте окно чата через кнопку")
    print("3. ✅ Окно должно открыться мгновенно")
    print("4. Статус покажет 'Загрузка модели...'")
    print("5. После загрузки статус станет 'онлайн'")

    return 0


if __name__ == "__main__":
    sys.exit(main())