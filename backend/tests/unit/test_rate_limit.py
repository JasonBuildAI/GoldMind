"""滑动窗口限流器的单元测试。

重点不只是「能限流」，还包括原实现的两个缺陷：
内存无界增长、以及健康检查被一起限流。
"""
import pytest

from app.utils.rate_limit import SlidingWindowRateLimiter


@pytest.mark.unit
def test_allows_up_to_limit_then_blocks():
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)

    for i in range(3):
        allowed, retry_after = limiter.allow("1.2.3.4", now=100.0)
        assert allowed is True, f"第 {i + 1} 次应当放行"
        assert retry_after == 0

    allowed, retry_after = limiter.allow("1.2.3.4", now=100.0)
    assert allowed is False
    assert retry_after > 0


@pytest.mark.unit
def test_window_slides_and_frees_capacity():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)

    assert limiter.allow("ip", now=0.0)[0] is True
    assert limiter.allow("ip", now=1.0)[0] is True
    assert limiter.allow("ip", now=2.0)[0] is False

    # 越过窗口后，最早的两次记录都应过期
    assert limiter.allow("ip", now=11.0)[0] is True


@pytest.mark.unit
def test_keys_are_independent():
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)

    assert limiter.allow("a", now=0.0)[0] is True
    assert limiter.allow("b", now=0.0)[0] is True
    assert limiter.allow("a", now=0.0)[0] is False
    assert limiter.allow("b", now=0.0)[0] is False


@pytest.mark.unit
def test_retry_after_is_within_window():
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=30)
    limiter.allow("ip", now=0.0)

    allowed, retry_after = limiter.allow("ip", now=5.0)

    assert allowed is False
    assert 0 < retry_after <= 30


@pytest.mark.unit
def test_memory_does_not_grow_without_bound():
    """回归：原实现从不删除 IP 键，长期运行内存无界增长。

    这里制造远超清理阈值的一次性 key，验证它们会被清理掉。
    """
    limiter = SlidingWindowRateLimiter(limit=5, window_seconds=1)

    # 每个 key 只来一次，时间各不相同；随后用很晚的时间点触发全量清理
    for i in range(1500):
        limiter.allow(f"ip-{i}", now=float(i) / 1000.0)

    # 触发一次位于很晚时刻的请求，使前面所有记录都过期
    limiter.allow("late", now=10_000.0)

    assert limiter.tracked_keys() < 1500, "过期的一次性 key 必须被清理"


@pytest.mark.unit
def test_tracked_keys_counts_active_only():
    limiter = SlidingWindowRateLimiter(limit=5, window_seconds=10)

    limiter.allow("a", now=0.0)
    limiter.allow("b", now=0.0)

    assert limiter.tracked_keys() == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    "limit,window",
    [(0, 60), (-1, 60), (10, 0), (10, -5)],
)
def test_rejects_invalid_configuration(limit, window):
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=limit, window_seconds=window)
