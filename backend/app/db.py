"""SQLite 持久化：会话历史 + 面试场次（Agent 记忆回填 / 前端展示 / 评分报告）。"""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DB_PATH, ensure_dirs

ensure_dirs()

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Interview(Base):
    """一次模拟面试场次：方向、状态、总分与完整评分报告。"""

    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(32), default="通用")
    status: Mapped[str] = mapped_column(String(16), default="ongoing")
    score: Mapped[int] = mapped_column(default=0)
    report: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[str] = mapped_column(Text, default="")
    prep: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class InterviewQA(Base):
    """面试中的一道题：题目、作答、点评、追问、追问作答与参考答案。"""

    __tablename__ = "interview_qa"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    interview_id: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(32), default="")
    level: Mapped[str] = mapped_column(String(16), default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(default=0)
    competency: Mapped[str] = mapped_column(String(64), default="")
    rubric: Mapped[str] = mapped_column(Text, default="[]")
    seed_followups: Mapped[str] = mapped_column(Text, default="[]")
    answer: Mapped[str] = mapped_column(Text, default="")
    answer_score: Mapped[int] = mapped_column(default=0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    followup: Mapped[str] = mapped_column(Text, default="")
    followup_answer: Mapped[str] = mapped_column(Text, default="")
    reference: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class UserProfile(Base):
    """候选人档案：目标岗位、技能栈、项目经历（个人画像，驱动个性化出题）。"""

    __tablename__ = "user_profiles"

    profile_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    target_role: Mapped[str] = mapped_column(String(64), default="")
    target_direction: Mapped[str] = mapped_column(String(64), default="")
    skills: Mapped[str] = mapped_column(Text, default="[]")
    weak_areas: Mapped[str] = mapped_column(Text, default="[]")
    projects: Mapped[str] = mapped_column(Text, default="[]")
    jd_text: Mapped[str] = mapped_column(Text, default="")
    jd_analysis: Mapped[str] = mapped_column(Text, default="{}")
    resume_text: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class InterviewReview(Base):
    """面经复盘记录：原文 + 结构化复盘结果，供求职作战室回看。"""

    __tablename__ = "interview_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_key: Mapped[str] = mapped_column(String(32), index=True)
    source_text: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    highlights: Mapped[str] = mapped_column(Text, default="[]")
    weaknesses: Mapped[str] = mapped_column(Text, default="[]")
    key_points: Mapped[str] = mapped_column(Text, default="[]")
    action_plan: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_columns()


_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "interview_qa": [
        ("difficulty", "INTEGER DEFAULT 0"),
        ("competency", "VARCHAR(64) DEFAULT ''"),
        ("rubric", "TEXT DEFAULT '[]'"),
        ("seed_followups", "TEXT DEFAULT '[]'"),
        ("answer_score", "INTEGER DEFAULT 0"),
    ],
    "interviews": [
        ("plan", "TEXT DEFAULT ''"),
        ("prep", "TEXT DEFAULT ''"),
    ],
    "user_profiles": [
        ("jd_text", "TEXT DEFAULT ''"),
        ("jd_analysis", "TEXT DEFAULT '{}'"),
        ("resume_text", "TEXT DEFAULT ''"),
    ],
}


def _migrate_columns() -> None:
    """轻量迁移：为新表补充新列（幂等，重复调用安全）。"""
    with engine.connect() as conn:
        for table, columns in _MIGRATIONS.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.commit()


@contextmanager
def get_session():
    with SessionLocal() as session:
        yield session
