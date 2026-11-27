"""路线规划 · 交互式候选方案构建器（供网页端选择、记录与展开 9 项具体能力差）。

为全部 9 位角色生成：
  - 旧基准路线（old_baseline）
  - 新纯以终为始最优路线（new_best）
  - 若含提前 S/L 提醒，同时生成不赌公式的稳过备选（safe_fallback）
  - 所有方案均完整展开相对旧基准的 9 项具体能力差（HP/力/魔/速/技/防/魔防/幸/魅）、转职保底明细、
    金币/训练/精通/净值差，以及每个额外职业的边际 9 项能力差。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RNG_DIR = ROOT / "levelup" / "rng"
if str(RNG_DIR) not in sys.path:
    sys.path.insert(0, str(RNG_DIR))

from fe_growth import STATS  # noqa: E402
from planner import _TIER, plan_all  # noqa: E402
import run_plans as R  # noqa: E402
from .objective import DEFAULT_TIER_POLICIES  # noqa: E402
from .two_stage_planner import (  # noqa: E402
    EvaluatedPlan,
    exam_margin,
    plan_two_stage,
    prepare_goal_first_planner,
)

# Yizhuo 已确认按新目标函数更新的角色（网页上默认预选 new_best，但仍保留旧基准对照并可随时改选）
CONFIRMED_NEW_BEST = {"伊欧", "奇洛伊卡", "米迦艾拉", "杨界"}


def _fmt_stat_diff(vec: list[int] | tuple[int, ...]) -> str:
    parts = [f"{STATS[i]}{v:+d}" for i, v in enumerate(vec) if v]
    return "、".join(parts) if parts else "9 项能力完全相同"


def _fmt_promo_lifts(lifts: dict[int, list[tuple[int, int, int]]]) -> list[str]:
    out = []
    for st, items in sorted(lifts.items()):
        for i, o, n in items:
            out.append(f"{STATS[i]} {o}→{n} (+{n - o})")
    return out


def _describe_exams(p: Any, acts: tuple[tuple[str, str], ...]) -> list[dict[str, Any]]:
    exams = []
    lv = p.level
    lifts = p.floor_lifts(acts)
    for st, (a, c) in enumerate(acts):
        if a == "升级":
            lv += 1
            continue
        if c == "跳过":
            continue
        ok, pct, margin, roll, is_certain = exam_margin(p, st, c, lv)
        tr_rk = (getattr(p, "exam_train_ranks", {}) or {}).get(c, 0)
        tr_sk = (getattr(p, "exam_train", {}) or {}).get(c, []) if tr_rk else []
        fl = [f"{STATS[i]} {o}→{n}" for i, o, n in lifts.get(st, [])]
        exams.append({
            "step": st + 1,
            "lv": lv,
            "cls": c,
            "tier": _TIER.get(c, "中级"),
            "pct": pct,
            "roll": round(roll, 2),
            "margin": margin,
            "isCertain": is_certain,
            "trainRanks": tr_rk,
            "trainSkills": list(tr_sk),
            "promoFloor": fl,
        })
    return exams


def _title_from_exams(exams: list[dict[str, Any]], skips: int) -> str:
    parts = [f"Lv{e['lv']} 考{e['cls']}" for e in exams]
    if skips:
        parts.append(f"跳过 {skips} 次")
    return " + ".join(parts) if parts else "不考新职业"


def _pack_option(
    opt_id: str,
    tag: str,
    p: Any,
    acts: tuple[tuple[str, str], ...],
    stat_vec: tuple[int, ...] | list[int],
    stat_w: float,
    promo_floor_w: float,
    gold: int,
    train_ranks: int,
    mastery_levels: int,
    net: float,
    objective: float,
    baseline_summary: dict[str, Any],
    sl_warnings: list[dict[str, Any]] | None = None,
    marginals: list[dict[str, Any]] | None = None,
    summary_note: str = "",
) -> dict[str, Any]:
    skips = sum(1 for a, c in acts if a == "考试" and c == "跳过")
    exams = _describe_exams(p, acts)
    lifts = p.floor_lifts(acts)
    sv = list(stat_vec)
    bv = baseline_summary["statVec"]
    sdiff = [sv[i] - bv[i] for i in range(9)]
    end_lv = p.level + sum(1 for a, _ in acts if a == "升级")

    return {
        "id": opt_id,
        "tag": tag,
        "title": _title_from_exams(exams, skips),
        "summaryNote": summary_note,
        "exams": exams,
        "skips": skips,
        "endLevel": end_lv,
        "statVec": sv,
        "rawPoints": sum(sv),
        "statWeighted": round(stat_w, 1),
        "promoFloorWeighted": round(promo_floor_w, 1),
        "promoFloorDetails": _fmt_promo_lifts(lifts),
        "gold": gold,
        "trainRanks": train_ranks,
        "masteryLevels": mastery_levels,
        "net": round(net, 1),
        "objective": round(objective, 2),
        "slWarnings": sl_warnings or [],
        "marginals": marginals or [],
        "diffVsBaseline": {
            "statDiff": sdiff,
            "statDiffText": _fmt_stat_diff(sdiff),
            "pts": sum(sv) - baseline_summary["rawPoints"],
            "statW": round(stat_w - baseline_summary["statWeighted"], 1),
            "promoFloorW": round(promo_floor_w - baseline_summary["promoFloorWeighted"], 1),
            "gold": gold - baseline_summary["gold"],
            "trainRanks": train_ranks - baseline_summary["trainRanks"],
            "masteryLevels": mastery_levels - baseline_summary["masteryLevels"],
            "net": round(net - baseline_summary["net"], 1),
        },
    }


def _pack_evaluated(
    opt_id: str,
    tag: str,
    p: Any,
    ev: EvaluatedPlan,
    baseline_summary: dict[str, Any],
    marginals: list[dict[str, Any]] | None = None,
    summary_note: str = "",
) -> dict[str, Any]:
    b = ev.breakdown
    warns = [
        {
            "step": w.step + 1,
            "level": w.level,
            "cls": w.cls,
            "estPct": w.est_pct,
            "roll": w.roll,
            "margin": w.margin,
            "message": w.message,
        }
        for w in ev.sl_warnings
    ]
    return _pack_option(
        opt_id=opt_id,
        tag=tag,
        p=p,
        acts=ev.actions,
        stat_vec=b.stat_vector,
        stat_w=b.stat_weighted + b.physique_bonus,
        promo_floor_w=b.promo_floor_weighted,
        gold=b.gold,
        train_ranks=b.train_ranks,
        mastery_levels=b.mastery_levels,
        net=b.net_without_mastery,
        objective=b.objective,
        baseline_summary=baseline_summary,
        sl_warnings=warns,
        marginals=marginals,
        summary_note=summary_note,
    )


def build_route_proposals() -> list[dict[str, Any]]:
    """生成全 9 位角色的交互式候选方案对照（含 9 项具体能力差、转职保底明细、边际收益与 S/L 预警）。"""
    proposals: list[dict[str, Any]] = []

    for name in R.ORDER:
        if name not in R.OWNED:
            continue
        tier = R.tier_of(name)
        pol = DEFAULT_TIER_POLICIES[tier]
        _, lv = R.current_state(name)
        target = max(R.HORIZON_MIN_LEVEL, lv + R.HORIZON_MIN_STEPS)

        # 1) 旧基准路线（当前 golden 基线）
        p_old = R.make_planner(name, target)
        plans, k = plan_all(p_old, R.MAX_EXAMS)
        old_plan = plans[k]
        old_acts = tuple((r.action, r.cls) for r in old_plan.rows)
        old_lifts = p_old.floor_lifts(old_acts)
        old_fl_g = [0] * 9
        for ls in old_lifts.values():
            for i, o, n in ls:
                old_fl_g[i] += n - o
        old_g = [0] * 9
        for r in old_plan.rows:
            if r.action == "升级":
                old_g = [a + b for a, b in zip(old_g, r.gains)]
        old_tot_g = [a + b for a, b in zip(old_g, old_fl_g)]
        old_fl_w = sum(p_old.weights[i] * old_fl_g[i] for i in range(9))
        old_gold = sum(
            p_old.permit_gold["初级"] if c == "跳过" else p_old.permit_gold.get(_TIER.get(c, "中级"), 500)
            for a, c in old_acts
            if a == "考试"
        )
        old_tr = p_old.train_ranks(old_acts)
        old_net = p_old.plan_net(old_acts, old_plan.total, old_gold)
        old_exam_set = {c for a, c in old_acts if a == "考试" and c != "跳过"}
        old_mastery = sum(1 for a, c in old_acts if a == "升级" and c in old_exam_set)
        old_obj = old_net + old_mastery * pol.mastery_pts_per_lv

        baseline_summary = {
            "statVec": old_tot_g,
            "rawPoints": sum(old_tot_g),
            "statWeighted": float(old_plan.total),
            "promoFloorWeighted": float(old_fl_w),
            "gold": old_gold,
            "trainRanks": old_tr,
            "masteryLevels": old_mastery,
            "net": float(old_net),
        }

        # 2) 新纯以终为始两阶段规划
        p_new, _ = prepare_goal_first_planner(name, target)
        res = plan_two_stage(p_new, tier, include_timing_matrix=False)
        best = res.best
        same_as_old = (
            [(i, c) for i, (a, c) in enumerate(best.actions) if a == "考试"]
            == [(i, c) for i, (a, c) in enumerate(old_acts) if a == "考试"]
            and list(best.breakdown.stat_vector) == old_tot_g
        )

        marginals_packed = [
            {
                "cls": m.cls,
                "isRequired": m.is_required,
                "usedLevels": m.used_levels,
                "statDiff": list(m.delta_stat_vector),
                "statDiffText": _fmt_stat_diff(m.delta_stat_vector),
                "deltaPts": m.delta_pts,
                "deltaStatW": round(m.delta_stat_w, 1),
                "deltaPromoFloorW": round(m.delta_promo_floor_w, 1),
                "deltaGold": m.delta_gold,
                "deltaTrainRanks": m.delta_train_ranks,
                "deltaMasteryLv": m.delta_mastery_lv,
                "deltaNet": round(m.delta_net, 1),
                "deltaObjective": round(m.delta_objective, 2),
            }
            for m in res.marginal_gains
        ]

        options: list[dict[str, Any]] = []
        if same_as_old:
            options.append(
                _pack_evaluated(
                    "new_best",
                    "新旧完全一致",
                    p_new,
                    best,
                    baseline_summary,
                    marginals=marginals_packed,
                    summary_note="新纯目标函数与当前路线结果完全一致，无需改动。",
                )
            )
            default_pick: str | None = "new_best"
            status = "identical"
        else:
            is_confirmed = name in CONFIRMED_NEW_BEST
            best_tag = (
                "新最优（已确认默认）"
                if is_confirmed
                else ("新最优（⚠️ 需提前 S/L 实测）" if best.sl_warnings else "新最优（纯以终为始）")
            )
            options.append(
                _pack_evaluated(
                    "new_best",
                    best_tag,
                    p_new,
                    best,
                    baseline_summary,
                    marginals=marginals_packed,
                    summary_note="按统一目标函数 J(π) 算出的全局最优路线。",
                )
            )
            if res.safe_fallback is not None and res.safe_fallback.exam_at != best.exam_at:
                options.append(
                    _pack_evaluated(
                        "safe_fallback",
                        "稳过备选（无需赌公式）",
                        p_new,
                        res.safe_fallback,
                        baseline_summary,
                        summary_note="若提前 S/L 实测不通过并校准公式后，自动切换的稳过次优路线。",
                    )
                )
            options.append(
                _pack_option(
                    opt_id="old_baseline",
                    tag="保留旧路线",
                    p=p_old,
                    acts=old_acts,
                    stat_vec=old_tot_g,
                    stat_w=float(old_plan.total),
                    promo_floor_w=float(old_fl_w),
                    gold=old_gold,
                    train_ranks=old_tr,
                    mastery_levels=old_mastery,
                    net=float(old_net),
                    objective=float(old_obj),
                    baseline_summary=baseline_summary,
                    summary_note="当前页面正在执行的旧规划器基准路线。",
                )
            )
            default_pick = "new_best" if is_confirmed else None
            status = "confirmed_default" if is_confirmed else "pending"

        proposals.append({
            "name": name,
            "tier": tier,
            "level": lv,
            "target": target,
            "seeds": p_new.n_seeds,
            "weights": list(p_new.weights),
            "defaultPick": default_pick,
            "status": status,  # identical | confirmed_default | pending
            "options": options,
        })

    tier_order = {"P0": 0, "P1": 1, "P2": 2}
    proposals.sort(key=lambda pr: (tier_order.get(pr["tier"], 9), R.ORDER.index(pr["name"])))
    return proposals
