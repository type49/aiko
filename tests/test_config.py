from utils.config_manager import ConfigManager
import os


def test_config_defaults():
    # Создаем конфиг без файла (имя временное)
    test_filename = "test_config_temp.json"

    # Убедимся, что файла нет перед тестом
    if os.path.exists(test_filename):
        os.remove(test_filename)

    try:
        cfg = ConfigManager(test_filename)

        # Проверяем дефолты
        assert cfg.get("bot.name") == "Айко"
        assert cfg.get("audio.master_volume") == 0.7

    finally:
        # Clean up: Всегда удаляем мусор за собой, даже если тест упал
        if os.path.exists(test_filename):
            os.remove(test_filename)