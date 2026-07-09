"""Local folder connector: incremental sync (skip unchanged, re-ingest changed,
drop removed), unsupported-file filtering, and the polling watch loop."""

from pathlib import Path

from app.ingestion.folder_connector import FolderConnector


class _Recorder:
    def __init__(self):
        self.ingested: list[str] = []

    def __call__(self, path: Path) -> None:
        self.ingested.append(path.name)


def _connector(rec, tmp_path, **kw):
    return FolderConnector(ingest=rec, manifest_path=tmp_path / "manifest.json", **kw)


def test_first_sync_ingests_supported_files(tmp_path):
    (tmp_path / "a.md").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")
    (tmp_path / "skip.bin").write_bytes(b"\x00\x01")  # unsupported extension
    rec = _Recorder()

    report = _connector(rec, tmp_path).sync(tmp_path)

    assert sorted(rec.ingested) == ["a.md", "b.txt"]
    assert report.summary()["added"] == 2
    assert "skip.bin" not in rec.ingested


def test_resync_skips_unchanged_files(tmp_path):
    (tmp_path / "a.md").write_text("alpha")
    rec = _Recorder()
    connector = _connector(rec, tmp_path)

    connector.sync(tmp_path)
    report = connector.sync(tmp_path)  # nothing changed

    assert rec.ingested == ["a.md"]  # not ingested a second time
    assert report.summary() == {"added": 0, "updated": 0, "skipped": 1, "removed": 0, "failed": 0}


def test_changed_file_is_reingested(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("alpha")
    rec = _Recorder()
    connector = _connector(rec, tmp_path)
    connector.sync(tmp_path)

    # Change content and bump mtime so the signature differs.
    f.write_text("alpha beta gamma")
    import os

    os.utime(f, (10_000, 10_000))
    report = connector.sync(tmp_path)

    assert rec.ingested == ["a.md", "a.md"]  # ingested again
    assert report.summary()["updated"] == 1


def test_removed_file_is_dropped_from_manifest(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("alpha")
    rec = _Recorder()
    connector = _connector(rec, tmp_path)
    connector.sync(tmp_path)

    f.unlink()
    report = connector.sync(tmp_path)

    assert report.summary()["removed"] == 1
    assert str(f.resolve()) not in connector._load()


def test_failed_file_does_not_abort_sync_and_is_not_marked_done(tmp_path):
    (tmp_path / "good.md").write_text("ok")
    (tmp_path / "bad.md").write_text("boom")

    def _ingest(path: Path) -> None:
        if path.name == "bad.md":
            raise RuntimeError("extractor blew up")

    connector = _connector(_ingest, tmp_path)
    report = connector.sync(tmp_path)

    assert report.summary()["added"] == 1
    assert report.summary()["failed"] == 1
    # The failed file is NOT recorded, so a later sync retries it.
    manifest = connector._load()
    assert not any(k.endswith("bad.md") for k in manifest)


def test_recurses_into_subdirectories(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.md").write_text("deep")
    rec = _Recorder()

    _connector(rec, tmp_path).sync(tmp_path)

    assert rec.ingested == ["nested.md"]


def test_watch_runs_bounded_iterations(tmp_path):
    (tmp_path / "a.md").write_text("alpha")
    rec = _Recorder()
    connector = _connector(rec, tmp_path)
    reports = []
    sleeps = []

    connector.watch(
        tmp_path,
        poll_interval=1.0,
        on_sync=reports.append,
        _sleep=sleeps.append,
        _iterations=3,
    )

    assert len(reports) == 3  # synced three times
    assert len(sleeps) == 2  # slept between iterations, not after the last
