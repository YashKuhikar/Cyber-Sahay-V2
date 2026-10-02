from __future__ import annotations

from ..ocr.extractor import OCRExtractor
from .document_classifier import DocumentClassifier
from .document_analyzer import DocumentAnalyzer
from .information_extraction_agent import InformationExtractionAgent
from .retrieval_agent import RetrievalAgent


class OCRAgent:
    """
    Agent coordinating OCR text extraction, document classification,
    risk analysis, entity extraction, and legal advisory via RAG.
    """

    def __init__(self):
        self.extractor = OCRExtractor()
        self.analyzer = DocumentAnalyzer()
        self.classifier = DocumentClassifier()
        self.information_extraction_agent = InformationExtractionAgent()
        self.retrieval_agent = RetrievalAgent()

    def extract_text(self, file_path: str) -> str:
        return self.extractor.extract(file_path)

    def analyze_document(self, file_path: str) -> dict:
        # Step 1: OCR
        text = self.extractor.extract(file_path)

        # Step 2: Document Classification
        classification = self.classifier.classify(text)

        # Step 3: Document Analysis
        analysis = self.analyzer.analyze(
            classification.get("document_type", "Unknown"),
            text,
        )
        information = self.information_extraction_agent.extract(text, mode="document")

        # Step 4: Call Hybrid RAG if legal guidance is recommended
        legal_guidance = None
        if analysis.get("requires_rag") and analysis.get("rag_query"):
            rag_res = self.retrieval_agent.handle(analysis["rag_query"])
            legal_guidance = rag_res.get("answer", "") if isinstance(rag_res, dict) else str(rag_res)

        return {
            "ocr_text": text,
            "classification": classification,
            "analysis": analysis,
            "information": information,
            "legal_guidance": legal_guidance,
        }