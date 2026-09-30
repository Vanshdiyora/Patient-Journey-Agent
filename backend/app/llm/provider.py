from app.core.config import settings
from app.llm.maq_ai import MAQAIClient

_client = None

def get_llm_client():
    global _client
    if not settings.maq_ai_enabled:
        return None
    if _client is None:
        _client = MAQAIClient()
    return _client
