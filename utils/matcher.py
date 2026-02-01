from fuzzywuzzy import fuzz
from utils.logger import logger


class CommandMatcher:
    @staticmethod
    def extract(text, variants, threshold=80):
        best_match = None
        max_score = 0
        text = text.lower().strip()

        for variant in variants:
            score = fuzz.ratio(text, variant.lower())
            if score > max_score:
                max_score = score
                best_match = variant

        # ЛОГГИРОВАНИЕ ДЛЯ ОТЛАДКИ
        if max_score > 30:  # Чтобы не спамить совсем уж на мусор
            logger.debug(f"Matcher: '{text}' vs '{best_match}' = {max_score}% (порог {threshold}%)")

        if max_score >= threshold:
            return best_match, max_score

        return None, max_score

    @staticmethod
    def check_trigger(text, triggers, threshold=80):
        words = text.lower().split()
        if not words:
            return False, ""

        # Проверяем первое слово (или два, если триггер 'ай ко')
        first_word = words[0]
        match, score = CommandMatcher.extract(first_word, triggers, threshold)

        if match:
            # Если триггер состоял из двух слов (например 'ай ко'), отрезаем два
            offset = len(match.split())
            remaining_text = " ".join(words[offset:])
            return True, remaining_text

        return False, ""