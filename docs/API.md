# GoldMind API 接口文档

<p align="center">
  <img src="https://img.shields.io/badge/API-RESTful-green?style=for-the-badge" alt="RESTful API">
  <img src="https://img.shields.io/badge/Version-v1.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Base_URL-/api-orange?style=for-the-badge" alt="Base URL">
</p>

---

## 目录

- [概述](#概述)
- [基础信息](#基础信息)
- [接口分类](#接口分类)
  - [黄金价格](#黄金价格)
  - [市场分析](#市场分析)
  - [新闻资讯](#新闻资讯)
  - [价格预测](#价格预测)
- [错误码](#错误码)
- [限流策略](#限流策略)

---

## 概述

GoldMind API 提供完整的黄金市场数据服务，包括实时价格、历史数据、AI智能分析、机构预测等功能。所有接口均遵循 RESTful 设计规范，返回 JSON 格式数据。

### 核心价值

| 特性 | 说明 |
|------|------|
| **实时数据** | 黄金价格10秒级更新，美元指数实时同步 |
| **AI分析** | 多智能体协同分析，RAG增强生成 |
| **机构观点** | 高盛、瑞银、摩根士丹利、花旗四大机构预测 |
| **智能缓存** | 多级缓存策略，毫秒级响应 |

---

## 基础信息

### 基础URL

```
开发环境: http://localhost:8000/api
生产环境: https://api.goldmind.ai/api
```

### 请求格式

- **Content-Type**: `application/json`
- **字符编码**: UTF-8
- **时间格式**: ISO 8601 (`2025-01-15T10:30:00Z`)
- **日期格式**: `YYYY-MM-DD`

### 通用响应格式

**成功响应:**
```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

**错误响应:**
```json
{
  "success": false,
  "error": "错误描述",
  "code": "ERROR_CODE"
}
```

---

## 接口分类

### 黄金价格

#### 1. 获取日线价格数据

获取黄金日线价格数据，支持自动合并实时价格。

```http
GET /gold/prices/daily
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `start_date` | string | 否 | 2025-01-01 | 开始日期 (YYYY-MM-DD) |
| `end_date` | string | 否 | 当前日期 | 结束日期 (YYYY-MM-DD) |
| `limit` | integer | 否 | 100 | 返回条数，最大500 |
| `include_realtime` | boolean | 否 | true | 是否包含实时价格作为最新数据 |

**响应示例:**

```json
[
  {
    "date": "2025-01-13",
    "price": 2685.50,
    "volume": 152340
  },
  {
    "date": "2025-01-14",
    "price": 2692.30,
    "volume": 148920
  },
  {
    "date": "2025-01-15",
    "price": 2710.80,
    "volume": 0
  }
]
```

**使用示例:**

```bash
# 获取最近30天数据
curl "http://localhost:8000/api/gold/prices/daily?limit=30"

# 获取指定日期范围
curl "http://localhost:8000/api/gold/prices/daily?start_date=2025-01-01&end_date=2025-01-15"
```

---

#### 2. 获取黄金与美元指数相关性数据

获取黄金与美元指数的历史相关性数据，用于分析负相关关系。

```http
GET /gold/prices/correlation
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | integer | 否 | 100 | 返回条数，最大500 |
| `include_realtime` | boolean | 否 | true | 是否包含实时数据 |

**响应示例:**

```json
[
  {
    "date": "2025-01-13",
    "gold_price": 2685.50,
    "dollar_index": 108.45
  },
  {
    "date": "2025-01-14",
    "gold_price": 2692.30,
    "dollar_index": 108.12
  },
  {
    "date": "2025-01-15",
    "gold_price": 2710.80,
    "dollar_index": 107.85
  }
]
```

**数据说明:**
- 黄金与美元指数通常呈负相关
- 美元指数下跌时，黄金价格往往上涨
- 数据可用于绘制双轴对比图表

---

#### 3. 获取实时美元指数

直接获取ICE美元指数实时数据。

```http
GET /gold/dollar-realtime
```

**响应示例:**

```json
{
  "price": 107.85,
  "change": -0.25,
  "change_percent": -0.23,
  "timestamp": "2025-01-15T10:30:00Z",
  "source": "Sina Finance"
}
```

**错误响应:**

```json
{
  "detail": "无法获取实时美元指数"
}
```

---

#### 4. 获取黄金统计数据

获取黄金市场的综合统计数据。

```http
GET /gold/stats
```

**响应示例:**

```json
{
  "current_price": 2710.80,
  "open_price": 2695.00,
  "high_price": 2725.50,
  "low_price": 2688.20,
  "prev_close": 2692.30,
  "change": 18.50,
  "change_percent": 0.69,
  "volume": 145230,
  "ytd_high": 2790.00,
  "ytd_low": 2650.20,
  "ytd_change": 5.23,
  "volatility_range": 5.12
}
```

**字段说明:**

| 字段 | 说明 |
|------|------|
| `current_price` | 当前价格 |
| `open_price` | 开盘价 |
| `high_price` | 最高价 |
| `low_price` | 最低价 |
| `change` | 涨跌额 |
| `change_percent` | 涨跌幅(%) |
| `ytd_high` | 年初至今最高价 |
| `ytd_low` | 年初至今最低价 |
| `ytd_change` | 年初至今涨幅(%) |
| `volatility_range` | 波动率(%) |

---

#### 5. 获取最新价格

获取黄金最新价格（简化版）。

```http
GET /gold/latest
```

**响应示例:**

```json
{
  "date": "2025-01-15",
  "price": 2710.80,
  "change": 0.69
}
```

---

### 市场分析

#### 6. 获取AI看涨因子分析

基于24小时内新闻资讯，使用AI智能分析看涨因子。

```http
GET /analysis/bullish-factors-ai
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `refresh` | boolean | 否 | false | 是否强制刷新（重新分析） |

**响应示例:**

```json
{
  "factors": [
    {
      "title": "美联储降息预期升温",
      "subtitle": "通胀数据回落，市场预期2025年降息3次",
      "description": "最新CPI数据显示通胀持续回落...",
      "impact": "high",
      "details": [
        "12月CPI同比增长2.9%，低于预期",
        "美联储官员释放鸽派信号",
        "美元指数创三个月新低"
      ]
    },
    {
      "title": "地缘政治风险加剧",
      "subtitle": "中东局势紧张，避险需求上升",
      "description": "地区冲突升级引发市场担忧...",
      "impact": "medium",
      "details": [
        "原油价格上涨带动通胀预期",
        "全球股市波动加剧",
        "资金流向避险资产"
      ]
    }
  ],
  "summary": "当前市场看涨情绪占主导，主要受美联储政策转向预期和地缘政治风险支撑",
  "last_updated": "2025-01-15T10:30:00Z",
  "next_update": "2025-01-15T11:30:00Z"
}
```

**缓存策略:**
- 内存缓存：10分钟
- 数据库缓存：1小时
- 强制刷新：`refresh=true`

---

#### 7. 刷新看涨因子分析

手动触发看涨因子重新分析。

```http
POST /analysis/bullish-factors-ai/refresh
```

**响应示例:**

```json
{
  "success": true,
  "message": "看涨因子分析已刷新",
  "data": { ... }
}
```

---

#### 8. 获取AI看空因子分析

基于24小时内新闻资讯，使用AI智能分析看空因子。

```http
GET /analysis/bearish-factors-ai
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `refresh` | boolean | 否 | false | 是否强制刷新 |

**响应示例:**

```json
{
  "factors": [
    {
      "title": "美元短期反弹",
      "subtitle": "技术面支撑强劲，美元指数企稳",
      "description": "美元指数在107附近获得强力支撑...",
      "impact": "medium",
      "details": [
        "技术支撑位107.00",
        "空头回补推动反弹",
        "短期反弹目标108.50"
      ]
    }
  ],
  "summary": "看空因素有限，主要关注美元短期反弹对黄金的压制",
  "last_updated": "2025-01-15T10:30:00Z"
}
```

---

#### 9. 获取机构预测分析

获取高盛、瑞银、摩根士丹利、花旗四大机构的最新预测。

```http
GET /analysis/institution-predictions-ai
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `refresh` | boolean | 否 | false | 是否强制刷新 |

**响应示例:**

```json
{
  "institutions": [
    {
      "name": "高盛 (Goldman Sachs)",
      "logo": "https://.../gs-logo.png",
      "rating": "买入",
      "target_price": 2900,
      "timeframe": "12个月",
      "reasoning": "基于美联储降息周期和央行购金需求...",
      "key_points": [
        "预计2025年降息75个基点",
        "央行购金需求持续强劲",
        "目标价2900美元/盎司"
      ]
    },
    {
      "name": "瑞银 (UBS)",
      "logo": "https://.../ubs-logo.png",
      "rating": "买入",
      "target_price": 2850,
      "timeframe": "12个月",
      "reasoning": "避险需求和实际利率下降支撑金价...",
      "key_points": [
        "实际利率下行利好黄金",
        "地缘政治风险溢价",
        "目标价2850美元/盎司"
      ]
    }
  ],
  "consensus": "看涨",
  "average_target": 2875,
  "last_updated": "2025-01-15T10:30:00Z"
}
```

**机构列表:**

| 机构 | 英文名称 | 权重 |
|------|---------|------|
| 高盛 | Goldman Sachs | 25% |
| 瑞银 | UBS | 25% |
| 摩根士丹利 | Morgan Stanley | 25% |
| 花旗 | Citi | 25% |

---

#### 10. 获取AI投资建议

基于多维度数据生成个性化投资策略建议。

```http
GET /analysis/investment-advice-ai
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `refresh` | boolean | 否 | false | 是否强制刷新 |

**响应示例:**

```json
{
  "market_overview": "当前金价2710美元，处于年内高位区间...",
  "strategies": [
    {
      "type": "conservative",
      "name": "保守型策略",
      "allocation": "20%仓位",
      "action": "逢低分批建仓",
      "rationale": "当前价格接近年内高点，建议等待回调至2650-2680区间再入场",
      "risk_level": "低",
      "expected_return": "5-8%年化"
    },
    {
      "type": "balanced",
      "name": "均衡型策略",
      "allocation": "50%仓位",
      "action": "部分建仓+定投",
      "rationale": "中期趋势向好，可分批建仓，回调加仓",
      "risk_level": "中",
      "expected_return": "10-15%年化"
    },
    {
      "type": "opportunistic",
      "name": "机会型策略",
      "allocation": "80%仓位",
      "action": "积极布局",
      "rationale": "突破2720可追涨，目标2800-2900",
      "risk_level": "高",
      "expected_return": "15-25%年化"
    }
  ],
  "risk_warning": "黄金价格波动较大，建议根据自身风险承受能力选择策略",
  "last_updated": "2025-01-15T10:30:00Z"
}
```

---

#### 11. 获取市场综合分析

基于DeepSeek LLM生成全面的市场总结和综合判断。

```http
GET /analysis/market-summary-ai
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `refresh` | boolean | 否 | false | 是否强制刷新 |

**响应示例:**

```json
{
  "core_logic": "当前黄金市场的核心逻辑是美联储政策转向预期...",
  "risk_factors": [
    "美元指数短期反弹风险",
    "通胀数据反复可能",
    "地缘政治局势变化"
  ],
  "institution_targets": {
    "highest": 2900,
    "lowest": 2700,
    "average": 2875,
    "consensus": "看涨"
  },
  "comprehensive_judgment": "综合判断：中期看涨，短期注意回调风险...",
  "confidence_level": "high",
  "key_levels": {
    "support": [2680, 2650, 2600],
    "resistance": [2720, 2750, 2800]
  },
  "last_updated": "2025-01-15T10:30:00Z"
}
```

---

### 新闻资讯

#### 12. 获取新闻列表

获取黄金市场相关新闻资讯。

```http
GET /news/news
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | integer | 否 | 20 | 返回条数，最大100 |
| `source` | string | 否 | - | 新闻来源筛选 |
| `sentiment` | string | 否 | - | 情感倾向筛选 (positive/neutral/negative) |

**响应示例:**

```json
[
  {
    "id": 1,
    "title": "黄金价格创三个月新高，分析师看好后市",
    "content": "受美联储降息预期影响，黄金价格周三上涨...",
    "source": "新浪财经",
    "url": "https://finance.sina.com.cn/...",
    "published_at": "2025-01-15T09:30:00Z",
    "sentiment": "positive",
    "keywords": ["黄金", "美联储", "降息"],
    "created_at": "2025-01-15T10:00:00Z"
  },
  {
    "id": 2,
    "title": "美元指数企稳，黄金短期承压",
    "content": "美元指数在107附近获得支撑，黄金短期面临回调压力...",
    "source": " Bloomberg",
    "url": "https://www.bloomberg.com/...",
    "published_at": "2025-01-15T08:15:00Z",
    "sentiment": "neutral",
    "keywords": ["美元", "黄金", "技术支撑"],
    "created_at": "2025-01-15T09:00:00Z"
  }
]
```

---

#### 13. 获取新闻详情

获取单条新闻的详细内容。

```http
GET /news/news/{news_id}
```

**路径参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `news_id` | integer | 是 | 新闻ID |

**响应示例:**

```json
{
  "id": 1,
  "title": "黄金价格创三个月新高，分析师看好后市",
  "content": "受美联储降息预期影响，黄金价格周三上涨1.2%...",
  "source": "新浪财经",
  "url": "https://finance.sina.com.cn/...",
  "published_at": "2025-01-15T09:30:00Z",
  "sentiment": "positive",
  "keywords": ["黄金", "美联储", "降息"]
}
```

---

#### 14. 获取情感分析摘要

获取新闻情感分布统计。

```http
GET /news/news/sentiment/summary
```

**响应示例:**

```json
{
  "positive": 12,
  "neutral": 8,
  "negative": 5,
  "total": 25,
  "positive_ratio": 0.48,
  "sentiment_trend": "bullish"
}
```

---

### 价格预测

#### 15. 获取价格预测列表

获取AI生成的价格预测数据。

```http
GET /predictions/predictions
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `limit` | integer | 否 | 10 | 返回条数 |

**响应示例:**

```json
[
  {
    "id": 1,
    "prediction_type": "短期",
    "target_price": 2750,
    "confidence": 0.75,
    "timeframe": "1周",
    "reasoning": "技术面突破2720阻力位，有望继续上行...",
    "factors": ["技术突破", "美元走弱", "避险需求"],
    "created_at": "2025-01-15T10:00:00Z"
  },
  {
    "id": 2,
    "prediction_type": "中期",
    "target_price": 2900,
    "confidence": 0.68,
    "timeframe": "3个月",
    "reasoning": "美联储降息周期支撑金价...",
    "factors": ["降息预期", "央行购金", "通胀对冲"],
    "created_at": "2025-01-14T15:30:00Z"
  }
]
```

---

#### 16. 获取最新预测

获取最新的价格预测。

```http
GET /predictions/predictions/latest
```

**响应示例:**

```json
{
  "type": "短期",
  "target_price": 2750,
  "confidence": 0.75,
  "timeframe": "1周",
  "reasoning": "技术面突破2720阻力位，有望继续上行...",
  "factors": ["技术突破", "美元走弱", "避险需求"],
  "created_at": "2025-01-15T10:00:00Z"
}
```

**无数据时:**

```json
{
  "message": "暂无预测数据"
}
```

---

## 错误码

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 400 | `BAD_REQUEST` | 请求参数错误 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 429 | `RATE_LIMITED` | 请求过于频繁 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 |
| 503 | `SERVICE_UNAVAILABLE` | 服务暂时不可用 |

**错误响应示例:**

```json
{
  "success": false,
  "error": "无法获取实时美元指数",
  "code": "SERVICE_UNAVAILABLE",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

## 限流策略

### 默认限流规则

| 接口类型 | 限流策略 |
|---------|---------|
| 价格数据 | 100次/分钟 |
| AI分析 | 20次/分钟 |
| 新闻数据 | 60次/分钟 |
| 预测数据 | 30次/分钟 |

### 限流响应

当触发限流时，返回HTTP 429状态码：

```json
{
  "success": false,
  "error": "请求过于频繁，请稍后再试",
  "code": "RATE_LIMITED",
  "retry_after": 60
}
```

---

## 前端调用示例

### 使用 fetch

```javascript
// 获取实时价格
const getLatestPrice = async () => {
  const response = await fetch('http://localhost:8000/api/gold/latest');
  const data = await response.json();
  return data;
};

// 获取AI分析（带缓存控制）
const getMarketAnalysis = async (refresh = false) => {
  const response = await fetch(
    `http://localhost:8000/api/analysis/market-summary-ai?refresh=${refresh}`
  );
  const data = await response.json();
  return data;
};
```

### 使用 axios

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
});

// 获取日线数据
const getDailyPrices = async (params) => {
  const { data } = await api.get('/gold/prices/daily', { params });
  return data;
};

// 刷新AI分析
const refreshAnalysis = async () => {
  const { data } = await api.post('/analysis/bullish-factors-ai/refresh');
  return data;
};
```

---

<p align="center">
  <strong>GoldMind API</strong> - 为智能黄金投资提供数据动力
  <br>
  <sub>如有问题，请参考 <a href="./ARCHITECTURE.md">架构文档</a> 或提交 <a href="../CONTRIBUTING.md">Issue</a></sub>
</p>
