import time
import pygetwindow as gw
from interfaces import AikoCommand
from utils.audio_player import audio_manager
from utils.matcher import CommandMatcher
from utils.logger import logger


class FocusManager(AikoCommand):
    def __init__(self):
        self.type = "focus_manager"
        self.is_active = False
        self.last_check_time = 0
        self.check_interval = 5  # Интервал проверки окон (сек)

        # Список сайтов и приложений для блокировки
        self.distractors = ["youtube", "vk", "telegram", "netflix", "twitch", "instagram", "facebook", "poker"]

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
        # 1. Считаем скоры для обоих списков через Мэтчер
        # Порог 70 для стопа (чтобы легче было выключить в шуме)
        match_stop, score_stop = CommandMatcher.extract(text, self.stop_triggers, threshold=70)
        # Порог 75 для старта
        match_start, score_start = CommandMatcher.extract(text, self.start_triggers, threshold=75)

        # 2. Сравниваем, какое намерение победило
        # Если фраза больше похожа на команду ОСТАНОВКИ
        if score_stop > score_start and match_stop:
            if not self.is_active:
                ctx.ui_output("Режим концентрации и так выключен.", "info")
                return True

            self.is_active = False


            ctx.ui_output("Режим концентрации ВЫКЛЮЧЕН. Свобода.", "info")
            logger.info(f"FocusManager: Деактивация через '{match_stop}' ({score_stop}%)")

            return True

        # 3. Если фраза больше похожа на команду ЗАПУСКА
        if match_start:
            if self.is_active:
                logger.debug("FocusManager: Попытка повторного включения (уже активен).")
                return True

            self.is_active = True
            ctx.ui_output("РЕЖИМ КОНЦЕНТРАЦИИ АКТИВИРОВАН. Я слежу.", "error")
            # ПРОВЕРЬ ПУТЬ: он должен соответствовать структуре твоего проекта
            audio_manager.play("assets/sound/system/alarm.wav", volume=0.3)
            logger.info(f"FocusManager: Активация через '{match_start}' ({score_start}%)")
            return True

        return False

    def on_tick(self, ctx):
        """Метод вызывается Ядром каждые 5 сек (из scheduler_loop или отдельного тика)"""
        if not self.is_active:
            return

        curr_t = time.time()
        if curr_t - self.last_check_time < self.check_interval:
            return

        self.last_check_time = curr_t
        try:
            window = gw.getActiveWindow()
            if not window:
                return

            title = window.title.lower()

            # Поиск нарушителей в заголовке окна
            for d in self.distractors:
                if d in title:
                    logger.warning(f"FocusManager: Нарушение! Найдено '{d}' в окне '{title}'")
                    self._punish(ctx, d)
                    break
        except Exception as e:
            logger.error(f"FocusManager Tick Error: {e}")

    def _punish(self, ctx, site):
        """Метод наказания при обнаружении отвлекающих факторов"""
        ctx.ui_output(f"ВЕРНИСЬ К РАБОТЕ! {site.upper()} под запретом.", "error")
        # Повышаем громкость для наказания
        audio_manager.play("assets/sound/system/alarm.wav", volume=0.6)