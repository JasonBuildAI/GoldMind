"""全项目唯一的时区入口。

规则（见 `AGENTS.md` 红线 5 与 `docs/ARCHITECTURE.md` 第七节）：

> 数据进入系统时立刻换算成它，离开系统时才转回去。

时区口径由 `settings.SCHEDULER_TIMEZONE` 决定。**不要**在业务代码里直接写
`datetime.now()` —— 那是服务器本地时间：容器默认 UTC，而 cron 用的是
`SCHEDULER_TIMEZONE`，两者不一致时「今天是哪天」就会算错。

这个模块是被两次真实故障逼出来的：

1. 定时任务用 `datetime.now().date()` 取「今天」，同一份行情在 Docker 里
   被记到前一天；
2. RSS 的 `published_parsed` 是 UTC，直接当本地时间存，「最近 24 小时」
   的窗口实际覆盖到约 32 小时。

后来清点时又发现接口层还有近二十处同样的写法，所以收敛到这里。
"""
from datetime import date, datetime
from typing import Optional

from app.config import settings

try:  # zoneinfo 需要时区数据库（tzdata，已在 requirements.txt 里显式声明）
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 不会有，留个明确的失败点
    ZoneInfo = None  # type: ignore[assignment]


def _tz():
    """项目时区；加载不到时返回 None（调用方退回本地时间）。"""
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(settings.SCHEDULER_TIMEZONE)
    except Exception:
        return None


def now() -> datetime:
    """项目时区下带 tzinfo 的当前时间。"""
    tz = _tz()
    return datetime.now(tz) if tz else datetime.now()


def now_naive() -> datetime:
    """项目时区下的当前时间，**去掉 tzinfo**。

    数据库列是 naive DateTime，写入前统一用这个，保证库里存的一律是项目时区。
    """
    return now().replace(tzinfo=None)


def today() -> date:
    """项目时区下的「今天」。"""
    return now().date()


def today_str() -> str:
    """项目时区下的「今天」，格式 ``YYYY-MM-DD``。"""
    return today().strftime("%Y-%m-%d")


def now_str() -> str:
    """项目时区下的当前时间，格式 ``YYYY-MM-DD HH:MM:SS``。"""
    return now_naive().strftime("%Y-%m-%d %H:%M:%S")


def now_iso() -> str:
    """项目时区下的当前时间，ISO 格式（含偏移）。"""
    return now().isoformat()


def from_utc_naive(moment: Optional[datetime]) -> Optional[datetime]:
    """把一个「UTC 的 naive 时间」换算成项目时区的 naive 时间。

    用于外部时间戳：RSS 的 ``published_parsed``、某些 API 返回的 UTC 时间。
    """
    if moment is None:
        return None
    from datetime import timezone

    tz = _tz()
    aware = moment.replace(tzinfo=timezone.utc)
    return (aware.astimezone(tz) if tz else aware).replace(tzinfo=None)
