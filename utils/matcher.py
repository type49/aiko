from fuzzywuzzy import fuzz
from functools import lru_cache
from utils.logger import logger
from utils.config_manager import aiko_cfg


class CommandMatcher:
    """
    Утилита для нечеткого сравнения текста.
    Используется для распознавания имен активации и ключевых слов плагинов.

    ОПТИМИЗИРОВАНА с LRU-кешем для частых запросов.
    """

    # Вводные слова перед именем бота (опциональные префиксы)
    PREFIX_PHONETIC = {
        'слушай': 100,
        'слуш': 95,
        'слышь': 90,
        'эй': 100,
        'хей': 95,
        'окей': 100,
    }

    # Фонетические варианты для "айко" (защита от ошибок Vosk)
    AIKO_PHONETIC = {
        'айко': 100,
        'айка': 95,
        'айки': 90,
        'айку': 90,
        "хайку": 85,
        'ай ко': 95,
        'ай к': 85,
        'майко': 80,
        'майка': 75,
        'эйко': 90,
        'райков': 70,
    }

    @staticmethod
    @lru_cache(maxsize=256)
    def _compute_score(text: str, variant: str, partial: bool) -> int:
        t = text.lower().strip()
        v = variant.lower().strip()

        if partial:
            # token_set_ratio — самый устойчивый к перестановкам и лишним словам
            score_set = fuzz.token_set_ratio(t, v)
            # partial_ratio — хорош для поиска подстроки
            score_part = fuzz.partial_ratio(t, v)
            # Берем максимум, чтобы покрыть оба случая
            return max(score_set, score_part)
        else:
            return fuzz.ratio(t, v)

    @staticmethod
    def extract(text: str, variants: list, threshold=80, partial=False):
        """
        Ищет наилучшее совпадение из списка вариантов.

        :param text: Входной текст для поиска
        :param variants: Список вариантов для сравнения
        :param threshold: Минимальный порог совпадения (0-100)
        :param partial: True для поиска подстроки, False для строгого сравнения
        :return: (best_match, max_score)
        """
        best_match = None
        max_score = 0
        text = text.lower().strip()

        if not text or not variants:
            return None, 0

        for variant in variants:
            variant_lower = variant.lower()

            # Используем кешированный метод
            score = CommandMatcher._compute_score(text, variant_lower, partial)

            if score > max_score:
                max_score = score
                best_match = variant

            # ОПТИМИЗАЦИЯ: Ранняя остановка при точном совпадении
            if score == 100:
                break

        # Дебаг для калибровки порогов (threshold)
        is_debug = aiko_cfg.get("debug.matcher_debug", True)  # По умолчанию ВЫКЛ
        if is_debug and max_score > 40:
            mode = "PARTIAL" if partial else "RATIO"
            cache_info = CommandMatcher._compute_score.cache_info()
            logger.debug(
                f"Matcher: [{mode}] '{text}' ↔ '{best_match}' "
                f"Score: {max_score} (Min: {threshold}) | "
                f"Cache: {cache_info.hits}/{cache_info.hits + cache_info.misses} hits"
            )

        if max_score >= threshold:
            return best_match, max_score

        return None, max_score

    @staticmethod
    def check_trigger(text: str, triggers: list, threshold=80):
        """
        Проверяет наличие имени активации в начале фразы.
        Умеет корректно отрезать триггер, даже если он распознан с ошибкой.

        Поддерживает опциональные префиксы:
        - "айко" → срабатывает
        - "слушай айко" → срабатывает
        - "эй айко" → срабатывает

        Для "айко" использует фонетическую таблицу вместо fuzzy-поиска.
        """
        words = text.lower().split()
        if not words:
            return False, ""

        # Специальная обработка для "айко"
        if 'айко' in [t.lower() for t in triggers]:
            # Проверяем наличие префикса в первом слове
            prefix_detected = False
            prefix_length = 0

            if words[0] in CommandMatcher.PREFIX_PHONETIC:
                prefix_score = CommandMatcher.PREFIX_PHONETIC[words[0]]
                if prefix_score >= 85:  # Порог для префиксов
                    prefix_detected = True
                    prefix_length = 1
                    logger.debug(f"Matcher: Префикс '{words[0]}' распознан (Score: {prefix_score})")

            # Проверяем 1-2 слова после префикса (или с начала, если префикса нет)
            start_idx = prefix_length
            for i in range(start_idx + 1, min(len(words) + 1, start_idx + 3)):
                probe = " ".join(words[start_idx:i])

                # Проверка по фонетической таблице
                if probe in CommandMatcher.AIKO_PHONETIC:
                    score = CommandMatcher.AIKO_PHONETIC[probe]
                    if score >= 70:  # Жесткий порог для фонетики
                        remaining_text = " ".join(words[i:]).strip()
                        logger.debug(f"Matcher: Фонетика '{probe}' → AIKO (Score: {score})")
                        return True, remaining_text

        # Обычная логика для других триггеров
        for i in range(1, min(len(words) + 1, 3)):
            probe = " ".join(words[:i])
            match, score = CommandMatcher.extract(probe, triggers, threshold, partial=False)

            if match:
                remaining_text = " ".join(words[i:]).strip()
                return True, remaining_text

        return False, ""

    @staticmethod
    def clear_cache():
        """Очистка кеша (полезно при изменении конфигурации плагинов)"""
        CommandMatcher._compute_score.cache_clear()
        logger.info("Matcher: Кеш очищен")

    @staticmethod
    def get_cache_stats():
        """Получить статистику кеша"""
        return CommandMatcher._compute_score.cache_info()


