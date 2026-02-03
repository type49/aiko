import re
from interfaces import AikoCommand
from utils.audio_player import audio_manager
from utils.matcher import CommandMatcher
from utils.logger import logger


class ReminderPlugin(AikoCommand):
    def __init__(self):
        self.type = "reminder"
        self.triggers = [
            "напомни", "напоминание", "поставь задачу",
            "запиши", "добавь напоминание", "не забудь", "зафиксируй"
        ]
        logger.info("ReminderPlugin: Работает в базовом режиме (вызов GUI).")

    def execute(self, text, ctx):
        text_lower = text.lower().strip()

        # 1. Поиск намерения (Intent Matching)
        match, score = CommandMatcher.extract(text_lower, self.triggers, threshold=80, partial=True)

        if match and text_lower.find(match.lower()) <= 3:
            logger.info(f"ReminderPlugin: Намерение опознано ({score}%)")

            # 2. Очистка текста: удаляем триггер и лишние слова
            # Регулярка убирает триггер и любые окончания (напомни, напомнить)
            clean_payload = re.sub(rf'^{match}\w*\s*', '', text_lower, flags=re.IGNORECASE).strip()

            # Дополнительная очистка связок
            garbage = ["про ", "что ", "чтобы ", "о том ", "о ", "мне ", "нам ", "записать "]
            for word in garbage:
                if clean_payload.startswith(word):
                    clean_payload = clean_payload[len(word):].strip()

            # 3. Звуковой отклик и вызов окна
            audio_manager.play("assets/sound/system/alarm.wav", volume=0.3)

            if not clean_payload:
                clean_payload = "Новая задача"

            logger.info(f"ReminderPlugin: Вызов GUI с текстом: {clean_payload}")
            ctx.ui_open_reminder(clean_payload.capitalize())

            return True

        return False

    def on_schedule(self, data, ctx):
        """
        Метод вызывается Ядром, когда время задачи в базе наступило.
        """
        import json
        try:
            payload = json.loads(data) if isinstance(data, str) else data
        except:
            payload = {"text": str(data)}

        text = payload.get('text', 'Пустое напоминание')
        logger.info(f"ReminderPlugin: Сработка таймера -> {text}")

        # Сигнал и уведомление
        audio_manager.play("assets/sound/system/alarm.wav", volume=0.7)
        ctx.broadcast(f"🔔 НАПОМИНАНИЕ: {text}")

        if ctx.ui_show_alarm:
            ctx.ui_show_alarm(payload)