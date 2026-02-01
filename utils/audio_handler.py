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

    def _callback(self, indata, frames, time_info, status):
        """Внутренний колбэк для захвата байтов"""
        if status:
            logger.warning(f"Статус аудио-потока: {status}")
        self.last_audio_time = time.time()
        self.audio_q.put(bytes(indata))

    def listen(self, stop_event):
        logger.info(f"Захват аудио запущен на устройстве {self.device_id}")

        while not stop_event.is_set():
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

                    while not stop_event.is_set():
                        if self.is_active and (time.time() - self.last_audio_time > 5.0):
                            logger.error("Поток аудио прерван (тайм-аут данных)")
                            break
                        time.sleep(1.0)
            except Exception as e:
                self.is_active = False
                logger.warning(f"Ошибка аудио-входа: {e}. Повтор через 5 сек...")
                time.sleep(5)