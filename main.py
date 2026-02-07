from utils.audio_player import audio_manager
startup_channel = audio_manager.play.first_startup(volume=1.0, ignore_master=True)

import asyncio
import sys
import threading

from PySide6.QtWidgets import QApplication

from aiko_core import AikoCore
from aiko_gui import AikoApp
from core.context import AikoContext
from services.telegram.bot import AikoTelegramService
from core.global_context import set_global_context


def run_telegram(tg_service):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(tg_service.start())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    ctx = AikoContext()

    # Регистрируем контекст глобально
    set_global_context(ctx)

    core = AikoCore(ctx)
    tg_service = AikoTelegramService(ctx, core)

    aiko_gui = AikoApp(ctx, core)

    threading.Thread(target=run_telegram, args=(tg_service,), daemon=True, name="TGThread").start()

    threading.Thread(target=core.run, daemon=True, name="CoreThread").start()

    audio_manager.play.second_startup(volume=0.5, ignore_master=True)
    if startup_channel:
        startup_channel.fadeout(1000)
    ctx.broadcast('Готова к работе', to_all=True)

sys.exit(app.exec())