"""POST /refresh 的可选令牌门（2.0.2 第 20 条）。

刷新接口会真实调用付费 LLM、抓取外网或重算量化回测。本机 / 内网部署不需要
鉴权（默认行为不变），但公开部署时任何人都能反复触发 —— 设一个
`REFRESH_TOKEN`，之后所有 `POST .../refresh` 必须带 `X-Refresh-Token` 请求头。

规则只有三条：

- `REFRESH_TOKEN` 为空（默认）= 不拦，保持旧行为；
- 配了令牌 = 缺头 / 不匹配一律 401，且**在读取请求体与执行任何副作用之前**拒绝；
- 比较用 `secrets.compare_digest`，不泄露前缀匹配的时序信息。

令牌只进 `.env` 与部署环境（红线 2），错误信息里不回显任何一部分。
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings

REFRESH_TOKEN_HEADER = "X-Refresh-Token"


def require_refresh_token(
    x_refresh_token: Optional[str] = Header(default=None, alias=REFRESH_TOKEN_HEADER),
) -> None:
    """FastAPI 依赖：配置了 `REFRESH_TOKEN` 时校验请求头，否则放行。"""
    configured = settings.REFRESH_TOKEN.get_secret_value().strip()
    if not configured:
        return

    provided = (x_refresh_token or "").strip()
    if not provided or not secrets.compare_digest(provided, configured):
        raise HTTPException(
            status_code=401,
            detail=(
                f"缺少或错误 {REFRESH_TOKEN_HEADER}：该部署已开启刷新鉴权，"
                "请在请求头里携带与 REFRESH_TOKEN 一致的令牌。"
            ),
        )