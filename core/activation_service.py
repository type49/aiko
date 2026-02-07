import time

from utils.audio_player import audio_manager
from utils.config_manager import aiko_cfg
from utils.matcher import CommandMatcher
from utils.logger import logger

class ActivationService:
    """
    Сервис управления активацией и жизненным циклом 'активного окна' диалога.
    Обеспечивает логику 'слуха' и управления временными интервалами ожидания.
    """

    def __init__(self, ctx):
        self.ctx = ctx
        self.bot_name = aiko_cfg.get("bot.name", "айко").lower()
        self.threshold = aiko_cfg.get("audio.match_threshold", 80)

        logger.info(f"Activation: Инициализация (Имя: {self.bot_name}, Порог: {self.threshold}%)")

    def check(self, text: str):
        """
        Определяет, адресована ли фраза боту.
        :return: (bool, clean_text)
        """
        # 1. Триггер по имени (Айко, ...)
        is_trig, cmd_text = CommandMatcher.check_trigger(text, [self.bot_name], self.threshold)
        if is_trig:
            logger.info(f"Activation: Триггер '{self.bot_name}' найден. Команда: '{cmd_text}'")
            return True, cmd_text

        # 2. Активное окно (продолжение диалога)
        if self._is_window_active():
            audio_manager.play.listen()

            logger.debug("Activation: Фраза в активном окне.")
            return True, text

        return False, None

    def extend_post_command_window(self):
        """
        Продлевает окно ожидания после успешного выполнения команды.
        Дает пользователю короткое время (post_command_window) на уточнение без повтора имени.
        """
        self.ctx.last_activation_time = time.time() - (self.ctx.active_window - self.ctx.post_command_window)
        logger.debug("Activation: Окно продлено после команды.")

    def refresh_activation(self):
        """
        Сбрасывает таймер окна на полную длительность (active_window).
        Обычно вызывается при простом упоминании имени бота.
        """
        self.ctx.last_activation_time = time.time()
        logger.debug("Activation: Таймер окна сброшен на максимум.")

    def handle_timeouts(self, set_state_cb):
        """Сброс состояния в idle при неактивности."""
        if not self._is_window_active() and self.ctx.state == "active":
            logger.info("Activation: Окно закрыто по таймауту.")
            set_state_cb("idle")

    def _is_window_active(self) -> bool:
        """Внутренняя проверка: открыто ли сейчас окно диалога."""
        return (time.time() - self.ctx.last_activation_time) < self.ctx.active_window
