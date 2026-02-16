# -*- coding: utf-8 -*-
import sounddevice as sd
import queue
import time
import threading
from utils.logger import logger


class AudioHandler:
    """
    Интерфейс захвата аудио.
    Обеспечивает стабильный поток данных из микрофона в систему.
    Поддерживает физическое включение/выключение микрофона.

    ИСПРАВЛЕНО: Устранен deadlock через использование очереди команд
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

        # ИСПРАВЛЕНИЕ: Очередь команд для thread-safe управления потоком
        self._command_queue = queue.Queue()
        self._ctx_ref = None  # Слабая ссылка на контекст (избегаем циклических импортов)

    def set_context(self, ctx):
        """Устанавливает ссылку на контекст после инициализации"""
        self._ctx_ref = ctx

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

    def get_stream_state(self):
        """
        Безопасное получение реального состояния потока.
        Используется для синхронизации UI.
        """
        with self._stream_lock:
            return self._stream_active

    def _clear_audio_queue(self):
        """Безопасная очистка очереди аудио"""
        # ИСПРАВЛЕНИЕ: Правильная очистка без прямого доступа к внутренней структуре
        while not self.audio_q.empty():
            try:
                self.audio_q.get_nowait()
            except queue.Empty:
                break

    def _stop_stream_internal(self):
        """
        Внутренний метод остановки потока.
        Вызывается только из audio потока.
        """
        with self._stream_lock:
            if self._stream is not None and self._stream_active:
                try:
                    self._stream.stop()
                    self._stream.close()
                    self._stream = None
                    self._stream_active = False
                    logger.info("Audio: Поток остановлен, микрофон освобождён")

                    # Очищаем очередь
                    self._clear_audio_queue()

                except Exception as e:
                    logger.error(f"Audio: Ошибка остановки потока: {e}")

    def stop_stream(self):
        """
        Публичный метод остановки потока.
        Безопасен для вызова из любого потока.
        """
        # ИСПРАВЛЕНИЕ: Добавляем команду в очередь вместо прямого вызова
        self._command_queue.put(('stop', None))

    def _start_stream_internal(self):
        """
        Внутренний метод запуска потока.
        Вызывается только из audio потока.
        """
        # Быстрая проверка без блокировки
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
            self._clear_audio_queue()

            # Создаём поток БЕЗ глобальной блокировки (sounddevice thread-safe)
            new_stream = sd.InputStream(
                samplerate=self.samplerate,
                device=self.device_id,
                channels=1,
                dtype='int16',
                callback=self._callback,
                blocksize=4000
            )

            # Запускаем поток
            new_stream.start()

            # Атомарное обновление состояния с минимальной блокировкой
            with self._stream_lock:
                self._stream = new_stream
                self._stream_active = True
                self.last_audio_time = time.time()

            logger.info("Audio: Поток запущен, микрофон захвачен")
            return True

        except Exception as e:
            error_msg = f"Не удалось захватить микрофон: {str(e)[:60]}"
            self._notify(False, error_msg)
            logger.error(f"Audio: Ошибка запуска потока: {e}")

            # ИСПРАВЛЕНИЕ: Безопасное уведомление контекста без deadlock
            if self._ctx_ref:
                # Не вызываем set_microphone_state напрямую - это может вызвать deadlock
                # Вместо этого только логируем и уведомляем через broadcast
                try:
                    self._ctx_ref.broadcast(error_msg, level="error", ui=True, tg=False)
                except Exception as broadcast_err:
                    logger.error(f"Audio: Ошибка broadcast: {broadcast_err}")

            return False

    def start_stream(self):
        """
        Публичный метод запуска потока.
        Безопасен для вызова из любого потока.
        """
        # ИСПРАВЛЕНИЕ: Добавляем команду в очередь вместо прямого вызова
        self._command_queue.put(('start', None))

    def _process_commands(self):
        """Обработка команд из очереди (вызывается в audio потоке)"""
        try:
            command, args = self._command_queue.get_nowait()

            if command == 'start':
                self._start_stream_internal()
            elif command == 'stop':
                self._stop_stream_internal()
            elif command == 'restart':
                device_id = args
                if device_id is not None:
                    self.device_id = device_id
                self._stop_stream_internal()
                time.sleep(0.5)
                if self._ctx_ref and self._ctx_ref.get_microphone_should_listen():
                    self._start_stream_internal()

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Audio: Ошибка обработки команды: {e}")

    def listen(self, stop_event):
        """
        Основной цикл захвата. Инициализирует поток и следит за его 'здоровьем'.
        Теперь с поддержкой динамического включения/выключения.
        """
        logger.info(f"Audio: Запуск захвата (Device: {self.device_id}, Rate: {self.samplerate})")

        # Запускаем поток сразу при старте
        self._start_stream_internal()

        while not stop_event.is_set():
            # ИСПРАВЛЕНИЕ: Обрабатываем команды из очереди
            self._process_commands()

            # Проверяем здоровье потока только если он должен быть активен
            if self._stream_active and self._ctx_ref and self._ctx_ref.get_microphone_should_listen():
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
                                    if self._ctx_ref:
                                        try:
                                            self._ctx_ref.broadcast(
                                                "Микрофон захвачен другим приложением",
                                                level="error",
                                                ui=True,
                                                tg=False
                                            )
                                        except Exception as broadcast_err:
                                            logger.error(f"Audio: Ошибка broadcast: {broadcast_err}")

                                    # Останавливаем поток
                                    self._stop_stream_internal()

                except Exception as e:
                    logger.error(f"Audio: Ошибка проверки здоровья: {e}")

            time.sleep(0.1)  # Уменьшили с 0.5 для более быстрой обработки команд

        # Останавливаем поток при завершении
        self._stop_stream_internal()
        logger.info("Audio: Цикл захвата завершён")

    def restart(self, new_device_id=None):
        """
        Принудительный перезапуск потока (например, при смене настроек в GUI).
        Безопасен для вызова из любого потока.
        """
        logger.warning(f"Audio: Запрошен горячий рестарт (Device ID -> {new_device_id or self.device_id})")
        # ИСПРАВЛЕНИЕ: Добавляем команду в очередь
        self._command_queue.put(('restart', new_device_id))