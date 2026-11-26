"""路线规划 · 两阶段全局最优规划器（Two-Stage Goal-First Planner）。

严格按照「先定职业集合 → 再找全局最优考试时机与跳过」两阶段解耦设计：

  Stage 1（选职业集合 T）：
    - 输入：已有职业 owned、必考职业 required、合法候选池 candidates、档位政策 policy。
    - 对每个候选职业组合 T（0 / 1 / 2 个额外职业，满足中级达标要求），调用 Stage 2 求该集合在固定乱数预算 N 内的
      全局最优时机方案，按统一目标函数 J(π) 比较。
    - 彻底消除「用旧职业下的第一个坏乱数评估新职业」的近视幻觉（例如努蒂奴 step 7、乌尔坦德 step 9）。

  Stage 2（固定职业集合 T，找最优考试时机 + 跳过）：
    - 枚举 T 中所有职业的合法考试步组合 (t_1, t_2, ...)（满足不踩保留种子、严格通过判定、且估计成功率余量 >= min_est_margin）。
    - 在每个考试步组合下执行确定性步进模拟（含均衡、体格、额外纯跳过规则、保底计算）。
    - 按统一目标值 J(π) 选出全局最优时机，并产出每场考试相对其他候选时机的区间 [t1, t2] 四项拆解与 Good/Bad 标签。
"""
from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RNG_DIR = ROOT / "levelup" / "rng"
if str(RNG_DIR) not in sys.path:
    sys.path.insert(0, str(RNG_DIR))

from fe_growth import STATS  # noqa: E402
from planner import Planner, _TIER, _TIER_RANK  # noqa: E402
from .objective import (  # noqa: E402
    DEFAULT_TIER_POLICIES,
    ObjectiveBreakdown,
    TierPolicy,
    TimingIntervalDiff,
    classify_timing_choice,
)


@dataclass
class EvaluatedPlan:
    targets: tuple[str, ...]
    exam_at: dict[int, str]
    actions: tuple[tuple[str, str], ...]
    breakdown: ObjectiveBreakdown
    min_exam_margin: float | None
    notes: dict[Any, Any]


@dataclass
class TwoStageResult:
    name: str
    policy: TierPolicy
    best: EvaluatedPlan
    timing_candidates: dict[str, list[TimingIntervalDiff]]
    class_set_ranking: list[EvaluatedPlan]


def exam_margin(p: Planner, step: int, cls: str, lv: int) -> tuple[bool, float | None, bool]:
    """返回 (是否通过, 成功率余量 pct - roll, 是否确定无拟合误差)。
    游戏实测读数（exam_chance）或满概率（pct >= 100）不存在公式拟合误差，均视为确定。"""
    roll = p.exam_value(step)
    is_observed = cls in (p.exam_chance or {})
    pct = p.exam_pct(cls, lv)
    ok = p.exam_ok(step, cls, lv)
    is_certain = is_observed or (pct is not None and pct >= 100)
    if pct is None:
        return ok, None, is_certain
    return ok, round(pct - roll, 2), is_certain


