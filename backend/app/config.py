"""配置管理"""
import os
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # 数据库配置
    # 默认指向本机 MySQL，但**故意不带密码**：凭据只能来自 .env 与部署环境
    # （AGENTS.md 的红线 2）。带一个弱默认密码的后果是「没配也能连上」——
    # 那会掩盖配置缺失，也让弱口令看起来是正常用法。
    # 没配 .env 时这里会认证失败，是期望的行为。
    # 同样用 SecretStr：连接串里带数据库密码，
    # repr/日志里不该出现。取用时用 `.get_secret_value()`。
    DATABASE_URL: SecretStr = SecretStr("mysql+pymysql://root@localhost:3306/gold_analysis")
    
    # LLM 供应商（当前仅支持 mimo）
    LLM_PROVIDER: str = "mimo"

    # 小米 MiMo 配置
    # 推理与联网搜索共用同一个端点与密钥；所有调用点统一走
    # app/services/llm_provider.py 的工厂，不要在此之外直接构造客户端。
    # `SecretStr` 而不是 `str`：pydantic 的 repr / str / model_dump
    # 都会把它显示成 `**********`。明文 str 的话，任何一句
    # `logger.info(settings)` 或包含 settings 的异常回溯都会把 key 打进日志。
    MIMO_API_KEY: SecretStr = SecretStr("")  # 从.env文件读取
    # Token Plan 端点。按量付费的普通 API 为 https://api.xiaomimimo.com/v1
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"
    # 推理模型（mimo-v2.6-flash / mimo-v2.6-pro / mimo-v2.6-pro-ultraspeed）
    MIMO_MODEL: str = "mimo-v2.6-flash"
    # 联网搜索所用模型
    MIMO_SEARCH_MODEL: str = "mimo-v2.6-flash"
    # 单次搜索最大关键词数（每轮搜索会并发展开为多次插件调用，按次计费）
    MIMO_SEARCH_MAX_KEYWORD: int = 2
    # 是否让 httpx 读取宿主的代理环境变量（ALL_PROXY / HTTP_PROXY / NO_PROXY 等）。
    #
    # 默认 False。宿主环境里一个写坏的代理配置就足以让整个 AI 功能失效：
    #   - ALL_PROXY=socks5://... 但未安装 socksio → httpx 构造客户端即抛异常
    #   - NO_PROXY 里含 `[::1]` 这类写法          → httpx 解析时报
    #                                               Invalid port: ':1]'
    # 两者都会让所有 LLM 调用失败；而失败会被上层吞掉并回退到硬编码默认值，
    # 表现成「页面上有分析内容，其实一次模型都没调用」。
    #
    # 如果你的网络确实必须经代理才能访问 MiMo，设为 true，
    # 并确保已安装 httpx[socks]（见 requirements.txt）。
    MIMO_TRUST_ENV: bool = False

    # ------------------------------------------------------------------
    # 迁移前的旧供应商配置（DeepSeek / 智谱AI）已全部移除。
    # 历史实现见 git 历史；如需回滚请整体回退该次提交。
    # ------------------------------------------------------------------
    
    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    # 只影响 `uvicorn --reload`（见 main.py 末尾）。
    #
    # 默认 False：没有 .env 时（例如直接部署、或忘了复制模板）不该默认打开
    # 开发期的自动重载 —— 它在生产里白耗资源，也不是 uvicorn 建议的用法。
    # 本地开发想要热重载就在 .env 里显式写 DEBUG=true；
    # docker-compose 已用 `DEBUG=${DEBUG:-false}` 覆盖。
    DEBUG: bool = False
    # 日志级别：DEBUG / INFO / WARNING / ERROR。
    # .env.example 里一直写着这一项，但此前没有任何代码读它 —— 设了也不生效。
    LOG_LEVEL: str = "INFO"
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    # 新闻 RSS 源，格式 "名称|URL,名称|URL"；留空则使用 news_service 内置默认源
    NEWS_RSS_SOURCES: str = ""
    # 文件缓存目录；留空则用默认的 backend/cache。
    # 可配置是为了让测试用独立目录，避免与开发时的缓存互相污染。
    CACHE_DIR: str = ""

    # ------------------------------------------------------------------
    # CORS 与限流
    # ------------------------------------------------------------------
    # 允许的跨域来源（逗号分隔）。
    #
    # 前端默认走相对路径（开发期 vite 代理、生产期 nginx 反代），因此正常情况下
    # 根本不产生跨域请求；这里只列出本地开发地址即可。
    #
    # 不要填 "*"：若同时允许携带凭证，等于任何站点都能带着用户凭证调用本 API。
    # main.py 也做了兜底 —— 来源为 "*" 时自动关闭凭证。
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )
    # 每 IP 每分钟的请求上限（普通接口）
    RATE_LIMIT_PER_MINUTE: int = 60
    # 会触发付费 LLM 调用的接口单独用更严的上限，避免被刷爆额度
    RATE_LIMIT_AI_PER_MINUTE: int = 6

    # 实时数据更新（黄金价格、美元指数）- 保持原有频率
    UPDATE_PRICE_CRON: str = "30 6 * * *"   # 每天早上6:30更新前一日收盘价
    # Agent更新配置 - 偶数整点更新
    UPDATE_NEWS_CRON: str = "0 0,2,4,6,8,10,12,14,16,18,20,22 * * *"    # 偶数整点更新新闻
    UPDATE_AI_ANALYSIS_CRON: str = "0 0,2,4,6,8,10,12,14,16,18,20,22 * * *"  # 偶数整点更新AI分析（看涨/看跌/机构/建议）

    # ------------------------------------------------------------------
    # 量化预测引擎（app/services/quant）
    # ------------------------------------------------------------------
    # 总开关：关闭后不注册因子同步与预测任务（已落库的数据仍可读）。
    QUANT_ENABLED: bool = True
    # 因子同步：每 2 小时的第 15 分钟。各源还会按自己的最小间隔跳过未到期的抓取
    # （见 services/quant/sync.py 的 SOURCE_MIN_INTERVALS）。
    UPDATE_FACTORS_CRON: str = "15 */2 * * *"
    # 首次回填的年数（之后都是增量抓取）。
    QUANT_HISTORY_YEARS: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
