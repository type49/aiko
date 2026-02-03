import asyncio
import atexit
import sys
import threading

from PySide6.QtWidgets import QApplication

from aiko_core import AikoContext, AikoCore
from aiko_gui import AikoApp
from services.telegram.bot import AikoTelegramService
from utils.lifecycle import lifecycle
from utils.logger import logger


def run_telegram(tg_service):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(tg_service.start())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    ctx = AikoContext()
    core = AikoCore(ctx)
    tg_service = AikoTelegramService(ctx, core)

    aiko_gui = AikoApp(ctx, core)

    threading.Thread(target=run_telegram, args=(tg_service,), daemon=True, name="TGThread").start()

    threading.Thread(target=core.run, daemon=True, name="CoreThread").start()

    sys.exit(app.exec())