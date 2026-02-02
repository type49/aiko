import re
from interfaces import AikoCommand
from utils.audio_player import audio_manager
from utils.matcher import CommandMatcher
from utils.logger import logger


class ReminderPlugin(AikoCommand):
    def __init__(self):
        self.type = "reminder"
        # Список триггеров для Этапа 2
        self.triggers = [
            "напомни", "напоминание", "поставь задачу",
            "запиши", "добавь напоминание", "не забудь", "зафиксируй"
        ]
        logger.info("ReminderPlugin: Инициализирован и готов к работе.")

    def execute(self, text, ctx):
        text_lower = text.lower().strip()

        # ЭТАП 2: Поиск намерения (Intent Matching)
        # Используем partial=True, чтобы найти триггер в начале фразы
        match, score = CommandMatcher.extract(text_lower, self.triggers, threshold=80, partial=True)

        # Проверяем, что триггер находится в самом начале (индекс 0-2)
        # Это исключает ложные срабатывания, если слово "напомни" встретилось в середине другой фразы
        if match and text_lower.find(match.lower()) <= 2:
            logger.info(f"ReminderPlugin: Намерение опознано через '{match}' ({score}%)")

            # Звуковой отклик (Этап подтверждения)
            audio_manager.play("assets/sound/system/alarm.wav", volume=0.3)

            # ЭТАП 3: Экстракция данных (Entity Extraction)
            # Извлекаем только то, что идет после триггера
            clean_payload = self._extract_payload(text_lower, match)

            if not clean_payload:
                clean_payload = "Пустая задача..."  # На случай, если пользователь сказал только триггер

            logger.info(f"ReminderPlugin: Отправка в GUI задачи: '{clean_payload}'")

            # Вызываем окно напоминания в GUI
            ctx.ui_open_reminder(clean_payload)
            return True

        return False

    def _extract_payload(self, text, match):
        """
        Отрезает триггер и чистит связующие предлоги.
        Пример: 'напомни про купить хлеб' -> 'Купить хлеб'
        """
        # 1. Удаляем сам найденный триггер
        # Используем регулярку, чтобы удалить только первое вхождение
        pattern = re.compile(re.escape(match), re.IGNORECASE)
        payload = pattern.sub('', text, count=1).strip()

        # 2. Список 'мусора', который часто идет после триггера
        garbage_connectors = [
            "про ", "что ", "чтобы ", "о том ", "о ", "мне ", "нам ", "записать "
        ]

        # Чистим, пока текст начинается с какого-то из этих слов
        changed = True
        while changed:
            changed = False
            for word in garbage_connectors:
                if payload.lower().startswith(word):
                    payload = payload[len(word):].strip()
                    changed = True

        return payload.capitalize()

    def on_schedule(self, payload, ctx):
        """Сработка таймера из планировщика Ядра"""
        logger.info(f"ReminderPlugin: Исполнение таймера -> {payload}")
        ctx.ui_log(f"НАПОМИНАНИЕ: {payload}", "cmd")
        audio_manager.play("assets/sound/system/alarm.wav", volume=0.8)