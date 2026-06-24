from pathlib import Path

from bs4 import BeautifulSoup

from app.ingestion.extractors.base import Extractor


class HTMLExtractor(Extractor):
    supported_extensions = (".html", ".htm")

    def extract(self, file_path: Path) -> str:
        html = file_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
