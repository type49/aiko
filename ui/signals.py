from PySide6.QtCore import QObject, Signal

class AikoSignals(QObject):
    # Только один аргумент типа object (туда мы положим dict)
    show_window = Signal(object)
    display_message = Signal(str, str, str)
    audio_status_changed = Signal(bool, str)