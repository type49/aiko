from PySide6.QtCore import QObject, Signal


class AikoSignals(QObject):
    # Только один аргумент типа object (туда мы положим dict)
    show_window = Signal(object)
    display_message = Signal(str, str, str, bool)
    audio_status_changed = Signal(bool, str)

    # НОВОЕ: Безопасные межпоточные сигналы
    state_changed = Signal(str, bool)  # (state_name: str, new_value: bool) - для aiko_window
    ui_status_changed = Signal(str)  # (new_status: str) - для трея и других UI