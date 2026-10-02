#!/usr/bin/env python
"""权重敏感性报告（2.0.2 第 6 条）：生产权重一个字不改，只回答「换个权重结论变不变」。

用法（在 backend 目录下）：

    python scripts/weight_sensitivity.py                  # 五个尺度，200 次扰动
    python scripts/weight_sensitivity.py --horizons 20,60 # 只看长尺度
    python scripts/weight_sensitivity.py --out <目录>      # 写 weight_sensitivity.md

口径（与线上共用同一份公式，见 ``engine.composite_score(weights_override=...)``）：

- 基准 = 线上合成得分（``mode="weighted"``，权重来自 ``definitions.FACTORS``）；
- 扰动 = 每个权重乘以 U(1−jitter, 1+jitter) 的独立随机数（固定种子，可复跑），
  再走同一份公式重算得分；
- 指标：
  - **秩相关**（Spearman，扰动 vs 基准，全部有效交易日）：排序不变 = 信号稳定；
  - **符号翻转率**：方向翻转的交易日占比；
  - **最大单日变化**：|Δ得分| 的最大值；
  - **逐因子杠杆**：把**一个**因子的权重缩放 1±jitter 时 |Δ得分| 的中位数 ——
    找出到底是谁在主导排序。
- 判据（只用于报告分档）：中位秩相关 ≥ 0.99 且翻转率 ≤ 1% 记「稳定」，
  否则记「对权重敏感」；不通过也不改生产权重，先复核。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.quant import engine  # noqa: E402
from app.services.quant.definitions import FACTORS, factor_by_key  # noqa: E402
from app.utils import timeutil  # noqa: E402

DEFAULT_HORIZONS = (1, 5, 20, 60, 250)
DEFAULT_DRAWS = 200
DEFAULT_JITTER = 0.2
DEFAULT_SEED = 20261003
STABLE_RANK = 0.99
STABLE_FLIP = 0.01
MIN_DAYS = 20


def weights_for(horizon: Optional[int]) -> dict[str, float]:
    """该尺度的线上权重（唯一真源：definitions.FACTORS）。"""
    return {factor.key: float(factor.weight_for(horizon)) for factor in FACTORS}


def _perturbed(
    signals: pd.DataFrame, horizon: Optional[int], weights: dict[str, float]
) -> pd.Series:
    return engine.composite_score(signals, horizon=horizon, weights_override=weights)


def analyse_horizon(
    signals: pd.DataFrame,
    horizon: Optional[int],
    *,
    draws: int = DEFAULT_DRAWS,
    jitter: float = DEFAULT_JITTER,
    seed: int = DEFAULT_SEED,
) -> dict:
    """一个尺度的扰动统计。返回 ``available=False`` 时字段照给、数字为空。"""
    base_weights = weights_for(horizon)
    base = _perturbed(signals, horizon, base_weights).dropna()
    result: dict = {
        "horizon": horizon,
        "weights": {key: base_weights[key] for key in sorted(base_weights)},
        "observations": int(base.shape[0]),
        "available": False,
        "reason": None,
        "draws": draws,
        "jitter": jitter,
        "rank_median": None,
        "rank_p05": None,
        "rank_min": None,
        "sign_flip_rate": None,
        "max_abs_delta": None,
        "flip_magnitude_median": None,
        "base_magnitude_median": float(base.abs().median()) if not base.empty else None,
        "leverage": {},
        "verdict": "不可用",
    }
    if base.empty or base.shape[0] < MIN_DAYS:
        result["reason"] = f"有效交易日不足（{base.shape[0]} < {MIN_DAYS}）"
        return result
    if len(base_weights) < 2:
        result["reason"] = "只有一个因子，秩相关无定义"
        return result

    rng = np.random.default_rng(seed)
    ranks: list[float] = []
    flips: list[float] = []
    deltas: list[float] = []
    flip_magnitudes: list[float] = []
    for _ in range(max(1, draws)):
        draw = {
            key: max(value * (1.0 + float(rng.uniform(-jitter, jitter))), 1e-9)
            for key, value in base_weights.items()
        }
        score = _perturbed(signals, horizon, draw).reindex(base.index)
        paired = pd.concat([base.rename("base"), score.rename("draw")], axis=1).dropna()
        if paired.shape[0] < MIN_DAYS:
            continue
        correlation = paired["base"].corr(paired["draw"], method="spearman")
        if pd.notna(correlation):
            ranks.append(float(correlation))
        same_sign = np.sign(paired["base"]) == np.sign(paired["draw"])
        flipped = ~same_sign
        flips.append(float(flipped.mean()))
        if bool(flipped.any()):
            flip_magnitudes.append(float(paired.loc[flipped, "base"].abs().median()))
        deltas.append(float((paired["draw"] - paired["base"]).abs().max()))

    result["available"] = bool(ranks)
    if not ranks:
        result["reason"] = "扰动样本不足，算不出秩相关"
        return result
    result["rank_median"] = float(np.median(ranks))
    result["rank_p05"] = float(np.percentile(ranks, 5))
    result["rank_min"] = float(np.min(ranks))
    result["sign_flip_rate"] = float(np.median(flips)) if flips else None
    result["max_abs_delta"] = float(np.max(deltas)) if deltas else None
    result["flip_magnitude_median"] = (
        float(np.median(flip_magnitudes)) if flip_magnitudes else None
    )

    leverage: dict[str, float] = {}
    for key, value in base_weights.items():
        changes: list[float] = []
        for multiplier in (1.0 - jitter, 1.0 + jitter):
            draw = dict(base_weights)
            draw[key] = max(value * multiplier, 1e-9)
            score = _perturbed(signals, horizon, draw).reindex(base.index)
            paired = pd.concat([base.rename("base"), score.rename("draw")], axis=1).dropna()
            if not paired.empty:
                changes.append(float((paired["draw"] - paired["base"]).abs().median()))
        leverage[key] = float(np.max(changes)) if changes else 0.0
    result["leverage"] = leverage

    stable = (
        result["rank_median"] is not None
        and result["rank_median"] >= STABLE_RANK
        and result["sign_flip_rate"] is not None
        and result["sign_flip_rate"] <= STABLE_FLIP
    )
    result["verdict"] = "稳定" if stable else "对权重敏感"
    return result


def _format(value: Optional[float], digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    return f"{value:.{digits}f}"


def format_markdown(
    reports: list[dict],
    *,
    generated_at: str,
    days: int,
    start: Optional[str],
    end: Optional[str],
    draws: int,
    jitter: float,
    seed: int,
) -> str:
    lines = [
        "# 权重敏感性报告（排序稳定性）",
        "",
        f"- 生成时间：{generated_at}",
        f"- 面板：有效交易日 {days}（{start or '—'} — {end or '—'}）",
        f"- 扰动：每个权重 × U(1−{jitter:.0%}, 1+{jitter:.0%})，{draws} 次，种子 {seed}",
        "- 生产权重不变：本报告只读，不写数据库、不改任何线上口径",
        "",
        "| 尺度 | 有效日 | 中位秩相关 | P5 秩相关 | 最小秩相关 | 符号翻转率 | 翻转日得分中位 | 全体得分中位 | 最大单日变化 | 结论 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    labels = {None: "基础", 1: "1 日", 5: "5 日", 20: "20 日", 60: "60 日", 250: "250 日"}
    for report in reports:
        horizon = report["horizon"]
        if not report["available"]:
            lines.append(
                f"| {labels.get(horizon, horizon)} | {report['observations']} | — | — | — | — | — | — | — | 不可用（{report['reason']}） |"
            )
            continue
        flip = report["sign_flip_rate"]
        lines.append(
            "| {label} | {days} | {median} | {p05} | {minimum} | {flip} | {flip_mag} | {base_mag} | {delta} | {verdict} |".format(
                label=labels.get(horizon, horizon),
                days=report["observations"],
                median=_format(report["rank_median"]),
                p05=_format(report["rank_p05"]),
                minimum=_format(report["rank_min"]),
                flip="—" if flip is None else f"{flip:.2%}",
                flip_mag=_format(report["flip_magnitude_median"], 4),
                base_mag=_format(report["base_magnitude_median"], 4),
                delta=_format(report["max_abs_delta"], 3),
                verdict=report["verdict"],
            )
        )
    lines += ["", "## 逐因子杠杆（中位 |Δ得分|）", ""]
    factor_keys = sorted({key for report in reports for key in report["leverage"]})
    header = "| 因子 | 名称 | " + " | ".join(
        labels.get(report["horizon"], str(report["horizon"])) for report in reports
    ) + " |"
    lines.append(header)
    lines.append("|---|---|" + "---|" * len(reports))
    for key in factor_keys:
        name = factor_by_key[key].name if key in factor_by_key else key
        cells = [_format(report["leverage"].get(key), 4) for report in reports]
        lines.append(f"| {key} | {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "> 杠杆越大 = 该因子权重的小幅变化越能改变排序。它只用于定位主导项，",
        "> 不代表「应该调权」；任何调权都得按预注册流程先写死、再执行。",
        "",
    ]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    try:  # Windows 控制台默认可能是 GBK
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="权重敏感性：扰动权重，报告排序稳定性")
    parser.add_argument("--horizons", default=None, help="逗号分隔的尺度；默认 1,5,20,60,250")
    parser.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    parser.add_argument("--jitter", type=float, default=DEFAULT_JITTER)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=None, help="输出目录（weight_sensitivity.md）")
    args = parser.parse_args(argv)

    horizons: tuple[Optional[int], ...] = DEFAULT_HORIZONS
    if args.horizons:
        try:
            horizons = tuple(int(part) for part in args.horizons.split(",") if part.strip())
        except ValueError:
            print(f"--horizons 需要逗号分隔的整数：{args.horizons}", file=sys.stderr)
            return 2

    from app.database import SessionLocal
    from app.services.quant.service import load_panel

    try:
        with SessionLocal() as db:
            factors, close = load_panel(db)
    except Exception as error:  # 数据库不可用 → 如实报告，不编数据
        print(f"数据不可用：{error}", file=sys.stderr)
        return 2
    if close is None or close.empty or not factors:
        print("数据不可用：库里没有价格或因子序列（先同步数据）", file=sys.stderr)
        return 2

    calendar = close.index
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    reports = [
        analyse_horizon(signals, horizon, draws=args.draws, jitter=args.jitter, seed=args.seed)
        for horizon in horizons
    ]
    markdown = format_markdown(
        reports,
        generated_at=timeutil.now_iso(),
        days=int(signals.shape[0]),
        start=calendar[0].date().isoformat() if len(calendar) else None,
        end=calendar[-1].date().isoformat() if len(calendar) else None,
        draws=args.draws,
        jitter=args.jitter,
        seed=args.seed,
    )
    print(markdown)
    if args.out is not None:
        target = Path(args.out) / "weight_sensitivity.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        print(f"已写出 {target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())