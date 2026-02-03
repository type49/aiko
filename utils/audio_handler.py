import sounddevice as sd
import queue
import time
from utils.logger import logger


class AudioHandler:
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
        """Вызывается библиотекой sounddevice для каждого чанка аудио."""
        if status:
            # overflow — это норма при пиках нагрузки, игнорируем его
            if "input overflow" not in str(status).lower():
                logger.error(f"Audio: Статус ошибки PortAudio: {status}")
                return  # Не прерываем поток из-за разовой ошибки

        self.last_audio_time = time.time()
        # Помещаем данные в очередь для STT
        self.audio_q.put(indata.copy().tobytes())

    def _notify(self, new_state, msg):
        """Уведомление системы с защитой от спама."""
        # Если состояние такое же, как было — ничего не делаем
        if self.is_active == new_state:
            return

        # Если состояние изменилось — обновляем и уведомляем
        self.is_active = new_state

        prefix = "✅" if new_state else "❌"
        logger.info(f"Audio: {prefix} {msg}")

        if self.on_status_change:
            self.on_status_change(new_state, msg)

    def listen(self, stop_event):
        """Основной цикл захвата. Работает в отдельном потоке."""
        logger.info(f"Audio: Старт потока захвата (ID: {self.device_id}, Rate: {self.samplerate})")

        while not stop_event.is_set():
            self._need_restart = False
            self.last_audio_time = time.time()

            try:
                # Проверяем существование устройства перед открытием
                devices = sd.query_devices()
                if self.device_id >= len(devices):
                    raise IndexError(f"Устройство {self.device_id} не найдено в системе.")

                dev_info = devices[self.device_id]
                logger.info(f"Audio: Попытка открыть '{dev_info['name']}'")

                with sd.InputStream(
                        samplerate=self.samplerate,
                        device=self.device_id,
                        channels=1,
                        dtype='int16',
                        callback=self._callback,
                        blocksize=4000  # ~250ms чанки
                ):
                    self._notify(True, "Микрофон подключен")
                    self.error_count = 0  # Сброс счетчика ошибок при успехе

                    while not stop_event.is_set() and not self._need_restart:
                        # Watchdog: проверка «зависания» потока данных
                        if time.time() - self.last_audio_time > 2.0:
                            logger.error("Audio: Поток данных прерван (Hardware Timeout)")
                            raise sd.PortAudioError("Устройство не передает данные.")

                        time.sleep(0.5)

            except Exception as e:
                self._notify(False, f"Ошибка аудио: {str(e)[:50]}")
                wait_time = 10
                for _ in range(wait_time):
                    if stop_event.is_set() or self._need_restart: break
                    time.sleep(1)

    def restart(self, new_device_id=None):
        """Метод для 'горячей' смены микрофона"""
        if new_device_id is not None:
            self.device_id = new_device_id
        logger.warning(f"Audio: Запрошен перезапуск. Новое устройство: {self.device_id}")
        self._need_restart = True