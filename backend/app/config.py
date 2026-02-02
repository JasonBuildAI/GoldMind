"""配置管理"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:root123@localhost:3306/gold_analysis"
    
    # DeepSeek配置
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""  # 从.env文件读取
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    MODEL_NAME: str = "deepseek-chat"
    
    # 智谱AI配置（用于实时搜索）
    ZHIPU_API_KEY: str = ""  # 从.env文件读取，获取地址：https://open.bigmodel.cn/
    ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_MODEL: str = "glm-4-plus"  # 付费版，支持Web Search
    
    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    # 实时数据更新（黄金价格、美元指数）- 保持原有频率
    UPDATE_PRICE_CRON: str = "30 6 * * *"   # 每天早上6:30更新前一日收盘价
    # Agent更新配置 - 偶数整点更新
    UPDATE_NEWS_CRON: str = "0 0,2,4,6,8,10,12,14,16,18,20,22 * * *"    # 偶数整点更新新闻
    UPDATE_AI_ANALYSIS_CRON: str = "0 0,2,4,6,8,10,12,14,16,18,20,22 * * *"  # 偶数整点更新AI分析（看涨/看跌/机构/建议）
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
