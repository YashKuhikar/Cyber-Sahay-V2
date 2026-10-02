from __future__ import annotations

import re
from typing import Dict, List, Tuple
from pydantic import BaseModel


class LanguageProfile(BaseModel):
    detected_language: str  # "english", "hindi", "marathi", "hinglish", "roman_marathi"
    script: str  # "devanagari", "latin"
    confidence: float
    canonical_query_en: str
    target_response_language: str


# Common Indian multilingual keywords mapped to canonical concepts
CONCEPT_DICTIONARY = {
    "financial_fraud": [
        "paise chale gaye", "paise kat gaye", "khate se paise", "khathatun paise",
        "mazya account madhun", "mere account se", "rupaye kat gaye", "pese cut",
        "खात्यातून पैसे गेले", "पैसे कापले", "माझ्या खात्यातून", "मेरे खाते से पैसे", "पैसे कट गए"
    ],
    "phishing": [
        "link aayi thi", "link aali", "link var click kela", "link par click kiya",
        "sms link", "whatsapp link", "parcel link", "bijli bill link",
        "लिंक वर क्लिक केले", "लिंक आली होती", "लिंक पर क्लिक किया"
    ],
    "otp_fraud": [
        "otp manga tha", "otp dila", "otp share kela", "otp share kiya", "call par otp",
        "ओटीपी दिला", "ओटीपी मागितला", "ओटीपी शेयर किया"
    ],
    "device_theft": [
        "phone chori", "mobile chori", "phone haravla", "mobile haravla", "phone kho gaya",
        "फोन चोरी झाला", "मोबाईल हरवला", "फोन चोरी हो गया", "मोबाइल खो गया"
    ],
    "blackmail": [
        "video call", "dhamki de raha hai", "dhamki det aahe", "photo leak", "blackmail karto",
        "धमकी देत आहे", "फोटो व्हायरल करण्याची धमकी", "धमकी दे रहा है"
    ],
}


class MultilingualProcessor:
    """
    Detects language, script, and normalizes queries across
    English, Hindi, Marathi, Hinglish, and Roman Marathi.
    """

    DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

    # Linguistic distinctive markers
    MARATHI_DEVANAGARI_MARKERS = ["आहे", "गेले", "माझ्या", "खात्यातून", "तक्रार", "झाला", "झाली", "केले", "होता", "होती"]
    HINDI_DEVANAGARI_MARKERS = ["है", "गए", "मेरे", "खाते", "शिकायत", "हुआ", "हुई", "किया", "किए", "था", "थी"]

    ROMAN_MARATHI_MARKERS = ["mazya", "majhya", "madhun", "khathatun", "gele", "aale", "zala", "zali", "aahe", "kela", "takraar", "haravla"]
    HINGLISH_MARKERS = ["mere", "meri", "chale", "gaye", "kat", "gaya", "kya", "kare", "karo", "nahi", "batao", "hua", "huye", "aaya", "aayi"]

    @classmethod
    def analyze_query(cls, text: str) -> LanguageProfile:
        cleaned = text.strip()
        has_devanagari = bool(cls.DEVANAGARI_REGEX.search(cleaned))
        lower = cleaned.lower()

        # 1. Script & Language Identification
        if has_devanagari:
            marathi_score = sum(1 for m in cls.MARATHI_DEVANAGARI_MARKERS if m in cleaned)
            hindi_score = sum(1 for m in cls.HINDI_DEVANAGARI_MARKERS if m in cleaned)

            if marathi_score > hindi_score:
                lang = "marathi"
                target = "Marathi"
            else:
                lang = "hindi"
                target = "Hindi"
            script = "devanagari"
            confidence = 0.95
        else:
            script = "latin"
            words = set(re.findall(r"\b\w+\b", lower))

            marathi_hits = sum(1 for w in cls.ROMAN_MARATHI_MARKERS if w in words)
            hinglish_hits = sum(1 for w in cls.HINGLISH_MARKERS if w in words)

            if marathi_hits > 0:
                lang = "roman_marathi"
                target = "Roman Marathi / Marathi"
                confidence = 0.92
            elif hinglish_hits > 0:
                lang = "hinglish"
                target = "Hinglish"
                confidence = 0.92
            else:
                lang = "english"
                target = "English"
                confidence = 0.96

        # 2. Concept Normalization into Canonical English Search Query
        canonical_expansion = []
        for concept, phrases in CONCEPT_DICTIONARY.items():
            for phrase in phrases:
                if phrase in lower:
                    if concept == "financial_fraud":
                        canonical_expansion.append("unauthorized electronic transaction financial fraud upi banking refund 1930")
                    elif concept == "phishing":
                        canonical_expansion.append("phishing link malicious website fraudulent message cybercrime report")
                    elif concept == "otp_fraud":
                        canonical_expansion.append("otp fraud unauthorized access banking credential theft")
                    elif concept == "device_theft":
                        canonical_expansion.append("stolen lost mobile phone imei blocking sanchar saathi ceir police fir")
                    elif concept == "blackmail":
                        canonical_expansion.append("sextortion online blackmail video call harassment it act 67")
                    break

        if canonical_expansion:
            canonical_query_en = f"{cleaned} {' '.join(canonical_expansion)}"
        else:
            canonical_query_en = cleaned

        return LanguageProfile(
            detected_language=lang,
            script=script,
            confidence=confidence,
            canonical_query_en=canonical_query_en,
            target_response_language=target,
        )
