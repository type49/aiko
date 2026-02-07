"""
Тесты для CommandMatcher (нечеткое сравнение)
"""
import pytest
from utils.matcher import CommandMatcher


@pytest.mark.unit
class TestCommandMatcher:
    """Тесты нечеткого сопоставления команд"""
    
    def test_exact_match(self):
        """Проверка точного совпадения"""
        variants = ["напомни", "таймер", "погода"]
        match, score = CommandMatcher.extract("напомни", variants, threshold=80)
        
        assert match == "напомни"
        assert score == 100
    
    def test_partial_match(self):
        """Проверка частичного совпадения"""
        variants = ["напомни мне", "установи таймер"]
        match, score = CommandMatcher.extract(
            "напомни", variants, threshold=70, partial=True
        )
        
        assert match == "напомни мне"
        assert score >= 70
    
    def test_fuzzy_match(self):
        """Проверка нечеткого совпадения (опечатки)"""
        variants = ["айко"]
        match, score = CommandMatcher.extract("айка", variants, threshold=75)
        
        assert match == "айко"
        assert score >= 75
    
    def test_no_match_below_threshold(self):
        """Проверка что не возвращается совпадение ниже порога"""
        variants = ["напомни", "таймер"]
        match, score = CommandMatcher.extract("погода", variants, threshold=80)
        
        assert match is None
        assert score < 80
    
    def test_case_insensitive(self):
        """Проверка нечувствительности к регистру"""
        variants = ["НАПОМНИ"]
        match, score = CommandMatcher.extract("напомни", variants, threshold=80)
        
        assert match == "НАПОМНИ"
        assert score == 100
    
    def test_check_trigger_with_prefix(self):
        """Проверка триггера с префиксом"""
        triggers = ["айко"]
        
        # С префиксом
        is_trigger, cmd = CommandMatcher.check_trigger(
            "слушай айко включи музыку", triggers, threshold=80
        )
        assert is_trigger is True
        assert cmd == "включи музыку"
    
    def test_check_trigger_without_prefix(self):
        """Проверка триггера без префикса"""
        triggers = ["айко"]
        
        is_trigger, cmd = CommandMatcher.check_trigger(
            "айко какая погода", triggers, threshold=80
        )
        assert is_trigger is True
        assert cmd == "какая погода"
    
    def test_check_trigger_phonetic_variants(self):
        """Проверка фонетических вариантов"""
        triggers = ["айко"]
        
        # Фонетические варианты из AIKO_PHONETIC
        test_cases = [
            ("айка поставь таймер", True, "поставь таймер"),
            ("эйко включи свет", True, "включи свет"),
            ("хайку что нового", True, "что нового"),
        ]
        
        for text, expected_trigger, expected_cmd in test_cases:
            is_trigger, cmd = CommandMatcher.check_trigger(text, triggers, threshold=70)
            assert is_trigger == expected_trigger, f"Failed for: {text}"
            if expected_trigger:
                assert cmd == expected_cmd, f"Wrong command for: {text}"
    
    def test_check_trigger_no_match(self):
        """Проверка когда триггер не найден"""
        triggers = ["айко"]
        
        is_trigger, cmd = CommandMatcher.check_trigger(
            "какая погода сегодня", triggers, threshold=80
        )
        assert is_trigger is False
        assert cmd == ""
    
    def test_cache_functionality(self):
        """Проверка работы кеша"""
        variants = ["тестовая команда"]
        
        # Первый вызов
        CommandMatcher.extract("тестовая", variants, threshold=80, partial=True)
        stats1 = CommandMatcher.get_cache_stats()
        
        # Второй вызов (должен попасть в кеш)
        CommandMatcher.extract("тестовая", variants, threshold=80, partial=True)
        stats2 = CommandMatcher.get_cache_stats()
        
        assert stats2.hits > stats1.hits
    
    def test_clear_cache(self):
        """Проверка очистки кеша"""
        variants = ["команда"]
        CommandMatcher.extract("команда", variants)
        
        CommandMatcher.clear_cache()
        stats = CommandMatcher.get_cache_stats()
        
        assert stats.hits == 0
        assert stats.misses == 0
    
    def test_empty_input(self):
        """Проверка пустого ввода"""
        variants = ["команда"]
        
        match, score = CommandMatcher.extract("", variants)
        assert match is None
        assert score == 0
        
        match, score = CommandMatcher.extract("   ", variants)
        assert match is None
        assert score == 0
    
    def test_empty_variants(self):
        """Проверка пустого списка вариантов"""
        match, score = CommandMatcher.extract("текст", [])
        assert match is None
        assert score == 0
