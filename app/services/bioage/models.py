"""bioage 模块 ORM Model。使用独立 BioageBase，便于整体迁移。"""

from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import declarative_base, mapped_column, Mapped, Session

BioageBase = declarative_base()


class BioageCalculation(BioageBase):
    __tablename__ = "bioage_calculations"
    __table_args__ = (
        Index("idx_ba_cust_ver", "customer_id", "param_version"),
        Index("idx_ba_cust_date", "customer_id", "created_at"),
        {"comment": "生物年龄测算结果表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="客户ID")
    param_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v2.0-draft", comment="参数版本号")

    # 输入快照
    chronological_age: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False, comment="日历年龄")
    gender: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="1男 2女")
    checkup_date: Mapped[str | None] = mapped_column(Date, nullable=True, comment="体检日期")
    checkup_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="距体检天数")
    bp_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="血压窗口天数")
    bp_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="血压记录数")

    # 核心结果
    biological_age: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False, comment="生物年龄BA")
    age_acceleration: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False, comment="BAA=BA-CA")
    n_biomarkers: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="参与计算指标数")
    total_biomarkers: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=8, comment="算法总指标数")
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, comment="high/medium/low")
    age_weight_applied: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, comment="体检超18月降权")

    # 维度贡献度
    dim_scores: Mapped[str | None] = mapped_column(Text, nullable=True, comment="维度分数JSON")
    contributions: Mapped[str | None] = mapped_column(Text, nullable=True, comment="指标贡献度JSON")
    missing_codes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="缺失指标JSON")

    # 输入值快照
    input_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True, comment="输入值快照JSON")

    # 警告
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True, comment="警告JSON")

    # LLM 解读
    llm_reading: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用户端解读文案")
    llm_actions: Mapped[str | None] = mapped_column(Text, nullable=True, comment="行动建议JSON")
    llm_coach_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="教练参考话术")
    llm_generated_at: Mapped[str | None] = mapped_column(DateTime, nullable=True, comment="LLM生成时间")

    # 元数据
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=True, default="manual", comment="触发方式")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow)

    @classmethod
    def get_latest_by_customer(cls, db: Session, customer_id: int) -> "BioageCalculation | None":
        return (
            db.query(cls)
            .filter(cls.customer_id == customer_id)
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def get_history_by_customer(cls, db: Session, customer_id: int, limit: int = 20) -> list["BioageCalculation"]:
        return (
            db.query(cls)
            .filter(cls.customer_id == customer_id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )
