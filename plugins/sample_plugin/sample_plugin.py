from interfaces import AikoCommand
from utils.logger import logger


class SamplePlugin(AikoCommand):
    def __init__(self):
        super().__init__()
        self.triggers = ["плагин"]
        self.samples = [
        ]
        self.is_active = False


    def execute(self, text: str, ctx) -> bool:
        """
        Основная логика при получении команды.
        """
        self.ctx = ctx
        self.ctx.register_ui_status_callback(self.on_status_change)

        ctx.reply("Плагин запущен", level="success")
        ctx.broadcast("Привяу, телеграм, плагин запущен!", ui=False, tg=True)
        logger.info("PomodoroPlugin: Сессия успешно инициализирована.")
        return True

    def on_tick(self, ctx):
        """
        Метод вызывается платформой каждую итерацию цикла (Tick).
        """
        print('Плагин работает')

    def on_status_change(self, new_status: str):
        """
        Вызывается при смене статуса платформы.
        """
        print(f"Current status: {new_status}")
