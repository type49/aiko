import random
import threading
import os
import pygame
from interfaces import AikoCommand

# Скрываем поддержку pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"


class ChatPlugin(AikoCommand):
    def __init__(self):
        pygame.mixer.init()
        # Каждому триггеру соответствует список ПАР (текст, файл)
        self.responses = {
            "как дела": [
                {"text": "Системы в норме. Готова к работе.", "audio": "assets/sounds/status_ok.wav"},
                {"text": "Всё отлично. Жду твоих указаний.", "audio": "assets/sounds/waiting.wav"},
                {"text": "Холодный расчет показывает стабильность.", "audio": "assets/sounds/stable.wav"}
            ],
            "кто ты": [
                {"text": "Я — Айко. Твой стратегический советник. И сюда ещё охуительно длинный текст лацо длоцадлоцула рщлцоуар щшгцура щшгцуращшг цуращ шцщша щшмлвок зущшкр щшзукр пщшуоим рдломломклоукрм лшокур шкущорщзшокур зшщугк р", "audio": "assets/sounds/identity.wav"}
            ],
            "спасибо": [
                {"text": "Всегда пожалуйста.", "audio": "assets/sounds/welcome.wav"},
                {"text": "Рада быть полезной.", "audio": "assets/sounds/happy_to_help.wav"}
            ]
        }

    def play_sound(self, file_path):
        """Асинхронный запуск аудио, чтобы не блокировать ядро"""
        if os.path.exists(file_path):
            def _play():
                try:
                    sound = pygame.mixer.Sound(file_path)
                    sound.play()
                except Exception as e:
                    print(f"[CHAT ERROR]: Ошибка воспроизведения {e}")

            threading.Thread(target=_play, daemon=True).start()
        else:
            print(f"[CHAT ERROR]: Файл не найден: {file_path}")

    def execute(self, text, ctx):
        text = text.lower()

        for trigger, variants in self.responses.items():
            if trigger in text:
                # Выбираем ОДНУ конкретную пару из доступных для этого триггера
                line = random.choice(variants)

                # 1. Выводим текст в HUD (субтитры)
                if hasattr(ctx, 'ui_log'):
                    ctx.ui_log(line["text"], "info")

                # 2. Озвучиваем именно этот текст
                self.play_sound(line["audio"])

                return True
        return False