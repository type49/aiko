#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностический скрипт для отладки проблемы Shiboken::Conversions
"""

import sys
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication


class SignalTester(QObject):
    """Тестер для проверки передачи типов в сигналы"""

    # Сигналы с разными типами
    signal_str = Signal(str)
    signal_bool = Signal(bool)
    signal_str_bool = Signal(str, bool)
    signal_object = Signal(object)

    def __init__(self):
        super().__init__()

        # Подключаем слоты
        self.signal_str.connect(self.on_str)
        self.signal_bool.connect(self.on_bool)
        self.signal_str_bool.connect(self.on_str_bool)
        self.signal_object.connect(self.on_object)

    @Slot(str)
    def on_str(self, value):
        print(f"✓ Received str: {type(value).__name__} = '{value}'")

    @Slot(bool)
    def on_bool(self, value):
        print(f"✓ Received bool: {type(value).__name__} = {value}")

    @Slot(str, bool)
    def on_str_bool(self, s, b):
        print(f"✓ Received str+bool: {type(s).__name__}='{s}', {type(b).__name__}={b}")

    @Slot(object)
    def on_object(self, value):
        print(f"✓ Received object: {type(value).__name__} = {value}")

    def test_valid_types(self):
        """Тест корректных типов"""
        print("\n=== ТЕСТ КОРРЕКТНЫХ ТИПОВ ===")

        try:
            print("1. Отправка str...")
            self.signal_str.emit("test")
        except Exception as e:
            print(f"✗ Ошибка: {e}")

        try:
            print("2. Отправка bool...")
            self.signal_bool.emit(True)
        except Exception as e:
            print(f"✗ Ошибка: {e}")

        try:
            print("3. Отправка str + bool...")
            self.signal_str_bool.emit("active", True)
        except Exception as e:
            print(f"✗ Ошибка: {e}")

    def test_invalid_types(self):
        """Тест некорректных типов - вызовут ошибку Shiboken"""
        print("\n=== ТЕСТ НЕКОРРЕКТНЫХ ТИПОВ (ОЖИДАЮТСЯ ОШИБКИ) ===")

        try:
            print("1. Отправка None в signal_str...")
            self.signal_str.emit(None)  # ОШИБКА!
        except Exception as e:
            print(f"✗ Ошибка (ожидаемо): {e}")

        try:
            print("2. Отправка int в signal_str...")
            self.signal_str.emit(123)  # ОШИБКА!
        except Exception as e:
            print(f"✗ Ошибка (ожидаемо): {e}")

        try:
            print("3. Отправка str в signal_bool...")
            self.signal_bool.emit("not a bool")  # ОШИБКА!
        except Exception as e:
            print(f"✗ Ошибка (ожидаемо): {e}")

        try:
            print("4. Отправка (None, True) в signal_str_bool...")
            self.signal_str_bool.emit(None, True)  # ОШИБКА!
        except Exception as e:
            print(f"✗ Ошибка (ожидаемо): {e}")

        try:
            print("5. Отправка ('test', 'not bool') в signal_str_bool...")
            self.signal_str_bool.emit("test", "not bool")  # ОШИБКА!
        except Exception as e:
            print(f"✗ Ошибка (ожидаемо): {e}")

    def test_type_conversions(self):
        """Тест автоматической конвертации типов"""
        print("\n=== ТЕСТ КОНВЕРТАЦИИ ТИПОВ ===")

        try:
            print("1. Отправка int как bool (должно работать)...")
            self.signal_bool.emit(1)  # Должно конвертироваться в True
        except Exception as e:
            print(f"✗ Ошибка: {e}")

        try:
            print("2. Отправка 0 как bool (должно работать)...")
            self.signal_bool.emit(0)  # Должно конвертироваться в False
        except Exception as e:
            print(f"✗ Ошибка: {e}")

    def test_with_explicit_conversion(self):
        """Тест с явной конвертацией (ПРАВИЛЬНЫЙ СПОСОБ)"""
        print("\n=== ТЕСТ С ЯВНОЙ КОНВЕРТАЦИЕЙ (ПРАВИЛЬНО) ===")

        # Симулируем ситуацию где может быть None
        value = None

        try:
            print("1. Проверка и конвертация перед emit...")
            if value is None:
                value = "idle"  # Значение по умолчанию

            # Явная конвертация
            safe_value = str(value)
            self.signal_str.emit(safe_value)
        except Exception as e:
            print(f"✗ Ошибка: {e}")

        try:
            print("2. Защита от None в паре значений...")
            s_val = None
            b_val = "not bool"

            # Проверка и конвертация
            if s_val is None or not isinstance(s_val, str):
                s_val = "default"
            if b_val is None or not isinstance(b_val, bool):
                b_val = bool(b_val) if b_val else False

            self.signal_str_bool.emit(str(s_val), bool(b_val))
        except Exception as e:
            print(f"✗ Ошибка: {e}")


def main():
    """Основная функция"""
    print("=" * 60)
    print("ДИАГНОСТИКА ПРОБЛЕМЫ Shiboken::Conversions")
    print("=" * 60)

    app = QApplication(sys.argv)
    tester = SignalTester()

    # Запускаем тесты
    tester.test_valid_types()
    tester.test_invalid_types()
    tester.test_type_conversions()
    tester.test_with_explicit_conversion()

    print("\n" + "=" * 60)
    print("РЕЗЮМЕ:")
    print("=" * 60)
    print("✓ Для избежания ошибки Shiboken ВСЕГДА:")
    print("  1. Проверяйте что значение не None")
    print("  2. Проверяйте тип с isinstance()")
    print("  3. Явно конвертируйте: str(value), bool(value)")
    print("  4. Используйте значения по умолчанию для None")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())