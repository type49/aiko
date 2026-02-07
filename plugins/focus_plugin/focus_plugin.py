import time
import psutil
import pygetwindow as gw
from interfaces import AikoCommand
from utils.audio_player import audio_manager
from utils.matcher import CommandMatcher
from utils.logger import logger
from vignette_overlay import VignetteOverlay

class FocusManager(AikoCommand):
    def __init__(self):
        super().__init__()
        self.type = "focus_manager"
        self.is_active = False
        self.last_check_time = 0
        self.check_interval = 5  # Интервал проверки (сек)
        self.vignette_overlay = VignetteOverlay()  # Создаём обёртку

        # Список сайтов для блокировки (в заголовках окон)
        self.distractors = [
            "youtube", "vk", "telegram", "netflix", "twitch",
            "instagram", "facebook", "poker", "tiktok", "reddit"
        ]

        # Список запрещенных процессов (игры, программы)
        self.blocked_processes = [
            "steam.exe", "steamwebhelper.exe",
            "league of legends.exe", "valorant.exe", "csgo.exe",
            "dota2.exe", "gta5.exe", "minecraft.exe",
            "discord.exe", "spotify.exe",
            # Добавь свои процессы
        ]

        # Намерения на ВКЛЮЧЕНИЕ
        self.start_triggers = [
            "режим концентрации", "включи фокус", "активируй режим фокуса",
            "режим работы", "пора работать", "запусти концентрацию",
            "рабочий режим", "фокус включи"
        ]

        # Намерения на ВЫКЛЮЧЕНИЕ
        self.stop_triggers = [
            "выключи режим концентрации", "стоп фокус", "отмени концентрацию",
            "останови режим фокуса", "хватит следить", "отключи фокус",
            "завершить работу", "выключи концентрацию", "я закончил работать",
            "хватит", "стоп", "сто режим", "отмена"
        ]

    def execute(self, text, ctx):
        # 1. Проверяем команды остановки
        match_stop, score_stop = CommandMatcher.extract(text, self.stop_triggers, threshold=70)
        match_start, score_start = CommandMatcher.extract(text, self.start_triggers, threshold=75)

        # 2. Команда ОСТАНОВКИ
        if score_stop > score_start and match_stop:
            if not self.is_active:
                ctx.ui_output("Режим концентрации и так выключен.", "info")
                return True

            self.is_active = False
            self._hide_vignette()
            ctx.ui_output("Режим концентрации ВЫКЛЮЧЕН. Свобода.", "info")
            logger.info(f"FocusManager: Деактивация через '{match_stop}' ({score_stop}%)")
            return True

        # 3. Команда ЗАПУСКА
        if match_start:
            if self.is_active:
                logger.debug("FocusManager: Попытка повторного включения (уже активен).")
                return True

            self.is_active = True
            ctx.ui_output("РЕЖИМ КОНЦЕНТРАЦИИ АКТИВИРОВАН. Я слежу.", "error")
            audio_manager.play.alarm()
            logger.info(f"FocusManager: Активация через '{match_start}' ({score_start}%)")
            return True

        return False

    def on_tick(self, ctx):
        """Проверка окон и процессов каждые N секунд"""
        if not self.is_active:
            return

        curr_t = time.time()
        if curr_t - self.last_check_time < self.check_interval:
            return

        self.last_check_time = curr_t

        try:
            # Проверка активного окна
            window = gw.getActiveWindow()
            if window:
                title = window.title.lower()
                for d in self.distractors:
                    if d in title:
                        self._punish(ctx, f"сайт {d.upper()}")
                        return

            # Проверка запущенных процессов
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name'].lower()
                    for blocked in self.blocked_processes:
                        if blocked.lower() in proc_name:
                            self._punish(ctx, f"программа {blocked.upper()}")
                            return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            logger.error(f"FocusManager Tick Error: {e}")

    def _punish(self, ctx, violator):
        """Наказание: звук + виньетка + уведомление"""
        ctx.ui_output(f"⚠️ ВЕРНИСЬ К РАБОТЕ! Обнаружен: {violator}", "error")
        audio_manager.play.alarm()

        # Показываем пульсирующую виньетку
        self._show_vignette_pulse()

    def _show_vignette_pulse(self):
        """Показывает пульсирующую виньетку"""
        try:
            self.vignette_overlay.pulse(duration=0.3, intensity=0.7, count=3)
        except Exception as e:
            logger.error(f"Ошибка виньетки: {e}")

