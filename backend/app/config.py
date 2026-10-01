"""配置管理"""
import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent

# 默认数据库：backend/goldmind.db（SQLite 单文件，零安装）。
# 用绝对路径，避免「从哪个目录启动就建到哪」。
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'goldmind.db').as_posix()}"


class Settings(BaseSettings):
    # 数据库配置
    # 默认 SQLite：零安装、单文件，不需要 MySQL / Docker / 任何数据库凭据，
    # 任何人都能在自己电脑上复现整个系统。
    #
    # 需要 MySQL 时在 backend/.env 里显式写
    #   DATABASE_URL=mysql+pymysql://user:password@localhost:3306/gold_analysis
    # 覆盖即可。应用、init_db.py、seed_data.py、scripts/*.py 共用这一处真源。
    #
    # 用 SecretStr：连接串里可能带数据库密码，repr/日志里不该出现。
    # 取用时用 `.get_secret_value()`。
    DATABASE_URL: SecretStr = SecretStr(DEFAULT_DATABASE_URL)
    
    # ------------------------------------------------------------------
    # LLM 接入 —— 任何 OpenAI 兼容端点，不绑定具体供应商
    # ------------------------------------------------------------------
    # 所有调用点统一走 app/services/llm_provider.py 的工厂，
    # 不要在此之外直接构造 ChatOpenAI / OpenAI 客户端。
    #
    # 密钥、端点、模型三项必须**同时**存在才算「已配置」。
    # 缺任意一项时各分析服务如实返回「暂不可用」，不会退回任何内置内容
    # （AGENTS.md 红线 1：不许编造）。默认值全部为空 —— 不在代码里替用户
    # 选定某一家供应商。
    #
    # 复制到 backend/.env 的示例（任选其一，换成自己的 key）：
    #   OpenAI      LLM_BASE_URL=https://api.openai.com/v1    LLM_MODEL=gpt-4o-mini
    #   DeepSeek    LLM_BASE_URL=https://api.deepseek.com/v1  LLM_MODEL=deepseek-chat
    #   通义千问     LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    #               LLM_MODEL=qwen-plus
    #   Kimi        LLM_BASE_URL=https://api.moonshot.cn/v1    LLM_MODEL=moonshot-v1-8k
    #   Ollama 本地  LLM_BASE_URL=http://localhost:11434/v1    LLM_MODEL=qwen2.5:14b
    #   小米 MiMo   LLM_BASE_URL=https://api.xiaomimimo.com/v1 LLM_MODEL=mimo-v2.6-flash
    #
    # `SecretStr` 而不是 `str`：pydantic 的 repr / str / model_dump
    # 都会把它显示成 `**********`。明文 str 的话，任何一句
    # `logger.info(settings)` 或包含 settings 的异常回溯都会把 key 打进日志。
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    # 仅用于界面展示（页脚「由 … 生成」），可留空 —— 拿不到就不猜。
    LLM_PROVIDER: str = ""
    # 单次输出的 token 上限。推理类模型把它同时用于思考与正文：
    # 4096 会让「三档投资策略」这类大 JSON 被截断、解析失败，页面如实显示
    # 「暂不可用」。8192 留出两倍余量（实测当前端点接受，且能完整返回
    # 4600+ tokens 的 JSON）。
    LLM_MAX_TOKENS: int = 8192
    # 是否让 httpx 读取宿主的代理环境变量（ALL_PROXY / HTTP_PROXY / NO_PROXY 等）。
    #
    # 默认 False。宿主环境里一个写坏的代理配置就足以让整个 AI 功能失效：
    #   - ALL_PROXY=socks5://... 但未安装 socksio → httpx 构造客户端即抛异常
    #   - NO_PROXY 里含 `[::1]` 这类写法          → httpx 解析时报
    #                                               Invalid port: ':1]'
    # 两者都会让所有 LLM 调用失败；而失败会被上层吞掉并回退到硬编码默认值，
    # 表现成「页面上有分析内容，其实一次模型都没调用」。
    #
    # 如果你的网络确实必须经代理才能访问 LLM 端点，设为 true，
    # 并确保已安装 httpx[socks]（见 requirements.txt）。
    LLM_TRUST_ENV: bool = False

    # ------------------------------------------------------------------
    # 联网搜索（可选，默认关闭）
    # ------------------------------------------------------------------
    # 开启后使用「MiMo 插件式」的 web_search 工具（请求体里带
    # tools=[{"type": "web_search", ...}]）。这不是通用 OpenAI 能力：
    # 只有声明支持该工具的端点可用。账号未开通时端点会返回
    #   HTTP 400 · web search tool found in the request body,
    #   but webSearchEnabled is false
    # 此时保持关闭即可 —— 关闭时分析直接走数据库 / RSS 回退，不发起无效请求。
    LLM_SEARCH_ENABLED: bool = False
    # 搜索所用模型；留空则跟随 LLM_MODEL。
    LLM_SEARCH_MODEL: str = ""
    # 搜索专用凭据与端点；留空则跟随 LLM_API_KEY / LLM_BASE_URL。
    # 分开配置是为了支持「推理用低成本端点、搜索用另一端点」的部署。
    LLM_SEARCH_API_KEY: SecretStr = SecretStr("")
    LLM_SEARCH_BASE_URL: str = ""
    # 单次搜索最大关键词数（每轮搜索会并发展开为多次插件调用，按次计费）
    LLM_SEARCH_MAX_KEYWORD: int = 2

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
    # 机构观点的新闻扫描窗口（天）。机构预测不再要求「24 小时内发布」——
    # 在窗口内逐家提取**最近一次可核实**的预测（可以是窗口内较早发布的）；
    # 没有新研报不等于机构撤回了旧预测，空目标价绝不覆盖已有真实记录。
    INSTITUTION_NEWS_LOOKBACK_DAYS: int = 30
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
    # 量化预测与回测：每 2 小时的第 45 分钟（回测本身按 24 小时节流）。
    UPDATE_QUANT_CRON: str = "45 */2 * * *"
    # 首次回填的年数（之后都是增量抓取）。
    QUANT_HISTORY_YEARS: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
