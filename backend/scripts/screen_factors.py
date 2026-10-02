"""因子候选筛选：把 `app.services.quant.screen` 的三道闸门跑在真实库上。

用法：

    python scripts/screen_factors.py                      # 开发期（留出期之前）全候选
    python scripts/screen_factors.py --horizons 5,20,60   # 只看部分尺度
    python scripts/screen_factors.py --as-of 2026-10-01   # 按当天可见的输入重建面板
    python scripts/screen_factors.py --include-holdout    # 明知故犯：连留出期一起看

为什么单独一个脚本而不是塞进研究台：研究台回答「线上口径的变体谁更好」，
这里回答的是「一个新信息值不值得进因子集」—— 判定规则、分母（Bonferroni 按整轮算）
和输出都不同，混在一起会让两边的事前承诺互相污染。

默认只看**开发期**（`HOLDOUT_START` 之前）。留出期是将来第 ③ 道闸门用的，
现在拿它筛因子等于事后挑参数，所以要把这个开关做成显式且带警告的。
"""
from __future__ import annotations

import argparse

import sys
from pathlib import Path
from typing import Callable, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from app.services.quant import screen  # noqa: E402
from app.services.quant.definitions import (  # noqa: E402
    BENCHMARK_KEY,
    FACTORS,
    HOLDOUT_START,
    HORIZONS,
)

# 候选 = 「原始序列 + 一种变换」。变换只用工况里已有的那三种语义，
# 不发明新口径 —— 新口径该先进 definitions / engine 再进这里。
TRANSFORMS: dict[str, Callable[[pd.Series], pd.Series]] = {
    "level": lambda s: s,
    "chg20": lambda s: s.diff(20),
    "chg63": lambda s: s.diff(63),
}

# 额外候选：库里若有这些序列（新摄入的信息源），一并筛
EXTRA_CANDIDATES: dict[str, Callable[[dict], Optional[pd.Series]]] = {
    "gold_silver_ratio": lambda series: series.get("gold_silver_ratio"),
    "copper_gold_ratio": lambda series: series.get("copper_gold_ratio"),
    "gvz": lambda series: series.get("gvz"),
    "cftc_net_oi_ratio": lambda series: series.get("cftc_net_oi_ratio"),
    # 官方地缘指数：现有 geopolitical 因子是新闻语料代理（实测只有 1 条观测，等于没跑）
    "gpr_daily": lambda series: series.get("gpr_daily"),
}


