import joblib
import hashlib
import re
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline

from utils.logger import logger
from utils.config_manager import aiko_cfg


class IntentClassifier:
    """
    Двухуровневый классификатор команд:
    1. Быстрая проверка по ключевым словам (triggers)
    2. ML-модель для сложных случаев (samples)
    
    Это решает проблему перекрытия слов и ускоряет работу.
    """

    def __init__(self, model_path="data/nlu_model.pkl"):
        self.model_path = Path(model_path)
        self.model_path.parent.mkdir(exist_ok=True)
        
        # Уровень 1: Точные триггеры (быстро)
        self.trigger_map = {}  # {"напомни": PluginObject, ...}
        
        # Уровень 2: ML-модель (медленно, но умно)
        self.pipeline = None
        self.is_trained = False
        self.intent_to_plugin = {}
        
        self.confidence_threshold = aiko_cfg.get("nlu.threshold", 0.6)
        logger.info("NLU: Двухуровневая архитектура (Keywords → ML)")

    def _calculate_data_hash(self, data_dict):
        """Создает уникальный отпечаток тренировочных данных для детекции изменений."""
        content = str(sorted(data_dict.items())).encode()
        return hashlib.md5(content).hexdigest()

    def _preprocess(self, text: str) -> str:
        """Очистка текста перед обработкой."""
        text = text.lower().replace("ё", "е")
        return re.sub(r'[^\w\s]', '', text).strip()

    def train(self, plugins):
        """
        Обучает двухуровневую систему:
        1. Строит карту triggers → plugin
        2. Обучает ML на samples
        """
        # --- Уровень 1: Триггеры ---
        self.trigger_map.clear()
        for plugin in plugins:
            triggers = getattr(plugin, 'triggers', [])
            for trigger in triggers:
                clean_trigger = self._preprocess(trigger)
                if clean_trigger:
                    # Приоритет: последний плагин в списке (можно изменить логику)
                    self.trigger_map[clean_trigger] = plugin
                    logger.debug(f"NLU: Trigger '{clean_trigger}' → {plugin.__class__.__name__}")

        logger.info(f"NLU: Зарегистрировано {len(self.trigger_map)} триггеров")

        # --- Уровень 2: ML на samples ---
        data_dict = {}
        current_mapping = {}

        for plugin in plugins:
            samples = getattr(plugin, 'samples', [])
            if samples:
                p_name = plugin.__class__.__name__
                data_dict[p_name] = sorted(list(set(samples)))
                current_mapping[p_name] = plugin

        self.intent_to_plugin = current_mapping

        if len(data_dict) < 2:
            logger.warning("NLU: Недостаточно samples для ML (минимум 2 класса). Работаем только на триггерах.")
            return

        new_hash = self._calculate_data_hash(data_dict)

        # Проверка кэша
        if self.model_path.exists():
            try:
                saved = joblib.load(self.model_path)
                if saved.get('hash') == new_hash:
                    self.pipeline = saved['pipeline']
                    self.is_trained = True
                    logger.info("NLU: ML-модель актуальна (загружена из кэша).")
                    return
            except Exception as e:
                logger.debug(f"NLU: Кэш невалиден: {e}")

        # Обучение ML
        X, y = [], []
        for intent, phrases in data_dict.items():
            for p in phrases:
                X.append(self._preprocess(p))
                y.append(intent)

        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb', use_idf=True)),
            ('clf', LinearSVC(C=1.2, max_iter=2000, tol=1e-3, dual=False))
        ])

        try:
            self.pipeline.fit(X, y)
            self.is_trained = True
            joblib.dump({'pipeline': self.pipeline, 'hash': new_hash}, self.model_path)
            logger.info(f"NLU: ML-модель обучена. Классов: {len(data_dict)}. Hash: {new_hash[:8]}")
        except Exception as e:
            logger.error(f"NLU: Критическая ошибка обучения ML: {e}", exc_info=True)

    def predict(self, text: str):
        """
        Предсказывает плагин для фразы:
        1. Сначала проверяет по ключевым словам (triggers)
        2. Если не нашло → идет в ML-модель (samples)
        """
        if not text:
            return None

        clean_text = self._preprocess(text)
        if not clean_text:
            return None

        # --- Уровень 1: Проверка триггеров (O(1) поиск) ---
        words = clean_text.split()
        
        # Проверяем первые 3 слова на совпадение с триггерами
        for i in range(min(3, len(words)), 0, -1):
            probe = " ".join(words[:i])
            if probe in self.trigger_map:
                plugin = self.trigger_map[probe]
                logger.debug(f"NLU: Keyword Match → {plugin.__class__.__name__} ('{probe}')")
                return plugin

        # Проверяем вхождение триггера в любом месте фразы
        for trigger, plugin in self.trigger_map.items():
            if trigger in clean_text:
                logger.debug(f"NLU: Keyword Partial → {plugin.__class__.__name__} ('{trigger}')")
                return plugin

        # --- Уровень 2: ML-модель ---
        if not self.is_trained or self.pipeline is None:
            logger.debug(f"NLU: ML не обучена, пропускаем '{clean_text}'")
            return None

        try:
            decision = self.pipeline.decision_function([clean_text])
            score = decision.max()

            if score < self.confidence_threshold:
                logger.debug(f"NLU: ML Low Confidence ({score:.2f} < {self.confidence_threshold}) для '{clean_text}'")
                return None

            intent_name = self.pipeline.predict([clean_text])[0]
            plugin = self.intent_to_plugin.get(intent_name)

            if plugin:
                logger.debug(f"NLU: ML Match → {intent_name} (Score: {score:.2f})")

            return plugin

        except Exception as e:
            logger.error(f"NLU: Ошибка ML-классификации: {e}")
            return None
