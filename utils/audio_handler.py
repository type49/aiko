import sounddevice as sd
import queue
import time
from utils.logger import logger


class AudioHandler:
    def __init__(self, device_id=1, samplerate=16000, on_status_change=None):
        self.device_id = device_id
        self.samplerate = samplerate
        self.audio_q = queue.Queue()
        self.is_active = False
        self._need_restart = False
        self.on_status_change = on_status_change
        self.last_audio_time = 0

    def _callback(self, indata, frames, time_info, status):
        if status:
            if "input overflow" not in str(status).lower():
                raise sd.CallbackAbort

        self.last_audio_time = time.time()
        self.audio_q.put(indata.copy().tobytes())

    def _notify(self, new_state, msg):
        if self.is_active != new_state:
            self.is_active = new_state
            if self.on_status_change:
                self.on_status_change(new_state, msg)

    def listen(self, stop_event):
        while not stop_event.is_set():
            self._need_restart = False
            self.last_audio_time = time.time()

            try:
                # Обновляем список устройств перед каждой попыткой (важно для Windows)
                sd.query_devices()

                with sd.InputStream(
                        samplerate=self.samplerate,
                        device=self.device_id,
                        channels=1,
                        dtype='int16',
                        callback=self._callback,
                        blocksize=4000
                ):
                    self._notify(True, "Микрофон активен")

                    while not stop_event.is_set() and not self._need_restart:
                        # Если данных нет 1.5 сек — устройство захвачено DAW
                        if time.time() - self.last_audio_time > 1.5:
                            raise sd.PortAudioError("Микрофон недоступен.")
                        time.sleep(0.5)

            except Exception as e:
                self._notify(False, f"Ожидание: {e}")
                logger.warning(f"Микрофон недоступен. Попытка возврата через 10с...")

                # Ждем 10 секунд
                retry_time = 10
                while retry_time > 0 and not stop_event.is_set():
                    if self._need_restart: break
                    time.sleep(1)
                    retry_time -= 1