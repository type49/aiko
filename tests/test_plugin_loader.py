"""
Тесты для PluginLoader
"""
import pytest
from pathlib import Path
from core.plugin_loader import PluginLoader
from interfaces import AikoCommand


@pytest.mark.unit
class TestPluginLoader:
    """Тесты загрузчика плагинов"""
    
    def test_load_empty_directory(self, temp_dir):
        """Проверка загрузки из пустой директории"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        assert commands == []
        assert intent_map == {}
        assert fallbacks == []
    
    def test_load_single_file_plugin(self, temp_dir):
        """Проверка загрузки одиночного плагина из .py файла"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        # Создаем простой плагин
        plugin_code = '''
from interfaces import AikoCommand

class TestCommand(AikoCommand):
    def __init__(self):
        super().__init__()
        self.triggers = ["тест"]
    
    def execute(self, text, ctx):
        return True
'''
        (plugins_dir / "test_plugin.py").write_text(plugin_code, encoding="utf-8")
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        assert len(commands) == 1
        assert commands[0].__class__.__name__ == "TestCommand"
        assert "тест" in intent_map
        assert len(fallbacks) == 0
    
    def test_load_package_plugin(self, temp_dir):
        """Проверка загрузки плагина-пакета"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        # Создаем пакет
        package_dir = plugins_dir / "test_package"
        package_dir.mkdir()
        
        # __init__.py
        init_code = '''
from interfaces import AikoCommand

class PackageCommand(AikoCommand):
    def __init__(self):
        super().__init__()
        self.triggers = ["пакет"]
'''
        (package_dir / "__init__.py").write_text(init_code, encoding="utf-8")
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        assert len(commands) == 1
        assert commands[0].__class__.__name__ == "PackageCommand"
    
    def test_plugin_with_multiple_triggers(self, temp_dir):
        """Проверка плагина с несколькими триггерами"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        plugin_code = '''
from interfaces import AikoCommand

class MultiTriggerCommand(AikoCommand):
    def __init__(self):
        super().__init__()
        self.triggers = ["первый триггер", "второй триггер", "третий"]
'''
        (plugins_dir / "multi.py").write_text(plugin_code, encoding="utf-8")
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        # Проверяем что все слова из триггеров попали в intent_map
        assert "первый" in intent_map
        assert "второй" in intent_map
        assert "третий" in intent_map
        assert "триггер" in intent_map
    
    def test_fallback_plugin(self, temp_dir):
        """Проверка фолбэк плагина (без триггеров)"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        plugin_code = '''
from interfaces import AikoCommand

class FallbackCommand(AikoCommand):
    def __init__(self):
        super().__init__()
        # Нет triggers
'''
        (plugins_dir / "fallback.py").write_text(plugin_code, encoding="utf-8")
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        assert len(commands) == 1
        assert len(fallbacks) == 1
        assert fallbacks[0].__class__.__name__ == "FallbackCommand"
    
    def test_mixed_plugins(self, temp_dir):
        """Проверка смешанной загрузки (файлы + пакеты)"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        # Файл-плагин
        file_code = '''
from interfaces import AikoCommand
class FilePlugin(AikoCommand):
    def __init__(self):
        super().__init__()
        self.triggers = ["файл"]
'''
        (plugins_dir / "file_plugin.py").write_text(file_code, encoding="utf-8")
        
        # Пакет-плагин
        package_dir = plugins_dir / "package_plugin"
        package_dir.mkdir()
        init_code = '''
from interfaces import AikoCommand
class PackagePlugin(AikoCommand):
    def __init__(self):
        super().__init__()
        self.triggers = ["пакет"]
'''
        (package_dir / "__init__.py").write_text(init_code, encoding="utf-8")
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        assert len(commands) == 2
        plugin_names = {cmd.__class__.__name__ for cmd in commands}
        assert "FilePlugin" in plugin_names
        assert "PackagePlugin" in plugin_names
    
    def test_skip_pycache(self, temp_dir):
        """Проверка пропуска __pycache__"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "__pycache__").mkdir()
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        assert commands == []
    
    def test_error_handling_invalid_plugin(self, temp_dir, caplog):
        """Проверка обработки ошибок при невалидном плагине"""
        plugins_dir = temp_dir / "plugins"
        plugins_dir.mkdir()
        
        # Создаем плагин с синтаксической ошибкой
        (plugins_dir / "bad.py").write_text("invalid python code {{{", encoding="utf-8")
        
        commands, intent_map, fallbacks = PluginLoader.load_all(str(plugins_dir))
        
        # Не должно упасть, просто пропустить
        assert commands == []
        assert "Ошибка при загрузке bad.py" in caplog.text
