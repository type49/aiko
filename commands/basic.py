import datetime
from interfaces import AikoCommand
from utils.matcher import CommandMatcher
from utils.logger import logger

1/0

class TimePlugin(AikoCommand):
    def __init__(self):
        self.type = "time"
        self.triggers = ["время", "который час", "сколько времени", "час"]

    def execute(self, text, ctx):
        text_lower = text.lower().strip()

        # Используем STRICT (partial=False), чтобы не ловить "время" в середине фраз
        # Но проверяем только ПЕРВОЕ слово фразы
        first_word = text_lower.split()[0] if text_lower.split() else ""

        match, score = CommandMatcher.extract(first_word, self.triggers, threshold=80, partial=False)

        if match:
            now = datetime.datetime.now().strftime("%H:%M")
            msg = f"Сейчас {now}"

            ctx.ui_log(msg, "info")
            logger.info(f"TimePlugin: Опознано по слову '{first_word}' (score: {score}%)")
            return True

        return False