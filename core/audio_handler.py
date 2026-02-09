import sounddevice as sd
import queue
import time
from utils.logger import logger
from core.global_context import ctx


class AudioHandler:
    """
    Интерфейс захвата аудио.
    Обеспечивает стабильный поток данных из микрофона в систему.
    """

    def __init__(self, device_id=1, samplerate=16000, on_status_change=None):
        self.device_id = device_id
        self.samplerate = samplerate
        self.audio_q = queue.Queue()

        self.is_active = None
        self._need_restart = False
        self.on_status_change = on_status_change

        self.last_audio_time = 0
        self.error_count = 0

    def _callback(self, indata, frames, time_info, status):
        """
        Низкоуровневый колбэк PortAudio. Вызывается в отдельном высокоприоритетном потоке.
        """
        if status:
            # Игнорируем переполнение буфера, это обычное дело при кратковременных нагрузках
            if "input overflow" not in str(status).lower():
                logger.error(f"Audio: PortAudio status error: {status}")
                return

        self.last_audio_time = time.time()
        # Копируем данные, чтобы избежать повреждения при переиспользовании буфера библиотекой
        self.audio_q.put(indata.copy().tobytes())

    def _notify(self, new_state: bool, msg: str):
        """
        Уведомляет ядро и UI об изменении состояния микрофона.
        Использует фильтр повторов, чтобы не спамить в логи.
        """
        if self.is_active == new_state:
            return

        self.is_active = new_state
        prefix = "🟢" if new_state else "🔴"
        logger.info(f"Audio: {prefix} {msg}")

        if self.on_status_change:
            # Передаем статус дальше (например, для отрисовки иконки в GUI)
            self.on_status_change(new_state, msg)

    def listen(self, stop_event):
        """
        Основной цикл захвата. Инициализирует поток и следит за его 'здоровьем'.
        """
        logger.info(f"Audio: Запуск захвата (Device: {self.device_id}, Rate: {self.samplerate})")

        while not stop_event.is_set():
            self._need_restart = False
            self.last_audio_time = time.time()

            # Очищаем очередь от старых данных перед новым запуском
            with self.audio_q.mutex:
                self.audio_q.queue.clear()

            try:
                # Валидация устройства
                devices = sd.query_devices()
                if self.device_id >= len(devices):
                    raise IndexError(f"Устройство #{self.device_id} отсутствует.")

                dev_info = devices[self.device_id]
                logger.debug(f"Audio: Открытие потока для '{dev_info['name']}'")

                # Настройка входного потока
                with sd.InputStream(
                        samplerate=self.samplerate,
                        device=self.device_id,
                        channels=1,
                        dtype='int16',
                        callback=self._callback,
                        blocksize=4000  # Снизил до 125мс для лучшей отзывчивости, можно 4000
                ):
                    ctx().broadcast(f"Микрофон готов", level="error", ui=True)
                    self._notify(True, "Микрофон готов")
                    self.error_count = 0

                    # Контрольный цикл внутри активного стрима
                    while not stop_event.is_set() and not self._need_restart:
                        # Hardware Watchdog: если данные не поступали более 2 секунд
                        if time.time() - self.last_audio_time > 2.0:
                            raise sd.PortAudioError("Hardware Timeout: Устройство молчит.")

                        time.sleep(0.4)

            except Exception as e:
                self._notify(False, f"Ошибка: {str(e)[:40]}")
                # Экспоненциальная пауза перед рестартом не нужна,
                # фиксированные 5-10 секунд достаточно, чтобы не перегреть лог
                logger.warning("Audio: Ожидание перед повторной попыткой подключения...")

                wait_counter = 0
                while wait_counter < 10 and not stop_event.is_set() and not self._need_restart:
                    time.sleep(1)
                    wait_counter += 1

    def restart(self, new_device_id=None):
        """
        Принудительный перезапуск потока (например, при смене настроек в GUI).
        """
        if new_device_id is not None:
            self.device_id = new_device_id

        logger.warning(f"Audio: Запрошен горячий рестарт (Device ID -> {self.device_id})")
        self._need_restart = True
