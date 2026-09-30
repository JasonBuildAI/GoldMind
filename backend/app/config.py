"""配置管理"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:root123@localhost:3306/gold_analysis"
    
    # LLM 供应商（当前仅支持 mimo）
    LLM_PROVIDER: str = "mimo"

    # 小米 MiMo 配置
    # 推理与联网搜索共用同一个端点与密钥；所有调用点统一走
    # app/services/llm_provider.py 的工厂，不要在此之外直接构造客户端。
    MIMO_API_KEY: str = ""  # 从.env文件读取
    # Token Plan 端点。按量付费的普通 API 为 https://api.xiaomimimo.com/v1
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"
    # 推理模型（mimo-v2.6-flash / mimo-v2.6-pro / mimo-v2.6-pro-ultraspeed）
    MIMO_MODEL: str = "mimo-v2.6-flash"
    # 联网搜索所用模型
    MIMO_SEARCH_MODEL: str = "mimo-v2.6-flash"
    # 单次搜索最大关键词数（每轮搜索会并发展开为多次插件调用，按次计费）
    MIMO_SEARCH_MAX_KEYWORD: int = 2

    # ------------------------------------------------------------------
    # 迁移前的旧供应商配置（DeepSeek / 智谱AI）已全部移除。
    # 历史实现见 git 历史；如需回滚请整体回退该次提交。
    # ------------------------------------------------------------------
    
    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    # 新闻 RSS 源，格式 "名称|URL,名称|URL"；留空则使用 news_service 内置默认源
    NEWS_RSS_SOURCES: str = ""
    # 实时数据更新（黄金价格、美元指数）- 保持原有频率
    UPDATE_PRICE_CRON: str = "30 6 * * *"   # 每天早上6:30更新前一日收盘价
    # Agent更新配置 - 偶数整点更新
    UPDATE_NEWS_CRON: str = "0 0,2,4,6,8,10,12,14,16,18,20,22 * * *"    # 偶数整点更新新闻
    UPDATE_AI_ANALYSIS_CRON: str = "0 0,2,4,6,8,10,12,14,16,18,20,22 * * *"  # 偶数整点更新AI分析（看涨/看跌/机构/建议）
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
