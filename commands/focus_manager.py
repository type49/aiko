import re
import time
import pygetwindow as gw
from interfaces import AikoCommand
from utils.audio_player import audio_manager


class FocusManager(AikoCommand):
    def __init__(self):
        self.type = "focus_manager"
        self.is_active = False
        self.last_check_time = 0
        self.check_interval = 5  # В режиме фокуса проверяем чаще (раз в 15 сек)
        self.distractors = ["youtube", "vkontakte", "telegram", "netflix", "twitch", "instagram", "facebook"]
        self.browsers = ["chrome", "firefox", "edge", "opera", "browser", "yandex"]

    def execute(self, text, ctx):
        text_lower = text.lower()

        if "режим концентрации" in text_lower or "режим фокуса" in text_lower:
            if "выключи" in text_lower or "отмени" in text_lower or "стоп" in text_lower:
                self.is_active = False
                ctx.ui_log("Режим концентрации ВЫКЛЮЧЕН. Свобода.", "info")
                return True

            self.is_active = True
            ctx.ui_log("РЕЖИМ КОНЦЕНТРАЦИИ АКТИВИРОВАН. Я слежу за тобой.", "cmd")
            audio_manager.play("assets/sound/alarm.wav", volume=0.3)
            return True
        return False

    def on_tick(self, ctx):
        """Метод, который ядро будет дергать в каждом цикле"""
        if not self.is_active:
            return

        curr_t = time.time()
        if curr_t - self.last_check_time < self.check_interval:
            return

        self.last_check_time = curr_t
        try:
            window = gw.getActiveWindow()
            if not window: return

            title = window.title.lower()

            # Проверяем на отвлечения
            for d in self.distractors:
                if d in title:
                    print(f"[FOCUS]: Нарушение! Обнаружен {d}")
                    self._punish(ctx, d)
                    break
        except Exception as e:
            print(f"[FOCUS ERROR]: {e}")

    def _punish(self, ctx, site):
        if hasattr(ctx, 'ui_log'):
            ctx.ui_log(f"ВЕРНИСЬ К РАБОТЕ! {site.upper()} под запретом.", "error")
        audio_manager.play("assets/sound/alarm.wav", volume=0.6)