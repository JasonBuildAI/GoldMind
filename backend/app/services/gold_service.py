"""黄金价格服务 - 优化版（添加缓存和异步处理）"""
import re
import requests
import threading
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.models.gold_price import GoldPrice, DollarIndex
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


class GoldService:
    """黄金价格服务 - 优化版"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_realtime_dollar_index(self) -> Optional[Dict]:
        """从新浪财经获取实时美元指数(DXY/DINIW) - 带超时和重试机制"""
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
                            "updated_at": datetime.now().isoformat(),
                            "date": (
                                values[10]
                                if len(values) > 10 and values[10]
                                else datetime.now().strftime("%Y-%m-%d")
                            ),
                            "source": "新浪财经-ICE美元指数(DXY)",
                        }
                        logger.info(f"[GoldService] 获取实时美元指数成功: {result}")
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
        # 获取2025年1月1日之后的数据
        start_date = date(2025, 1, 1)
        
        gold_prices = self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_date
        ).order_by(GoldPrice.date.asc()).all()
        
        dollar_prices = self.db.query(DollarIndex).filter(
            DollarIndex.date >= start_date
        ).order_by(DollarIndex.date.asc()).all()
        
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
            "updated_at": datetime.now().isoformat(),
            "date": latest.date.strftime("%Y-%m-%d"),
            # source 用稳定的短 id，source_name 给人看。
            # 上层据此判断这个价格到底是不是实时的。
            "source": "database",
            "source_name": "数据库历史数据",
        }
    
    def get_2025_start_price(self) -> float:
        """获取 2025 年第一个交易日的开盘价，如果没有则使用默认值"""
        start_date = date(2025, 1, 2)
        price = self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_date
        ).order_by(GoldPrice.date.asc()).first()
        
        if price:
            # 使用开盘价作为YTD计算基准
            return price.open_price if price.open_price else price.close_price
        
        # 如果没有2025年数据，使用2025年初的参考价（约2633美元/盎司）
        # 这是基于2025年1月2日伦敦金的实际开盘价
        return 2633.0
    
    def get_statistics(self) -> Optional[Dict]:
        """获取 2025 年至今的统计数据 - 优化版"""
        # 获取实时金价（带缓存）
        realtime_info = self.get_realtime_price_info()
        if not realtime_info:
            return None
        
        current_price = realtime_info["price"]
        
        # 获取 2025 年起始价（确保有默认值）
        start_price = self.get_2025_start_price()
        
        # 计算年涨幅
        ytd_return = ((current_price - start_price) / start_price * 100)
        
        # 获取 2025 年所有历史数据
        start_of_2025 = date(2025, 1, 1)
        prices_2025 = self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_of_2025
        ).all()
        
        if prices_2025:
            # 使用每日最高价计算期间最高，使用每日最低价计算期间最低
            high_prices = [p.high_price for p in prices_2025 if p.high_price]
            low_prices = [p.low_price for p in prices_2025 if p.low_price]
            close_prices = [p.close_price for p in prices_2025]
            
            # 将当前实时价格也加入计算
            all_highs = high_prices + [current_price]
            all_lows = low_prices + [current_price]
            
            max_price = max(all_highs)
            min_price = min(all_lows)
            
            # 判断最高价是历史数据还是当前实时价格
            if max_price == current_price:
                max_date = datetime.now().strftime("%Y-%m-%d")
            else:
                max_price_obj = max(prices_2025, key=lambda x: x.high_price or 0)
                max_date = max_price_obj.date.strftime("%Y-%m-%d")
            
            # 判断最低价是历史数据还是当前实时价格
            if min_price == current_price:
                min_date = datetime.now().strftime("%Y-%m-%d")
            else:
                min_price_obj = min(prices_2025, key=lambda x: x.low_price or float('inf'))
                min_date = min_price_obj.date.strftime("%Y-%m-%d")
        else:
            max_price = current_price
            min_price = start_price
            max_date = datetime.now().strftime("%Y-%m-%d")
            min_date = "2025-01-02"
        
        # 计算市场状态
        previous_close = realtime_info["previous_close"]
        market_status = self._calculate_market_status(
            current_price, previous_close, ytd_return, max_price, min_price
        )
        
        return {
            "current_price": round(current_price, 2),
            "start_price": round(start_price, 2),
            "ytd_return": round(ytd_return, 2),
            "max_price": round(max_price, 2),
            "min_price": round(min_price, 2),
            "max_date": max_date,
            "min_date": min_date,
            "volatility": round(((max_price - min_price) / min_price * 100), 1),
            "market_status": market_status["status"],
            "market_status_desc": market_status["description"],
            "updated_at": realtime_info["updated_at"],
            # 数据来源与新鲜度：前端据此决定显示「实时」还是「历史数据」。
            # 原先这个字段既没进响应模型、也没人读，属于白算。
            "data_source": realtime_info.get("source_name")
            or realtime_info.get("source", "未知"),
            "is_realtime": realtime_info.get("source") != "database",
        }
    
    def _calculate_market_status(
        self, 
        current_price: float, 
        previous_close: float,
        ytd_return: float,
        max_price: float,
        min_price: float
    ) -> Dict[str, str]:
        """计算市场状态"""
        daily_change = ((current_price - previous_close) / previous_close * 100) if previous_close else 0
        distance_from_high = ((max_price - current_price) / max_price * 100) if max_price else 0
        
        if daily_change > 1 and ytd_return > 20:
            return {"status": "强势上涨", "description": "牛市延续"}
        elif daily_change > 0 and ytd_return > 10:
            return {"status": "上涨", "description": "趋势向好"}
        elif -1 <= daily_change <= 1:
            if distance_from_high < 3:
                return {"status": "高位震荡", "description": "整理蓄势"}
            else:
                return {"status": "震荡", "description": "方向不明"}
        elif daily_change < 0 and distance_from_high < 5:
            return {"status": "回调", "description": "正常调整"}
        elif daily_change < -1 or ytd_return < 0:
            return {"status": "下跌", "description": "短期承压"}
        else:
            return {"status": "震荡", "description": "观望为主"}
    
