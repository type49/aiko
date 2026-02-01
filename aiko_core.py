import json
import time
import threading
import importlib.util
from pathlib import Path
from vosk import Model, KaldiRecognizer
from fuzzywuzzy import fuzz

from interfaces import AikoCommand
from utils.db_manager import db
from utils.logger import logger
from utils.audio_handler import AudioHandler
from utils.matcher import CommandMatcher

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
        self.state = "idle"

        self.log_commands = True

        self.ui_log = lambda text, type: None
        self.ui_open_reminder = lambda text: None
        self.ui_status = lambda status: None


class AikoCore:
    def __init__(self, ctx=None):
        self.ctx = ctx or AikoContext()
        logger.info("Инициализация AikoCore...")

        # 1. Проверка модели
        if not self.ctx.model_path.exists():
            logger.critical(f"Модель не найдена: {self.ctx.model_path}")
            raise FileNotFoundError("Vosk model missing")

        self.model = Model(str(self.ctx.model_path))
        self.rec = KaldiRecognizer(self.model, 16000)

        # 2. Инициализация аудио-обработчика
        self.audio = AudioHandler(device_id=self.ctx.device_id)
        self.stop_event = threading.Event()

        # 3. Загрузка способностей
        self._load_plugins()

        # 4. Запуск фоновых процессов
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
        """Проверка активационного имени 'Айко'"""
        triggers = ["айко", "айка", "хайко", "лайко", "аико", "ойко", "найко", "ай ко"]

        is_trig, cmd_text = CommandMatcher.check_trigger(text, triggers)

        if is_trig:
            logger.info(f"Триггер опознан! Остаток фразы: '{cmd_text}'")

        return is_trig, cmd_text

    def run(self):
        """Точка входа: запуск захвата аудио и цикла распознавания."""
        # Запускаем "уши"
        threading.Thread(target=self.audio.listen, args=(self.stop_event,), daemon=True, name="AudioIn").start()
        logger.info("Основной цикл распознавания запущен.")

        while self.ctx.is_running:
            curr_t = time.time()

            # Сброс активного окна (если долго молчим)
            in_win = (curr_t - self.ctx.last_activation_time) < self.ctx.active_window
            if not in_win and self.ctx.state == "active":
                self.set_state("idle")

            try:
                # Получаем байты из AudioHandler
                data = self.audio.audio_q.get(timeout=0.2)

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
                                self.ctx.last_activation_time = 0  # Сброс окна после выполнения
                        elif in_win:
                            if getattr(self.ctx, 'log_commands', False):
                                logger.info(f" ГИПЕРФОКУС: Уточнение -> '{res}'")
                            if self.process_logic(res):
                                self.ctx.last_activation_time = 0

            except Exception as e:
                # Если очередь пуста или микрофон заблокирован
                if self.ctx.mic_active and not self.audio.is_active:
                    self.set_state("blocked")
                continue

    def _scheduler_loop(self):
        """Фоновый планировщик задач и тиков."""
        while self.scheduler_active and self.ctx.is_running:
            try:
                # 1. Задачи из БД
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