def simulate_fixed_exams(
    p: Planner,
    exam_at: dict[int, str],
    policy: TierPolicy,
    targets: tuple[str, ...],
    allow_skips: bool = True,
) -> EvaluatedPlan | None:
    """无副作用的确定性模拟：固定 exam_at={step: cls}，其余步按均衡+体格选最佳已有职业，
    若满足本档跳过规则且不在保留种子中则执行纯跳过（或 skip_take）。"""
    owned = list(p.owned)
    stats = list(p.stats) if p.stats else None
    cur_str = p.str_start
    no_skip_seeds = set(getattr(p, "no_skip_seeds", ()) or ())
    skip_take = tuple(getattr(p, "skip_take", ()) or ())
    pg = getattr(p, "permit_gold", {"初级": 300, "中级": 500, "上级": 3000})

    acts: list[tuple[str, str]] = []
    notes: dict[Any, Any] = {}
    done = 0
    gold = 0
    stat_w = 0
    phys_w = 0
    g_sum = [0] * 9
    min_margin: float | None = None

    for step in range(p.n_seeds):
        lv = p.level + done
        seed = p.seed_at(step)
        keep = seed in no_skip_seeds

        if step in exam_at:
            cls = exam_at[step]
            if keep or cls in owned:
                return None
            ok, margin, is_certain = exam_margin(p, step, cls, lv)
            if not ok:
                return None
            if not is_certain and margin is not None and margin < policy.min_est_margin:
                return None
            if not is_certain and margin is not None:
                min_margin = margin if min_margin is None else min(min_margin, margin)
            owned.append(cls)
            gold += pg.get(_TIER.get(cls, "中级"), 500)
            acts.append(("考试", cls))
            continue

        # 选最佳已有职业（含均衡权重与体格加分）
        w, why = p.balanced_weights(stats) if stats else ([float(x) for x in p.weights], "")
        tie = p._tie_terms()

        def val(c: str) -> float:
            g = p.result(step, lv, c)[1]
            return (
                sum(a * b for a, b in zip(g, w))
                + (p.str_gain_bonus(cur_str, g) if cur_str is not None else 0)
                + tie(c)
            )

        best_c = max(owned, key=val)
        sbest = val(best_c)

        want_skip = False
        if allow_skips and not keep:
            fut = p._future15(step, lv, tuple(owned), tuple(w), cur_str)
            c1 = sbest <= policy.skip_cap + 1e-6
            c2 = sbest <= (sum(fut) / len(fut)) * (1 - policy.skip_pct) + 1e-6
            want_skip = (c1 or c2) if policy.skip_or else (c1 and c2)

        if want_skip:
            skip_cls = "跳过"
            for x in skip_take:
                if x not in owned and p.exam_ok(step, x, lv):
                    skip_cls = x
                    break
            if skip_cls != "跳过":
                owned.append(skip_cls)
                gold += pg.get(_TIER.get(skip_cls, "中级"), 500)
                acts.append(("考试", skip_cls))
            else:
                gold += pg["初级"]
                acts.append(("考试", "跳过"))
            continue

        sc, g = p.result(step, lv, best_c)
        bonus = p.str_gain_bonus(cur_str, g) if cur_str is not None else 0
        stat_w += sc
        phys_w += bonus
        g_sum = [a + b for a, b in zip(g_sum, g)]
        if stats is not None:
            stats = [a + b for a, b in zip(stats, g)]
        if cur_str is not None:
            cur_str += g[1]
        acts.append(("升级", best_c))
        done += 1

    acts_t = tuple(acts)
    used = {c for a, c in acts_t if a == "升级"}
    skip_take_set = set(skip_take)
    # 所有目标职业（含为精通而必考的职业，仅 skip_take 除外）考完后至少要用来升 1 级，避免拖到最后一步拿不到精通
    for c in targets:
        if c not in skip_take_set and c not in used:
            return None

    lifts = p.floor_lifts(acts_t)
    floor_g = [0] * 9
    for ls in lifts.values():
        for i, old_v, new_v in ls:
            floor_g[i] += new_v - old_v
    floor_w = sum(p.weights[i] * floor_g[i] for i in range(9))
    tot_g = tuple(a + b for a, b in zip(g_sum, floor_g))

    target_set = set(targets)
    mastery_lv = sum(1 for a, c in acts_t if a == "升级" and c in target_set)
    train_rk = p.train_ranks(acts_t)

    bd = ObjectiveBreakdown(
        stat_weighted=stat_w,
        physique_bonus=phys_w,
        floor_weighted=floor_w,
        mastery_levels=mastery_lv,
        mastery_bonus=round(mastery_lv * policy.mastery_pts_per_lv, 3),
        gold=gold,
        gold_penalty=round(gold / policy.gold_per_pt, 3),
        train_ranks=train_rk,
        train_penalty=round(train_rk * policy.train_pts_per_rank, 3),
        raw_points=sum(tot_g),
        stat_vector=tot_g,
        end_level=p.level + done,
        skips=sum(1 for a, c in acts_t if a == "考试" and c == "跳过"),
    )
    return EvaluatedPlan(
        targets=targets,
        exam_at=dict(exam_at),
        actions=acts_t,
        breakdown=bd,
        min_exam_margin=min_margin,
        notes=notes,
    )


