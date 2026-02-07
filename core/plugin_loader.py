import importlib
import importlib.util
from pathlib import Path
from interfaces import AikoCommand
from utils.logger import logger


class PluginLoader:
    @staticmethod
    @staticmethod
    def load_all(plugins_dir="plugins"):
        commands, intent_map, fallbacks = [], {}, []
        path = Path(plugins_dir).absolute()  # Используем абсолютный путь
        path.mkdir(exist_ok=True)

        for item in path.iterdir():
            if item.name.startswith(("_", ".")) or item.name == "__pycache__":
                continue

            module = None
            try:
                # Определяем целевой файл для загрузки
                if item.is_dir() and (item / "__init__.py").exists():
                    target_file = item / "__init__.py"
                    module_name = item.name
                elif item.is_file() and item.suffix == ".py":
                    target_file = item
                    module_name = item.stem
                else:
                    continue

                # Универсальная загрузка по пути
                spec = importlib.util.spec_from_file_location(module_name, str(target_file))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                if module:
                    PluginLoader._extract_commands(module, commands, intent_map, fallbacks)

            except Exception as e:
                logger.error(f"Loader: Ошибка при загрузке {item.name}: {e}")

        return commands, intent_map, fallbacks

    @staticmethod
    def _extract_commands(module, commands, intent_map, fallbacks):
        """Вспомогательный метод для поиска классов в модуле"""
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, AikoCommand) and obj is not AikoCommand:
                instance = obj()
                commands.append(instance)

                if hasattr(instance, 'triggers') and instance.triggers:
                    for trig in instance.triggers:
                        for word in trig.lower().split():
                            intent_map.setdefault(word, []).append(instance)
                else:
                    fallbacks.append(instance)