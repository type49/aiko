

class AikoCommand:
    def __init__(self):
        self.triggers = []
        self.samples = []
        self.is_active = False

    def execute(self, text: str, ctx) -> bool:
        self.is_active = True
        return True

    def on_tick(self, ctx):
        pass