def compare_timing_interval(
    p: Planner,
    cls: str,
    early_plan: EvaluatedPlan,
    late_plan: EvaluatedPlan,
    policy: TierPolicy,
) -> TimingIntervalDiff:
    """精确拆解早考 t1 vs 晚考 t2 (t1 < t2) 在区间 [t1, t2] 与区间外 (> t2) 的差异（早考减晚考）。"""
    t1 = next(k for k, v in early_plan.exam_at.items() if v == cls)
    t2 = next(k for k, v in late_plan.exam_at.items() if v == cls)
    if t1 > t2:
        t1, t2 = t2, t1
        early_plan, late_plan = late_plan, early_plan

    def walk_gains(acts: tuple[tuple[str, str], ...]) -> list[tuple[str, str, int, tuple[int, ...] | None]]:
        out, lv = [], p.level
        for st, (a, c) in enumerate(acts):
            if a == "升级":
                out.append((a, c, lv, p.result(st, lv, c)[1]))
                lv += 1
            else:
                out.append((a, c, lv, None))
        return out

    we, wl = walk_gains(early_plan.actions), walk_gains(late_plan.actions)
    lv1, lv2 = we[t1][2], wl[t2][2]

    swap_g = [0] * 9
    interval_g = [0] * 9
    post_g = [0] * 9

    for k in range(p.n_seeds):
        ge = we[k][3] or (0,) * 9
        gl = wl[k][3] or (0,) * 9
        dg = [a - b for a, b in zip(ge, gl)]
        if k == t1 or k == t2:
            swap_g = [a + b for a, b in zip(swap_g, dg)]
        elif t1 < k < t2:
            interval_g = [a + b for a, b in zip(interval_g, dg)]
        elif k > t2:
            post_g = [a + b for a, b in zip(post_g, dg)]

    def floor_vec(acts: tuple[tuple[str, str], ...]) -> list[int]:
        v = [0] * 9
        for ls in p.floor_lifts(acts).values():
            for i, o, n in ls:
                v[i] += n - o
        return v

    fe, fl = floor_vec(early_plan.actions), floor_vec(late_plan.actions)
    df = [a - b for a, b in zip(fe, fl)]

    wsum = lambda vec: sum(w * x for w, x in zip(p.weights, vec))
    swap_pts, swap_w = sum(swap_g), wsum(swap_g)
    int_pts, int_w = sum(interval_g), wsum(interval_g)
    post_pts, post_w = sum(post_g), wsum(post_g)
    fl_pts, fl_w = sum(df), wsum(df)

    m_early = sum(1 for a, c in early_plan.actions if a == "升级" and c == cls)
    m_late = sum(1 for a, c in late_plan.actions if a == "升级" and c == cls)
    mastery_delta = m_early - m_late
    gold_delta = early_plan.breakdown.gold - late_plan.breakdown.gold

    _, em, e_cert = exam_margin(p, t1, cls, lv1)
    _, lm, l_cert = exam_margin(p, t2, cls, lv2)
    verdict, reason = classify_timing_choice(
        total_w=swap_w + int_w + post_w + fl_w,
        total_pts=swap_pts + int_pts + post_pts + fl_pts,
        gold_delta=gold_delta,
        mastery_lv_delta=mastery_delta,
        early_margin=None if e_cert else em,
        min_est_margin=policy.min_est_margin,
    )

    return TimingIntervalDiff(
        cls=cls,
        t_early=t1,
        t_late=t2,
        lv_early=lv1,
        lv_late=lv2,
        seed_swap_pts=swap_pts,
        seed_swap_w=swap_w,
        interval_class_pts=int_pts,
        interval_class_w=int_w,
        post_carryover_pts=post_pts,
        post_carryover_w=post_w,
        floor_pts=fl_pts,
        floor_w=fl_w,
        mastery_lv_delta=mastery_delta,
        gold_delta=gold_delta,
        early_margin=em,
        late_margin=lm,
        verdict=verdict,
        reason=reason,
    )


