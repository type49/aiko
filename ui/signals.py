from PySide6.QtCore import QObject, Signal

class AikoSignals(QObject):
    """Единая шина событий. Хрупко! Не добавлять сюда логику."""
    display_message = Signal(str, str) # текст, тип (info, success, error)
    open_reminder = Signal(str)        # текст-заготовка