from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import tempfile
from typing import Dict, Optional

import fitz  # PyMuPDF

from ..config import MAX_PDF_PAGES

logger = logging.getLogger("cybersahay.ocr_extractor")


class OCRExtractor:
    """
    Production-grade OCR service for image and PDF evidence extraction.
    Features:
    - Lazy-loaded EasyOCR reader (zero startup delay)
    - In-memory SHA-256 deduplication cache
    - Fast native text extraction via PyMuPDF for electronic PDFs
    - Bounded page processing (MAX_PDF_PAGES)
    - Isolated temporary file cleanup for rendered pages
    """

    SUPPORTED_IMAGES = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
    }

    SUPPORTED_PDFS = {
        ".pdf",
    }

    def __init__(self):
        self._reader = None
        self._cache: Dict[str, str] = {}
        logger.info("OCRExtractor initialized with lazy reader loading.")

    @property
    def reader(self):
        """
        Lazily initializes the EasyOCR Reader on the first image OCR request.
        """
        if self._reader is None:
            try:
                import easyocr
                logger.info("Initializing EasyOCR reader (English, CPU mode)...")
                self._reader = easyocr.Reader(["en"], gpu=False)
                logger.info("EasyOCR reader initialized successfully.")
            except Exception as e:
                logger.warning(f"EasyOCR reader initialization failed or unavailable: {e}")
                self._reader = None
        return self._reader

    # --------------------------------------------------

    def extract(self, file_path: str) -> str:
        """
        Extracts plain text from an image or PDF.
        Uses SHA-256 caching to avoid redundant OCR passes.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Evidence file not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in self.SUPPORTED_IMAGES and suffix not in self.SUPPORTED_PDFS:
            raise ValueError(f"Unsupported file type for OCR: {suffix}")

        # Compute SHA-256 hash for caching
        try:
            with open(path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            if file_hash in self._cache:
                logger.info(f"OCR cache HIT for hash: {file_hash[:12]}...")
                return self._cache[file_hash]
        except Exception:
            file_hash = None

        if suffix in self.SUPPORTED_IMAGES:
            extracted_text = self._extract_image(path)
        elif suffix in self.SUPPORTED_PDFS:
            extracted_text = self._extract_pdf(path)
        else:
            extracted_text = ""

        if file_hash:
            self._cache[file_hash] = extracted_text

        return extracted_text

    # --------------------------------------------------

    def _extract_image(self, path: Path) -> str:
        r = self.reader
        if r is None:
            logger.warning("EasyOCR reader unavailable. Returning empty OCR extraction.")
            return ""

        try:
            results = r.readtext(str(path), detail=0)
            return "\n".join(results)
        except Exception as e:
            logger.error(f"Error extracting text from image {path.name}: {e}")
            return ""

    # --------------------------------------------------

    def _extract_pdf(self, path: Path) -> str:
        try:
            document = fitz.open(path)
        except Exception as e:
            raise ValueError(f"Invalid or corrupted PDF file: {e}")

        total_pages = len(document)
        if total_pages > MAX_PDF_PAGES:
            document.close()
            raise ValueError(
                f"PDF exceeds maximum allowed page count of {MAX_PDF_PAGES} pages (found {total_pages})."
            )

        pages = []
        try:
            for page in document:
                # 1. First attempt: Fast native text extraction
                native_text = page.get_text()
                if native_text and native_text.strip():
                    pages.append(native_text.strip())
                    continue

                # 2. Scanned page fallback: Render pixmap to temporary file
                pix = page.get_pixmap()
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                    tmp_img_path = Path(tmp_file.name)

                try:
                    pix.save(str(tmp_img_path))
                    page_text = self._extract_image(tmp_img_path)
                    if page_text.strip():
                        pages.append(page_text.strip())
                finally:
                    tmp_img_path.unlink(missing_ok=True)
        finally:
            document.close()

        return "\n\n".join(pages)