"""黄金价格服务 - 优化版（添加缓存和异步处理）"""
import re
import requests
import threading
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from sqlalchemy.orm import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.models.gold_price import GoldPrice, DollarIndex

# 缓存目录
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# 内存缓存（进程内）
_price_cache = {}
_cache_lock = threading.Lock()
_cache_ttl = 300  # 5分钟缓存

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
    
    def _get_cached_price(self) -> Optional[Dict]:
        """从缓存获取价格（先查内存，再查文件）"""
        # 1. 检查内存缓存
        with _cache_lock:
            if 'realtime_price' in _price_cache:
                cached_data, timestamp = _price_cache['realtime_price']
                if datetime.now().timestamp() - timestamp < _cache_ttl:
                    return cached_data
        
        # 2. 检查文件缓存
        try:
            cache_file = CACHE_DIR / "realtime_price.json"
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    timestamp = cached.get('_timestamp', 0)
                    if datetime.now().timestamp() - timestamp < _cache_ttl:
                        data = cached.get('data')
                        # 更新内存缓存
                        with _cache_lock:
                            _price_cache['realtime_price'] = (data, timestamp)
                        return data
        except Exception as e:
            print(f"[GoldService] 读取文件缓存失败: {e}")
        
        return None
    
    def _set_cached_price(self, data: Dict) -> None:
        """设置价格缓存（同时更新内存和文件）"""
        timestamp = datetime.now().timestamp()
        
        # 1. 更新内存缓存
        with _cache_lock:
            _price_cache['realtime_price'] = (data, timestamp)
        
        # 2. 更新文件缓存
        try:
            cache_file = CACHE_DIR / "realtime_price.json"
            cache_data = {
                'data': data,
                '_timestamp': timestamp,
                '_created_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GoldService] 写入文件缓存失败: {e}")
    
    def get_realtime_price_from_tencent(self) -> Optional[Dict]:
        """从腾讯财经获取实时金价 - 实时获取，不缓存（带重试机制）"""
        # 实时获取最新价格，不使用缓存
        try:
            url = "https://qt.gtimg.cn/q=hf_GC"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            # 使用带重试的session，设置较短的超时时间
            session = get_http_session()
            response = session.get(url, headers=headers, timeout=3)
            
            if response.status_code == 200:
                # 解析数据
                match = re.search(r'v_hf_GC="([^"]+)"', response.text)
                if match:
                    data = match.group(1).split(',')
                    latest = float(data[0])
                    prev_close = float(data[7])
                    change_pct = (latest - prev_close) / prev_close * 100
                    
                    result = {
                        "price": latest,
                        "previous_close": prev_close,
                        "change_percent": round(change_pct, 2),
                        "open": float(data[2]),
                        "high": float(data[3]),
                        "low": float(data[4]),
                        "updated_at": datetime.now().isoformat(),
                        "date": data[12],
                        "source": "腾讯财经-纽约黄金"
                    }
                    # 不缓存，直接返回实时数据
                    return result
        except requests.exceptions.Timeout:
            print("[GoldService] 腾讯财经API超时，使用数据库数据")
        except Exception as e:
            print(f"[GoldService] 获取腾讯财经金价失败: {e}")
        
        return None
    
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
                # 解析新浪返回的数据格式: var hq_str_DINIW="时间,最新价,..."
                text = response.text
                match = re.search(r'var hq_str_DINIW="([^"]*)"', text)
                if match and match.group(1):
                    values = match.group(1).split(',')
                    if len(values) >= 10:
                        # 解析字段
                        # 0:时间, 1:最新价, 2:买价, 3:卖价, 4:成交量, 5:开盘价, 6:最高价, 7:最低价, 8:昨收, 9:名称
                        latest = float(values[1])  # 最新价
                        prev_close = float(values[8])  # 昨收
                        change_pct = round((latest - prev_close) / prev_close * 100, 2)  # 涨跌幅

                        result = {
                            "price": round(latest, 2),
                            "previous_close": round(prev_close, 2),
                            "change_percent": change_pct,
                            "updated_at": datetime.now().isoformat(),
                            "source": "新浪财经-ICE美元指数(DXY)"
                        }
                        print(f"[GoldService] 获取实时美元指数成功: {result}")
                        return result
        except requests.exceptions.Timeout:
            print("[GoldService] 美元指数API超时")
        except Exception as e:
            print(f"[GoldService] 获取实时美元指数失败: {e}")

        return None
    
    def get_daily_prices(self, start_date: datetime, end_date: datetime) -> List[GoldPrice]:
        return self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_date.date(),
            GoldPrice.date <= end_date.date()
        ).order_by(GoldPrice.date).all()
    
    def get_monthly_summary(self, months: int = 12) -> List[Dict]:
        # 获取2025年1月1日之后的数据
        start_date = date(2025, 1, 1)
        prices = self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_date
        ).order_by(GoldPrice.date.asc()).all()
        
        monthly_data = {}
        for price in prices:
            month_key = price.date.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "month": month_key,
                    "open": None,
                    "close": None,
                    "min": float('inf'),
                    "max": float('-inf')
                }
            
            # 第一个价格作为开盘价
            if monthly_data[month_key]["open"] is None:
                monthly_data[month_key]["open"] = price.close_price
            # 最后一个价格作为收盘价
            monthly_data[month_key]["close"] = price.close_price
            monthly_data[month_key]["min"] = min(
                monthly_data[month_key]["min"],
                price.low_price or price.close_price
            )
            monthly_data[month_key]["max"] = max(
                monthly_data[month_key]["max"],
                price.high_price or price.close_price
            )
        
        # 按时间正序排列
        result = []
        for month_key in sorted(monthly_data.keys()):
            data = monthly_data[month_key]
            change = ((data["close"] - data["open"]) / data["open"] * 100) if data["open"] else 0
            result.append({
                "month": month_key,
                "open": round(data["open"], 2),
                "close": round(data["close"], 2),
                "change": round(change, 2)
            })
        
        return result
    
    def get_correlation_data(self, limit: int = 100) -> List[Dict]:
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
        return self.db.query(GoldPrice).order_by(
            GoldPrice.date.desc()
        ).first()
    
    def get_realtime_price_info(self) -> Optional[Dict]:
        """获取当前金价信息（优先使用腾讯财经实时数据，带缓存）"""
        # 首先尝试获取腾讯财经实时数据（带缓存）
        tencent_data = self.get_realtime_price_from_tencent()
        if tencent_data:
            return tencent_data
        
        # 如果失败，使用数据库最新数据
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
            "change_percent": round(daily_change, 2),
            "updated_at": datetime.now().isoformat(),
            "date": latest.date.strftime("%Y-%m-%d"),
            "source": "数据库历史数据"
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
            "data_source": realtime_info.get("source", "未知")
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
    
    def fetch_and_save_prices(self):
        """从Yahoo Finance获取历史价格数据（备用方案）"""
        try:
            import yfinance as yf
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="1y")
            
            for index, row in hist.iterrows():
                date_obj = index.date()
                
                # 检查是否已存在
                existing = self.db.query(GoldPrice).filter(GoldPrice.date == date_obj).first()
                if existing:
                    continue
                
                price = GoldPrice(
                    date=date_obj,
                    open_price=round(row['Open'], 2),
                    high_price=round(row['High'], 2),
                    low_price=round(row['Low'], 2),
                    close_price=round(row['Close'], 2),
                    volume=int(row['Volume']) if not pd.isna(row['Volume']) else 0
                )
                self.db.add(price)
            
            self.db.commit()
            print(f"[GoldService] 成功保存历史价格数据")
        except Exception as e:
            print(f"[GoldService] 获取历史价格失败: {e}")
    
    def fetch_and_save_dollar_index(self):
        """获取美元指数（备用方案）"""
        try:
            import yfinance as yf
            ticker = yf.Ticker("DX-Y.NYB")
            hist = ticker.history(period="1y")
            
            for index, row in hist.iterrows():
                date_obj = index.date()
                
                existing = self.db.query(DollarIndex).filter(DollarIndex.date == date_obj).first()
                if existing:
                    continue
                
                dollar = DollarIndex(
                    date=date_obj,
                    open_price=round(row['Open'], 2),
                    high_price=round(row['High'], 2),
                    low_price=round(row['Low'], 2),
                    close_price=round(row['Close'], 2)
                )
                self.db.add(dollar)
            
            self.db.commit()
        except Exception as e:
            print(f"[GoldService] 获取美元指数失败: {e}")
    
    def save_realtime_price(self, realtime_data: Dict) -> None:
        """
        保存实时金价到数据库
        
        Args:
            realtime_data: 包含实时价格数据的字典
        """
        try:
            from datetime import datetime
            
            today = datetime.now().date()
            
            # 检查今天是否已有记录
            existing = self.db.query(GoldPrice).filter(GoldPrice.date == today).first()
            
            if existing:
                # 更新今天的记录
                existing.close_price = realtime_data['price']
                existing.high_price = max(existing.high_price or realtime_data['price'], realtime_data['high'])
                existing.low_price = min(existing.low_price or realtime_data['price'], realtime_data['low'])
                existing.updated_at = datetime.now()
            else:
                # 创建新记录
                price = GoldPrice(
                    date=today,
                    open_price=realtime_data['open'],
                    high_price=realtime_data['high'],
                    low_price=realtime_data['low'],
                    close_price=realtime_data['price'],
                    volume=0,  # 实时数据通常没有成交量
                    change_percent=realtime_data.get('change_percent', 0)
                )
                self.db.add(price)
            
            self.db.commit()
            print(f"[GoldService] 实时金价已保存: ${realtime_data['price']}")
            
        except Exception as e:
            self.db.rollback()
            print(f"[GoldService] 保存实时金价失败: {e}")
            raise
