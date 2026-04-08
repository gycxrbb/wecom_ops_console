from __future__ import annotations

import argparse

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models import Material
from app.schema_migrations import ensure_asset_folders_schema
from app.services.material_storage_service import migrate_material_to_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Migrate local materials to object storage provider.')
    parser.add_argument('--target-provider', default='qiniu', help='Target storage provider name, default: qiniu')
    parser.add_argument('--material-id', type=int, help='Only migrate one material id')
    parser.add_argument('--limit', type=int, default=0, help='Max material count to migrate')
    parser.add_argument('--include-disabled', action='store_true', help='Include disabled materials')
    parser.add_argument('--dry-run', action='store_true', help='Only print candidate materials')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ensure_asset_folders_schema(engine)

    migrated = 0
    skipped = 0
    failed = 0

    with SessionLocal() as db:
        stmt = select(Material).order_by(Material.id.asc())
        if not args.include_disabled:
            stmt = stmt.where(Material.enabled == 1)
        if args.material_id:
            stmt = stmt.where(Material.id == args.material_id)
        materials = list(db.scalars(stmt))
        if args.limit and args.limit > 0:
            materials = materials[: args.limit]

        print(f'[material-migrate] candidates={len(materials)} target_provider={args.target_provider} dry_run={args.dry_run}')
        for material in materials:
            has_ready_target = (
                (material.storage_provider or '').strip().lower() == args.target_provider.strip().lower()
                and bool(material.storage_key)
                and bool(material.public_url or material.url)
            )
            if has_ready_target:
                skipped += 1
                print(f'[skip] material_id={material.id} name={material.name} provider={material.storage_provider}')
                continue

            print(
                '[plan] '
                f"material_id={material.id} name={material.name} "
                f"from={material.storage_provider or 'local'} "
                f"storage_path={material.storage_path or '-'}"
            )
            if args.dry_run:
                continue

            try:
                changed = migrate_material_to_provider(
                    db,
                    material,
                    target_provider=args.target_provider,
                    operator_ip='migration-script',
                    keep_local_copy=True,
                )
                if changed:
                    db.commit()
                    migrated += 1
                    print(
                        '[done] '
                        f'material_id={material.id} provider={material.storage_provider} '
                        f'key={material.storage_key} public_url={material.public_url}'
                    )
                else:
                    db.rollback()
                    skipped += 1
                    print(f'[skip] material_id={material.id} already matches target provider')
            except Exception as exc:
                db.rollback()
                failed += 1
                print(f'[fail] material_id={material.id} name={material.name} error={exc}')

    print(f'[summary] migrated={migrated} skipped={skipped} failed={failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
