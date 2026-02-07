"""
Тесты для ConfigManager
"""
import pytest
import json
from pathlib import Path
from utils.config_manager import ConfigManager


@pytest.mark.unit
class TestConfigManager:
    """Тесты менеджера конфигурации"""
    
    def test_create_default_config(self, temp_dir):
        """Проверка создания дефолтной конфигурации"""
        config_path = temp_dir / "config.json"
        cfg = ConfigManager(str(config_path))
        
        assert config_path.exists()
        assert cfg.get("bot.name") == "Айко"
        assert cfg.get("audio.device_id") == 1
    
    def test_load_existing_config(self, temp_dir):
        """Проверка загрузки существующей конфигурации"""
        config_path = temp_dir / "config.json"
        
        # Создаем файл конфигурации
        test_config = {
            "bot": {"name": "TestBot"},
            "custom": {"value": 42}
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(test_config, f)
        
        cfg = ConfigManager(str(config_path))
        assert cfg.get("bot.name") == "TestBot"
        assert cfg.get("custom.value") == 42
    
    def test_get_nested_value(self, temp_dir):
        """Проверка получения вложенных значений"""
        cfg = ConfigManager(str(temp_dir / "config.json"))
        
        assert cfg.get("audio.master_volume") == 0.7
        assert cfg.get("trigger.active_window") == 5.0
    
    def test_get_with_default(self, temp_dir):
        """Проверка получения с дефолтным значением"""
        cfg = ConfigManager(str(temp_dir / "config.json"))
        
        assert cfg.get("nonexistent.key", "default") == "default"
        assert cfg.get("bot.nonexistent", 999) == 999
    
    def test_set_value(self, temp_dir):
        """Проверка установки значения"""
        config_path = temp_dir / "config.json"
        cfg = ConfigManager(str(config_path))
        
        cfg.set("audio.master_volume", 0.5, autosave=False)
        assert cfg.get("audio.master_volume") == 0.5
    
    def test_set_creates_nested_path(self, temp_dir):
        """Проверка создания вложенного пути"""
        cfg = ConfigManager(str(temp_dir / "config.json"))
        
        cfg.set("new.nested.path.value", "test", autosave=False)
        assert cfg.get("new.nested.path.value") == "test"
    
    def test_autosave(self, temp_dir):
        """Проверка автосохранения"""
        config_path = temp_dir / "config.json"
        cfg = ConfigManager(str(config_path))
        
        cfg.set("test.value", 123, autosave=True)
        
        # Перезагружаем конфиг из файла
        cfg2 = ConfigManager(str(config_path))
        assert cfg2.get("test.value") == 123
    
    def test_manual_save(self, temp_dir):
        """Проверка ручного сохранения"""
        config_path = temp_dir / "config.json"
        cfg = ConfigManager(str(config_path))
        
        cfg.set("test.key", "value", autosave=False)
        assert cfg.save() is True
        
        # Проверяем что сохранилось
        cfg2 = ConfigManager(str(config_path))
        assert cfg2.get("test.key") == "value"
    
    def test_corrupted_config_fallback(self, temp_dir):
        """Проверка фолбэка при поврежденном конфиге"""
        config_path = temp_dir / "config.json"
        
        # Создаем невалидный JSON
        with open(config_path, "w") as f:
            f.write("invalid json {")
        
        cfg = ConfigManager(str(config_path))
        # Должен загрузить дефолты
        assert cfg.get("bot.name") == "Айко"
