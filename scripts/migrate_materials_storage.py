from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.services.material_storage_migration import migrate_materials_to_provider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将素材从当前存储迁移到目标存储 provider。")
    parser.add_argument("--target", default="qiniu", help="目标 provider，默认 qiniu")
    parser.add_argument("--material-id", action="append", type=int, default=[], help="只迁移指定素材 ID，可重复传入")
    parser.add_argument("--limit", type=int, default=None, help="限制本次处理数量")
    parser.add_argument("--dry-run", action="store_true", help="只做读取与可迁移检查，不真正上传")
    parser.add_argument("--force", action="store_true", help="即使素材已在目标 provider 也强制重新迁移")
    parser.add_argument(
        "--delete-local-copy",
        action="store_true",
        help="迁移成功后删除本地源文件。默认保留，作为降级 fallback。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        stats = migrate_materials_to_provider(
            db,
            target_provider=args.target,
            material_ids=args.material_id or None,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
            keep_local_copy=not args.delete_local_copy,
        )
        print(
            json.dumps(
                {
                    "scanned": stats.scanned,
                    "migrated": stats.migrated,
                    "skipped": stats.skipped,
                    "failed": stats.failed,
                    "migrated_ids": stats.migrated_ids,
                    "skipped_ids": stats.skipped_ids,
                    "failed_items": stats.failed_items,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if stats.failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
