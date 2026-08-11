"""SQLite 持久化：会话历史（Agent 记忆回填 + 前端历史展示）。"""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, String, Text
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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    with SessionLocal() as session:
        yield session
