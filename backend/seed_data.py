"""数据库种子数据初始化脚本

自动获取2025年至今的黄金和美元指数历史数据，支持多数据源备选：
1. 新浪财经（国内，优先）
2. 东方财富（国内，备选）
3. Yahoo Finance（国外，最后尝试）

使用方式:
    cd backend
    python seed_data.py
"""

import os
import sys
import re
import requests
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.database import mysql_connection_params  # noqa: E402

# 数据库配置：以 DATABASE_URL 为唯一真源（与后端应用一致）。
# 曾经这里读 DB_*、应用读 DATABASE_URL，两处不一致时会把数据灌到另一个库上，
# 且没有任何报错 —— 表现只是「接口里没数据」。
DB_PARAMS = mysql_connection_params(include_database=True)
DB_NAME = DB_PARAMS["database"]

# 数据获取配置
START_DATE = date(2025, 1, 1)
END_DATE = date.today()


class DataSourceError(Exception):
    """数据源错误"""
    pass


class DatabaseError(Exception):
    """数据库错误"""
    pass


def get_db_connection():
    """获取数据库连接"""
    try:
        return pymysql.connect(**DB_PARAMS)
    except Exception as e:
        raise DatabaseError(f"数据库连接失败: {e}")


def safe_float(val, default=0.0) -> float:
    """安全转换为浮点数"""
    try:
        if val is None or val == '' or val == '0.0':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


# =============================================================================
# 黄金数据源
# =============================================================================

def fetch_gold_from_sina() -> Optional[List[Dict]]:
    """
    从新浪财经获取黄金历史数据
    
    API: http://stock2.finance.sina.com.cn/futures/api/jsonp.php/var_GC/
         CffexFuturesService.getCffexFuturesDailyKLine?symbol=GC
    """
    try:
        print("  尝试从新浪财经获取黄金数据...")
        
        # 新浪外盘期货历史数据接口。两个关键点：
        #   1. 服务名必须写在**路径**里。原实现只传 ?var=GC&symbol=GC，
        #      服务端直接回 "Invalid service name"，这个数据源从未成功过。
        #   2. 返回形如 `var _GC=([{...}]);` —— 数组外面还套了一层括号。
        url = (
            "https://stock.finance.sina.com.cn/futures/api/jsonp.php/"
            "var%20_GC=/GlobalFuturesService.getGlobalFuturesDailyKLine"
        )
        params = {'symbol': 'GC'}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise DataSourceError(f"HTTP {response.status_code}")
        
        # 解析JSONP响应
        text_data = response.text
        match = re.search(r'var\s+_GC=\((\[.*?\])\);', text_data, re.DOTALL)

        if not match:
            raise DataSourceError("无法解析响应数据")

        data = json.loads(match.group(1))

        result = []
        for item in data:
            # 实际格式是对象数组：{"date","open","high","low","close","volume",...}
            # 原实现按数组下标 item[0]/item[1] 取值，与真实格式完全不符。
            item_date = datetime.strptime(item['date'], '%Y-%m-%d').date()

            # 只保留2025年至今的数据
            if item_date < START_DATE:
                continue

            result.append({
                'date': item_date,
                'open_price': safe_float(item.get('open')),
                'high_price': safe_float(item.get('high')),
                'low_price': safe_float(item.get('low')),
                'close_price': safe_float(item.get('close')),
                'volume': int(safe_float(item.get('volume'), 0)),
            })
        
        if result:
            print(f"  ✅ 新浪财经: 获取到 {len(result)} 条黄金数据")
            return sorted(result, key=lambda x: x['date'])
        else:
            raise DataSourceError("没有获取到数据")
            
    except Exception as e:
        print(f"  ❌ 新浪财经失败: {e}")
        return None


