from enum import Enum


class IntentType(str, Enum):
    RETRIEVAL = "retrieval"
    COMPLAINT = "complaint"
    EMERGENCY = "emergency"
    GREETING = "greeting"
    UNKNOWN = "unknown"


class LanguageType(str, Enum):
    ENGLISH = "english"
    HINDI = "hindi"
    MARATHI = "marathi"
    HINGLISH = "hinglish"
    UNKNOWN = "unknown"