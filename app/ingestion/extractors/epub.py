from pathlib import Path

from app.ingestion.extractors.base import Extractor


class EpubExtractor(Extractor):
    supported_extensions = (".epub",)

    def extract(self, file_path: Path) -> str:
        from bs4 import BeautifulSoup
        from ebooklib import ITEM_DOCUMENT, epub

        book = epub.read_epub(str(file_path))
        chapters: list[str] = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if text:
                chapters.append(text)
        return "\n\n".join(chapters)
