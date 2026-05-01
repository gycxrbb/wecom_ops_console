from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TimestampMixinAuto:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutoRankingConfig(Base, TimestampMixinAuto):
    __tablename__ = 'auto_ranking_configs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    crm_group_ids_json: Mapped[str] = mapped_column(Text, default='[]')
    target_local_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    must_scene_keys_json: Mapped[str] = mapped_column(Text, default='["top_leader", "top_six"]')
    extra_scene_pool_json: Mapped[str] = mapped_column(Text, default='[]')
    scene_count: Mapped[int] = mapped_column(Integer, default=3)
    speech_style: Mapped[str] = mapped_column(String(32), default='professional')
    include_breakdown_on_monday: Mapped[int] = mapped_column(Integer, default=1)
    skip_weekends: Mapped[int] = mapped_column(Integer, default=0)
    skip_dates_json: Mapped[str] = mapped_column(Text, default='[]')
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default='')