def build_candidates(series: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """因子表 + 额外序列，逐个套 level/chg20/chg63 三种变换。"""
    candidates: dict[str, pd.Series] = {}
    sources = {factor.key: series.get(factor.key) for factor in FACTORS}
    for key, builder in EXTRA_CANDIDATES.items():
        sources[key] = builder(series)
    for key, values in sources.items():
        if values is None or values.empty:
            continue
        for transform, apply in TRANSFORMS.items():
            transformed = apply(values).dropna()
            if len(transformed) >= screen.MIN_SCREEN_SAMPLES:
                candidates[f"{key}:{transform}"] = transformed
    return candidates


def format_markdown(rows: list[dict], *, horizons: tuple[int, ...]) -> str:
    lines = [
        "| 候选 | 判定 | 尺度 | 样本 | t(HAC) | p | t(iid) | 命中率 | α(Bonf) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        def fmt(value, spec: str = ".2f") -> str:
            return "-" if value is None else format(value, spec)
        lines.append(
            f"| {row['candidate']} | {row['status']} | {row['horizon_days']} "
            f"| {row['samples']} | {fmt(row['t_stat'])} | {fmt(row['p_value'], '.4f')} "
            f"| {fmt(row['t_stat_iid'])} | {fmt(row['hit_rate'], '.3f')} "
            f"| {fmt(row['bonferroni_alpha'], '.5f')} |"
        )
    verdicts = {row["candidate"]: row["status"] for row in rows}
    advancing = sorted(key for key, status in verdicts.items() if status == screen.STATUS_AWAIT)
    lines.append("")
    lines.append(
        f"检验总数 {len(rows)}（{len(verdicts)} 候选 × {len(horizons)} 尺度），"
        f"Bonferroni α = {0.05 / max(1, len(rows)):.5f}，另要求 |t| ≥ {screen.MIN_T_TO_PASS:g}。"
    )
    lines.append(
        "过闸门①②（等前向窗口确认）：" + ("、".join(advancing) if advancing else "无")
    )
    return "\n".join(lines)


def format_forward_window(
    benchmark: pd.Series,
    verdicts: list[screen.Verdict],
    candidates: dict[str, pd.Series],
    *,
    horizons: tuple[int, ...],
) -> str:
    """第 ③ 道闸门的进度：什么时候才可能判，以及已经能判的候选复核成了什么。

    这一节的存在是为了防止一种漂移：闸门①②当场就能给出漂亮结论，于是没人再等
    新数据。把「还差多少个交易日」印在报告里，等与不等就都是一个可见的决定。
    """
    lines = [
        "",
        "## 第 ③ 道闸门（前向窗口）",
        "",
        f"窗口起点 {screen.FORWARD_WINDOW_START.isoformat()}（第二轮结论写进 spec 的那天）。"
        "起点之前的样本都已被翻看并汇报过，拿它们「确认」结论等于事后挑参数，"
        f"所以只有起点之后新增的观测才算证据（下限 {screen.MIN_FORWARD_BETS} 次独立下注）。",
        "",
        "| 尺度 | 窗口内观测 | 独立下注 | 需要 | 可判 | 还差(交易日) |",
        "|---|---|---|---|---|---|",
    ]

    def num(value: Optional[float], spec: str = ".2f") -> str:
        return "-" if value is None else format(value, spec)

    decidable: dict[int, bool] = {}
    for horizon in horizons:
        item = screen.forward_window_readiness(benchmark, horizon)
        decidable[horizon] = bool(item["decidable"])
        lines.append(
            f"| {horizon} | {item['observations']} | {item['independent_bets']} "
            f"| {item['required_bets']} | {'是' if item['decidable'] else '否'} "
            f"| {item['approx_trading_days_needed']} |"
        )

    awaiting = [verdict for verdict in verdicts if verdict.status == screen.STATUS_AWAIT]
    if not awaiting:
        lines += ["", "过闸门 ①② 的候选：无 —— 第 ③ 道闸门本轮无需复核。"]
        return "\n".join(lines)

    checks: list[str] = []
    for verdict in awaiting:
        for result in verdict.results:
            if not decidable.get(result.horizon):
                continue
            check = screen.confirm_on_forward_window(
                verdict.name,
                candidates[verdict.name],
                benchmark,
                result.horizon,
                development_t=result.t_stat,
            )
            checks.append(
                f"- {verdict.name} @ {result.horizon} 日：{check['verdict']} "
                f"（开发期 t={num(result.t_stat)}，前向 t={num(check['forward_t'])}）—— "
                f"{check['reason']}"
            )
    if checks:  # 一条结论都不许在窗口攒够之前提前给出
        lines += ["", "已可判尺度上的前向复核："] + checks
    pending_scales = sorted(h for h, ok in decidable.items() if not ok)
    if pending_scales:
        days = "、".join(str(h) for h in pending_scales)
        lines.append(f"其余尺度（{days} 日）等到窗口攒够样本后再判，本轮不预判。")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    try:  # Windows 控制台默认可能是 GBK，输出里的 ⚠ 与勾叉会直接抛 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="因子候选筛选（三道闸门）")
    parser.add_argument("--horizons", default=None, help="逗号分隔的尺度；默认 " + ",".join(map(str, HORIZONS)))
    parser.add_argument("--as-of", default=None, help="按修订流水重建成那一天的面板（YYYY-MM-DD）")
    parser.add_argument("--include-holdout", action="store_true", help="连留出期一起看（会污染事前承诺，默认关闭）")
    parser.add_argument("--out", type=Path, default=None, help="输出目录（screen_factors.md / .csv）")
    args = parser.parse_args(argv)

    try:
        horizons = (
            HORIZONS
            if not args.horizons
            else tuple(int(item) for item in args.horizons.split(",") if item.strip())
        )
    except ValueError:
        print("--horizons 需要逗号分隔的整数", file=sys.stderr)
        return 2

    from sqlalchemy.orm import sessionmaker

    from app.database import engine as db_engine
    from app.services.quant import service

    as_of = pd.Timestamp(args.as_of).date() if args.as_of else None
    session = sessionmaker(bind=db_engine)()
    try:
        series, close = service.load_panel(session, as_of=as_of)
    finally:
        session.close()
    benchmark = close if close is not None and not close.empty else series.get(BENCHMARK_KEY)
    if benchmark is None or len(benchmark) < 500:
        print("数据不可用：金价序列不足，无法筛选", file=sys.stderr)
        return 2

    candidates = build_candidates(series)
    if not candidates:
        print("库里没有任何可筛选的序列", file=sys.stderr)
        return 2

    mask = None
    if not args.include_holdout:
        mask = pd.Series(benchmark.index < pd.Timestamp(HOLDOUT_START), index=benchmark.index)
        print(
            f"筛选窗口：开发期（{HOLDOUT_START.isoformat()} 之前）；留出期留给第 ③ 道闸门。",
            file=sys.stderr,
        )
    else:
        print("⚠ 已包含留出期：本次结果不可用于因子入选，只能当诊断。", file=sys.stderr)

    verdicts = screen.screen_round(candidates, benchmark, horizons=horizons, mask=mask)
    rows = screen.summary_rows(verdicts)
    markdown = format_markdown(rows, horizons=horizons) + "\n" + format_forward_window(
        benchmark, verdicts, candidates, horizons=horizons
    )
    print(markdown)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "screen_factors.md").write_text(markdown, encoding="utf-8")
        pd.DataFrame(rows).to_csv(args.out / "screen_factors.csv", index=False, encoding="utf-8-sig")
        print(f"\n已写出 {args.out / 'screen_factors.md'} 与 screen_factors.csv", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
