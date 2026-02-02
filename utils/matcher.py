from fuzzywuzzy import fuzz
from utils.logger import logger
from utils.config_manager import aiko_cfg


class CommandMatcher:
    @staticmethod
    def extract(text, variants, threshold=80, partial=False):
        """
        Ищет совпадение в списке вариантов.
        :param partial: Если True, ищет подстроку (для команд в предложении).
                        Если False, сравнивает строки целиком (для имен активации).
        """
        best_match = None
        max_score = 0
        text = text.lower().strip()

        for variant in variants:
            variant_lower = variant.lower()

            # ВЫБОР АЛГОРИТМА
            if partial:
                # Находит "напомни" внутри "напомни купить хлеб"
                score = fuzz.partial_ratio(text, variant_lower)
            else:
                # Строгое сравнение "айко" vs "айка"
                score = fuzz.ratio(text, variant_lower)

            if score > max_score:
                max_score = score
                best_match = variant

        is_debug = aiko_cfg.get("debug.matcher_debug", True)
        if is_debug and max_score > 30:
            mode = "PARTIAL" if partial else "STRICT"
            logger.debug(f"Matcher [{mode}]: '{text}' ~ '{best_match}' = {max_score}% (порог {threshold}%)")

        if max_score >= threshold:
            return best_match, max_score

        return None, max_score

    @staticmethod
    def check_trigger(text, triggers, threshold=80):
        """Проверка активационного имени (всегда строгое сравнение)"""
        words = text.lower().split()
        if not words:
            return False, ""

        # Проверяем первое слово (или два, если триггер 'ай ко')
        first_word = words[0]
        # Для имени активации partial=False, так как нам нужно четкое совпадение
        match, score = CommandMatcher.extract(first_word, triggers, threshold, partial=False)

        if match:
            offset = len(match.split())
            remaining_text = " ".join(words[offset:])
            return True, remaining_text

        return False, ""