import json
import os
from utils.logger import logger


class ConfigManager:
    def __init__(self, path="config.json"):
        self.path = path
        self.config = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            defaults = self._get_defaults()
            self._save_to_file(defaults)
            logger.info(f"Создан дефолтный конфиг: {self.path}")
            return defaults

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения конфига {self.path}: {e}")
            return self._get_defaults()

    def _save_to_file(self, data):
        """Внутренний метод записи данных в файл"""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Ошибка записи в файл {self.path}: {e}")
            return False

    def save(self):
        """Публичный метод для сохранения текущего состояния self.config"""
        return self._save_to_file(self.config)

    def _get_defaults(self):
        return {
            "bot": {
                "name": "Айко"
            },
            "audio": {
                "device_index": 0,
                "samplerate": 16000,
                "master_volume": 0.7,
                "match_threshold": 80 # Вынес порог сюда
            },
            "trigger": {
                "active_window": 5.0
            },
            "debug": {
                "log_commands": True,
                "matcher_debug": True
            }
        }

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.config
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return self.get_from_defaults(key) or default

    def get_from_defaults(self, key):
        """Вспомогательный метод для поиска в дефолтном словаре"""
        keys = key.split('.')
        val = self._get_defaults()
        try:
            for k in keys:
                val = val[k]
            return val
        except:
            return None

    def set(self, key, value):
        """
        Устанавливает значение в конфиг. Поддерживает вложенность 'folder.subfolder.key'.
        """
        keys = key.split('.')
        data = self.config

        # Идем по дереву словаря до предпоследнего ключа
        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]

        last_key = keys[-1]
        old_value = data.get(last_key)

        if old_value != value:
            data[last_key] = value
            logger.debug(f"Config: Update {key} -> {value}")


aiko_cfg = ConfigManager()