from typing import Dict, Any, Optional
from pydantic import BaseModel

from .enums import IntentType, LanguageType


class IntentResult(BaseModel):
    intent: IntentType
    category: str
    language: LanguageType
    confidence: float
    entities: Dict[str, Any] = {}
    reasoning: Optional[str] = None