def optimize_exam_timings(
    p: Planner,
    targets: tuple[str, ...],
    policy: TierPolicy,
    step_hints: dict[str, list[int]] | None = None,
) -> EvaluatedPlan | None:
    """Stage 2：固定职业集合 targets，全局搜索最优考试时机组合 (t_1, ..., t_m)。
    - 单职业：严格穷举窗口内全部合法步（O(N)）。
    - 多职业：先用各职业单职业前 top-6 候选步做笛卡尔积求初解，再做逐职业全窗口坐标上升至收敛。"""
    if not targets:
        return simulate_fixed_exams(p, {}, policy, ())

    n = p.n_seeds
    no_skip = set(getattr(p, "no_skip_seeds", ()) or ())
    all_steps: dict[str, list[int]] = {}
    for c in targets:
        steps = []
        for st in range(n):
            if p.seed_at(st) in no_skip:
                continue
            max_lv = p.level + st
            ok, margin, is_obs = exam_margin(p, st, c, max_lv)
            if ok and (is_obs or margin is None or margin >= policy.min_est_margin):
                steps.append(st)
        if not steps:
            return None
        all_steps[c] = steps

    if len(targets) == 1:
        c = targets[0]
        best: EvaluatedPlan | None = None
        for st in all_steps[c]:
            ev = simulate_fixed_exams(p, {st: c}, policy, targets)
            if ev is not None and (best is None or _rank_key(ev) > _rank_key(best)):
                best = ev
        return best

    # 多职业：用提示候选步（每职业最多 6 步）做网格搜索，再做全窗口坐标上升精修
    grid_lists = []
    for c in targets:
        hint = (step_hints or {}).get(c)
        if hint:
            picked = [st for st in hint if st in all_steps[c]][:6]
            grid_lists.append(picked or all_steps[c][:6])
        else:
            grid_lists.append(all_steps[c][:8])

    best = None
    for combo in itertools.product(*grid_lists):
        if len(set(combo)) != len(combo):
            continue
        ev = simulate_fixed_exams(p, {st: c for st, c in zip(combo, targets)}, policy, targets)
        if ev is not None and (best is None or _rank_key(ev) > _rank_key(best)):
            best = ev

    if best is None:
        return None

    # 坐标上升：轮流对每个职业扫描全部合法步直至全局不动点
    improved = True
    while improved:
        improved = False
        for c in targets:
            others = {k: v for k, v in best.exam_at.items() if v != c}
            for st in all_steps[c]:
                if st in others or best.exam_at.get(st) == c:
                    continue
                ev = simulate_fixed_exams(p, {**others, st: c}, policy, targets)
                if ev is not None and _rank_key(ev) > _rank_key(best):
                    best = ev
                    improved = True
    return best


def _rank_key(ev: EvaluatedPlan) -> tuple[float, float, int, float, int]:
    """统一排序键：目标函数 J(π) → 净值 → 总点数 → 最小余量（更稳）→ 更少金币。"""
    return (
        round(ev.breakdown.objective, 4),
        round(ev.breakdown.net_without_mastery, 4),
        ev.breakdown.raw_points,
        round(ev.min_exam_margin if ev.min_exam_margin is not None else 100.0, 2),
        -ev.breakdown.gold,
    )


def _satisfies_mid(p: Planner, targets: tuple[str, ...]) -> bool:
    if not getattr(p, "require_mid", False):
        return True
    return any(_TIER_RANK.get(_TIER.get(c, ""), 0) >= 2 for c in targets)


def _top_steps_for_class(p: Planner, cls: str, policy: TierPolicy) -> list[int]:
    """评估单职业在窗口内每个合法步的目标值，按降序返回最优候选步列表（供多职业搜索剪枝）。"""
    no_skip = set(getattr(p, "no_skip_seeds", ()) or ())
    scored: list[tuple[tuple[float, float, int, float, int], int]] = []
    for st in range(p.n_seeds):
        if p.seed_at(st) in no_skip:
            continue
        ev = simulate_fixed_exams(p, {st: cls}, policy, (cls,))
        if ev is not None:
            scored.append((_rank_key(ev), st))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [st for _, st in scored]


