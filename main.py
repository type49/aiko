import os
import tempfile

from utils.audio_player import audio_manager
startup_channel = audio_manager.play.first_startup(volume=1.0, ignore_master=True)
from filelock import FileLock, Timeout

import asyncio
import sys
import threading

from PySide6.QtWidgets import QApplication

from aiko_core import AikoCore
from aiko_gui import AikoApp
from core.context import AikoContext
from services.telegram.bot import AikoTelegramService
from core.global_context import set_global_context

LOCK_PATH = os.path.join(tempfile.gettempdir(), "aiko_assistant.lock")
lock = FileLock(LOCK_PATH, timeout=0)

def run_telegram(tg_service):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(tg_service.start())

def is_already_running():
    """Проверяет, запущен ли уже экземпляр приложения"""
    try:
        # Пытаемся захватить файл. timeout=0 значит "не ждать"
        lock.acquire()
        return False
    except Timeout:
        return True


if __name__ == "__main__":
    if is_already_running():
        print("⚠️ Айко уже запущена. Завершение дубликата.")
        sys.exit(0)
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
    ctx.broadcast('Готова к работе', to_all=True, status='success')

    sys.exit(app.exec())