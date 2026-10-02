from __future__ import annotations

from pathlib import Path

import easyocr
import fitz  # PyMuPDF


class OCRExtractor:
    """
    Handles OCR for both images and PDFs.
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

        print("=" * 60)
        print("Initializing OCR Engine...")
        print("=" * 60)

        self.reader = easyocr.Reader(
            ["en"],
            gpu=False,
        )

        print("OCR Engine Ready.")
        print("=" * 60)

    # --------------------------------------------------

    def extract(
        self,
        file_path: str,
    ) -> str:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(file_path)

        suffix = path.suffix.lower()

        if suffix in self.SUPPORTED_IMAGES:
            return self._extract_image(path)

        if suffix in self.SUPPORTED_PDFS:
            return self._extract_pdf(path)

        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    # --------------------------------------------------

    def _extract_image(
        self,
        path: Path,
    ) -> str:

        results = self.reader.readtext(
            str(path),
            detail=0,
        )

        return "\n".join(results)

    # --------------------------------------------------

    def _extract_pdf(
        self,
        path: Path,
    ) -> str:

        document = fitz.open(path)

        pages = []

        for page in document:

            text = page.get_text()

            if text.strip():

                pages.append(text)

            else:

                pix = page.get_pixmap()

                image_path = path.with_suffix(".png")

                pix.save(image_path)

                pages.append(
                    self._extract_image(image_path)
                )

                image_path.unlink(
                    missing_ok=True,
                )

        document.close()

        return "\n\n".join(pages)