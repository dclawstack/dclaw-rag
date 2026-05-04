#!/usr/bin/env python3
"""Batch ingest all files in a folder."""

import argparse
import asyncio
from pathlib import Path

from app.ingestion.pipeline import IngestionPipeline
from app.models.schemas import IngestRequest


async def main(folder: Path, source_prefix: str, tenant_id: str | None) -> None:
    pipeline = IngestionPipeline()

    for file_path in folder.iterdir():
        if file_path.is_file():
            request = IngestRequest(
                source=f"{source_prefix}/{file_path.name}",
                title=file_path.name,
                tenant_id=tenant_id,
            )
            try:
                doc_id = pipeline.ingest_file(file_path, request)
                print(f"Ingested {file_path.name} → {doc_id}")
            except Exception as exc:
                print(f"Failed {file_path.name}: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch ingest a folder")
    parser.add_argument("folder", type=Path, help="Folder containing files")
    parser.add_argument("--source-prefix", default="local", help="Source prefix")
    parser.add_argument("--tenant-id", default=None, help="Tenant ID")
    args = parser.parse_args()

    asyncio.run(main(args.folder, args.source_prefix, args.tenant_id))
