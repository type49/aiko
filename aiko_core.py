import sounddevice as sd
import queue
import json
import time
import threading
import importlib.util
from pathlib import Path
from vosk import Model, KaldiRecognizer
from fuzzywuzzy import fuzz

from interfaces import AikoCommand
from utils.db_manager import db  # Твой новый менеджер БД


class AikoContext:
    def __init__(self):
        self.is_running = True
        self.mic_active = True
        self.last_activation_time = 0
        self.active_window = 5.0
        self.device_id = 1
        # Путь к модели (используем относительный через Path)
        self.model_path = Path("models/small/vosk-model-small-ru-0.22")
        self.commands = []
        self.state = "idle"

        # Слот для GUI функций (Dependency Injection)
        self.ui_log = lambda text, type: None
        self.ui_open_reminder = lambda text: None
        self.ui_status = lambda status: None


class AikoCore:
    def __init__(self, ctx=None):
        self.ctx = ctx or AikoContext()
        self.audio_q = queue.Queue()
        self.last_audio_arrival = 0

        if not self.ctx.model_path.exists():
            raise FileNotFoundError(f"Модель не найдена: {self.ctx.model_path}")

        self.model = Model(str(self.ctx.model_path))
        self.rec = KaldiRecognizer(self.model, 16000)

        # Теперь БД инициализируется внутри db_manager автоматически при импорте
        self._load_plugins()

        # ЗАПУСК ПЛАНИРОВЩИКА И МОНИТОРИНГА:
        self.scheduler_active = True
        self.sched_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.sched_thread.start()

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
                        print(f"[CORE]: Загружен плагин: {attr}")
            except Exception as e:
                print(f"[ОШИБКА ЗАГРУЗКИ]: {file.name} -> {e}")

    def _audio_callback(self, indata, frames, time_info, status):
        if self.ctx.mic_active:
            self.last_audio_arrival = time.time()
            self.audio_q.put(bytes(indata))

    def set_state(self, new_state):
        if self.ctx.state != new_state:
            self.ctx.state = new_state
            if callable(self.ctx.ui_status):
                self.ctx.ui_status(new_state)

    def listen_worker(self):
        print(f"[CORE]: Мониторинг микрофона (ID: {self.ctx.device_id})")
        last_log = None

        while self.ctx.is_running:
            if not self.ctx.mic_active:
                self.set_state("off")
                time.sleep(1.0)
                continue

            try:
                with sd.RawInputStream(samplerate=16000, blocksize=4000, device=self.ctx.device_id,
                                       dtype='int16', channels=1, callback=self._audio_callback):

                    start_t = time.time()
                    self.last_audio_arrival = 0

                    while self.ctx.is_running and self.ctx.mic_active:
                        curr_t = time.time()

                        if self.last_audio_arrival > 0:
                            if last_log != "ok":
                                if self.ctx.state != "active":
                                    self.set_state("idle")
                                self.ctx.ui_log("Микрофон активен", "success")
                                last_log = "ok"

                        deadline = self.last_audio_arrival if self.last_audio_arrival > 0 else start_t
                        if curr_t - deadline > 2.5:
                            raise RuntimeError("DAW Capture Detected")

                        time.sleep(0.3)

            except Exception:
                if last_log != "error":
                    self.set_state("blocked")
                    self.ctx.ui_log("Микрофон занят DAW", "error")
                    last_log = "error"

                self.last_audio_arrival = 0
                time.sleep(5)

    def process_logic(self, text):
        if not text: return
        for cmd in self.ctx.commands:
            if cmd.execute(text, self.ctx):
                return True
        return False

    def run(self):
        threading.Thread(target=self.listen_worker, daemon=True).start()

        while self.ctx.is_running:
            curr_t = time.time()

            in_win = (curr_t - self.ctx.last_activation_time) < self.ctx.active_window
            if not in_win and self.ctx.state == "active":
                self.set_state("idle")

            try:
                data = self.audio_q.get(timeout=0.2)

                if self.rec.AcceptWaveform(data):
                    res = json.loads(self.rec.Result()).get('text', '')
                    if res:
                        print(f"[CORE]: -> {res}")
                        is_trig, cmd = self._check_trigger(res)

                        if is_trig:
                            self.set_state("active")
                            self.ctx.last_activation_time = time.time()
                            if cmd:
                                if self.process_logic(cmd):
                                    self.ctx.last_activation_time = 0

                        elif in_win:
                            if self.process_logic(res):
                                self.ctx.last_activation_time = 0

            except queue.Empty:
                continue

    def _check_trigger(self, text):
        words = text.lower().split()
        if not words: return False, ""
        trigger = "айко"
        variants = ["айка", "хайко", "лайко", "аико", "ойко", "найко", "ай ко", "а и ко"]
        scores = [fuzz.ratio(words[0], trigger)] + [fuzz.ratio(words[0], v) for v in variants]
        if max(scores) >= 80:
            return True, " ".join(words[1:])
        return False, ""

    def _scheduler_loop(self):
        print("[CORE]: Планировщик и тики плагинов запущены.")
        while self.scheduler_active and self.ctx.is_running:
            try:
                # 1. Проверка задач через DBManager
                tasks = db.get_pending_tasks()
                for t_id, t_type, t_payload in tasks:
                    for cmd in self.ctx.commands:
                        if hasattr(cmd, 'on_schedule') and t_type == cmd.type:
                            cmd.on_schedule(t_payload, self.ctx)

                    db.update_task_status(t_id, 'done')

                # 2. Проверка активных состояний (тики)
                for cmd in self.ctx.commands:
                    if hasattr(cmd, 'on_tick'):
                        cmd.on_tick(self.ctx)

            except Exception as e:
                print(f"[SCHEDULER ERROR]: {e}")

            time.sleep(5)

    def add_scheduler_task(self, task_type, payload, exec_at):
        """Проброс метода сохранения в DBManager"""
        return db.add_task(task_type, payload, exec_at)