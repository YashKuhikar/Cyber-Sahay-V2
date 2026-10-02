from __future__ import annotations

from pathlib import Path
from fastapi import HTTPException, UploadFile, status

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".bmp", ".webp"}

MAGIC_NUMBERS = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".pdf": [b"%PDF-"],
    ".bmp": [b"BM"],
}


async def validate_uploaded_file(file: UploadFile) -> tuple[str, int]:
    """
    Validates uploaded file against extension whitelist, magic byte signatures,
    and maximum payload size.

    Returns:
        (extension: str, file_size: int)

    Raises:
        HTTPException 400 on invalid extension or corrupt signature.
        HTTPException 413 on oversized file (>10MB).
    """
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()

    if not suffix or suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS)).upper()}.",
        )

    # 1. Read first 512 bytes to inspect magic header bytes
    header = await file.read(512)
    if not header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    # 2. Magic byte check
    is_valid_signature = False
    if suffix in MAGIC_NUMBERS:
        for magic in MAGIC_NUMBERS[suffix]:
            if header.startswith(magic):
                is_valid_signature = True
                break
    elif suffix == ".webp":
        if header.startswith(b"RIFF") and b"WEBP" in header[:16]:
            is_valid_signature = True

    if not is_valid_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file signature. The file content does not match its claimed extension (disguised or corrupt file).",
        )

    # 3. Check total file size by reading remaining bytes
    remaining = await file.read()
    total_size = len(header) + len(remaining)

    if total_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of 10 MB (File size: {total_size / (1024*1024):.2f} MB).",
        )

    # 4. Reset stream cursor so downstream tools can read the full file
    await file.seek(0)

    return suffix, total_size
