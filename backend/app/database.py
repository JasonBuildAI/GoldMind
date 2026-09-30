"""数据库连接和模型基类"""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.pool import QueuePool, StaticPool
from app.config import settings


def _build_engine():
    """按数据库类型构造引擎。

    MySQL 与 SQLite 的连接参数差异很大，这里显式区分：

    - **SQLite**：必须 `check_same_thread=False`，否则 FastAPI 把同步依赖丢进
      线程池后会报跨线程错误；内存库还必须用 `StaticPool` 共用同一个连接，
      否则每个连接看到的是各自独立的空库。
    - **MySQL**：保留原有连接池与超时设置（生产路径，行为不变）。

    支持 SQLite 是为了让测试可以完全脱离 MySQL 运行。
    """
    url = settings.DATABASE_URL
    kwargs: dict = {"echo": False}

    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        is_memory = ":memory:" in url or url.rstrip("/") == "sqlite:"
        if is_memory:
            kwargs["poolclass"] = StaticPool
        else:
            kwargs.update(
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
            )
    else:
        kwargs.update(
            poolclass=QueuePool,           # 使用队列连接池
            pool_size=10,                  # 保持10个永久连接
            max_overflow=20,               # 最多溢出20个临时连接
            pool_pre_ping=True,            # 连接前ping测试，自动回收死连接
            pool_recycle=3600,             # 1小时回收连接，防止MySQL wait_timeout
            pool_timeout=30,               # 获取连接超时时间
            connect_args={
                "connect_timeout": 10,
                "read_timeout": 30,
                "write_timeout": 30,
            },
        )

    return create_engine(url, **kwargs)


engine = _build_engine()

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


def mysql_connection_params(include_database: bool = True) -> dict:
    """从 `DATABASE_URL` 解析出 pymysql 需要的连接参数。

    ## 为什么要有这个函数

    数据库连接信息原本有**两处来源**：

    - `DATABASE_URL` —— 应用（`app/database.py`）用它
    - `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` ——
      `init_db.py` 与 `seed_data.py` 用它们

    两处一旦不一致，**建表与灌数据的库和应用实际读写的库就不是同一个**，
    而且不会有任何报错 —— 表现只是「接口里没数据」。
    这违反了项目自己那条「同一事实只保留一个权威来源」。

    现在统一以 `DATABASE_URL` 为准，`DB_*` 只在它缺失时兜底。

    Args:
        include_database: 是否需要库名。`init_db.py` 要先连上去建库，
            此时库还不存在，必须传 False。
    """
    url = settings.DATABASE_URL or ""

    if url.startswith("mysql"):
        from urllib.parse import unquote, urlparse

        parsed = urlparse(url)
        params = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or "root"),
            "password": unquote(parsed.password or ""),
            "charset": "utf8mb4",
        }
        if include_database:
            params["database"] = (parsed.path or "/").lstrip("/") or "gold_analysis"
        return params

    # 没配 DATABASE_URL（或用的不是 MySQL）时，退回旧的 DB_* 约定。
    # 密码同样**不给默认值** —— 凭据只能来自环境（AGENTS.md 红线 2）。
    import os

    params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset": "utf8mb4",
    }
    if include_database:
        params["database"] = os.getenv("DB_NAME", "gold_analysis")
    return params


def init_db():
    Base.metadata.create_all(bind=engine)
