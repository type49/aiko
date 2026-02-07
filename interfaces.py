class AikoCommand:
    def __init__(self):
        self.triggers = []
        self.samples = []

    def execute(self, text: str, ctx) -> bool:
        return False