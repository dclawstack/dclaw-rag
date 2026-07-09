#!/usr/bin/env python3
"""Sync a local folder into the index — incremental, dedup, optional watch.

Re-running only ingests new/changed files (a manifest tracks mtime+size); files
removed from disk are dropped from the manifest. Content dedup is handled by the
pipeline. Fits the local-first stance: no cloud, no upload step.

    python scripts/sync_folder.py ~/Documents/notes --tenant-id acme
    python scripts/sync_folder.py ~/Documents/notes --watch --interval 5
"""

import argparse
from pathlib import Path

from app.core.config import settings
from app.ingestion.folder_connector import FolderConnector, make_pipeline_ingest


def _manifest_path(directory: Path) -> Path:
    # One manifest per absolute directory path, under the app data dir.
    import hashlib

    digest = hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:16]
    return Path(settings.data_dir).expanduser() / "folder_sync" / f"{digest}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a local folder into the index")
    parser.add_argument("folder", type=Path, help="Directory to sync (recursive)")
    parser.add_argument("--source-prefix", default="local")
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--collection-id", default=None)
    parser.add_argument("--watch", action="store_true", help="Keep syncing on an interval")
    parser.add_argument("--interval", type=float, default=5.0, help="Watch poll seconds")
    args = parser.parse_args()

    connector = FolderConnector(
        ingest=make_pipeline_ingest(args.source_prefix, args.tenant_id, args.collection_id),
        manifest_path=_manifest_path(args.folder),
    )

    def _report(report):
        s = report.summary()
        print(
            f"synced {args.folder}: +{s['added']} ~{s['updated']} "
            f"skip {s['skipped']} -{s['removed']} fail {s['failed']}"
        )
        for path, error in report.failed:
            print(f"  failed {path}: {error}")

    if args.watch:
        print(f"watching {args.folder} every {args.interval}s (Ctrl-C to stop)")
        try:
            connector.watch(args.folder, poll_interval=args.interval, on_sync=_report)
        except KeyboardInterrupt:
            print("stopped")
    else:
        _report(connector.sync(args.folder))


if __name__ == "__main__":
    main()
