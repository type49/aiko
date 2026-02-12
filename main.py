# -*- coding: utf-8 -*-
"""
ИСПРАВЛЕНО:
- Устранены циклические зависимости импортов
- Правильная инициализация аудио после QApplication
"""
import os
import tempfile
import asyncio
import sys
import threading

from PySide6.QtWidgets import QApplication
from filelock import FileLock, Timeout

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
        sys.exit(0)

    # ИСПРАВЛЕНИЕ: Создаем QApplication в самом начале
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # ИСПРАВЛЕНИЕ: Теперь безопасно импортировать модули с Qt зависимостями
    from ui.notifications import PopupNotification
    from utils.audio_player import audio_manager
    from aiko_core import AikoCore
    from aiko_gui import AikoApp
    from core.context import AikoContext
    from services.telegram.bot import AikoTelegramService
    from core.global_context import set_global_context
    from ui.left_window import LiquidGlassWindow

    # ИСПРАВЛЕНИЕ: Запускаем стартовый звук после инициализации QApplication
    startup_channel = audio_manager.play.first_startup(volume=1.0, ignore_master=True)

    # Инициализация контекста
    ctx = AikoContext()
    notifications = PopupNotification()

    # Регистрируем в логгере
    from utils.logger import register_ui_logger

    register_ui_logger(notifications)
    ctx.ui_manager = notifications

    # Регистрируем контекст глобально
    set_global_context(ctx)

    # Инициализация ядра
    core = AikoCore(ctx)

    # Сохраняем core в контексте для доступа из плагинов
    ctx.core = core

    # Инициализация сервисов
    tg_service = AikoTelegramService(ctx, core)
    aiko_gui = AikoApp(ctx, core)
    left_widget = LiquidGlassWindow()
    left_widget.showMinimized()

    # Запуск потоков
    threading.Thread(target=run_telegram, args=(tg_service,), daemon=True, name="TGThread").start()
    threading.Thread(target=core.run, daemon=True, name="CoreThread").start()

    # ИСПРАВЛЕНИЕ: Финальные звуки и уведомления
    audio_manager.play.second_startup(volume=0.5, ignore_master=True)
    if startup_channel:
        startup_channel.fadeout(1000)
    ctx.broadcast('Готова к работе', to_all=True, status='success')

    sys.exit(app.exec())