def fetch_gold_from_eastmoney() -> Optional[List[Dict]]:
    """
    从东方财富获取黄金历史数据
    
    API: http://push2his.eastmoney.com/api/qt/stock/kline/get
    """
    try:
        print("  尝试从东方财富获取黄金数据...")
        
        # 东方财富黄金期货代码: 黄金主连 (AU0)
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            # 113.AU0 是无效代码（服务端返回 data=null）；
            # 101.GC00Y 才是 COMEX 黄金主连。
            'secid': '101.GC00Y',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57',
            'klt': '101',  # 日K线
            'fqt': '0',
            'beg': START_DATE.strftime('%Y%m%d'),
            'end': END_DATE.strftime('%Y%m%d'),
            'smplmt': '1000'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise DataSourceError(f"HTTP {response.status_code}")
        
        data = response.json()
        
        if data.get('data') is None or data['data'].get('klines') is None:
            raise DataSourceError("响应中没有数据")
        
        klines = data['data']['klines']
        result = []
        
        for line in klines:
            # 数据格式: 日期,开盘价,收盘价,最低价,最高价,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
            parts = line.split(',')
            if len(parts) >= 6:
                item_date = datetime.strptime(parts[0], '%Y-%m-%d').date()
                # 本地也过滤一次：不能只依赖接口的 beg 参数，
                # 新浪那条路是本地过滤的，两边行为必须一致。
                if item_date < START_DATE:
                    continue
                result.append({
                    'date': item_date,
                    'open_price': safe_float(parts[1]),
                    'close_price': safe_float(parts[2]),
                    # 东财 klines 的字段顺序是 date,open,close,HIGH,LOW,volume,amount。
                    # 原实现把 [3] 当最低价、[4] 当最高价，两者正好写反，
                    # 导致最高价低于最低价，期间高低点与波动区间全部失真。
                    'high_price': safe_float(parts[3]),
                    'low_price': safe_float(parts[4]),
                    'volume': int(safe_float(parts[5], 0)),
                })
        
        if result:
            print(f"  ✅ 东方财富: 获取到 {len(result)} 条黄金数据")
            return sorted(result, key=lambda x: x['date'])
        else:
            raise DataSourceError("没有获取到数据")
            
    except Exception as e:
        print(f"  ❌ 东方财富失败: {e}")
        return None


