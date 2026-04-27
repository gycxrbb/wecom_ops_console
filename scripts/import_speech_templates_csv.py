"""Import external speech CSV rows into the speech template table."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.speech_template_import import import_speech_templates_csv_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import speech templates from CSV.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--index-rag", action="store_true", help="Run RAG indexing after import.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = import_speech_templates_csv_file(db, args.csv_path, dry_run=args.dry_run)
    finally:
        db.close()
    print(f"created={stats['created']} updated={stats['updated']} skipped={stats['skipped']}")
    for error in stats["errors"]:
        print(f"error: {error}")
    for row in stats["rows"]:
        print(
            f"{row['action']}: {row['source_id']} -> "
            f"{row['scene_key']}/{row['style']} {row['title']}"
        )

    if args.index_rag and not args.dry_run:
        from app.rag.resource_indexer import index_speech_templates

        db = SessionLocal()
        try:
            rag_stats = asyncio.run(index_speech_templates(db))
            print(f"rag_index={rag_stats}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
