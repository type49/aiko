import re
from utils.logger import logger
from utils.matcher import CommandMatcher


class CommandRouter:
    """
    Диспетчер команд. Ответственен за сопоставление текстового ввода
    с конкретным исполнителем (плагином) через цепочку приоритетов.
    """

    def __init__(self, nlu, intent_map, fallbacks):
        self.nlu = nlu
        self.intent_map = intent_map
        self.fallbacks = fallbacks
        self._log_initialization()

    def _log_initialization(self):
        """Выводит детальный отчет о загруженных мощностях."""
        # Собираем уникальные имена из всех источников
        all_plugins = set()
        for plugins in self.intent_map.values():
            for p in plugins:
                all_plugins.add(p.__class__.__name__)
        for p in self.fallbacks:
            all_plugins.add(p.__class__.__name__)

        plugin_list = ", ".join(sorted(all_plugins))

        logger.info(f"Router: Загружено {len(all_plugins)} плагинов.")
        logger.info(f"Router: Список: [{plugin_list}]")
        logger.debug(f"Router: Карта триггеров содержит {len(self.intent_map)} ключей.")

    def route(self, text: str, ctx) -> bool:
        """
        Основной вход в логику маршрутизации.
        Проходит по каскаду кандидатов, пока один из них не подтвердит исполнение.
        """
        raw_text = text.lower().strip()
        tried = set()

        logger.debug(f"Router: Начало маршрутизации фразы: '{raw_text}'")

        for plugin, route_name in self._get_candidates(raw_text):
            if not plugin or plugin in tried:
                continue

            if self._execute(plugin, raw_text, route_name, ctx):
                return True

            tried.add(plugin)

        logger.warning(f"Router: Ни один плагин не обработал команду: '{raw_text}'")
        return False

    def _get_candidates(self, text):
        """Генератор кандидатов: NLU -> Triggers -> Fallbacks."""
        # 1. NLU
        nlu_plugin = self.nlu.predict(text)
        if nlu_plugin:
            yield nlu_plugin, "NLU"

        # 2. Fast Triggers
        all_possible_triggers = list(self.intent_map.keys())
        match, score = CommandMatcher.extract(text, all_possible_triggers, threshold=70, partial=True)

        if match:
            for plugin in self.intent_map[match]:
                yield plugin, f"Match:{match}({score}%)"

        # 3. Fallbacks
        for plugin in self.fallbacks:
            yield plugin, "Fallback"

    def _execute(self, plugin, text, route, ctx):
        """Безопасный запуск плагина."""
        p_name = plugin.__class__.__name__
        try:
            if plugin.execute(text, ctx):
                logger.info(f"Router: [OK] {p_name} через {route}")
                return True
            logger.debug(f"Router: [SKIP] {p_name} отклонил {route}")
            return False
        except Exception as e:
            logger.error(f"Router: [ERR] {p_name} в {route}: {e}", exc_info=True)
            return False