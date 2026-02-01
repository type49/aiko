import subprocess
from interfaces import AikoCommand

class LauncherPlugin(AikoCommand):
    def __init__(self):
        # Добавь сюда свои пути
        self.apps = {
            "калькулятор": "calc.exe",
            "блокнот": "notepad.exe",
            "браузер": "start msedge",
            "диспетчер": "taskmgr.exe"
        }

    def execute(self, text, ctx):
        text = text.lower()
        for name, cmd in self.apps.items():
            if f"открой {name}" in text or f"запусти {name}" in text:
                try:
                    subprocess.Popen(cmd, shell=True)
                    if hasattr(ctx, 'ui_log'):
                        ctx.ui_log(f"Запускаю {name}", "success") # Зеленый цвет
                    return True
                except Exception as e:
                    if hasattr(ctx, 'ui_log'):
                        ctx.ui_log(f"Ошибка: {str(e)[:20]}", "error") # Красный цвет
                    return True
        return False