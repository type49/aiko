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
            self._save(defaults)
            logger.info(f"Создан дефолтный конфиг: {self.path}")
            return defaults

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения конфига {self.path}: {e}")
            return self._get_defaults()

    def _save(self, data):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _get_defaults(self):
        return {
            "audio": {
                "device_id": 1,
                "samplerate": 16000,
                "match_threshold": 80
            },
            "trigger": {
                "names": ["айко", "айка", "хайко", "лайко", "аико", "ойко", "найко", "ай ко"],
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
            return default


aiko_cfg = ConfigManager()