from email import policy
from email.parser import BytesParser
from pathlib import Path

from app.ingestion.extractors.base import Extractor


class EmailExtractor(Extractor):
    supported_extensions = (".eml",)

    def extract(self, file_path: Path) -> str:
        with file_path.open("rb") as handle:
            message = BytesParser(policy=policy.default).parse(handle)

        header_lines = [
            f"{name}: {message[name]}"
            for name in ("From", "To", "Date", "Subject")
            if message[name]
        ]

        body = message.get_body(preferencelist=("plain", "html"))
        content = body.get_content() if body else ""
        if body and body.get_content_type() == "text/html":
            from bs4 import BeautifulSoup

            content = BeautifulSoup(content, "html.parser").get_text(
                separator="\n", strip=True
            )

        return "\n".join(header_lines) + "\n\n" + content.strip()
