import re
from interfaces import AikoCommand
from utils.audio_player import audio_manager


class ReminderPlugin(AikoCommand):
    def __init__(self):
        self.type = "reminder"
        print("[REMINDER]: Плагин загружен и готов.")

    def execute(self, text, ctx):
        """Срабатывает на голос"""
        text_lower = text.lower()

        # Проверяем наличие ключевого слова
        if "напомни" in text_lower:
            print(f"[REMINDER]: Команда поймана. Текст: {text_lower}")

            # Играем звук подтверждения (путь без точки в начале!)
            audio_manager.play("assets/sound/system/alarm.wav", volume=0.5)

            # Извлекаем суть (удаляем всё до слова 'напомни' включительно)
            clean_text = re.sub(r'.*напомни', '', text_lower, flags=re.IGNORECASE).strip()

            # Если после "напомни" ничего нет, clean_text будет пустой строкой.
            # Это нормально, пользователь впишет суть в GUI.

            if hasattr(ctx, 'ui_open_reminder') and ctx.ui_open_reminder:
                print("[REMINDER]: Отправляю сигнал на открытие окна GUI...")
                ctx.ui_open_reminder(clean_text)
                return True
            else:
                print("[REMINDER ERROR]: Метод ui_open_reminder не найден в контексте!")
                return False

        return False

    def on_schedule(self, payload, ctx):
        """Срабатывает из ядра по расписанию"""
        print(f"[REMINDER]: СРАБОТАЛО ПО ТАЙМЕРУ: {payload}")
        if hasattr(ctx, 'ui_log'):
            ctx.ui_log(f"ФОКУС: {payload}", "cmd")
        audio_manager.play("assets/sound/system/alarm.wav", volume=0.8)