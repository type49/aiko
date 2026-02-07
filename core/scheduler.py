import time
import threading
import json
from utils.logger import logger
from utils.db_manager import db


class TaskScheduler:
    def __init__(self, ctx):
        self.ctx = ctx
        self.active = False
        self.thread = None

    def start(self):
        """Запускает поток планировщика."""
        if self.active:
            return

        self.active = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="Scheduler")
        self.thread.start()
        logger.info("Scheduler: Служба планировщика запущена.")

    def stop(self):
        """Останавливает поток."""
        self.active = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _loop(self):
        """Основной цикл (рабочий метод)."""
        logger.info("Scheduler: Цикл обработки задач активен.")
        while self.active and self.ctx.is_running:
            try:
                tasks = db.get_pending_tasks()
                for t_id, t_type, t_payload in tasks:
                    self.process_task(t_id, t_type, t_payload)
            except Exception as e:
                logger.error(f"Scheduler: Ошибка цикла: {e}", exc_info=True)

            time.sleep(5)

    def process_task(self, t_id, t_type, t_payload):
        # Десериализация
        data = json.loads(t_payload) if isinstance(t_payload, str) else t_payload
        handler_found = False

        # Ищем исполнителя среди загруженных команд
        for cmd in self.ctx.commands:
            if getattr(cmd, 'type', None) == t_type:

                # 1. Выполнение действия
                if hasattr(cmd, 'on_schedule'):
                    try:
                        cmd.on_schedule(data, self.ctx, t_id)
                    except Exception as e:
                        logger.error(f"Scheduler: Ошибка в плагине {cmd}: {e}")

                # 2. Завершение задачи
                if hasattr(cmd, 'complete_task'):
                    cmd.complete_task(t_id, data)
                    handler_found = True

                break

        if not handler_found:
            warning = f"Scheduler: Не найден плагин для типа '{t_type}'."
            logger.warning(warning)
            self.ctx.broadcast(warning, priority="WARNING")
            db.update_task_status(t_id, 'done')