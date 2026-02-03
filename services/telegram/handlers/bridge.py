from aiogram import types, Dispatcher
from utils.config_manager import aiko_cfg
from utils.logger import logger


def register_bridge_handlers(dp: Dispatcher, ctx, core):
    @dp.message()
    async def handle_tg_message(message: types.Message):
        user_text = message.text.strip()
        chat_id = str(message.chat.id)

        saved_chat_id = aiko_cfg.get("telegram.chat_id")
        secret_phrase = str(aiko_cfg.get("telegram.secret_phrase", "aiko_init"))

        # ЭТАП 1: Регистрация (Handshake)
        if not saved_chat_id:
            if user_text == secret_phrase:
                aiko_cfg.set("telegram.chat_id", chat_id)
                ctx.tg_chat_id = chat_id
                logger.info(f"TG-Bridge: УСПЕШНАЯ АВТОРИЗАЦИЯ. ID {chat_id}")
                await message.answer(f"✅ Владелец подтвержден! ID: {chat_id}")
            else:
                await message.answer("❌ Введите секретную фразу.")
            return

        # ЭТАП 2: Защита (Security Check)
        if chat_id != str(saved_chat_id):
            logger.warning(f"TG-Bridge: Попытка доступа от чужого ID: {chat_id}")
            return

        # ЭТАП 3: Проброс в ядро (Logic Bridge)
        logger.info(f"TG-Bridge: Команда из Telegram -> {user_text}")

        # Устанавливаем источник ПЕРЕД выполнением, чтобы ctx.reply знал, куда отвечать
        ctx.set_input_source("tg")

        # Пытаемся выполнить логику
        success = core.process_logic(user_text.lower())

        # Если плагины промолчали (не сработал мэтчер) — уведомляем пользователя
        if not success:
            # Используем ctx.reply вместо прямого message.reply для единообразия логов
            ctx.reply("🤷 Не нашла подходящего плагина для этой команды.")

        # ВАЖНО: Мы убрали 'await message.reply("🚀 Выполнено")',
        # потому что плагины теперь отвечают сами через ctx.reply()