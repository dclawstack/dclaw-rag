from pathlib import Path

from app.ingestion.extractors.base import Extractor
from app.ingestion.extractors.ocr import IMAGE_EXTENSIONS, ocr_image_file


class ImageExtractor(Extractor):
    """OCR image uploads (png/jpg/tiff/...) to text via the lazy OCR path.

    Raises IngestionError (from the OCR helper) when the 'vision' extra or the
    system tesseract binary is missing — an image can't be ingested without OCR.
    """

    supported_extensions = IMAGE_EXTENSIONS

    def extract(self, file_path: Path) -> str:
        return ocr_image_file(file_path)
