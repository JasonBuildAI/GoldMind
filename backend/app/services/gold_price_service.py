"""伦敦金实时价格服务 - 国内可用数据源

支持多个国内可用的实时黄金数据源：
1. 新浪财经 - 伦敦金/纽约金实时数据（推荐，最稳定）
2. 东方财富 - 黄金期货数据
3. 腾讯财经 - 国际金价
"""
import re
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path

# 缓存目录
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


class GoldPriceService:
    """伦敦金实时价格服务"""
    
    def __init__(self):
        self.cache_file = CACHE_DIR / "london_gold_realtime.json"
        self.cache_ttl = 30  # 缓存30秒
    
    def _get_cached_price(self) -> Optional[Dict]:
        """从缓存获取价格"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    timestamp = cached.get('_timestamp', 0)
                    if datetime.now().timestamp() - timestamp < self.cache_ttl:
                        return cached.get('data')
        except Exception as e:
            print(f"[GoldPriceService] 读取缓存失败: {e}")
        return None
    
    def _set_cached_price(self, data: Dict) -> None:
        """设置价格缓存"""
        try:
            cache_data = {
                'data': data,
                '_timestamp': datetime.now().timestamp(),
                '_created_at': datetime.now().isoformat()
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GoldPriceService] 写入缓存失败: {e}")
    
    def get_london_gold_from_sina(self) -> Optional[Dict]:
        """
        从新浪财经获取伦敦金实时价格
        
        API: https://hq.sinajs.cn/list=hf_GC
        返回: 伦敦金现货价格（美元/盎司）
        
        数据格式:
        var hq_str_hf_GC="伦敦金,2880.50,0.0,0.0,2885.20,2875.80,0.0,0.0,0.0,0.0,0.0,2026-02-01 14:30:00";
        """
        # 先检查缓存
        cached = self._get_cached_price()
        if cached and cached.get('source') == 'sina':
            return cached
        
        try:
            # 新浪财经API - 国内访问稳定
            url = "https://hq.sinajs.cn/list=hf_GC"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://finance.sina.com.cn'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'gb2312'  # 新浪返回的是GB2312编码
            
            if response.status_code == 200:
                # 解析数据
                match = re.search(r'var hq_str_hf_GC="([^"]*)"', response.text)
                if match and match.group(1):
                    data = match.group(1).split(',')
                    # 新浪财经数据格式:
                    # [0]最新价, [1]涨跌额(空), [2]买价, [3]卖价, [4]最高价, [5]最低价, 
                    # [6]时间, [7]昨收, [8]开盘价, [9-11]其他, [12]日期, [13]名称
                    if len(data) >= 13:
                        # 安全转换函数
                        def safe_float(val, default=0.0):
                            try:
                                return float(val) if val and val.strip() else default
                            except (ValueError, TypeError):
                                return default
                        
                        latest_price = safe_float(data[0])  # 最新价
                        prev_close = safe_float(data[7])    # 昨收
                        high = safe_float(data[4])          # 最高价
                        low = safe_float(data[5])          # 最低价
                        open_price = safe_float(data[8])    # 开盘价
                        
                        # 计算涨跌
                        change = latest_price - prev_close if latest_price and prev_close else 0
                        change_pct = (change / prev_close * 100) if prev_close else 0
                        
                        # 更新时间
                        date_str = data[12] if data[12] else datetime.now().strftime('%Y-%m-%d')
                        time_str = data[6] if data[6] else datetime.now().strftime('%H:%M:%S')
                        update_time = f"{date_str} {time_str}"
                        
                        result = {
                            "price": latest_price,
                            "previous_close": prev_close,
                            "change": change,
                            "change_percent": change_pct,
                            "open": open_price,
                            "high": high,
                            "low": low,
                            "updated_at": datetime.now().isoformat(),
                            "update_time": update_time,
                            "source": "sina",
                            "source_name": "新浪财经-伦敦金",
                            "symbol": "XAU/USD",
                            "unit": "美元/盎司"
                        }
                        
                        # 缓存结果
                        self._set_cached_price(result)
                        print(f"[GoldPriceService] 成功获取伦敦金价格: ${latest_price} (新浪财经)")
                        return result
                        
        except requests.exceptions.Timeout:
            print("[GoldPriceService] 新浪财经API超时")
        except Exception as e:
            print(f"[GoldPriceService] 获取新浪财经金价失败: {e}")
        
        return None
    
    def get_london_gold_from_eastmoney(self) -> Optional[Dict]:
        """
        从东方财富获取伦敦金实时价格
        
        API: https://push2.eastmoney.com/api/qt/stock/get?secid=103.XAUUSD
        """
        try:
            url = "https://push2.eastmoney.com/api/qt/stock/get"
            params = {
                'secid': '103.XAUUSD',
                'fields': 'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f107',
                '_': int(datetime.now().timestamp() * 1000)
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    d = data['data']
                    latest = d.get('f43', 0) / 100  # 最新价
                    prev_close = d.get('f60', 0) / 100  # 昨收
                    open_price = d.get('f46', 0) / 100  # 开盘价
                    high = d.get('f44', 0) / 100  # 最高价
                    low = d.get('f45', 0) / 100  # 最低价
                    
                    change_pct = ((latest - prev_close) / prev_close * 100) if prev_close else 0
                    
                    result = {
                        "price": latest,
                        "previous_close": prev_close,
                        "change": latest - prev_close,
                        "change_percent": round(change_pct, 2),
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "updated_at": datetime.now().isoformat(),
                        "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "source": "eastmoney",
                        "source_name": "东方财富-伦敦金",
                        "symbol": "XAU/USD",
                        "unit": "美元/盎司"
                    }
                    
                    print(f"[GoldPriceService] 成功获取伦敦金价格: ${latest} (东方财富)")
                    return result
                    
        except Exception as e:
            print(f"[GoldPriceService] 获取东方财富金价失败: {e}")
        
        return None
    
    def get_realtime_price(self) -> Optional[Dict]:
        """
        获取伦敦金实时价格（带多源备份）
        
        优先级:
        1. 缓存数据（30秒内）
        2. 新浪财经
        3. 东方财富
        4. 返回None
        """
        # 1. 检查缓存
        cached = self._get_cached_price()
        if cached:
            return cached
        
        # 2. 尝试新浪财经（最稳定）
        result = self.get_london_gold_from_sina()
        if result:
            return result
        
        # 3. 尝试东方财富
        result = self.get_london_gold_from_eastmoney()
        if result:
            return result
        
        print("[GoldPriceService] 所有数据源均失败")
        return None


# 全局实例
gold_price_service = GoldPriceService()


def get_london_gold_price() -> Optional[Dict]:
    """便捷函数：获取伦敦金实时价格"""
    return gold_price_service.get_realtime_price()


if __name__ == "__main__":
    # 测试
    print("测试获取伦敦金实时价格...")
    price = get_london_gold_price()
    if price:
        print(f"\n当前伦敦金价格: ${price['price']}")
        print(f"涨跌: {price['change']:+.2f} ({price['change_percent']:+.2f}%)")
        print(f"最高: ${price['high']}, 最低: ${price['low']}")
        print(f"数据来源: {price['source_name']}")
        print(f"更新时间: {price['update_time']}")
    else:
        print("获取价格失败")
