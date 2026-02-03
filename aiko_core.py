import json
import time
import threading
import importlib.util
import queue
from pathlib import Path
from vosk import Model, KaldiRecognizer

from interfaces import AikoCommand
from utils.db_manager import db
from utils.logger import logger
from utils.audio_handler import AudioHandler
from utils.matcher import CommandMatcher
from utils.config_manager import aiko_cfg


class AikoContext:
    """Объект состояния системы. Передается между Ядром, GUI и Плагинами."""

    def __init__(self):
        # --- Состояние работы ---
        self.is_running = True
        self.state = "init"  # idle, active, blocked, error
        self.last_input_source = "mic"  # mic, tg, gui

        # --- Настройки аудио (Прямые атрибуты для Core) ---
        self.mic_active = True
        self.device_id = aiko_cfg.get("audio.device_id", 1)
        self.active_window = aiko_cfg.get("trigger.active_window", 5.0)
        self.last_activation_time = 0

        # --- Пути и ресурсы ---
        self.model_path = Path("models/small/vosk-model-small-ru-0.22")
        self.commands = []
        self.tg_chat_id = aiko_cfg.get("telegram.chat_id")

        # --- Коллбэки для UI (Группировка для чистоты) ---
        # Инициализируются в AikoApp через сигналы
        self.ui_log = lambda text, level="info": None
        self.ui_status = lambda status: None
        self.ui_audio_status = lambda is_ok, msg: None
        self.ui_show_alarm = None
        self.ui_open_reminder = lambda text: None

    def set_input_source(self, source):
        if source in ["mic", "tg", "gui"]:
            self.last_input_source = source

    def broadcast(self, text, level="info"):
        """Системное вещание во все каналы"""
        logger.info(f"BROADCAST: {text}")
        if self.ui_log:
            self.ui_log(text, level)

        # Ленивый импорт базы, чтобы избежать циклической зависимости
        from utils.db_manager import db
        db.add_tg_message(f"📢 {text}")

    def reply(self, text, level="info", to_all=False):
        """Универсальный ответ в зависимости от источника ввода"""
        logger.info(f"REPLY [{self.last_input_source}]: {text}")

        if self.last_input_source != "tg" or to_all:
            if self.ui_log:
                self.ui_log(text, level)

        if self.last_input_source == "tg" or to_all:
            from utils.db_manager import db
            db.add_tg_message(text)



class AikoCore:
    def __init__(self, ctx=None):
        self.ctx = ctx or AikoContext()
        logger.info("Core: Инициализация ядра...")

        self._stt_model = None
        self._stt_rec = None

        self.audio = AudioHandler(
            device_id=self.ctx.device_id,
            on_status_change=lambda is_ok, msg: self.ctx.ui_audio_status(is_ok, msg)
        )

        self.stop_event = threading.Event()
        self._load_plugins()

        self.scheduler_active = True
        threading.Thread(target=self._scheduler_loop, daemon=True, name="Scheduler").start()

    @property
    def stt(self):
        if self._stt_rec is None:
            if not self.ctx.model_path.exists():
                logger.critical(f"Core: Модель не найдена: {self.ctx.model_path}")
                raise FileNotFoundError("Vosk model missing")

            logger.info("Core: Загрузка STT модели в память...")
            self._stt_model = Model(str(self.ctx.model_path))
            self._stt_rec = KaldiRecognizer(self._stt_model, 16000)
            logger.info("Core: STT модель готова.")
        return self._stt_rec

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
                        logger.debug(f"Core: Загружен плагин: {attr}")
            except Exception as e:
                logger.error(f"Core: Ошибка загрузки плагина {file.name}: {e}")

    def set_state(self, new_state):
        if self.ctx.state != new_state:
            logger.info(f"Core: Состояние {self.ctx.state} -> {new_state}")
            self.ctx.state = new_state
            if callable(self.ctx.ui_status):
                self.ctx.ui_status(new_state)

    def run(self):
        """Основной поток: координация аудио-захвата и распознавания."""
        # Запуск захвата звука в отдельном потоке
        threading.Thread(target=self.audio.listen, args=(self.stop_event,), daemon=True, name="AudioIn").start()
        logger.info("Core: Поток захвата запущен. Ожидание данных...")

        while self.ctx.is_running:
            self._check_activation_timeout()

            try:
                # Получаем чанк аудио из очереди (блокировка 0.2с чтобы не грузить CPU)
                data = self.audio.audio_q.get(timeout=0.2)

                if self.stt.AcceptWaveform(data):
                    res = json.loads(self.stt.Result()).get('text', '')
                    if res:
                        self._process_phrase(res)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Core: Ошибка в цикле обработки: {e}")
                continue

    def _process_phrase(self, text):
        """Диспетчер распознанного текста"""
        logger.debug(f"Core: Распознано -> {text}")

        is_trig, cmd_text = self._check_trigger(text)
        in_win = self._is_in_active_window()

        if is_trig:
            self._handle_command(cmd_text or "", source="mic", set_active=True)
        elif in_win:
            self._handle_command(text, source="mic", set_active=False)

    def _handle_command(self, text, source="mic", set_active=False):
        """Выполнение логики и управление состоянием"""
        self.ctx.set_input_source(source)

        if set_active:
            self.set_state("active")
            self.ctx.last_activation_time = time.time()
            logger.info(f"Core: Активация триггером -> '{text}'")

        if text.strip():
            if self.process_logic(text):
                # Если команда успешно выполнена — закрываем окно ожидания
                self.ctx.last_activation_time = 0
                self.set_state("idle")

    def process_logic(self, text):
        """Проход по плагинам."""
        for cmd in self.ctx.commands:
            try:
                if cmd.execute(text, self.ctx):
                    logger.info(f"Core: Плагин {cmd.__class__.__name__} выполнил задачу.")
                    return True
            except Exception as e:
                logger.error(f"Core: Ошибка в плагине {cmd.__class__.__name__}: {e}")
        return False

    def _check_trigger(self, text):
        main_name = aiko_cfg.get("bot.name", "айко").lower()
        threshold = aiko_cfg.get("audio.match_threshold", 80)
        return CommandMatcher.check_trigger(text, [main_name], threshold)

    def _is_in_active_window(self):
        return (time.time() - self.ctx.last_activation_time) < self.ctx.active_window

    def _check_activation_timeout(self):
        if not self._is_in_active_window() and self.ctx.state == "active":
            self.set_state("idle")

    def _scheduler_loop(self):
        """Планировщик теперь тоже 'холодный' — просто дергает базу и плагины."""
        while self.scheduler_active and self.ctx.is_running:
            try:
                tasks = db.get_pending_tasks()
                for t_id, t_type, t_payload in tasks:
                    for cmd in self.ctx.commands:
                        if hasattr(cmd, 'on_schedule') and t_type == getattr(cmd, 'type', ''):
                            cmd.on_schedule(t_payload, self.ctx)
                    db.update_task_status(t_id, 'done')
            except Exception as e:
                logger.error(f"Core: Ошибка планировщика: {e}")
            time.sleep(5)

    def restart_audio_capture(self):
        new_device_id = aiko_cfg.get("audio.device_id", 1)
        self.ctx.device_id = new_device_id
        if self.audio:
            self.audio.restart(new_device_id)