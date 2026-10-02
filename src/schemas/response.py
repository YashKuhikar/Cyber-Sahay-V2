from pydantic import BaseModel
from datetime import datetime


class ChatResponse(BaseModel):
    success: bool
    intent: str
    category: str
    confidence: float
    response: str
    timestamp: datetime