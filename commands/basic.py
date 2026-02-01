import datetime
from interfaces import AikoCommand


class TimePlugin(AikoCommand):
    def execute(self, text, ctx):
        if "время" in text.lower() or "который час" in text.lower():
            now = datetime.datetime.now().strftime("%H:%M")
            msg = f"Сейчас {now}"

            # Вот здесь критический момент:
            if hasattr(ctx, 'ui_log'):
                ctx.ui_log(msg, "info")  # "info" даст бирюзовый цвет текста

            print(f"[PLUGIN]: {msg}")  # Оставляем для консоли
            return True
        return False