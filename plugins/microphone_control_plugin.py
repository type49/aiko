from interfaces import AikoCommand
from utils.matcher import CommandMatcher
from utils.logger import logger


class MicrophoneControl(AikoCommand):
    """
    Плагин для голосового управления микрофоном
    Работает через централизованное управление в ctx
    """

    def __init__(self):
        super().__init__()
        self.type = "microphone_control"

        # Триггеры для ВКЛЮЧЕНИЯ микрофона
        self.enable_triggers = [
            "включи микрофон", "запусти микрофон", "активируй микрофон",
            "микрофон включи", "включить микрофон", "разблокируй микрофон"
        ]

        # Триггеры для ВЫКЛЮЧЕНИЯ микрофона
        self.disable_triggers = [
            "выключи микрофон", "отключи микрофон", "останови микрофон",
            "микрофон выключи", "выключить микрофон", "заблокируй микрофон",
            "заткнись", "хватит слушать"
        ]

    def execute(self, text, ctx):
        # Проверяем команды на выключение
        match_off, score_off = CommandMatcher.extract(text, self.disable_triggers, threshold=70)
        match_on, score_on = CommandMatcher.extract(text, self.enable_triggers, threshold=70)

        # Команда ВЫКЛЮЧЕНИЯ
        if score_off > score_on and match_off:
            if not ctx.microphone_enabled:
                ctx.ui_output("Микрофон и так выключен.", "info")
                return True

            # Выключаем через централизованное управление
            if ctx.set_microphone_state(False, source="voice"):
                ctx.ui_output("Микрофон выключен", "info")
                logger.info(f"MicControl: Выключение через '{match_off}' ({score_off}%)")

                # Очищаем очередь аудио
                from core.global_context import get_context
                global_ctx = get_context()
                if global_ctx and hasattr(global_ctx, 'core'):
                    with global_ctx.core.audio.audio_q.mutex:
                        global_ctx.core.audio.audio_q.queue.clear()

            return True

        # Команда ВКЛЮЧЕНИЯ
        if match_on:
            if ctx.microphone_enabled:
                ctx.ui_output("Микрофон уже включен.", "info")
                return True

            # Включаем через централизованное управление
            if ctx.set_microphone_state(True, source="voice"):
                ctx.ui_output("Микрофон включен", "success")
                logger.info(f"MicControl: Включение через '{match_on}' ({score_on}%)")

            return True

        return False