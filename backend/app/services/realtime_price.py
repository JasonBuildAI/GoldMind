"""实时金价 —— 全项目唯一入口。

## 为什么要合并

原先有两套实现，各自带一份缓存，彼此不知道对方存在：

- ``gold_service``：腾讯 ``qt.gtimg.cn``。它自带的 ``_get_cached_price`` /
  ``_set_cached_price`` **从未被调用**；解析时把 open/high/low 的索引取错了
  （用了 ``[2]/[3]/[4]``，真实位置是 ``[8]/[4]/[5]``，见下方字段表）
- ``gold_price_service``：新浪 + 东方财富，自建文件缓存（30 秒 TTL、
  非原子写入、且不认 ``CACHE_DIR``）；它使用的东财代码 ``103.XAUUSD`` 已失效

后果是：腾讯接口一挂，``/stats`` 就只能退回数据库里的旧数据 ——
而当时新浪其实完全可用。

现在合并为「多源依次尝试 + 统一 CacheManager 缓存」。

## 数据源字段表（腾讯与新浪的 hf_ 格式完全一致，已用同刻数据交叉验证）

    [0] 最新价   [4] 最高价   [5] 最低价   [6] 时间
    [7] 昨收     [8] 开盘价   [12] 日期    [13] 名称

东方财富用 ``122.XAU``（黄金/美元）。``103.XAUUSD`` 返回 ``data: null``。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from app.services.cache_manager import CacheManager

# 依次尝试的数据源
SOURCE_ORDER = ("tencent", "sina", "eastmoney")

# 实时价缓存：30 秒，够短以免页面看到过期价，够长以免每次请求都打上游
CACHE_TTL_SECONDS = 30

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# hf_ 格式的字段位置（腾讯与新浪一致）
_F_PRICE = 0
_F_HIGH = 4
_F_LOW = 5
_F_TIME = 6
_F_PREV_CLOSE = 7
_F_OPEN = 8
_F_DATE = 12
_F_NAME = 13


def _safe_float(value: Any, default: float = 0.0) -> float:
    """把上游返回的字符串安全转成 float。"""
    try:
        text = str(value).strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def _build_result(
    *,
    price: float,
    previous_close: float,
    open_price: float,
    high: float,
    low: float,
    date_str: str,
    time_str: str,
    source: str,
    source_name: str,
) -> Dict[str, Any]:
    """拼出统一的返回结构。所有数据源都必须产出同一组字段。"""
    change = price - previous_close if previous_close else 0.0
    change_pct = (change / previous_close * 100) if previous_close else 0.0

    return {
        "price": round(price, 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "updated_at": datetime.now().isoformat(),
        "date": date_str,
        "update_time": f"{date_str} {time_str}",
        "source": source,
        "source_name": source_name,
        "symbol": "XAU/USD",
        "unit": "美元/盎司",
    }


def _parse_hq_payload(payload: str, *, source: str, source_name: str) -> Optional[Dict[str, Any]]:
    """解析腾讯 / 新浪的 hf_ 逗号分隔数据。"""
    parts = payload.split(",")
    if len(parts) < 13:
        return None

    price = _safe_float(parts[_F_PRICE])
    if not price:
        return None

    return _build_result(
        price=price,
        previous_close=_safe_float(parts[_F_PREV_CLOSE]),
        open_price=_safe_float(parts[_F_OPEN]),
        high=_safe_float(parts[_F_HIGH]),
        low=_safe_float(parts[_F_LOW]),
        date_str=parts[_F_DATE] or datetime.now().strftime("%Y-%m-%d"),
        time_str=parts[_F_TIME] if len(parts) > _F_TIME else "",
        source=source,
        source_name=source_name,
    )


# --------------------------------------------------------------------------- #
# 各数据源
# --------------------------------------------------------------------------- #
def fetch_from_tencent() -> Optional[Dict[str, Any]]:
    """腾讯财经（纽约黄金）。"""
    try:
        response = requests.get(
            "https://qt.gtimg.cn/q=hf_GC",
            headers={"User-Agent": _USER_AGENT},
            timeout=5,
        )
        if response.status_code != 200:
            return None
        match = re.search(r'v_hf_GC="([^"]+)"', response.text)
        if not match:
            return None
        return _parse_hq_payload(match.group(1), source="tencent", source_name="腾讯财经-纽约黄金")
    except Exception as exc:  # 网络、超时、解析
        print(f"[RealtimePrice] 腾讯财经失败: {exc}")
        return None


def fetch_from_sina() -> Optional[Dict[str, Any]]:
    """新浪财经（伦敦金）。必须带 Referer，且返回是 GB2312。"""
    try:
        response = requests.get(
            "https://hq.sinajs.cn/list=hf_GC",
            headers={
                "User-Agent": _USER_AGENT,
                "Referer": "https://finance.sina.com.cn",
            },
            timeout=5,
        )
        response.encoding = "gb2312"
        if response.status_code != 200:
            return None
        match = re.search(r'var hq_str_hf_GC="([^"]*)"', response.text)
        if not match or not match.group(1):
            return None
        return _parse_hq_payload(match.group(1), source="sina", source_name="新浪财经-伦敦金")
    except Exception as exc:
        print(f"[RealtimePrice] 新浪财经失败: {exc}")
        return None


def fetch_from_eastmoney() -> Optional[Dict[str, Any]]:
    """东方财富（黄金/美元）。

    代码是 ``122.XAU``。原实现用的 ``103.XAUUSD`` 已失效，返回 ``data: null``。
    该接口的价格字段都放大了 100 倍。
    """
    try:
        response = requests.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={
                "secid": "122.XAU",
                "fields": "f43,f44,f45,f46,f57,f58,f60",
                "_": int(datetime.now().timestamp() * 1000),
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=5,
        )
        if response.status_code != 200:
            return None

        data = (response.json() or {}).get("data")
        if not data:
            return None

        price = _safe_float(data.get("f43")) / 100
        if not price:
            return None

        now = datetime.now()
        return _build_result(
            price=price,
            previous_close=_safe_float(data.get("f60")) / 100,
            open_price=_safe_float(data.get("f46")) / 100,
            high=_safe_float(data.get("f44")) / 100,
            low=_safe_float(data.get("f45")) / 100,
            date_str=now.strftime("%Y-%m-%d"),
            time_str=now.strftime("%H:%M:%S"),
            source="eastmoney",
            source_name="东方财富-黄金/美元",
        )
    except Exception as exc:
        print(f"[RealtimePrice] 东方财富失败: {exc}")
        return None


_FETCHERS = {
    "tencent": fetch_from_tencent,
    "sina": fetch_from_sina,
    "eastmoney": fetch_from_eastmoney,
}


# --------------------------------------------------------------------------- #
# 对外入口
# --------------------------------------------------------------------------- #
def get_realtime_gold_price(*, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """获取实时金价：缓存 → 腾讯 → 新浪 → 东方财富。

    Returns:
        统一结构（price / previous_close / change / change_percent /
        open / high / low / updated_at / date / update_time /
        source / source_name / symbol / unit），全部数据源都失败时返回 None。
    """
    cache = CacheManager("realtime_gold_price", ttl=CACHE_TTL_SECONDS)

    if use_cache:
        cached = cache.get()
        if cached:
            return cached

    for name in SOURCE_ORDER:
        result = _FETCHERS[name]()
        if result:
            cache.set(result)
            print(f"[RealtimePrice] 成功: ${result['price']} ({result['source_name']})")
            return result

    print("[RealtimePrice] 所有数据源均失败")
    return None
