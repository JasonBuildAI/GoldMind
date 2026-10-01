#!/usr/bin/env python3
"""量化研究台：预注册候选 × 尺度 × 开发 / 留出 / 全样本 的对照报告。

预注册的候选清单写在 ``docs/specs/2026-10-02-量化策略提升路线图.md`` 的
「6.1 预注册候选清单」「阶段 2 入选判据」；本脚本只**照抄执行** ——
不在看到留出期成绩之后增删候选或改判定。``tests/unit/quant/test_quant_lab.py``
会把两边逐项对齐。

用法::

    python scripts/quant_lab.py                 # 读项目数据库，打印报告
    python scripts/quant_lab.py --out D:/Temp   # 另存 quant_lab.md + quant_lab.csv
    python scripts/quant_lab.py --horizons 20,250 --group baseline --group drift

研究台只有一种数据来源：项目数据库（``backend/.env`` 的 ``DATABASE_URL``，
默认 SQLite）。库里没有数据就报「数据不可用」并退出，不退回合成数据 ——
见 ``docs/00-产品方向.md`` 第四节：宁可显示「数据不可用」，不许编造。
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.quant import backtest, engine, preregistered  # noqa: E402
from app.services.quant.definitions import (  # noqa: E402
    CATEGORY_MONETARY,
    CATEGORY_RISK,
    FACTORS,
    HOLDOUT_START,
    HORIZONS,
)
from app.services.quant.preregistered import (  # noqa: E402
    INTERVAL_NOMINAL,
    RULE_2_ACCURACY_TOLERANCE,
    RULE_2_BRIER_P,
    RULE_OTHER_SCALE_TOLERANCE,
    TARGET_SCALE,
)
from app.utils import timeutil  # noqa: E402

PERIODS = ("development", "holdout", "full")
PERIOD_LABELS = {"development": "开发期", "holdout": "留出期", "full": "全样本"}

GROUP_LABELS = {
    "baseline": "基线族",
    "drift": "漂移三档",
    "composite": "合成四档",
    "interval": "分布四档",
    "factor_set": "因子集四档",
    "ensemble": "集成一档",
}


def _keys_with_categories(*categories: str) -> tuple[str, ...]:
    wanted = set(categories)
    return tuple(factor.key for factor in FACTORS if factor.category in wanted)


def _keys_without(*keys: str) -> tuple[str, ...]:
    excluded = set(keys)
    return tuple(factor.key for factor in FACTORS if factor.key not in excluded)


def _keys_with_min_weight(minimum: float) -> tuple[str, ...]:
    return tuple(factor.key for factor in FACTORS if factor.weight >= minimum)


# 因子集四档（顺序 = FACTORS 的定义顺序，保证可复现）
FACTOR_SETS = {
    "macro": _keys_with_categories(CATEGORY_MONETARY, CATEGORY_RISK),
    "no_alt": _keys_without("bitcoin", "risk_appetite", "seasonality"),
    "core": _keys_with_min_weight(0.6),
}


@dataclass(frozen=True)
class Candidate:
    """一个预注册候选：只改一个维度，其余保持 B0（线上 v4）口径。"""

    key: str
    group: str
    description: str
    score_modes: tuple[str, ...] = ("weighted",)
    include: Optional[tuple[str, ...]] = None
    regression_window: Optional[int] = None
    interval: str = "aci"

    @property
    def is_ensemble(self) -> bool:
        return len(self.score_modes) > 1

    def run_key(self) -> tuple:
        """参数指纹：同口径的控制候选（S4 / P4 / F4）与 B0 只计算一次。"""
        return (self.score_modes, self.include, self.regression_window, self.interval)


def candidates() -> tuple[Candidate, ...]:
    """预注册候选清单 —— 与 spec 6.1 的表格逐项对应，顺序即报告顺序。"""
    return (
        Candidate("B0", "baseline", "线上 v4 口径：加权合成 + 扩展窗口 + ACI 非对称 + 全部因子"),
        Candidate("D1", "drift", "回归窗口 = 滚动 252 个交易日（1 年）", regression_window=252),
        Candidate("D3", "drift", "回归窗口 = 滚动 756 个交易日（3 年）", regression_window=756),
        Candidate("D5", "drift", "回归窗口 = 滚动 1260 个交易日（5 年）", regression_window=1260),
        Candidate("S1", "composite", "合成得分 = 等权", score_modes=("equal",)),
        Candidate("S2", "composite", "合成得分 = winsor（z 截尾 ±2）", score_modes=("winsor",)),
        Candidate("S3", "composite", "合成得分 = trimmed（每行剔除绝对值最大的贡献）", score_modes=("trimmed",)),
        Candidate("S4", "composite", "合成得分 = 加权（控制，与 B0 同口径）", score_modes=("weighted",)),
        Candidate("P1", "interval", "区间 = ACI 对称", interval="aci_symmetric"),
        Candidate("P2", "interval", "区间 = 经验分位（无 ACI）", interval="empirical"),
        Candidate("P3", "interval", "区间 = 正态分位", interval="normal"),
        Candidate("P4", "interval", "区间 = ACI 非对称（控制，与 B0 同口径）", interval="aci"),
        Candidate("F1", "factor_set", "因子集 = 货币 + 避险（7 个）", include=FACTOR_SETS["macro"]),
        Candidate(
            "F2",
            "factor_set",
            "因子集 = 去掉弱先验（bitcoin / risk_appetite / seasonality）",
            include=FACTOR_SETS["no_alt"],
        ),
        Candidate("F3", "factor_set", "因子集 = 基础权重 ≥ 0.6（6 个）", include=FACTOR_SETS["core"]),
        Candidate("F4", "factor_set", "因子集 = 全部（控制，与 B0 同口径）", include=None),
        Candidate("E0", "ensemble", "集成 = 0.5×加权 + 0.5×等权 的得分平均", score_modes=("weighted", "equal")),
    )


CANDIDATES: tuple[Candidate, ...] = candidates()
CANDIDATES_BY_KEY = {candidate.key: candidate for candidate in CANDIDATES}

assert len(CANDIDATES_BY_KEY) == len(CANDIDATES), "候选 key 必须唯一"

ROW_FIELDS = (
    "candidate",
    "group",
    "description",
    "horizon_days",
    "period",
    "samples",
    "accuracy",
    "baseline_up",
    "baseline_momentum",
    "accuracy_diff_vs_up",
    "accuracy_ci_low",
    "accuracy_ci_high",
    "p_value_vs_up",
    "brier_score",
    "brier_skill_score",
    "brier_skill_p_value",
    "coverage_80",
    "coverage_ci_low",
    "coverage_ci_high",
    "effective_sample_size",
    "reason",
)


def ensemble_score(
    factors: dict[str, pd.Series],
    close: pd.Series,
    candidate: Candidate,
    *,
    horizon: int,
) -> Optional[pd.Series]:
    """集成候选的得分 = 各模式得分的逐日平均；单模式候选返回 None。"""
    if not candidate.is_ensemble:
        return None
    calendar = close.index
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    columns = [
        engine.composite_score(signals, horizon=horizon, mode=mode, include=candidate.include)
        for mode in candidate.score_modes
    ]
    return pd.concat(columns, axis=1).mean(axis=1)


def evaluate_candidate(
    factors: dict[str, pd.Series],
    close: pd.Series,
    candidate: Candidate,
    *,
    horizon: int,
    holdout_start=HOLDOUT_START,
) -> dict:
    """一个候选在一个尺度上的三列评估（开发期 / 留出期 / 全样本）。"""
    return backtest.evaluate_periods(
        factors,
        close,
        horizon=horizon,
        holdout_start=holdout_start,
        score_mode=candidate.score_modes[0],
        include=candidate.include,
        regression_window=candidate.regression_window,
        interval=candidate.interval,
        score=ensemble_score(factors, close, candidate, horizon=horizon),
    )


def _row(candidate: Candidate, horizon: int, period: str, evaluation) -> dict:
    metrics = evaluation.metrics or {}
    accuracy_ci = metrics.get("accuracy_ci95") or (None, None)
    coverage_ci = metrics.get("interval_coverage_ci95") or (None, None)
    return {
        "candidate": candidate.key,
        "group": candidate.group,
        "description": candidate.description,
        "horizon_days": horizon,
        "period": period,
        "samples": evaluation.sample_size,
        "accuracy": evaluation.accuracy,
        "baseline_up": evaluation.baseline_up_accuracy,
        "baseline_momentum": evaluation.baseline_momentum_accuracy,
        "accuracy_diff_vs_up": metrics.get("accuracy_diff_vs_up"),
        "accuracy_ci_low": accuracy_ci[0],
        "accuracy_ci_high": accuracy_ci[1],
        "p_value_vs_up": metrics.get("p_value_vs_up"),
        "brier_score": evaluation.brier_score,
        "brier_skill_score": metrics.get("brier_skill_score"),
        "brier_skill_p_value": metrics.get("brier_skill_p_value"),
        "coverage_80": metrics.get("interval_coverage_80"),
        "coverage_ci_low": coverage_ci[0],
        "coverage_ci_high": coverage_ci[1],
        "effective_sample_size": metrics.get("effective_sample_size"),
        "reason": metrics.get("reason"),
    }


def run_lab(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizons: tuple[int, ...] = HORIZONS,
    candidates: tuple[Candidate, ...] = CANDIDATES,
    holdout_start=HOLDOUT_START,
    progress: Optional[Callable[[int, int, Candidate], None]] = None,
) -> list[dict]:
    """跑完候选 × 尺度 × 三个样本期，返回长表行（含失败的尝试）。"""
    runs: dict[tuple, dict] = {}
    rows: list[dict] = []
    total = len(candidates)
    for index, candidate in enumerate(candidates, start=1):
        key = candidate.run_key()
        if key not in runs:
            runs[key] = {
                horizon: evaluate_candidate(
                    factors, close, candidate, horizon=horizon, holdout_start=holdout_start
                )
                for horizon in horizons
            }
        for horizon in horizons:
            for period in PERIODS:
                rows.append(_row(candidate, horizon, period, runs[key][horizon][period]))
        if progress is not None:
            progress(index, total, candidate)
    return rows


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _pct(value, digits: int = 1) -> str:
    return "—" if _missing(value) else f"{100.0 * value:.{digits}f}%"


def _number(value, digits: int = 3) -> str:
    return "—" if _missing(value) else f"{value:.{digits}f}"


def rule_flags(row: dict, baseline_row: dict) -> dict:
    """预注册硬规则的逐尺度判定（唯一实现见 ``preregistered.rule_flags``）。"""
    return preregistered.rule_flags(
        preregistered.RuleInput(
            accuracy_ci_low=row["accuracy_ci_low"],
            baseline_up=row["baseline_up"],
            accuracy_diff_vs_up=row["accuracy_diff_vs_up"],
            brier_skill_score=row["brier_skill_score"],
            brier_skill_p_value=row["brier_skill_p_value"],
            coverage_80=row["coverage_80"],
            baseline_coverage_80=baseline_row["coverage_80"],
        )
    )


def decide(rows: list[dict]) -> dict[str, dict]:
    """按预注册规则给出每个候选的裁决（留出期）。

    入选 = ≥3/5 个尺度过线，或目标尺度（250 日）过线且其它尺度对
    「永远看多」的命中率差不低于 −2pp。全部落空 → 保留 ``quant-v4``。
    """
    horizons = sorted({row["horizon_days"] for row in rows})
    index = {(row["candidate"], row["horizon_days"], row["period"]): row for row in rows}
    baseline_key = "B0" if ("B0", horizons[0], "holdout") in index else None
    results: dict[str, dict] = {}
    for candidate in _candidate_order(rows):
        flags = {}
        for horizon in horizons:
            key = (candidate.key, horizon, "holdout")
            baseline = index.get(("B0", horizon, "holdout")) if baseline_key else None
            flags[horizon] = (
                rule_flags(index[key], baseline)
                if key in index and baseline is not None
                else {"rule_1": False, "rule_2": False, "pass": False}
            )
        passed_scales = [horizon for horizon in horizons if flags[horizon]["pass"]]
        others_ok = preregistered.other_scales_ok(
            [
                index[(candidate.key, horizon, "holdout")]["accuracy_diff_vs_up"]
                for horizon in horizons
                if (candidate.key, horizon, "holdout") in index
            ],
            horizons=[
                horizon
                for horizon in horizons
                if (candidate.key, horizon, "holdout") in index
            ],
            target_scale=TARGET_SCALE,
        )
        target_ok = (
            TARGET_SCALE in flags
            and flags[TARGET_SCALE]["pass"]
            and (candidate.key, TARGET_SCALE, "holdout") in index
        )
        results[candidate.key] = {
            "flags": flags,
            "passed_scales": passed_scales,
            "target_ok": bool(target_ok),
            "others_ok": bool(others_ok),
            "selected": preregistered.selected(
                passed_scales, others_ok=bool(others_ok), target_scale=TARGET_SCALE
            ),
        }
    return results


def _candidate_order(rows: list[dict]) -> list[Candidate]:
    order: list[Candidate] = []
    for row in rows:
        candidate = CANDIDATES_BY_KEY.get(row["candidate"])
        if candidate is not None and candidate not in order:
            order.append(candidate)
    return order


def _verdict_cell(flag: dict) -> str:
    marks = [mark for mark, passed in (("①", flag["rule_1"]), ("②", flag["rule_2"])) if passed]
    return "".join(marks) or "—"


def format_markdown(
    rows: list[dict],
    *,
    horizons: tuple[int, ...] = HORIZONS,
    generated_at: Optional[str] = None,
) -> str:
    """报告主体：主表（开发 / 留出 / 全样本）+ 失败尝试 + 预注册裁决。"""
    index = {(row["candidate"], row["horizon_days"], row["period"]): row for row in rows}
    order = _candidate_order(rows)
    lines = [
        "# 量化研究台报告",
        "",
        "> 候选与判定为预注册（`docs/specs/2026-10-02-量化策略提升路线图.md` 6.1），",
        f"> 留出期起点 = {HOLDOUT_START.isoformat()}。报告呈现全部尝试，不做二次挑选。",
    ]
    if generated_at:
        lines.append(f"> 生成时间：{generated_at}")
    lines += [
        "",
        "## 主表（命中率三列）",
        "",
        "| 候选 | 组 | 尺度(日) | 开发期 | 留出期 | 全样本 | 留出样本 | 留出期 vs 看多 | p(>看多) | Brier 技能 | 覆盖率(留出) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for candidate in order:
        for horizon in horizons:
            development = index[(candidate.key, horizon, "development")]
            holdout = index[(candidate.key, horizon, "holdout")]
            full = index[(candidate.key, horizon, "full")]
            diff = holdout["accuracy_diff_vs_up"]
            difference = "—" if _missing(diff) else f"{100.0 * diff:+.1f}pp"
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    candidate.key,
                    GROUP_LABELS.get(candidate.group, candidate.group),
                    horizon,
                    _pct(development["accuracy"]),
                    _pct(holdout["accuracy"]),
                    _pct(full["accuracy"]),
                    holdout["samples"],
                    difference,
                    "—" if _missing(holdout["p_value_vs_up"]) else f"{holdout['p_value_vs_up']:.3f}",
                    _number(holdout["brier_skill_score"]),
                    _pct(holdout["coverage_80"]),
                )
            )

    failures = [row for row in rows if _missing(row["accuracy"])]
    lines += ["", "## 失败的尝试（样本不足 / 数据缺失）", ""]
    if not failures:
        lines.append("无：所有候选 × 尺度都有可评估样本。")
    else:
        lines += ["| 候选 | 尺度(日) | 样本期 | 说明 |", "|---|---|---|---|"]
        for row in failures:
            lines.append(
                f"| {row['candidate']} | {row['horizon_days']} | "
                f"{PERIOD_LABELS.get(row['period'], row['period'])} | {row['reason'] or '—'} |"
            )

    verdicts = decide(rows)
    lines += [
        "",
        "## 预注册裁决（留出期）",
        "",
        "判定：① 命中率 95% 自助下界 > 永远看多；② 命中率不劣化 ≤1pp 且 Brier 技能分",
        "显著为正（HAC DM，p<0.05）且覆盖率更接近 80%。入选 = ≥3/5 尺度成立，或 250 日",
        "成立且其它尺度相对永远看多不恶化 ≤2pp。",
        "",
        "| 候选 | 逐尺度(①/②) | 过线尺度数 | 250 日 | 其它尺度 ≤2pp | 结论 |",
        "|---|---|---|---|---|---|",
    ]
    for candidate in order:
        verdict = verdicts[candidate.key]
        flags = "；".join(
            f"{horizon}:{_verdict_cell(verdict['flags'][horizon])}" for horizon in sorted(verdict["flags"])
        )
        conclusion = "入选" if verdict["selected"] else "未过线（保留 v4）"
        lines.append(
            f"| {candidate.key} | {flags} | {len(verdict['passed_scales'])}/{len(verdict['flags'])} | "
            f"{'是' if verdict['target_ok'] else '否'} | {'是' if verdict['others_ok'] else '否'} | {conclusion} |"
        )
    selected = [key for key, verdict in verdicts.items() if verdict["selected"] and key != "B0"]
    lines += [
        "",
        (
            f"**裁决：候选 {', '.join(selected)} 过线**（落地前需按 spec 复核）。"
            if selected
            else "**裁决：无候选过线 → 保留 `quant-v4`，页面与文档标注「无统计优势」。**"
        ),
        "",
        "## 候选口径",
        "",
        "| 候选 | 组 | 口径 |",
        "|---|---|---|",
    ]
    for candidate in order:
        lines.append(
            f"| {candidate.key} | {GROUP_LABELS.get(candidate.group, candidate.group)} | {candidate.description} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ROW_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_horizons(value: Optional[str]) -> tuple[int, ...]:
    if not value:
        return HORIZONS
    horizons = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    unknown = [horizon for horizon in horizons if horizon not in HORIZONS]
    if unknown:
        raise argparse.ArgumentTypeError(f"未知尺度：{unknown}；可选 {list(HORIZONS)}")
    return horizons


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="量化研究台：预注册候选 × 尺度 × 三个样本期")
    parser.add_argument("--out", type=Path, default=None, help="输出目录（quant_lab.md / quant_lab.csv）")
    parser.add_argument("--horizons", default=None, help="逗号分隔的尺度；默认 " + ",".join(map(str, HORIZONS)))
    parser.add_argument("--group", action="append", default=None, help="只跑某一组候选（可重复）")
    parser.add_argument("--from-db", action="store_true", help="从项目数据库读取（默认行为，显式写法）")
    parser.add_argument("--holdout-start", default=HOLDOUT_START.isoformat())
    args = parser.parse_args(argv)

    try:
        horizons = _parse_horizons(args.horizons)
    except argparse.ArgumentTypeError as error:
        print(str(error), file=sys.stderr)
        return 2

    selected = CANDIDATES
    if args.group:
        wanted = set(args.group)
        selected = tuple(candidate for candidate in CANDIDATES if candidate.group in wanted)
        if not selected:
            print(f"没有匹配的候选组：{sorted(wanted)}；可选 {sorted(GROUP_LABELS)}", file=sys.stderr)
            return 2

    from app.database import SessionLocal
    from app.services.quant.service import load_panel

    try:
        with SessionLocal() as db:
            factors, close = load_panel(db)
    except Exception as error:  # 数据库不可用 → 如实报告，不退回合成数据
        print(f"数据不可用：{error}", file=sys.stderr)
        return 2
    if close is None or close.empty:
        print("数据不可用：库里没有黄金价格序列（先同步数据，再跑研究台）", file=sys.stderr)
        return 2
    if not factors:
        print("数据不可用：库里没有因子序列（先同步数据，再跑研究台）", file=sys.stderr)
        return 2

    def progress(index: int, total: int, candidate: Candidate) -> None:
        print(f"[{index}/{total}] {candidate.key} {candidate.description}", file=sys.stderr, flush=True)

    rows = run_lab(
        factors,
        close,
        horizons=horizons,
        candidates=selected,
        holdout_start=args.holdout_start,
        progress=progress,
    )
    markdown = format_markdown(
        rows,
        horizons=horizons,
        generated_at=timeutil.now_iso(),
    )
    print(markdown)
    if args.out is not None:
        write_markdown(markdown, args.out / "quant_lab.md")
        write_csv(rows, args.out / "quant_lab.csv")
        print(f"已写出 {args.out / 'quant_lab.md'} 与 {args.out / 'quant_lab.csv'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
