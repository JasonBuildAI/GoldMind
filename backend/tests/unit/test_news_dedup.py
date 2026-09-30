"""新闻去重：同一条新闻换个 URL 参数不该变成两条。

现实里的 RSS 链接经常带跟踪参数（WSJ / MarketWatch 的 `?mod=rss_...` 尤其常见）。
原实现按**原始 URL 字符串**比较，于是同一条新闻的每种写法都是一条新记录：

    实测：一条新闻的 5 种写法（带 mod、带 utm、带 fragment、带尾斜杠）
    入库了 5 次 —— 下游「最近24小时新闻」把同一件事重复喂给模型多次。

修法是入库前把 URL 规范化（`normalize_url`），并且**存规范化后的形式**，
保证「存进去的」与「拿来比的」是同一个东西。
"""
import pytest

from app.models.news import GoldNews
from app.services.news_service import NewsService, normalize_url

BASE = "https://www.marketwatch.com/story/gold-hits-record"


# --------------------------------------------------------------------------- #
# normalize_url
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize(
    "variant",
    [
        BASE,
        BASE + "?mod=mw_rss_marketpulse",
        BASE + "?mod=mw_rss_marketpulse&utm_source=rss",
        BASE + "?utm_source=rss&mod=mw_rss_marketpulse",  # 参数顺序不同
        BASE + "#comments",
        BASE + "/",
        BASE + "/?mod=rss",
        # 只把 scheme 与 host 大写 —— 路径大小写敏感，大写路径是**另一篇文章**
        BASE.replace("https://www.marketwatch.com", "HTTPS://WWW.MARKETWATCH.COM"),
    ],
)
def test_equivalent_urls_normalize_to_the_same_thing(variant):
    assert normalize_url(variant) == BASE


@pytest.mark.unit
def test_keeps_meaningful_query_params():
    """真正的文章标识不能被去掉 —— 去掉会串号。"""
    url = "https://example.invalid/article?id=12345&page=2"

    result = normalize_url(url)

    assert "id=12345" in result
    assert "page=2" in result


@pytest.mark.unit
def test_different_articles_stay_different():
    """规范化不能把不同的文章合并成一条。"""
    a = normalize_url("https://example.invalid/a")
    b = normalize_url("https://example.invalid/b")

    assert a != b


@pytest.mark.unit
def test_scheme_and_host_are_lowercased_but_path_is_not():
    """scheme/host 大小写不敏感，路径大小写敏感。"""
    result = normalize_url("HTTPS://WWW.Example.INVALID/Story/Gold")

    assert result.startswith("https://www.example.invalid/")
    assert result.endswith("/Story/Gold")


@pytest.mark.unit
@pytest.mark.parametrize("raw", [None, "", "   "])
def test_blank_input_returns_empty(raw):
    assert normalize_url(raw) == ""


# --------------------------------------------------------------------------- #
# save_news 的去重
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_same_story_with_tracking_params_is_stored_once(db_session):
    """核心回归：5 种写法只应入库 1 条。"""
    service = NewsService(db_session)
    variants = [
        BASE,
        BASE + "?mod=mw_rss_marketpulse",
        BASE + "?mod=mw_rss_marketpulse&utm_source=rss",
        BASE + "#comments",
        BASE + "/",
    ]

    for url in variants:
        service.save_news(
            {
                "title": "金价创历史新高",
                "content": "正文",
                "url": url,
                "source": "MarketWatch Commodities",
                "published_at": None,
            }
        )

    rows = db_session.query(GoldNews).all()
    assert len(rows) == 1, f"同一条新闻入库了 {len(rows)} 次"
    # 存的是规范化后的形式，链接依然可用
    assert rows[0].url == BASE


@pytest.mark.unit
def test_stored_url_is_already_normalized(db_session):
    """存进去的必须是规范化形式，否则下次比较又对不上。"""
    service = NewsService(db_session)

    service.save_news(
        {
            "title": "标题",
            "content": "正文",
            "url": BASE + "?mod=rss&utm_campaign=x#frag",
            "source": "测试源",
            "published_at": None,
        }
    )

    stored = db_session.query(GoldNews).one()
    assert stored.url == BASE
    assert normalize_url(stored.url) == stored.url, "存的是未规范化的 URL"


@pytest.mark.unit
def test_different_stories_are_both_kept(db_session):
    """去重不能过头：两条不同的新闻都要留下。"""
    service = NewsService(db_session)
    for title, url in (("新闻一", "https://e.invalid/1"), ("新闻二", "https://e.invalid/2")):
        service.save_news(
            {"title": title, "content": "x", "url": url, "source": "测试源", "published_at": None}
        )

    assert db_session.query(GoldNews).count() == 2


@pytest.mark.unit
def test_falls_back_to_title_and_source_when_url_is_missing(db_session):
    """没有 URL 时按「标题 + 来源」去重（原有行为，不能退化）。"""
    service = NewsService(db_session)
    payload = {"title": "无链接新闻", "content": "x", "url": "", "source": "测试源"}

    service.save_news(dict(payload))
    service.save_news(dict(payload))

    assert db_session.query(GoldNews).count() == 1
