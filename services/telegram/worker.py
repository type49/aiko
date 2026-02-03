import asyncio
from datetime import datetime
from aiogram import Bot
from utils.db_manager import db
from utils.logger import logger
from utils.config_manager import aiko_cfg


class TelegramWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.retry_delay = 5
        self.is_running = True

    async def run(self):
        logger.info("TG-Worker: Цикл мониторинга очереди запущен.")
        while self.is_running:
            try:
                # 1. Проверяем наличие chat_id перед началом круга
                current_chat_id = aiko_cfg.get("telegram.chat_id")
                if not current_chat_id:
                    # Если владельца нет, воркер спит дольше, чтобы не насиловать БД
                    await asyncio.sleep(10)
                    continue

                # 2. Опрашиваем БД
                messages = db.get_pending_tg_messages()
                if not messages:
                    await asyncio.sleep(2)  # Нет задач — быстро засыпаем
                    continue

                logger.debug(f"TG-Worker: Найдено сообщений в очереди: {len(messages)}")

                # 3. Рассылка
                for m_id, text, created_at in messages:
                    if await self._try_send(current_chat_id, m_id, text, created_at):
                        self.retry_delay = 5
                    else:
                        # Ошибка сети: ждем и уходим на Backoff
                        logger.warning(f"TG-Worker: Сеть недоступна. Ждем {self.retry_delay}с.")
                        await asyncio.sleep(self.retry_delay)
                        self.retry_delay = min(self.retry_delay * 2, 300)
                        break

            except Exception as e:
                logger.error(f"TG-Worker: Глобальная ошибка цикла: {e}")
                await asyncio.sleep(5)

    async def _try_send(self, chat_id, m_id, text, created_at):
        try:
            # Парсим время создания (теперь оно локальное)
            dt_created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            delta = datetime.now() - dt_created

            # Ставим "Дослано" только если реально прошло больше минуты
            if delta.total_seconds() > 60:
                text = f"⏳ *[Дослано]*\n_Создано: {created_at}_\n\n{text}"

            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown"
            )

            db.mark_tg_sent(m_id)
            return True
        except Exception as e:
            logger.error(f"TG-Worker: {e}")
            return False