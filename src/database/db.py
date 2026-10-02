import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cybersahay.db")

# SQLite needs check_same_thread=False for multithreaded FastAPI requests
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initializes database tables and migrates schema on application startup.
    """
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Lightweight auto-migration for SQLite to guarantee backward compatibility
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            # Check existing columns in chat_sessions
            res = conn.execute(text("PRAGMA table_info(chat_sessions)")).fetchall()
            existing_cols = {row[1] for row in res}
            if "state_json" not in existing_cols:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN state_json TEXT DEFAULT '{}'"))
            if "case_profile_json" not in existing_cols:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN case_profile_json TEXT DEFAULT '{}'"))
            conn.commit()
    except Exception as migr_err:
        pass

    print("Database tables initialized successfully.")



# Auto-create tables on first import for instant zero-config readiness
try:
    init_db()
except Exception as e:
    print(f"Warning: automatic DB init encountered: {e}")
