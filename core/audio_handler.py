import sounddevice as sd
import queue
import time
import threading
from utils.logger import logger
from core.global_context import ctx


class AudioHandler:
    """
    Интерфейс захвата аудио.
    Обеспечивает стабильный поток данных из микрофона в систему.
    Поддерживает физическое включение/выключение микрофона.
    """

    def __init__(self, device_id=1, samplerate=16000, on_status_change=None):
        self.device_id = device_id
        self.samplerate = samplerate
        self.audio_q = queue.Queue()

        self.is_active = None
        self._need_restart = False
        self._stream_active = False  # Флаг активности потока
        self.on_status_change = on_status_change

        self.last_audio_time = 0
        self.error_count = 0

        # Для контроля потока
        self._stream = None
        self._stream_lock = threading.Lock()

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

    def stop_stream(self):
        """
        Физически останавливает аудиопоток, освобождая микрофон.
        Вызывается при выключении микрофона через GUI или команду.
        """
        with self._stream_lock:
            if self._stream is not None and self._stream_active:
                try:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                    self._stream_active = False
                    self._notify(False, "Микрофон освобождён")
                    logger.info("Audio: Поток остановлен, микрофон освобождён")

                    # Очищаем очередь
                    with self.audio_q.mutex:
                        self.audio_q.queue.clear()

                except Exception as e:
                    logger.error(f"Audio: Ошибка остановки потока: {e}")

    def start_stream(self):
        """
        Физически запускает аудиопоток, захватывая микрофон.
        Вызывается при включении микрофона через GUI или команду.
        """
        with self._stream_lock:
            if self._stream_active:
                logger.debug("Audio: Поток уже активен")
                return True

            try:
                # Валидация устройства
                devices = sd.query_devices()
                if self.device_id >= len(devices):
                    raise IndexError(f"Устройство #{self.device_id} отсутствует.")

                dev_info = devices[self.device_id]
                logger.debug(f"Audio: Открытие потока для '{dev_info['name']}'")

                # Очищаем очередь перед запуском
                with self.audio_q.mutex:
                    self.audio_q.queue.clear()

                # Создаём поток
                self._stream = sd.InputStream(
                    samplerate=self.samplerate,
                    device=self.device_id,
                    channels=1,
                    dtype='int16',
                    callback=self._callback,
                    blocksize=4000
                )

                self._stream.start()
                self._stream_active = True
                self.last_audio_time = time.time()

                # self._notify(True, "Микрофон захвачен")
                logger.info("Audio: Поток запущен, микрофон захвачен")
                return True

            except Exception as e:
                error_msg = f"Не удалось захватить микрофон: {str(e)[:60]}"
                self._notify(False, error_msg)
                logger.error(f"Audio: Ошибка запуска потока: {e}")

                # Уведомляем контекст что микрофон заблокирован
                if ctx():
                    ctx().set_microphone_state(False, source="audio_error")
                    ctx().broadcast(error_msg, level="error", ui=True, tg=False)

                return False

    def listen(self, stop_event):
        """
        Основной цикл захвата. Инициализирует поток и следит за его 'здоровьем'.
        Теперь с поддержкой динамического включения/выключения.
        """
        logger.info(f"Audio: Запуск захвата (Device: {self.device_id}, Rate: {self.samplerate})")

        # Запускаем поток сразу при старте
        self.start_stream()

        while not stop_event.is_set():
            # Проверяем здоровье потока только если он должен быть активен
            if self._stream_active and ctx() and ctx().get_microphone_should_listen():
                try:
                    # Hardware Watchdog: если данные не поступали более 3 секунд
                    if time.time() - self.last_audio_time > 3.0:
                        logger.warning("Audio: Микрофон молчит более 3 секунд, возможна проблема")

                        # Проверяем, не забрала ли другая программа микрофон
                        with self._stream_lock:
                            if self._stream is not None:
                                try:
                                    # Пытаемся проверить активность потока
                                    if not self._stream.active:
                                        raise sd.PortAudioError("Поток неактивен - микрофон захвачен другой программой")
                                except Exception as e:
                                    logger.error(f"Audio: Обнаружена потеря микрофона: {e}")

                                    # Уведомляем систему о потере микрофона
                                    self._notify(False, "Микрофон захвачен другой программой")
                                    if ctx():
                                        ctx().set_microphone_state(False, source="hardware_conflict")
                                        ctx().broadcast(
                                            "Микрофон захвачен другим приложением",
                                            level="error",
                                            ui=True,
                                            tg=False
                                        )

                                    # Останавливаем поток
                                    self.stop_stream()

                except Exception as e:
                    logger.error(f"Audio: Ошибка проверки здоровья: {e}")

            time.sleep(0.5)

        # Останавливаем поток при завершении
        self.stop_stream()
        logger.info("Audio: Цикл захвата завершён")

    def restart(self, new_device_id=None):
        """
        Принудительный перезапуск потока (например, при смене настроек в GUI).
        """
        if new_device_id is not None:
            self.device_id = new_device_id

        logger.warning(f"Audio: Запрошен горячий рестарт (Device ID -> {self.device_id})")

        # Останавливаем текущий поток
        self.stop_stream()

        # Небольшая пауза
        time.sleep(0.5)

        # Запускаем новый поток если микрофон должен быть включен
        if ctx() and ctx().get_microphone_should_listen():
            self.start_stream()