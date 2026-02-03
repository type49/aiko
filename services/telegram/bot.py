import asyncio
from aiogram import Bot, Dispatcher
from services.telegram.worker import TelegramWorker
from utils.config_manager import aiko_cfg
from utils.logger import logger


class AikoTelegramService:
    def __init__(self, ctx, core):
        self.ctx = ctx
        self.core = core

        token = aiko_cfg.get("telegram.token")
        if not token:
            logger.error("TG-Service: ТОКЕН НЕ НАЙДЕН в конфигурации!")
            return

        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.worker = TelegramWorker(self.bot)
        logger.info("TG-Service: Объект бота и диспетчера создан.")

    async def start(self):
        logger.info("TG-Service: Запуск поллинга и воркера...")

        from services.telegram.handlers.bridge import register_bridge_handlers
        register_bridge_handlers(self.dp, self.ctx, self.core)

        try:
            # Запускаем всё параллельно
            await asyncio.gather(
                self.dp.start_polling(self.bot),
                self.worker.run()
            )
        except Exception as e:
            logger.error(f"TG-Service: КРИТИЧЕСКАЯ ОШИБКА ПОЛЛИНГА: {e}", exc_info=True)