from abc import ABC, abstractmethod
from pathlib import Path


class Extractor(ABC):
    supported_extensions: tuple[str, ...] = ()

    @abstractmethod
    def extract(self, file_path: Path) -> str:
        ...
