from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.services.material_storage_audit import audit_material_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="审计素材存储状态，找出源文件缺失的脏记录。")
    parser.add_argument("--material-id", action="append", type=int, default=[], help="只审计指定素材 ID，可重复传入")
    parser.add_argument("--mark-missing", action="store_true", help="将缺失源文件的素材标记为 source_missing，并记录审计日志")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        stats = audit_material_sources(
            db,
            mark_missing=args.mark_missing,
            material_ids=args.material_id or None,
        )
        print(
            json.dumps(
                {
                    "scanned": stats.scanned,
                    "healthy": stats.healthy,
                    "qiniu_ready": stats.qiniu_ready,
                    "local_ready": stats.local_ready,
                    "missing_source": stats.missing_source,
                    "marked_missing": stats.marked_missing,
                    "missing_items": stats.missing_items,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
