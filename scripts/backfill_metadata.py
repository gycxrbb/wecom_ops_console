"""One-time backfill: populate metadata_json for existing speech templates.

For builtin templates (is_builtin=1), derive metadata from scene_key.
For CSV-imported templates (is_builtin=0), metadata_json should already be set by import.

Run: python scripts/backfill_metadata.py
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import SpeechTemplate

# Map builtin scene_key → metadata structure
_BUILTIN_SCENE_META = {
    "top_leader": {"intervention_scene": ["top_leader"], "customer_goal": ["points_engagement"]},
    "top_six": {"intervention_scene": ["top_six"], "customer_goal": ["points_engagement"]},
    "top_ten": {"intervention_scene": ["top_ten"], "customer_goal": ["points_engagement"]},
    "consistent": {"intervention_scene": ["consistent"], "customer_goal": ["habit_building"]},
    "surge": {"intervention_scene": ["surge"], "customer_goal": ["points_engagement"]},
    "comeback": {"intervention_scene": ["comeback"], "customer_goal": ["re_engagement"]},
    "dropout_recovery": {"intervention_scene": ["dropout_recovery"], "customer_goal": ["re_engagement"]},
    "rapid_progress": {"intervention_scene": ["rapid_progress"], "customer_goal": ["habit_building"]},
    "reverse_bottom": {"intervention_scene": ["reverse_bottom"], "customer_goal": ["points_engagement"]},
    "lurker_remind": {"intervention_scene": ["lurker_remind"], "customer_goal": ["re_engagement"]},
    "daily_remind": {"intervention_scene": ["daily_remind"], "customer_goal": ["engagement"]},
    "group_pk": {"intervention_scene": ["group_pk"], "customer_goal": ["points_engagement"]},
    # Generic scenes
    "meal_checkin": {"intervention_scene": ["meal_checkin"], "customer_goal": ["weight_loss", "glucose_control"]},
    "meal_review": {"intervention_scene": ["meal_review"], "customer_goal": ["weight_loss", "glucose_control"]},
    "obstacle_breaking": {"intervention_scene": ["obstacle_breaking"], "customer_goal": ["habit_building"]},
    "habit_education": {"intervention_scene": ["habit_education"], "customer_goal": ["habit_building"]},
    "emotional_support": {"intervention_scene": ["emotional_support"], "customer_goal": ["habit_building"]},
    "qa_support": {"intervention_scene": ["qa_support"]},
    "period_review": {"intervention_scene": ["period_review"], "customer_goal": ["weight_loss"]},
    "maintenance": {"intervention_scene": ["maintenance"], "customer_goal": ["habit_building"]},
}


def main():
    db = SessionLocal()
    try:
        templates = db.query(SpeechTemplate).filter(
            SpeechTemplate.deleted_at.is_(None),
        ).all()

        updated = 0
        skipped = 0

        for tpl in templates:
            existing = getattr(tpl, "metadata_json", None)
            if existing and existing.strip():
                skipped += 1
                continue

            meta = _BUILTIN_SCENE_META.get(tpl.scene_key, {
                "intervention_scene": [tpl.scene_key],
            })

            # Add domain tag
            scene_key = tpl.scene_key
            points_scenes = {
                "top_leader", "top_six", "top_ten", "surge",
                "lurker_remind", "daily_remind", "group_pk",
                "consistent", "comeback", "dropout_recovery",
                "rapid_progress", "reverse_bottom",
            }
            if scene_key in points_scenes:
                meta["domain"] = "points_operation"

            tpl.metadata_json = json.dumps(meta, ensure_ascii=False)
            updated += 1
            print(f"  [{tpl.id}] scene={tpl.scene_key} label={tpl.label[:30]} → {meta}")

        db.commit()
        print(f"\nDone: updated={updated}, skipped={skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