def fetch_gold_from_yahoo() -> Optional[List[Dict]]:
    """
    从Yahoo Finance获取黄金历史数据
    
    代码: GC=F (COMEX黄金期货)
    """
    try:
        print("  尝试从Yahoo Finance获取黄金数据...")
        
        try:
            import yfinance as yf
        except ImportError:
            print("  ⚠️ 未安装yfinance，尝试安装...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
            import yfinance as yf
        
        # 下载黄金期货数据
        ticker = yf.Ticker("GC=F")
        df = ticker.history(start=START_DATE, end=END_DATE)
        
        if df.empty:
            raise DataSourceError("没有获取到数据")
        
        result = []
        for index, row in df.iterrows():
            result.append({
                'date': index.date(),
                'open_price': round(float(row['Open']), 2),
                'high_price': round(float(row['High']), 2),
                'low_price': round(float(row['Low']), 2),
                'close_price': round(float(row['Close']), 2),
                'volume': int(row['Volume']) if not pd.isna(row['Volume']) else 0
            })
        
        if result:
            print(f"  ✅ Yahoo Finance: 获取到 {len(result)} 条黄金数据")
            return sorted(result, key=lambda x: x['date'])
        else:
            raise DataSourceError("没有获取到数据")
            
    except Exception as e:
        print(f"  ❌ Yahoo Finance失败: {e}")
        return None


def fetch_gold_history() -> List[Dict]:
    """
    获取黄金历史数据（多数据源备选）
    
    优先级: 新浪财经 -> 东方财富 -> Yahoo Finance
    """
    print("\n📊 获取黄金历史数据...")
    
    # 尝试各个数据源
    data = fetch_gold_from_sina()
    if data:
        return data
    
    data = fetch_gold_from_eastmoney()
    if data:
        return data
    
    data = fetch_gold_from_yahoo()
    if data:
        return data
    
    raise DataSourceError("所有黄金数据源均不可用")


# =============================================================================
# 美元指数数据源
# =============================================================================

def fetch_dollar_from_eastmoney() -> Optional[List[Dict]]:
    """
    从东方财富获取美元指数历史数据
    """
    try:
        print("  尝试从东方财富获取美元指数数据...")
        
        # 东方财富美元指数代码
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            # 100.DINIW 返回 data=null；100.UDI 才是美元指数。
            'secid': '100.UDI',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57',
            'klt': '101',
            'fqt': '0',
            'beg': START_DATE.strftime('%Y%m%d'),
            'end': END_DATE.strftime('%Y%m%d'),
            'smplmt': '1000'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise DataSourceError(f"HTTP {response.status_code}")
        
        data = response.json()
        
        if data.get('data') is None or data['data'].get('klines') is None:
            raise DataSourceError("响应中没有数据")
        
        klines = data['data']['klines']
        result = []
        
        for line in klines:
            parts = line.split(',')
            if len(parts) >= 6:
                item_date = datetime.strptime(parts[0], '%Y-%m-%d').date()
                # 本地也过滤一次：不能只依赖接口的 beg 参数，
                # 新浪那条路是本地过滤的，两边行为必须一致。
                if item_date < START_DATE:
                    continue
                result.append({
                    'date': item_date,
                    'open_price': safe_float(parts[1]),
                    'close_price': safe_float(parts[2]),
                    # 同上：东财的顺序是 high 在前、low 在后
                    'high_price': safe_float(parts[3]),
                    'low_price': safe_float(parts[4]),
                })
        
        if result:
            print(f"  ✅ 东方财富: 获取到 {len(result)} 条美元指数数据")
            return sorted(result, key=lambda x: x['date'])
        else:
            raise DataSourceError("没有获取到数据")
            
    except Exception as e:
        print(f"  ❌ 东方财富失败: {e}")
        return None


def fetch_dollar_from_yahoo() -> Optional[List[Dict]]:
    """
    从Yahoo Finance获取美元指数历史数据
    
    代码: DX-Y.NYB (美元指数)
    """
    try:
        print("  尝试从Yahoo Finance获取美元指数数据...")
        
        try:
            import yfinance as yf
        except ImportError:
            print("  ⚠️ 未安装yfinance，尝试安装...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
            import yfinance as yf
        
        # 下载美元指数数据
        ticker = yf.Ticker("DX-Y.NYB")
        df = ticker.history(start=START_DATE, end=END_DATE)
        
        if df.empty:
            raise DataSourceError("没有获取到数据")
        
        result = []
        for index, row in df.iterrows():
            result.append({
                'date': index.date(),
                'open_price': round(float(row['Open']), 4),
                'high_price': round(float(row['High']), 4),
                'low_price': round(float(row['Low']), 4),
                'close_price': round(float(row['Close']), 4)
            })
        
        if result:
            print(f"  ✅ Yahoo Finance: 获取到 {len(result)} 条美元指数数据")
            return sorted(result, key=lambda x: x['date'])
        else:
            raise DataSourceError("没有获取到数据")
            
    except Exception as e:
        print(f"  ❌ Yahoo Finance失败: {e}")
        return None


def fetch_dollar_index_history() -> List[Dict]:
    """
    获取美元指数历史数据（多数据源备选）

    优先级: 东方财富 -> Yahoo Finance

    新浪那条路已移除：GlobalFuturesService 对 DINIW 返回 `var _DINIW=(null)`，
    拿不到任何历史数据。东方财富本身就是国内源，优先级上移到第一位。
    """
    print("\n📊 获取美元指数历史数据...")

    # 尝试各个数据源
    data = fetch_dollar_from_eastmoney()
    if data:
        return data
    
    data = fetch_dollar_from_yahoo()
    if data:
        return data
    
    raise DataSourceError("所有美元指数数据源均不可用")


# =============================================================================
# 数据库操作
# =============================================================================

def save_gold_prices(conn, data: List[Dict]) -> int:
    """保存黄金价格数据到数据库"""
    cursor = conn.cursor()
    inserted = 0
    skipped = 0
    
    for item in data:
        try:
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM gold_prices WHERE date = %s",
                (item['date'],)
            )
            if cursor.fetchone():
                skipped += 1
                continue
            
            # 计算涨跌幅
            change_pct = 0.0
            if item['open_price'] > 0:
                change_pct = round((item['close_price'] - item['open_price']) / item['open_price'] * 100, 2)
            
            # 插入数据
            cursor.execute("""
                INSERT INTO gold_prices 
                (date, open_price, high_price, low_price, close_price, volume, change_percent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                item['date'],
                item['open_price'],
                item['high_price'],
                item['low_price'],
                item['close_price'],
                item.get('volume', 0),
                change_pct
            ))
            inserted += 1
            
        except Exception as e:
            print(f"  警告: 插入数据失败 {item['date']}: {e}")
    
    conn.commit()
    cursor.close()
    
    print(f"  黄金数据: 新增 {inserted} 条, 跳过 {skipped} 条(已存在)")
    return inserted


def save_dollar_index(conn, data: List[Dict]) -> int:
    """保存美元指数数据到数据库"""
    cursor = conn.cursor()
    inserted = 0
    skipped = 0
    
    for item in data:
        try:
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM dollar_index WHERE date = %s",
                (item['date'],)
            )
            if cursor.fetchone():
                skipped += 1
                continue
            
            # 插入数据
            cursor.execute("""
                INSERT INTO dollar_index 
                (date, open_price, high_price, low_price, close_price)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                item['date'],
                item['open_price'],
                item['high_price'],
                item['low_price'],
                item['close_price']
            ))
            inserted += 1
            
        except Exception as e:
            print(f"  警告: 插入数据失败 {item['date']}: {e}")
    
    conn.commit()
    cursor.close()
    
    print(f"  美元指数数据: 新增 {inserted} 条, 跳过 {skipped} 条(已存在)")
    return inserted


