import json
import time
import threading
import importlib.util
from pathlib import Path
from vosk import Model, KaldiRecognizer
import queue
from interfaces import AikoCommand
from utils.db_manager import db
from utils.logger import logger
from utils.audio_handler import AudioHandler
from utils.matcher import CommandMatcher
from utils.config_manager import aiko_cfg


class AikoContext:
    """Объект состояния системы. Передается между Ядром, GUI и Плагинами."""

    def __init__(self):
        self.is_running = True
        self.mic_active = True
        self.last_activation_time = 0
        self.active_window = 5.0
        self.device_id = 1
        self.model_path = Path("models/small/vosk-model-small-ru-0.22")
        self.commands = []

        self.device_id = aiko_cfg.get("audio.device_id", 1)
        self.active_window = aiko_cfg.get("trigger.active_window", 5.0)
        self.log_commands = aiko_cfg.get("debug.log_commands", True)

        self.state = "idle"

        self.log_commands = True

        self.ui_log = lambda text, type: None
        self.ui_open_reminder = lambda text: None
        self.ui_status = lambda status: None
        self.ui_audio_status = lambda is_ok, msg: None

class AikoCore:
    def __init__(self, ctx=None):
        self.ctx = ctx or AikoContext()
        logger.info("Инициализация AikoCore...")

        if not self.ctx.model_path.exists():
            logger.critical(f"Модель не найдена: {self.ctx.model_path}")
            raise FileNotFoundError("Vosk model missing")

        self.model = Model(str(self.ctx.model_path))
        self.rec = KaldiRecognizer(self.model, 16000)

        self.audio = AudioHandler(
            device_id=self.ctx.device_id,
            on_status_change=self.ctx.ui_audio_status
        )

        self.stop_event = threading.Event()

        self._load_plugins()

        self.scheduler_active = True
        threading.Thread(target=self._scheduler_loop, daemon=True, name="Scheduler").start()

    def _load_plugins(self):
        plugins_dir = Path("commands")
        plugins_dir.mkdir(exist_ok=True)
        for file in plugins_dir.glob("*.py"):
            if file.name == "__init__.py": continue
            try:
                spec = importlib.util.spec_from_file_location(file.stem, file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, AikoCommand) and obj is not AikoCommand:
                        self.ctx.commands.append(obj())
                        logger.debug(f"Загружен плагин: {attr}")
            except Exception as e:
                logger.error(f"Ошибка загрузки плагина {file.name}: {e}")

    def set_state(self, new_state):
        if self.ctx.state != new_state:
            logger.info(f"Состояние: {self.ctx.state} -> {new_state}")
            self.ctx.state = new_state
            if callable(self.ctx.ui_status):
                self.ctx.ui_status(new_state)

    def process_logic(self, text):
        """Проход по плагинам. Возвращает True, если команда выполнена."""
        if not text: return False
        for cmd in self.ctx.commands:
            try:
                if cmd.execute(text, self.ctx):
                    logger.info(f"Команда обработана плагином: {cmd.__class__.__name__}")
                    return True
            except Exception as e:
                logger.error(f"Ошибка в плагине {cmd.__class__.__name__}: {e}")
        return False

    def _check_trigger(self, text):
        """Динамическая проверка имени из конфига"""
        main_name = aiko_cfg.get("bot.name").lower()

        triggers = [main_name]
        threshold = aiko_cfg.get("audio.match_threshold", 80)
        return CommandMatcher.check_trigger(text, triggers, threshold)

    def run(self):
        """Точка входа: запуск захвата аудио и цикла распознавания."""
        threading.Thread(target=self.audio.listen, args=(self.stop_event,), daemon=True, name="AudioIn").start()
        logger.info("Основной цикл распознавания запущен.")

        while self.ctx.is_running:
            curr_t = time.time()
            in_win = (curr_t - self.ctx.last_activation_time) < self.ctx.active_window

            if not in_win and self.ctx.state == "active":
                self.set_state("idle")

            try:
                # 1. Получаем данные ВСЕГДА (с таймаутом, чтобы не блокировать цикл)
                data = self.audio.audio_q.get(timeout=0.2)

                # 2. Обрабатываем только если данные реально пришли
                if self.rec.AcceptWaveform(data):
                    res = json.loads(self.rec.Result()).get('text', '')
                    if res:
                        logger.debug(f"Слушаю: {res}")
                        is_trig, cmd_text = self._check_trigger(res)

                        if is_trig:
                            if getattr(self.ctx, 'log_commands', False):
                                logger.info(f" ГИПЕРФОКУС: Получена команда -> '{cmd_text}'")
                            self.set_state("active")
                            self.ctx.last_activation_time = time.time()
                            if cmd_text and self.process_logic(cmd_text):
                                self.ctx.last_activation_time = 0
                        elif in_win:
                            if getattr(self.ctx, 'log_commands', False):
                                logger.info(f" ГИПЕРФОКУС: Уточнение -> '{res}'")
                            if self.process_logic(res):
                                self.ctx.last_activation_time = 0

            except queue.Empty:
                # Это нормально, если в очереди пока пусто
                continue
            except Exception as e:
                logger.error(f"Core Run Error: {e}")
                continue


    def _scheduler_loop(self):
        """Фоновый планировщик задач и тиков."""
        while self.scheduler_active and self.ctx.is_running:
            try:
                tasks = db.get_pending_tasks()
                for t_id, t_type, t_payload in tasks:
                    for cmd in self.ctx.commands:
                        if hasattr(cmd, 'on_schedule') and t_type == getattr(cmd, 'type', ''):
                            cmd.on_schedule(t_payload, self.ctx)
                    db.update_task_status(t_id, 'done')

                # 2. Тики мониторинга (для фокус-менеджера и т.д.)
                for cmd in self.ctx.commands:
                    if hasattr(cmd, 'on_tick'):
                        cmd.on_tick(self.ctx)

            except Exception as e:
                logger.error(f"Ошибка планировщика: {e}")
            time.sleep(5)

    def add_scheduler_task(self, task_type, payload, exec_at):
        """Метод для внешнего вызова (например, из GUI)"""
        return db.add_task(task_type, payload, exec_at)

    def restart_audio_capture(self):
        """Синхронизирует микрофон с актуальным конфигом"""
        new_device_id = aiko_cfg.get("audio.device_index", 1)  # Берем свежий ID из конфига
        logger.info(f"Core: Перезапуск аудио-захвата. Новый ID: {new_device_id}")

        # Обновляем контекст, чтобы другие модули видели изменения
        self.ctx.device_id = new_device_id

        # Сигнализируем аудио-хендлеру
        if self.audio:
            self.audio.restart(new_device_id)