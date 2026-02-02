import pygame
import threading
import os
from pathlib import Path

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

        # Определяем корень проекта (на одну папку выше, чем utils/)
        self.base_dir = Path(__file__).resolve().parent.parent

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(8)
            self._sounds = {}
            self._initialized = True
            print(f"[AUDIO]: Контроллер готов. Корень: {self.base_dir}")
        except Exception as e:
            print(f"[AUDIO ERROR]: {e}")

    def play(self, relative_path, volume=0.5, channel_id=None):
        if not self._initialized: return

        try:
            # Импортируем конфиг здесь, чтобы избежать циклического импорта
            from utils.config_manager import aiko_cfg

            # Читаем мастер-громкость (0.0 - 1.0)
            master_vol = aiko_cfg.get("audio.master_volume", 1.0)

            # Финальная громкость = (локальная громкость плагина) * (мастер-громкость)
            # Если в плагине 0.8, а в мастере 0.5 -> звук будет 0.4
            final_volume = volume * master_vol

            clean_path = relative_path.lstrip("./").lstrip("/")
            full_path = self.base_dir / clean_path
            str_path = str(full_path)

            if not full_path.exists():
                print(f"[AUDIO ERROR]: Файл не найден: {str_path}")
                return

            if str_path not in self._sounds:
                self._sounds[str_path] = pygame.mixer.Sound(str_path)

            sound = self._sounds[str_path]

            # Устанавливаем ВЫЧИСЛЕННУЮ громкость
            sound.set_volume(final_volume)

            if channel_id is not None:
                pygame.mixer.Channel(channel_id).play(sound)
            else:
                sound.play()

            # print(f"[AUDIO]: Play {relative_path} (Master: {master_vol}, Result: {final_volume})")

        except Exception as e:
            print(f"[AUDIO ERROR]: Ошибка воспроизведения {relative_path}: {e}")

audio_manager = AudioController()
