"""数据源可用性看板（2.0.2 第 2 条整改）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import source_status

router = APIRouter()


@router.get("/sources/status")
async def get_sources_status(db: Session = Depends(get_db)):
    """各抓取通道的最近一次尝试与可用性汇总。

    数据来源是只追加的 `fetch_attempts` 流水（量化因子同步 / 消息板块 / RSS /
    行情四条通道各自记录）；没有任何记录时如实返回空列表，不编造「可用」。
    """
    return source_status.payload(db)
