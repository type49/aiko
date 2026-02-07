import json
import os
from utils.logger import logger


class ConfigManager:
    """
    Централизованное управление конфигурацией.
    Поддерживает вложенные ключи через точку (напр. 'audio.master_volume').
    """

    def __init__(self, path="config.json"):
        self.path = path
        self.config = self._load()

    def _load(self):
        """Загрузка из файла или создание дефолта."""
        if not os.path.exists(self.path):
            defaults = self._get_defaults()
            self._save_to_file(defaults)
            logger.info(f"Config: Файл не найден. Создан дефолт: {self.path}")
            return defaults

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Config: Файл {self.path} успешно загружен.")
                return data
        except Exception as e:
            logger.error(f"Config: Критическая ошибка чтения {self.path}: {e}")
            return self._get_defaults()

    def _save_to_file(self, data):
        """Атомарная запись в JSON."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Config: Ошибка записи в {self.path}: {e}")
            return False

    def save(self):
        """Сброс текущего состояния памяти на диск."""
        return self._save_to_file(self.config)

    def _get_defaults(self):
        """Схема конфигурации по умолчанию."""
        return {
            "bot": {
                "name": "Айко"
            },
            "audio": {
                "device_id": 1,
                "samplerate": 16000,
                "master_volume": 0.7,
                "match_threshold": 80
            },
            "stt-model": {
                "path": "model"
            },
            "trigger": {
                "active_window": 5.0,
                "post_command_window": 3.0
            },
            "debug": {
                "log_commands": True,
                "matcher_debug": True
            }
        }

    def get(self, key, default=None):
        """
        Получение значения по ключу 'folder.sub.key'.
        Если ключ отсутствует, берется значение из дефолтов.
        """
        keys = key.split('.')

        # 1. Пробуем получить из текущего конфига
        val = self.config
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            # 2. Если не нашли — идем в дефолты
            return self._get_from_dict(self._get_defaults(), keys) or default

    def _get_from_dict(self, dictionary, keys):
        """Вспомогательный метод обхода дерева ключей."""
        val = dictionary
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return None

    def set(self, key, value, autosave=True):
        """
        Установка значения. Поддерживает создание путей.
        :param autosave: Если True, сразу пишет изменения в файл.
        """
        keys = key.split('.')
        data = self.config

        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]

        last_key = keys[-1]
        if data.get(last_key) != value:
            data[last_key] = value
            logger.info(f"Config: '{key}' изменен на '{value}'")
            if autosave:
                self.save()


# Глобальный экземпляр
aiko_cfg = ConfigManager()