def plan_two_stage(
    p: Planner,
    tier: str,
    policies: dict[str, TierPolicy] | None = None,
) -> TwoStageResult:
    """运行完整的两阶段规划：
      Stage 1: 评估单职业（并记录各职业最优候选步）→ 仅对前 6 名高潜力职业组合 2 职业
      Stage 2: 对每个候选集合 T 求全局最优考试时机，并用统一目标函数选出最优 T* 与时机对照表。
    """
    policy = (policies or DEFAULT_TIER_POLICIES)[tier]
    req = tuple(dict.fromkeys(p.required))
    cands = [c for c in p.exam_options if c not in req]

    # 预计算每个相关职业的单职业候选步排序（供多职业网格搜索剪枝）
    step_hints: dict[str, list[int]] = {}
    for c in req:
        step_hints[c] = _top_steps_for_class(p, c, policy)

    evaluated: list[EvaluatedPlan] = []
    # 0 额外职业（仅必考）
    if _satisfies_mid(p, req):
        ev0 = optimize_exam_timings(p, req, policy, step_hints)
        if ev0 is not None:
            evaluated.append(ev0)

    # 1 个额外职业：全量枚举所有合法候选
    single_ranked: list[tuple[EvaluatedPlan, str]] = []
    if policy.max_optional_classes >= 1:
        for c in cands:
            step_hints[c] = _top_steps_for_class(p, c, policy)
            tg = req + (c,)
            ev = optimize_exam_timings(p, tg, policy, step_hints)
            if ev is not None:
                single_ranked.append((ev, c))
                if _satisfies_mid(p, tg):
                    evaluated.append(ev)
        single_ranked.sort(key=lambda x: _rank_key(x[0]), reverse=True)

    # 2 个额外职业：对单职业排名前 6 的高潜力候选做两两组合（兼顾完备性与速度）
    if policy.max_optional_classes >= 2 and single_ranked:
        top_cands = [c for _, c in single_ranked[:6]]
        for c1, c2 in itertools.combinations(top_cands, 2):
            tg = req + (c1, c2)
            if not _satisfies_mid(p, tg):
                continue
            ev = optimize_exam_timings(p, tg, policy, step_hints)
            if ev is not None:
                evaluated.append(ev)

    evaluated.sort(key=_rank_key, reverse=True)
    if not evaluated:
        raise RuntimeError(f"{p.name} 找不到任何满足硬约束的合法方案")

    # 简洁性门槛：只有比「少考 1 个非必考职业」的子方案目标值增量 >= min_class_gain，才保留多出来的额外职业
    best = evaluated[0]
    by_set = {frozenset(e.targets): e for e in evaluated}
    while True:
        extras = [c for c in best.targets if c not in req]
        if not extras:
            break
        pruned = None
        for c in extras:
            sub_key = frozenset(t for t in best.targets if t != c)
            sub = by_set.get(sub_key)
            if sub is not None and (best.breakdown.objective - sub.breakdown.objective) < policy.min_class_gain - 1e-6:
                if pruned is None or _rank_key(sub) > _rank_key(pruned):
                    pruned = sub
        if pruned is None:
            break
        best = pruned

    # 为最佳方案里的每场考试生成「早考 vs 晚考」区间拆解表（含压线风险时机，便于人工复核）
    timing_candidates: dict[str, list[TimingIntervalDiff]] = {}
    relaxed_policy = TierPolicy(**{**policy.__dict__, "min_est_margin": 0.0})
    for st_best, cls in sorted(best.exam_at.items()):
        diffs: list[TimingIntervalDiff] = []
        base_others = {k: v for k, v in best.exam_at.items() if v != cls}
        for st_alt in range(p.n_seeds):
            if st_alt == st_best or st_alt in base_others:
                continue
            alt = simulate_fixed_exams(p, {**base_others, st_alt: cls}, relaxed_policy, best.targets)
            if alt is None:
                continue
            d = compare_timing_interval(p, cls, best if st_best < st_alt else alt, alt if st_best < st_alt else best, policy)
            diffs.append(d)
        timing_candidates[cls] = diffs

    return TwoStageResult(
        name=p.name,
        policy=policy,
        best=best,
        timing_candidates=timing_candidates,
        class_set_ranking=evaluated[:8],
    )