# =============================================================================
# 主程序
# =============================================================================

def main():
    """主函数"""
    print("=" * 60)
    print("🚀 数据库种子数据初始化")
    print("=" * 60)
    print(f"数据范围: {START_DATE} 至 {END_DATE}")
    print(f"数据库: {DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_NAME}")
    print("-" * 60)
    
    try:
        # 1. 连接数据库
        print("\n📡 连接数据库...")
        conn = get_db_connection()
        print("✅ 数据库连接成功")
        
        # 2. 获取黄金数据
        gold_data = fetch_gold_history()
        
        # 3. 获取美元指数数据
        dollar_data = fetch_dollar_index_history()
        
        # 4. 保存到数据库
        print("\n💾 保存数据到数据库...")
        gold_inserted = save_gold_prices(conn, gold_data)
        dollar_inserted = save_dollar_index(conn, dollar_data)
        
        # 5. 关闭连接
        conn.close()
        
        # 6. 显示结果
        print("\n" + "=" * 60)
        print("✅ 数据初始化完成!")
        print("=" * 60)
        print(f"黄金数据: {gold_inserted} 条")
        print(f"美元指数数据: {dollar_inserted} 条")
        print(f"数据日期范围: {START_DATE} 至 {END_DATE}")
        print("-" * 60)
        print("\n现在您可以启动后端服务了:")
        print("  python -m uvicorn app.main:app --reload")
        
        return True
        
    except DatabaseError as e:
        print(f"\n❌ 数据库错误: {e}")
        print("\n请检查:")
        print("  1. MySQL服务是否已启动")
        print("  2. 数据库配置是否正确")
        print("  3. 数据库 'gold_analysis' 是否存在")
        print("\n您可以通过以下命令创建数据库:")
        print("  python init_db.py")
        return False
        
    except DataSourceError as e:
        print(f"\n❌ 数据源错误: {e}")
        print("\n所有数据源均不可用，请检查:")
        print("  1. 网络连接是否正常")
        print("  2. 是否配置了代理（如需访问Yahoo Finance）")
        print("\n您可以尝试:")
        print("  1. 检查网络连接后重试")
        print("  2. 配置代理环境变量: HTTP_PROXY, HTTPS_PROXY")
        return False
        
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
