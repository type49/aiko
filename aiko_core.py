import time
import threading
import queue
from utils.logger import logger
from core.audio_handler import AudioHandler
from core.plugin_loader import PluginLoader
from utils.Intent_сlassifier import IntentClassifier
from core.activation_service import ActivationService
from core.scheduler import TaskScheduler
from core.plugin_router import CommandRouter
from core.stt import STTService


class AikoCore:
    """
    Финальная версия Core.
    Один класс. Управляемый lifecycle. Без архитектурного долга.
    """

    MAX_RESTARTS = 3
    RESTART_COOLDOWN = 5  # сек

    def __init__(self, ctx):
        self.ctx = ctx
        self.stop_event = threading.Event()

        self.threads = {}
        self.restart_counters = {}

        logger.info("Core: Инициализация...")

        # --- Подсистемы ---
        self.audio = AudioHandler(
            device_id=self.ctx.device_id,
            on_status_change=self.ctx.ui_audio_status
        )

        self.stt = STTService(self.ctx.model_path)
        self.activation = ActivationService(self.ctx)

        cmds, intent_map, fallbacks = PluginLoader.load_all()
        self.ctx.commands = cmds

        nlu = IntentClassifier()
        nlu.train(cmds)

        self.router = CommandRouter(nlu, intent_map, fallbacks)
        self.scheduler = TaskScheduler(self.ctx)

        logger.info("Core: Готово.")

    # =========================
    # Lifecycle
    # =========================

    def run(self):
        logger.info("Core: Запуск системы.")

        self._start_thread(
            name="AudioIn",
            target=self.audio.listen,
            args=(self.stop_event,)
        )

        self.scheduler.start()

        try:
            while not self.stop_event.is_set():
                self._monitor_health()
                self.activation.handle_timeouts(self.set_state)

                for cmd in self.ctx.commands:
                    if hasattr(cmd, 'on_tick'):
                        try:
                            cmd.on_tick(self.ctx)
                        except Exception as e:
                            logger.error(f"Core: Ошибка тика в {cmd.__class__.__name__}: {e}")
                    # ----------------------------------

                try:
                    # Уменьшаем timeout, чтобы цикл крутился чаще и тики были точнее
                    data = self.audio.audio_q.get(timeout=0.1)
                    phrase = self.stt.get_phrase(data)

                    if phrase:
                        self._on_phrase_detected(phrase)

                except queue.Empty:
                    continue

        except KeyboardInterrupt:
            logger.warning("Core: Остановка по Ctrl+C")
        except Exception:
            logger.critical("Core: Фатальный сбой", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Core: Shutdown...")

        self.stop_event.set()

        if self.scheduler:
            self.scheduler.stop()

        for name, t in self.threads.items():
            if t.is_alive():
                logger.debug(f"Core: Ожидание {name}")
                t.join(timeout=2)

        logger.info("Core: Остановлен корректно.")

    # =========================
    # Threads & Health
    # =========================

    def _start_thread(self, name, target, args=(), daemon=True):
        t = threading.Thread(
            name=name,
            target=target,
            args=args,
            daemon=daemon
        )
        t.start()
        self.threads[name] = t
        logger.debug(f"Core: Поток {name} запущен")

    def _monitor_health(self):
        for name, t in list(self.threads.items()):
            if not t.is_alive() and not self.stop_event.is_set():
                self._handle_thread_failure(name)

    def _handle_thread_failure(self, name):
        count = self.restart_counters.get(name, 0)

        if count >= self.MAX_RESTARTS:
            logger.critical(
                f"Health: Поток {name} упал {count} раз. Остановка системы."
            )
            self.stop_event.set()
            return

        logger.warning(
            f"Health: Поток {name} упал. Перезапуск {count + 1}/{self.MAX_RESTARTS}"
        )

        self.restart_counters[name] = count + 1
        time.sleep(self.RESTART_COOLDOWN)

        if name == "AudioIn":
            self._start_thread(
                name="AudioIn",
                target=self.audio.listen,
                args=(self.stop_event,)
            )

    # =========================
    # Logic
    # =========================

    def _on_phrase_detected(self, text: str):
        should_exec, clean_text = self.activation.check(text)

        if not should_exec:
            return

        self.ctx.set_input_source("mic")
        name_triggered = (clean_text != text)

        if name_triggered:
            self.set_state("active")
            # --- НОВАЯ ПРОВЕРКА ---
            if not clean_text.strip():
                logger.info("Core: Получена пустая активация (имя без команды). Ожидаю ввод...")
                self.activation.refresh_activation()
                # Здесь можно вызвать self.ctx.reply("Слушаю") или пискнуть
                return
                # ----------------------

        executed = self.router.route(clean_text, self.ctx)

        if executed:
            self.activation.extend_post_command_window()
        elif name_triggered:
            self.activation.refresh_activation()

    # =========================
    # UI State
    # =========================

    def set_state(self, new_state: str):
        if self.ctx.state != new_state:
            logger.debug(f"Core: state {self.ctx.state} → {new_state}")
            self.ctx.state = new_state
            if self.ctx.ui_status:
                self.ctx.ui_status(new_state)
