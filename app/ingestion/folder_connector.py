"""Local folder connector — sync a directory into the index, incrementally.

Fits the local-first stance: no cloud, no upload step. A JSON manifest records
each file's (mtime, size) so an unchanged file is skipped without re-extracting;
changed files re-ingest, and files removed from disk are dropped from the
manifest. Content-level dedup is still handled downstream by the ingestion
pipeline (idempotent by content checksum), so moved/renamed/duplicate files
don't produce duplicate chunks.

The connector is decoupled from the heavy pipeline via an injected `ingest`
callable, so it's unit-testable without models or Qdrant. `make_pipeline_ingest`
wires it to the real pipeline for the CLI. `watch` polls on an interval — no
extra dependency, and robust across filesystems that don't emit inotify events.
"""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from app.ingestion.loaders import SUPPORTED_EXTENSIONS

logger = structlog.get_logger(__name__)


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "updated": len(self.updated),
            "skipped": len(self.skipped),
            "removed": len(self.removed),
            "failed": len(self.failed),
        }


def _iter_files(directory: Path) -> Iterator[Path]:
    yield from (p for p in directory.rglob("*") if p.is_file())


def _signature(path: Path) -> list[float]:
    stat = path.stat()
    return [round(stat.st_mtime, 3), float(stat.st_size)]


def _default_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


class FolderConnector:
    def __init__(
        self,
        ingest: Callable[[Path], None],
        manifest_path: Path | None = None,
        is_supported: Callable[[Path], bool] | None = None,
    ) -> None:
        self.ingest = ingest
        self.manifest_path = manifest_path
        self.is_supported = is_supported or _default_supported

    def sync(self, directory: Path) -> SyncReport:
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(directory)
        manifest = self._load()
        report = SyncReport()
        seen: set[str] = set()
        manifest_resolved = self.manifest_path.resolve() if self.manifest_path else None

        for path in sorted(_iter_files(directory)):
            # Never ingest our own manifest if it happens to live under the tree.
            if manifest_resolved is not None and path.resolve() == manifest_resolved:
                continue
            if not self.is_supported(path):
                continue
            key = str(path.resolve())
            seen.add(key)
            signature = _signature(path)
            previous = manifest.get(key)
            if previous == signature:
                report.skipped.append(key)
                continue
            try:
                self.ingest(path)
            except Exception as exc:  # one bad file never aborts the sync
                logger.warning("folder_sync_file_failed", path=key, error=str(exc))
                report.failed.append((key, str(exc)))
                continue
            manifest[key] = signature
            (report.updated if previous else report.added).append(key)

        for gone in sorted(set(manifest) - seen):
            del manifest[gone]
            report.removed.append(gone)

        self._save(manifest)
        return report

    def watch(
        self,
        directory: Path,
        poll_interval: float = 2.0,
        on_sync: Callable[[SyncReport], None] | None = None,
        _sleep: Callable[[float], None] | None = None,
        _iterations: int | None = None,
    ) -> None:
        """Re-sync `directory` every `poll_interval` seconds until interrupted.

        Polling (not inotify) so there's no extra dependency and it works on
        network/virtual filesystems. `_sleep`/`_iterations` are test seams.
        """
        import time

        sleep = _sleep or time.sleep
        count = 0
        while _iterations is None or count < _iterations:
            report = self.sync(directory)
            if on_sync is not None:
                on_sync(report)
            count += 1
            if _iterations is not None and count >= _iterations:
                break
            sleep(poll_interval)

    def _load(self) -> dict[str, list[float]]:
        if not self.manifest_path or not self.manifest_path.exists():
            return {}
        try:
            data = json.loads(self.manifest_path.read_text())
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, manifest: dict[str, list[float]]) -> None:
        if not self.manifest_path:
            return
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest))


def make_pipeline_ingest(
    source_prefix: str = "local",
    tenant_id: str | None = None,
    collection_id: str | None = None,
) -> Callable[[Path], None]:
    """An `ingest` callable that pushes a file through the real ingestion
    pipeline. Imported lazily so the connector module stays light to import."""
    from app.ingestion.pipeline import IngestionPipeline
    from app.models.schemas import IngestRequest

    pipeline = IngestionPipeline()

    def _ingest(path: Path) -> None:
        request = IngestRequest(
            source=f"{source_prefix}/{path.name}",
            title=path.name,
            tenant_id=tenant_id,
            collection_id=collection_id,
        )
        pipeline.ingest_file(path, request)

    return _ingest
