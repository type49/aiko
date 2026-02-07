"""
Базовые фикстуры для тестов Aiko
"""
import pytest
import tempfile
import shutil
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Добавляем корневую директорию проекта в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.context import AikoContext
from utils.db_manager import DBManager


@pytest.fixture
def temp_dir():
    """Временная директория для тестов"""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def mock_config():
    """Мок конфигурации"""
    return {
        "bot": {"name": "Айко"},
        "audio": {
            "device_id": 1,
            "samplerate": 16000,
            "master_volume": 0.7,
            "match_threshold": 80
        },
        "stt-model": {"path": "model"},
        "trigger": {
            "active_window": 5.0,
            "post_command_window": 3.0
        },
        "debug": {
            "log_commands": True,
            "matcher_debug": False
        }
    }


@pytest.fixture
def mock_ctx():
    """Мок контекста AikoContext"""
    ctx = Mock(spec=AikoContext)
    ctx.is_running = True
    ctx.state = "idle"
    ctx.last_input_source = "mic"
    ctx.signals = None
    ctx.last_activation_time = 0.0
    ctx.active_window = 5.0
    ctx.post_command_window = 3.0
    ctx.commands = []

    # Моки для callbacks
    ctx.ui_output = Mock()
    ctx.ui_status = Mock()
    ctx.ui_audio_status = Mock()
    ctx.broadcast = Mock()
    ctx.reply = Mock()
    ctx.set_input_source = Mock()
    ctx.open_ui = Mock()

    return ctx


@pytest.fixture
def test_db(temp_dir):
    """Тестовая база данных"""
    db_path = temp_dir / "test.db"
    db = DBManager(str(db_path))
    yield db
    # Cleanup происходит автоматически через temp_dir


@pytest.fixture
def mock_plugin():
    """Базовый мок плагина"""
    from interfaces import AikoCommand

    plugin = Mock(spec=AikoCommand)
    plugin.triggers = ["тест"]
    plugin.samples = ["это тестовая команда", "запусти тест"]
    plugin.execute = Mock(return_value=True)
    plugin.__class__.__name__ = "TestPlugin"

    return plugin


@pytest.fixture(autouse=True)
def clear_singleton_cache():
    """Очищает кеш синглтонов между тестами"""
    from utils.audio_player import AudioController
    import core.global_context as gc

    # Сброс глобального контекста
    gc._context_instance = None

    # Сброс AudioController синглтона
    AudioController._instance = None

    yield

    # Повторная очистка после теста
    gc._context_instance = None
    AudioController._instance = None