"""黄金价格服务 - 优化版（添加缓存和异步处理）"""
import re
import requests
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.services.cache_manager import CacheManager, REALTIME_PRICE_CACHE_TTL
from app.utils import timeutil
from app.models.gold_price import GoldPrice, DollarIndex
from app.services.price_window import compute_price_window
from loguru import logger

# 创建带重试机制的HTTP Session（提升API稳定性）
def create_retry_session(
    retries=3,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    pool_connections=10,
    pool_maxsize=10
):
    """创建带重试机制的requests session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"]  # 允许重试的方法
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# 全局session实例（线程安全）
_http_session = None
_session_lock = threading.Lock()

def get_http_session():
    """获取带重试的HTTP session（懒加载）"""
    global _http_session
    if _http_session is None:
        with _session_lock:
            if _http_session is None:
                _http_session = create_retry_session()
    return _http_session


def format_market_status(stats: Optional[Dict]) -> str:
    """把 `get_statistics()` 的结果拼成给 LLM / 接口看的一行市场描述。

    统计口径的唯一来源是 `get_statistics()`（窗口实现见 `price_window`）；
    这里不再出现「年内 / 波动区间」这类会随日历失效的说法。
    """
    if not stats:
        return "暂无行情数据（数据库里没有可用的金价记录）"
    label = stats.get("window_label") or "滚动窗口"
    return (
        f"当前金价: ${stats.get('current_price', 0):.2f}, "
        f"{label}涨跌（首尾收盘比较）: {stats.get('window_return', 0):+.2f}%, "
        f"高低振幅（非波动率）: {stats.get('amplitude', 0):.2f}%"
    )


class GoldService:
    """黄金价格服务 - 优化版"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_realtime_dollar_index(self, use_cache: bool = True) -> Optional[Dict]:
        """获取实时美元指数（数据源：新浪财经 ICE 美元指数 DINIW）。

        原实现**完全没有缓存**：每次调用都新建 session 去上游取一次。
        而前端每 10 秒轮询一次 `/dollar-realtime` —— 一个浏览器标签页就是
        每分钟 6 次外部请求，开三个标签页就是 18 次，且不限速地持续下去。
        加一个与实时金价同级的短缓存（30 秒）之后，外部请求变成
        **每个实例每 30 秒一次**，与标签页数量无关。
        """
        cache = CacheManager("realtime_dollar_index", ttl=REALTIME_PRICE_CACHE_TTL)

        if use_cache:
            cached = cache.get()
            if cached:
                return cached

        try:
            # 使用新浪财经的DINIW接口（ICE美元指数）
            url = "https://hq.sinajs.cn/list=DINIW"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://finance.sina.com.cn',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            # 每次都创建新的session，避免连接复用导致的缓存问题
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=3)
            session.close()  # 立即关闭session

            if response.status_code == 200:
                # 新浪返回:
                # var hq_str_DINIW="时间,最新价,买价,卖价,成交量,开盘价,最高价,最低价,昨收,名称,日期"
                text = response.text
                match = re.search(r'var hq_str_DINIW="([^"]*)"', text)
                if match and match.group(1):
                    values = match.group(1).split(',')
                    if len(values) >= 10:
                        def _field(index: int, default: float = 0.0) -> float:
                            try:
                                return float(values[index])
                            except (ValueError, IndexError):
                                return default

                        latest = _field(1)
                        prev_close = _field(8)
                        if not latest:
                            return None

                        change_pct = (
                            round((latest - prev_close) / prev_close * 100, 2)
                            if prev_close
                            else 0.0
                        )

                        # 真实的 OHLC 就在响应里（[5]开 [6]高 [7]低）。
                        # 原实现只取了最新价与昨收，把这三个字段丢掉了，
                        # 于是定时任务只能用「昨收当开盘、max/min 当高低」
                        # 硬凑出一组 OHLC 写进数据库 —— 那是在编数据。
                        result = {
                            "price": round(latest, 2),
                            "previous_close": round(prev_close, 2),
                            "change": round(latest - prev_close, 2),
                            "change_percent": change_pct,
                            "open": round(_field(5, latest), 2),
                            "high": round(_field(6, latest), 2),
                            "low": round(_field(7, latest), 2),
                            "updated_at": timeutil.now_iso(),
                            "date": (
                                values[10]
                                if len(values) > 10 and values[10]
                                else timeutil.today_str()
                            ),
                            "source": "新浪财经-ICE美元指数(DXY)",
                        }
                        logger.info(f"[GoldService] 获取实时美元指数成功: {result}")
                        cache.set(result)
                        return result
        except requests.exceptions.Timeout:
            logger.error("[GoldService] 美元指数API超时")
        except Exception as e:
            logger.error(f"[GoldService] 获取实时美元指数失败: {e}")

        return None
    
    def get_daily_prices(self, start_date: datetime, end_date: datetime) -> List[GoldPrice]:
        return self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_date.date(),
            GoldPrice.date <= end_date.date()
        ).order_by(GoldPrice.date).all()
    
    def get_correlation_data(self) -> List[Dict]:
        """取金价与美元指数按日期对齐后的序列。

        原先带一个 `limit` 参数却从不使用 —— 调用方以为限制了条数，实际拿到全部。
        裁剪统一放在 router 里：只有那里能看到补完实时点之后的最终序列。
        """
        # 取全量后按日期对齐；时间窗裁剪统一由 router 的 days 参数负责
        # （最长 10 年）。这里原先写死「2025-01-01 之后」—— 与统计窗口同类的
        # 硬编码日历，会让更早的历史数据在「最近 N 天」的请求里被悄悄截断。
        gold_prices = self.db.query(GoldPrice).order_by(GoldPrice.date.asc()).all()
        dollar_prices = self.db.query(DollarIndex).order_by(DollarIndex.date.asc()).all()
        
        gold_dict = {p.date.strftime("%Y-%m-%d"): p.close_price for p in gold_prices}
        dollar_dict = {p.date.strftime("%Y-%m-%d"): p.close_price for p in dollar_prices}
        
        # 按时间正序排列
        result = []
        for date_str in sorted(gold_dict.keys()):
            if date_str in dollar_dict:
                result.append({
                    "date": date_str,
                    "gold_price": gold_dict[date_str],
                    "dollar_index": dollar_dict[date_str]
                })
        
        return result
    
    def get_latest_price(self) -> Optional[GoldPrice]:
        """获取数据库里最新一条金价。"""
        return self.db.query(GoldPrice).order_by(
            GoldPrice.date.desc()
        ).first()
    
    def get_realtime_price_info(self) -> Optional[Dict]:
        """获取当前金价：多源实时价优先，全部失败则退回数据库最新记录。

        实时部分交给 app/services/realtime_price.py —— 全项目唯一入口，
        内部按 腾讯 → 新浪 → 东方财富 依次尝试。
        原先只试腾讯，腾讯一挂就只能用数据库里的旧数据。
        """
        from app.services.realtime_price import get_realtime_gold_price

        realtime = get_realtime_gold_price()
        if realtime:
            return realtime

        # 实时源全部不可用时，退回数据库里的最新一条
        latest = self.get_latest_price()
        if not latest:
            return None

        prev = self.db.query(GoldPrice).filter(
            GoldPrice.date < latest.date
        ).order_by(GoldPrice.date.desc()).first()

        prev_close = prev.close_price if prev else latest.close_price
        daily_change = ((latest.close_price - prev_close) / prev_close * 100) if prev_close else 0

        return {
            "price": latest.close_price,
            "previous_close": prev_close,
            "change": round(latest.close_price - prev_close, 2),
            "change_percent": round(daily_change, 2),
            "updated_at": timeutil.now_iso(),
            "date": latest.date.strftime("%Y-%m-%d"),
            # source 用稳定的短 id，source_name 给人看。
            # 上层据此判断这个价格到底是不是实时的。
            "source": "database",
            "source_name": "数据库历史数据",
        }
    
    def get_statistics(self) -> Optional[Dict]:
        """获取**滚动窗口**统计数据（窗口口径的唯一实现在 `price_window`）。

        原实现把窗口起点写死在 ``date(2025, 1, 1)``，并把 2633.0 当作
        「没有 2025 年数据时」的兜底起始价 —— 进入 2026 年后，所谓「年涨幅」
        实际是最近 21 个月的涨幅，而兜底价会被当成真实行情展示给用户。
        现在：

        - 窗口 = 数据里最新价往前推 12 个月，跨年不失效；
          不足 12 个月时 label 如实说明实际长度；
        - 「高低振幅」= (期间最高 − 期间最低) / 最低，**不是波动率**；
        - 库里没有任何历史价时返回 None（不造数）。
        """
        # 获取实时金价（带缓存）
        realtime_info = self.get_realtime_price_info()
        if not realtime_info:
            return None

        window = compute_price_window(self.db)
        if window is None:
            logger.warning("[GoldService] 数据库里没有任何金价，统计不可用")
            return None

        current_price = realtime_info["price"]
        start_price = window.start_price
        window_return = (
            (current_price - start_price) / start_price * 100 if start_price else 0.0
        )

        # 实时价可能高于/低于窗口内的极值；严格越界时才把日期记到今天，
        # 相等时保留真实的历史极值日期（避免把旧高点标成「今天」）。
        max_price = max(window.high, current_price)
        min_price = min(window.low, current_price)
        max_date = (
            timeutil.today_str()
            if max_price > window.high
            else window.high_date.strftime("%Y-%m-%d")
        )
        min_date = (
            timeutil.today_str()
            if min_price < window.low
            else window.low_date.strftime("%Y-%m-%d")
        )

        # 计算市场状态
        previous_close = realtime_info["previous_close"]
        market_status = self._calculate_market_status(
            current_price, previous_close, window_return, max_price, min_price
        )

        return {
            "current_price": round(current_price, 2),
            "start_price": round(start_price, 2),
            "window_label": window.label,
            "window_start": window.window_start.isoformat(),
            "window_end": window.window_end.isoformat(),
            "window_return": round(window_return, 2),
            "max_price": round(max_price, 2),
            "min_price": round(min_price, 2),
            "max_date": max_date,
            "min_date": min_date,
            # 「振幅」= 期间最高与最低之差占最低的百分比。
            # 不是收益率标准差（波动率），也不是年化值。
            "amplitude": round(
                ((max_price - min_price) / min_price * 100) if min_price else 0.0, 1
            ),
            "market_status": market_status["status"],
            "market_status_desc": market_status["description"],
            "updated_at": realtime_info["updated_at"],
            # 数据来源与新鲜度：前端据此决定显示「实时」还是「历史数据」。
            "data_source": realtime_info.get("source_name")
            or realtime_info.get("source", "未知"),
            "is_realtime": realtime_info.get("source") != "database",
        }
    
    def _calculate_market_status(
        self, 
        current_price: float, 
        previous_close: float,
        window_return: float,
        max_price: float,
        min_price: float
    ) -> Dict[str, str]:
        """计算市场状态（阈值口径 = 滚动窗口涨跌幅，不再叫「年涨幅」）。"""
        daily_change = ((current_price - previous_close) / previous_close * 100) if previous_close else 0
        distance_from_high = ((max_price - current_price) / max_price * 100) if max_price else 0
        
        if daily_change > 1 and window_return > 20:
            return {"status": "强势上涨", "description": "牛市延续"}
        elif daily_change > 0 and window_return > 10:
            return {"status": "上涨", "description": "趋势向好"}
        elif -1 <= daily_change <= 1:
            if distance_from_high < 3:
                return {"status": "高位震荡", "description": "整理蓄势"}
            else:
                return {"status": "震荡", "description": "方向不明"}
        elif daily_change < 0 and distance_from_high < 5:
            return {"status": "回调", "description": "正常调整"}
        elif daily_change < -1 or window_return < 0:
            return {"status": "下跌", "description": "短期承压"}
        else:
            return {"status": "震荡", "description": "观望为主"}
    
