import csv
from pathlib import Path

from app.ingestion.extractors.base import Extractor


class CSVExtractor(Extractor):
    supported_extensions = (".csv", ".tsv")

    def extract(self, file_path: Path) -> str:
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
        rows: list[str] = []
        with file_path.open(newline="", encoding="utf-8", errors="ignore") as handle:
            for row in csv.reader(handle, delimiter=delimiter):
                cells = [cell.strip() for cell in row if cell.strip()]
                if cells:
                    rows.append(" | ".join(cells))
        return "\n".join(rows)
