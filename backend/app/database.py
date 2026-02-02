"""数据库连接和模型基类"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.pool import QueuePool, NullPool
from app.config import settings

# 使用QueuePool连接池提升性能，自动管理连接生命周期
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,           # 使用队列连接池
    pool_size=10,                  # 保持10个永久连接
    max_overflow=20,               # 最多溢出20个临时连接
    pool_pre_ping=True,            # 连接前ping测试，自动回收死连接
    pool_recycle=3600,             # 1小时回收连接，防止MySQL wait_timeout
    pool_timeout=30,               # 获取连接超时时间
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30
    } if "mysql" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


@contextmanager
def get_db_context():
    """同步上下文管理器获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI依赖注入使用的生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
