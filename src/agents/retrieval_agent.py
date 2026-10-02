from ..services.ai_service import AIService


class RetrievalAgent:

    def __init__(self):
        self.ai = AIService()

    def handle(self, query: str, history=None):
        return self.ai.ask(
            query=query,
            history=history
        )