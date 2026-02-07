import pygame
import threading
import time
from pathlib import Path
from utils.logger import logger
from core.global_context import ctx


class AudioNamespace:
    def __init__(self, controller):
        self._controller = controller

    def __getattr__(self, name):
        try:
            from utils.config_manager import aiko_cfg
            sound_map = aiko_cfg.get("system_sound", {})

            if name in sound_map:
                path = sound_map[name]
                # Возвращаем лямбду, которая теперь вернет объект Channel или None
                return lambda **kwargs: self._controller._execute_play(path, **kwargs)

            logger.warning(f"AudioController: Звук '{name}' не найден.")
            return lambda **kwargs: None
        except Exception as e:
            logger.error(f"AudioController: Ошибка доступа к конфигу: {e}")
            return lambda **kwargs: None

    def __call__(self, relative_path, **kwargs):
        return self._controller._execute_play(relative_path, **kwargs)


class AudioController:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AudioController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self.base_dir = Path(__file__).resolve().parent.parent

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(20)
            self._sounds = {}
            self.play = AudioNamespace(self)
            self._initialized = True
            logger.info("AudioController: Система инициализирована.")
        except Exception as e:
            logger.error(f"AudioController: Ошибка инициализации: {e}")

    def _execute_play(self, relative_path: str, volume=0.5, channel_id=None, ignore_master=False):
        """Возвращает объект Channel для управления запущенным звуком."""
        if not self._initialized: return None

        try:
            from utils.config_manager import aiko_cfg

            # Логика абсолютной громкости
            if ignore_master:
                final_volume = volume
            else:
                master_vol = aiko_cfg.get("audio.master_volume", 1.0)
                final_volume = volume * master_vol

            full_path = self.base_dir / relative_path
            str_path = str(full_path)

            if not full_path.exists():
                logger.error(f"AudioController: Файл не найден: {str_path}")
                return None

            if str_path not in self._sounds:
                self._sounds[str_path] = pygame.mixer.Sound(str_path)

            sound = self._sounds[str_path]
            sound.set_volume(final_volume)

            # Запуск на конкретном канале или автоматический поиск свободного
            if channel_id is not None:
                channel = pygame.mixer.Channel(channel_id)
                channel.play(sound)
            else:
                channel = sound.play()

            return channel  # Теперь мы можем управлять этим звуком после старта

        except Exception as e:
            logger.error(f"AudioController: Ошибка воспроизведения: {e}")
            return None

    def play_with_overlap(self, first_sound_func, second_sound_func, overlap_ms: int):
        """
        Запускает первый звук, затем второй, и через overlap_ms гасит первый.
        Аргументы: лямбда-вызовы из audio_manager.play
        """

        def logic():
            # Запускаем первый
            ch1 = first_sound_func()

            # Здесь может быть логика ожидания конца или какого-то события.
            # Для примера: сразу запускаем второй звук
            ch2 = second_sound_func()

            if ch1 and ch2:
                # Ждем N мс после старта ВТОРОГО звука
                time.sleep(overlap_ms / 1000.0)
                # Плавно гасим первый звук за 300мс, чтобы не было щелчка
                ch1.fadeout(300)

        threading.Thread(target=logic, daemon=True).start()

    def stop_all(self):
        if self._initialized:
            pygame.mixer.stop()


audio_manager = AudioController()