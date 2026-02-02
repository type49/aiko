import sounddevice as sd
import queue
import time
from utils.logger import logger


class AudioHandler:
    def __init__(self, device_id=1, samplerate=16000):
        self.device_id = device_id
        self.samplerate = samplerate
        self.audio_q = queue.Queue()
        self.last_audio_time = 0
        self.is_active = False
        self._need_restart = False  # Флаг для перезапуска

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"Статус аудио-потока: {status}")
        self.last_audio_time = time.time()
        self.audio_q.put(bytes(indata))

    def restart(self, new_device_id):
        """Метод для внешнего сигнала о смене микрофона"""
        logger.info(f"AudioHandler: Запрос перезапуска на устройство {new_device_id}")
        self.device_id = new_device_id
        self._need_restart = True  # Это разорвет внутренний while и пересоберет InputStream

    def listen(self, stop_event):
        while not stop_event.is_set():
            self._need_restart = False
            logger.info(f"Захват аудио инициирован: Dev {self.device_id}")

            try:
                with sd.RawInputStream(
                        samplerate=self.samplerate,
                        blocksize=8000,
                        device=self.device_id,
                        dtype='int16',
                        channels=1,
                        callback=self._callback
                ):
                    self.is_active = True
                    self.last_audio_time = time.time()

                    while not stop_event.is_set() and not self._need_restart:
                        if self.is_active and (time.time() - self.last_audio_time > 5.0):
                            logger.error("Поток аудио прерван (тайм-аут данных)")
                            break
                        time.sleep(0.5)  # Уменьшил время сна для отзывчивости

                if self._need_restart:
                    logger.info("AudioHandler: Поток закрыт для смены устройства.")
                    continue  # Переходит к началу внешнего цикла с новым ID

            except Exception as e:
                self.is_active = False
                logger.warning(f"Ошибка аудио-входа: {e}. Повтор через 5 сек...")
                time.sleep(5)