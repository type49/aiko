import json
import time
from vosk import Model, KaldiRecognizer
from utils.logger import logger


class STTService:
    """
    Сервис Speech-to-Text (STT).
    Обеспечивает трансформацию аудиопотока в текст с использованием модели Vosk.
    """

    def __init__(self, model_path):
        self.model_path = model_path
        self._rec = None
        self._model = None

    def _init_rec(self):
        """
        Ленивая инициализация модели и распознавателя.
        Загружает тяжелые веса нейросети в память только при первом обращении.
        """
        if not self._rec:
            start_time = time.time()
            logger.info(f"STT: Инициализация модели из {self.model_path}...")

            try:
                # Модель Vosk загружается один раз
                self._model = Model(str(self.model_path))
                # Распознаватель настраивается на частоту 16000 Гц (стандарт для микрофонов)
                self._rec = KaldiRecognizer(self._model, 16000)

                duration = time.time() - start_time
                logger.info(f"STT: Модель успешно загружена за {duration:.2f} сек.")
            except Exception as e:
                logger.error(f"STT: Критическая ошибка загрузки модели: {e}", exc_info=True)
                raise

        return self._rec

    def get_phrase(self, audio_data):
        """
        Обрабатывает фрагмент аудиоданных.
        :param audio_data: байтовый поток аудио.
        :return: str (текст фразы), если обнаружена пауза в конце речи, иначе None.
        """
        try:
            rec = self._init_rec()

            # AcceptWaveform возвращает True, когда Vosk считает фразу законченной
            if rec.AcceptWaveform(audio_data):
                result_json = rec.Result()
                text = json.loads(result_json).get('text', '')

                if text:
                    logger.debug(f"STT: Распознана финальная фраза: '{text}'")
                    print(text)
                    return text

            return None

        except Exception as e:
            logger.error(f"STT: Ошибка в процессе распознавания: {e}")
            return None

    def reset(self):
        """Сброс состояния распознавателя (полезно при смене контекста)."""
        if self._rec:
            self._rec.Reset()
            logger.debug("STT: Состояние распознавателя сброшено.")