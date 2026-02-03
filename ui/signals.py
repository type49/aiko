from PySide6.QtCore import QObject, Signal

class AikoSignals(QObject):
    """Единая шина событий. Хрупко! Не добавлять сюда логику."""
    display_message = Signal(str, str)
    open_reminder = Signal(str)
    audio_status_changed = Signal(bool, str)
    show_alarm = Signal(dict)