# -*- coding: utf-8 -*-
import importlib
import importlib.util
import sys
from pathlib import Path
from interfaces import AikoCommand
from utils.logger import logger


class PluginLoader:
    """
    ИСПРАВЛЕНО: Улучшена обработка ошибок при загрузке плагинов
    """

    @staticmethod
    def load_all(plugins_dir="plugins"):
        commands, intent_map, fallbacks = [], {}, []
        path = Path(plugins_dir).absolute()
        path.mkdir(exist_ok=True)

        loaded_count = 0
        failed_count = 0

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
                        try:
                            spec = importlib.util.spec_from_file_location(
                                f"{item.name}.__init__",
                                str(init_file)
                            )
                            if spec and spec.loader:
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)
                                modules.append(module)
                                logger.debug(f"Загружен __init__.py для {item.name}")
                        except Exception as init_err:
                            logger.error(f"Ошибка загрузки __init__.py для {item.name}: {init_err}", exc_info=True)
                            # ИСПРАВЛЕНИЕ: Продолжаем даже если __init__ не загрузился

                    # Загружаем основной файл pluginname_plugin.py
                    plugin_file = item / f"{item.name}.py"
                    if plugin_file.exists():
                        try:
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
                        except Exception as plugin_err:
                            logger.error(f"Ошибка загрузки {plugin_file.name}: {plugin_err}", exc_info=True)
                            failed_count += 1
                            continue  # ИСПРАВЛЕНИЕ: Пропускаем этот плагин, но продолжаем загрузку других

                # Если это отдельный .py файл
                elif item.is_file() and item.suffix == ".py":
                    try:
                        spec = importlib.util.spec_from_file_location(
                            item.stem,
                            str(item)
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            modules.append(module)
                            logger.info(f"Загружен плагин: {item.name}")
                    except Exception as file_err:
                        logger.error(f"Ошибка загрузки {item.name}: {file_err}", exc_info=True)
                        failed_count += 1
                        continue  # ИСПРАВЛЕНИЕ: Пропускаем этот плагин

                # ИСПРАВЛЕНИЕ: Извлекаем команды с обработкой ошибок для каждого модуля
                for module in modules:
                    try:
                        commands_before = len(commands)
                        PluginLoader._extract_commands(module, commands, intent_map, fallbacks)
                        commands_after = len(commands)

                        if commands_after > commands_before:
                            loaded_count += 1
                            logger.debug(f"Извлечено {commands_after - commands_before} команд из {module.__name__}")
                    except Exception as extract_err:
                        logger.error(f"Ошибка извлечения команд из {module.__name__}: {extract_err}", exc_info=True)
                        failed_count += 1

            except Exception as e:
                logger.error(f"Loader: Критическая ошибка при загрузке {item.name}: {e}", exc_info=True)
                failed_count += 1

        # ИСПРАВЛЕНИЕ: Подробная статистика загрузки
        logger.info(f"Загрузка плагинов завершена: {loaded_count} успешно, {failed_count} ошибок")
        logger.info(f"Всего команд: {len(commands)}, интентов: {len(intent_map)}, fallback: {len(fallbacks)}")

        return commands, intent_map, fallbacks

    @staticmethod
    def _extract_commands(module, commands, intent_map, fallbacks):
        """
        Извлечение классов команд из модуля

        ИСПРАВЛЕНО: Добавлена детальная обработка ошибок
        """
        for attr in dir(module):
            try:
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, AikoCommand) and obj is not AikoCommand:
                    try:
                        instance = obj()
                        commands.append(instance)

                        if hasattr(instance, 'triggers') and instance.triggers:
                            for trig in instance.triggers:
                                for word in trig.lower().split():
                                    intent_map.setdefault(word, []).append(instance)
                            logger.debug(f"Зарегистрирован плагин: {obj.__name__} с триггерами {instance.triggers}")
                        else:
                            fallbacks.append(instance)
                            logger.debug(f"Зарегистрирован fallback плагин: {obj.__name__}")
                    except Exception as instance_err:
                        logger.error(f"Ошибка создания экземпляра {obj.__name__}: {instance_err}", exc_info=True)
                        # ИСПРАВЛЕНИЕ: Не прерываем обработку других команд

            except Exception as e:
                logger.error(f"Ошибка при обработке атрибута {attr}: {e}", exc_info=True)
                # ИСПРАВЛЕНИЕ: Продолжаем обработку следующих атрибутов