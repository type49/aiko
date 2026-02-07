import importlib
import importlib.util
from pathlib import Path
from interfaces import AikoCommand
from utils.logger import logger


class PluginLoader:
    @staticmethod
    def load_all(plugins_dir="plugins"):
        commands = []
        intent_map = {}
        fallbacks = []

        path = Path(plugins_dir)
        path.mkdir(exist_ok=True)

        # Итерируемся по всем элементам в директории
        for item in path.iterdir():
            if item.name == "__init__.py" or item.name == "__pycache__":
                continue

            module = None
            try:
                # Случай 1: Это папка-пакет
                if item.is_dir() and (item / "__init__.py").exists():
                    module = importlib.import_module(f"{plugins_dir}.{item.name}")

                # Случай 2: Это одиночный .py файл
                elif item.is_file() and item.suffix == ".py":
                    module_name = item.stem
                    spec = importlib.util.spec_from_file_location(module_name, item)
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