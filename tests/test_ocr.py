from src.ocr.extractor import OCRExtractor

ocr = OCRExtractor()

text = ocr.extract("sample.jpg")

print("=" * 60)
print(text)
print("=" * 60)