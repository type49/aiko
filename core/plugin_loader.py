import importlib
import importlib.util
import sys
from pathlib import Path
from interfaces import AikoCommand
from utils.logger import logger


class PluginLoader:
    @staticmethod
    def load_all(plugins_dir="plugins"):
        commands, intent_map, fallbacks = [], {}, []
        path = Path(plugins_dir).absolute()
        path.mkdir(exist_ok=True)

        for item in path.iterdir():
            if item.name.startswith(("_", ".")) or item.name == "__pycache__":
                continue

            try:
                modules = []

                # Если это папка-плагин
                if item.is_dir():
                    # ВАЖНО: Добавляем папку плагина в sys.path для поддержки локальных импортов
                    plugin_path = str(item.absolute())
                    if plugin_path not in sys.path:
                        sys.path.insert(0, plugin_path)

                    # Загружаем __init__.py (если есть)
                    init_file = item / "__init__.py"
                    if init_file.exists():
                        spec = importlib.util.spec_from_file_location(
                            f"{item.name}.__init__",
                            str(init_file)
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            modules.append(module)

                    # Загружаем основной файл pluginname_plugin.py
                    plugin_file = item / f"{item.name}.py"
                    if plugin_file.exists():
                        spec = importlib.util.spec_from_file_location(
                            f"{item.name}",  # Убрали дублирование имени
                            str(plugin_file)
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[item.name] = module  # Регистрируем модуль
                            spec.loader.exec_module(module)
                            modules.append(module)
                            logger.info(f"Загружен плагин: {plugin_file.name}")

                # Если это отдельный .py файл
                elif item.is_file() and item.suffix == ".py":
                    spec = importlib.util.spec_from_file_location(
                        item.stem,
                        str(item)
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        modules.append(module)
                        logger.info(f"Загружен плагин: {item.name}")

                # Извлекаем команды из всех загруженных модулей
                for module in modules:
                    PluginLoader._extract_commands(module, commands, intent_map, fallbacks)

            except Exception as e:
                logger.error(f"Loader: Ошибка при загрузке {item.name}: {e}", exc_info=True)

        logger.info(f"Всего загружено команд: {len(commands)}")
        return commands, intent_map, fallbacks

    @staticmethod
    def _extract_commands(module, commands, intent_map, fallbacks):
        """Извлечение классов команд из модуля"""
        for attr in dir(module):
            try:
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, AikoCommand) and obj is not AikoCommand:
                    instance = obj()
                    commands.append(instance)

                    if hasattr(instance, 'triggers') and instance.triggers:
                        for trig in instance.triggers:
                            for word in trig.lower().split():
                                intent_map.setdefault(word, []).append(instance)
                        logger.debug(f"Зарегистрирована команда: {obj.__name__} с триггерами {instance.triggers}")
                    else:
                        fallbacks.append(instance)
                        logger.debug(f"Зарегистрирована fallback команда: {obj.__name__}")
            except Exception as e:
                logger.error(f"Ошибка при обработке атрибута {attr}: {e}")