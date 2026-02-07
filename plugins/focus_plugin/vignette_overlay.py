import ctypes
from ctypes import wintypes
import threading
import time


class VignetteOverlay:
    """Плавное затемнение всего экрана"""

    # ========== НАСТРОЙКИ ==========
    MAX_DARKNESS = 160  # Максимальное затемнение (0-255, больше = темнее)
    ANIMATION_STEPS = 15  # Плавность анимации (больше = плавнее)

    # ===============================

    def __init__(self):
        self.is_pulsing = False
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32

    def pulse(self, duration=1.5, intensity=0.7, count=3):
        """
        Плавное затемнение экрана

        Args:
            duration: Длительность ОДНОГО цикла затемнения (секунды)
            intensity: Интенсивность затемнения (0.0-1.0)
            count: Количество миганий (1-10)
        """
        if self.is_pulsing:
            return

        threading.Thread(target=self._darken, args=(duration, intensity, count), daemon=True).start()

    def _darken(self, duration, intensity, count):
        """Затемняет и возвращает экран несколько раз"""
        self.is_pulsing = True
        hwnd = None

        try:
            screen_width = self.user32.GetSystemMetrics(0)
            screen_height = self.user32.GetSystemMetrics(1)

            # Стили окна
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_TOPMOST = 0x8
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x80
            WS_POPUP = 0x80000000

            # Создаём окно
            hwnd = self.user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
                "Static",
                0, WS_POPUP,
                0, 0, screen_width, screen_height,
                0, 0, 0, 0
            )

            if not hwnd:
                print(f"Ошибка создания окна: {ctypes.get_last_error()}")
                return

            # Чёрный цвет для затемнения
            black_color = 0x00000000

            # Устанавливаем чёрный цвет
            self.user32.SetLayeredWindowAttributes(hwnd, 0, 0, 0x1)

            # Показываем окно
            SW_SHOWNA = 8
            self.user32.ShowWindow(hwnd, SW_SHOWNA)
            self.user32.UpdateWindow(hwnd)

            # Получаем DC и заливаем чёрным
            hdc = self.user32.GetDC(hwnd)
            brush = self.gdi32.CreateSolidBrush(black_color)
            rect = wintypes.RECT(0, 0, screen_width, screen_height)
            self.user32.FillRect(hdc, ctypes.byref(rect), brush)

            # Вычисляем параметры
            max_alpha = int(self.MAX_DARKNESS * intensity)
            step_duration = duration / (self.ANIMATION_STEPS * 2)

            # ЦИКЛ МИГАНИЙ
            for pulse_num in range(count):
                if not self.is_pulsing:
                    break

                # Фаза 1: Плавное затемнение (0 → max_alpha)
                for i in range(self.ANIMATION_STEPS):
                    if not self.is_pulsing:
                        break

                    alpha = int((i / self.ANIMATION_STEPS) * max_alpha)
                    self.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, 0x2)
                    time.sleep(step_duration)

                # Фаза 2: Плавное возвращение (max_alpha → 0)
                for i in range(self.ANIMATION_STEPS, -1, -1):
                    if not self.is_pulsing:
                        break

                    alpha = int((i / self.ANIMATION_STEPS) * max_alpha)
                    self.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, 0x2)
                    time.sleep(step_duration)

                # Пауза между миганиями (кроме последнего)
                if pulse_num < count - 1:
                    time.sleep(0.1)

            # Очистка
            self.gdi32.DeleteObject(brush)
            self.user32.ReleaseDC(hwnd, hdc)

        except Exception as e:
            print(f"Ошибка затемнения: {e}")
            import traceback
            traceback.print_exc()

        finally:
            if hwnd:
                self.user32.DestroyWindow(hwnd)
            self.is_pulsing = False

    def hide(self):
        self.is_pulsing = False

    def destroy(self):
        self.is_pulsing = False