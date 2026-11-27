"""路线规划 · 纯以终为始的两阶段全局最优规划器（Two-Stage Goal-First Planner）。

按 Yizhuo 11-26 审阅意见重构后的纯粹两阶段架构：

  Stage 1（确定职业集合 T —— 不限初级/中级职业个数，全凭边际收益决定）：
    - 所有档位（P0 / P1 / P2）均可自由训练，仅靠每段训练折算成本（0.5 / 2.0 / 3.0 分/段）权衡。
    - 不再人工锁单颗种子（默认忽略 no_skip_seeds，避免过程补丁与终局目标冲突）。
    - 不再强制「考完必须用来升级」（允许纯为转职保底、借技能或顺便替纯跳过而考）。
    - 从必考集合出发，枚举单职业 + 高潜力双职业组合，再做贪心迭代扩展（可扩至 3 个及以上初级/中级职业），
      直到再加任何职业都无法净增 >= min_marginal_gain 为止；并为每个已选职业产出精确的边际收益拆解。

  Stage 2（固定职业集合 T，全局求最优考试时机与跳过）：
    - 不设 3% 禁考红线：所有按公式/实测判定通过（roll < pct）的时机均公平竞争。
    - 单职业严格 O(N) 穷举；多职业用各职业 Top-6 候选步网格搜索 + 全窗口坐标上升至收敛。
    - 若最优方案中存在「非实测、非 100%、公式估值接近判定值（< sl_warn_margin）」的考试，
      自动附带 ⚠️ 提前 NS Online S/L 实测提醒，并同时给出 100% 无需赌公式的「稳过备选方案」。
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

from planner import Planner, _TIER, _TIER_RANK  # noqa: E402
from .objective import (  # noqa: E402
    ClassMarginalGain,
    DEFAULT_TIER_POLICIES,
    ObjectiveBreakdown,
    SLTestWarning,
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
    sl_warnings: tuple[SLTestWarning, ...]
    notes: dict[Any, Any]


@dataclass
class TwoStageResult:
    name: str
    policy: TierPolicy
    best: EvaluatedPlan
    safe_fallback: EvaluatedPlan | None          # 若 best 含 S/L 预警，给出不触发 S/L 预警的最优稳过备选
    marginal_gains: list[ClassMarginalGain]      # 最佳方案里每个职业的精确边际收益拆解
    timing_candidates: dict[str, list[TimingIntervalDiff]]
    class_set_ranking: list[EvaluatedPlan]


def prepare_goal_first_planner(name: str, target: int | None = None) -> tuple[Planner, str]:
    """构建纯以终为始的 Planner 实例（无全局副作用）：
    - 全档位允许训练（所有技能缺口均折算进 exam_train_ranks，由 TierPolicy.train_pts_per_rank 权衡）
    - 不人工锁定单颗种子（清空 no_skip_seeds）
    """
    import run_plans as rp  # noqa: E402

    tier = rp.tier_of(name)
    _, lv = rp.current_state(name)
    tgt = target if target is not None else max(rp.HORIZON_MIN_LEVEL, lv + rp.HORIZON_MIN_STEPS)
    p = rp.make_planner(name, tgt)

    # 全员允许照常训练：把所有有技能缺口的候选职业转成可训练成本，不再区分特批/禁练
    all_train_ranks = dict(p.exam_train_ranks or {})
    new_req = {}
    new_chance = dict(p.exam_chance or {})
    for c, r in (p.exam_req or {}).items():
        if r[1] > 0:
            all_train_ranks[c] = r[1]
            new_req[c] = (r[0], 0)
            # 练满技能后，旧截图里未练技能时的低实测率不再适用，改按练满后的公式估算
            if c in (p.exam_train or {}):
                new_chance.pop(c, None)
        else:
            new_req[c] = r
    p.exam_train_ranks = all_train_ranks
    p.exam_req = new_req
    p.exam_chance = new_chance
    p.no_skip_seeds = set()
    return p, tier


def exam_margin(p: Planner, step: int, cls: str, lv: int) -> tuple[bool, float | None, float | None, float, bool]:
    """返回 (是否通过, 成功率%, 余量 pct - roll, 判定值 roll, 是否确定无公式误差)。
    游戏实测读数（exam_chance）或满概率（pct >= 100）不存在公式误差，均视为确定。"""
    roll = p.exam_value(step)
    is_observed = cls in (p.exam_chance or {})
    pct = p.exam_pct(cls, lv)
    ok = p.exam_ok(step, cls, lv)
    is_certain = is_observed or (pct is not None and pct >= 100)
    if pct is None:
        return ok, None, None, roll, is_certain
    return ok, float(pct), round(pct - roll, 2), roll, is_certain


def simulate_fixed_exams(
    p: Planner,
    exam_at: dict[int, str],
    policy: TierPolicy,
    targets: tuple[str, ...],
    allow_skips: bool = True,
    avoid_sl_warnings: bool = False,
) -> EvaluatedPlan | None:
    """无副作用确定性模拟：
    - 固定 exam_at={step: cls}，其余步按均衡+体格选最佳已有职业，满足本档跳过条件则纯跳过（或 skip_take）。
    - 不强制考完必须用来升级（允许纯为转职保底、借技能或替纯跳过而考）。
    - 默认不因公式余量拒绝方案，而是收集 SLTestWarning；仅在求稳过备选（avoid_sl_warnings=True）时过滤。
    """
    owned = list(p.owned)
    stats = list(p.stats) if p.stats else None
    cur_str = p.str_start
    no_skip_seeds = set(getattr(p, "no_skip_seeds", ()) or ())
    skip_take = tuple(getattr(p, "skip_take", ()) or ())
    pg = getattr(p, "permit_gold", {"初级": 300, "中级": 500, "上级": 3000})

    acts: list[tuple[str, str]] = []
    warnings: list[SLTestWarning] = []
    notes: dict[Any, Any] = {}
    done = 0
    gold = 0
    stat_w = 0
    phys_w = 0
    g_sum = [0] * 9

    for step in range(p.n_seeds):
        lv = p.level + done
        seed = p.seed_at(step)
        keep = seed in no_skip_seeds

        if step in exam_at:
            cls = exam_at[step]
            if keep or cls in owned:
                return None
            ok, pct, margin, roll, is_certain = exam_margin(p, step, cls, lv)
            if not ok:
                return None
            if not is_certain and margin is not None and margin < policy.sl_warn_margin:
                if avoid_sl_warnings:
                    return None
                warnings.append(
                    SLTestWarning(
                        step=step,
                        level=lv,
                        cls=cls,
                        est_pct=pct if pct is not None else 0.0,
                        roll=round(roll, 2),
                        margin=margin,
                    )
                )
            owned.append(cls)
            gold += pg.get(_TIER.get(cls, "中级"), 500)
            acts.append(("考试", cls))
            continue

        # 选最佳已有职业（含均衡权重与体格加分）
        w, _ = p.balanced_weights(stats) if stats else ([float(x) for x in p.weights], "")
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
    # 转职保底（Class Promotion Stat Floor，区别于单次升级保底）
    lifts = p.floor_lifts(acts_t)
    floor_g = [0] * 9
    for ls in lifts.values():
        for i, old_v, new_v in ls:
            floor_g[i] += new_v - old_v
    promo_floor_w = sum(p.weights[i] * floor_g[i] for i in range(9))
    tot_g = tuple(a + b for a, b in zip(g_sum, floor_g))

    target_set = set(targets)
    mastery_lv = sum(1 for a, c in acts_t if a == "升级" and c in target_set)
    train_rk = p.train_ranks(acts_t)

    bd = ObjectiveBreakdown(
        stat_weighted=stat_w,
        physique_bonus=phys_w,
        promo_floor_weighted=promo_floor_w,
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
        sl_warnings=tuple(warnings),
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

    _, _, em, _, e_cert = exam_margin(p, t1, cls, lv1)
    _, _, lm, _, l_cert = exam_margin(p, t2, cls, lv2)
    eff_em = None if e_cert else em
    eff_lm = None if l_cert else lm
    verdict, reason = classify_timing_choice(
        total_w=swap_w + int_w + post_w + fl_w,
        total_pts=swap_pts + int_pts + post_pts + fl_pts,
        gold_delta=gold_delta,
        mastery_lv_delta=mastery_delta,
        early_margin=eff_em,
        sl_warn_margin=policy.sl_warn_margin,
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
        promo_floor_pts=fl_pts,
        promo_floor_w=fl_w,
        mastery_lv_delta=mastery_delta,
        gold_delta=gold_delta,
        early_margin=eff_em,
        late_margin=eff_lm,
        needs_sl_test=(eff_em is not None and eff_em < policy.sl_warn_margin),
        verdict=verdict,
        reason=reason,
    )


def optimize_exam_timings(
    p: Planner,
    targets: tuple[str, ...],
    policy: TierPolicy,
    step_hints: dict[str, list[int]] | None = None,
    avoid_sl_warnings: bool = False,
) -> EvaluatedPlan | None:
    """Stage 2：固定职业集合 targets，全局搜索最优考试时机组合 (t_1, ..., t_m)。"""
    if not targets:
        return simulate_fixed_exams(p, {}, policy, (), avoid_sl_warnings=avoid_sl_warnings)

    n = p.n_seeds
    no_skip = set(getattr(p, "no_skip_seeds", ()) or ())
    all_steps: dict[str, list[int]] = {}
    for c in targets:
        steps = []
        for st in range(n):
            if p.seed_at(st) in no_skip:
                continue
            max_lv = p.level + st
            ok, _, margin, _, is_certain = exam_margin(p, st, c, max_lv)
            if not ok:
                continue
            if avoid_sl_warnings and not is_certain and margin is not None and margin < policy.sl_warn_margin:
                continue
            steps.append(st)
        if not steps:
            return None
        all_steps[c] = steps

    if len(targets) == 1:
        c = targets[0]
        best: EvaluatedPlan | None = None
        for st in all_steps[c]:
            ev = simulate_fixed_exams(p, {st: c}, policy, targets, avoid_sl_warnings=avoid_sl_warnings)
            if ev is not None and (best is None or _rank_key(ev) > _rank_key(best)):
                best = ev
        return best

    # 多职业：用提示候选步做初始网格搜索，再做逐职业全窗口坐标上升至不动点
    width = 6 if len(targets) == 2 else 4 if len(targets) == 3 else 3
    grid_lists = []
    for c in targets:
        hint = (step_hints or {}).get(c)
        if hint:
            picked = [st for st in hint if st in all_steps[c]][:width]
            grid_lists.append(picked or all_steps[c][:width])
        else:
            grid_lists.append(all_steps[c][:width])

    best = None
    for combo in itertools.product(*grid_lists):
        if len(set(combo)) != len(combo):
            continue
        ev = simulate_fixed_exams(
            p,
            {st: c for st, c in zip(combo, targets)},
            policy,
            targets,
            avoid_sl_warnings=avoid_sl_warnings,
        )
        if ev is not None and (best is None or _rank_key(ev) > _rank_key(best)):
            best = ev

    if best is None:
        return None

    improved = True
    while improved:
        improved = False
        for c in targets:
            others = {k: v for k, v in best.exam_at.items() if v != c}
            for st in all_steps[c]:
                if st in others or best.exam_at.get(st) == c:
                    continue
                ev = simulate_fixed_exams(
                    p, {**others, st: c}, policy, targets, avoid_sl_warnings=avoid_sl_warnings
                )
                if ev is not None and _rank_key(ev) > _rank_key(best):
                    best = ev
                    improved = True
    return best


def _rank_key(ev: EvaluatedPlan) -> tuple[float, float, int, int, int, int, int]:
    """统一排序键：目标函数 J(π) → 不含精通净值 → 训练段数更少 → 金币更少 → 总点数 → 精通级数（零权重破平局）→ S/L 预警更少。"""
    return (
        round(ev.breakdown.objective, 4),
        round(ev.breakdown.net_without_mastery, 4),
        -ev.breakdown.train_ranks,
        -ev.breakdown.gold,
        ev.breakdown.raw_points,
        ev.breakdown.mastery_levels,
        -len(ev.sl_warnings),
    )


def _satisfies_mid(p: Planner, targets: tuple[str, ...]) -> bool:
    if not getattr(p, "require_mid", False):
        return True
    return any(_TIER_RANK.get(_TIER.get(c, ""), 0) >= 2 for c in targets)


def _top_steps_for_class(
    p: Planner, cls: str, policy: TierPolicy, avoid_sl_warnings: bool = False
) -> list[int]:
    no_skip = set(getattr(p, "no_skip_seeds", ()) or ())
    scored: list[tuple[tuple[float, float, int, int, int], int]] = []
    for st in range(p.n_seeds):
        if p.seed_at(st) in no_skip:
            continue
        ev = simulate_fixed_exams(p, {st: cls}, policy, (cls,), avoid_sl_warnings=avoid_sl_warnings)
        if ev is not None:
            scored.append((_rank_key(ev), st))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [st for _, st in scored]


def _search_best_class_set(
    p: Planner,
    policy: TierPolicy,
    avoid_sl_warnings: bool = False,
) -> tuple[EvaluatedPlan, list[EvaluatedPlan], dict[frozenset[str], EvaluatedPlan], dict[str, list[int]]]:
    """不限制初级/中级职业数量的 Stage 1 搜索：
      1. 评估 0 额外职业（仅必考）
      2. 全量评估所有 1 个额外职业
      3. 对单职业 Top-6 两两组合评估 2 个额外职业（捕捉互补双职）
      4. 从当前最优集合继续贪心迭代尝试加第 3、4... 个职业，只要边际目标增量 >= min_marginal_gain 就继续扩展
      5. 反向边际检验：若去掉任意非必考职业只损失 < min_marginal_gain，则精简掉该不划算职业
    """
    req = tuple(dict.fromkeys(p.required))
    cands = [c for c in p.exam_options if c not in req]

    step_hints: dict[str, list[int]] = {}
    for c in req:
        step_hints[c] = _top_steps_for_class(p, c, policy, avoid_sl_warnings=avoid_sl_warnings)

    by_set: dict[frozenset[str], EvaluatedPlan] = {}

    def eval_set(tg: tuple[str, ...]) -> EvaluatedPlan | None:
        key = frozenset(tg)
        if key in by_set:
            return by_set[key]
        ev = optimize_exam_timings(p, tg, policy, step_hints, avoid_sl_warnings=avoid_sl_warnings)
        if ev is not None:
            by_set[key] = ev
        return ev

    evaluated: list[EvaluatedPlan] = []
    if _satisfies_mid(p, req):
        ev0 = eval_set(req)
        if ev0 is not None:
            evaluated.append(ev0)

    single_ranked: list[tuple[EvaluatedPlan, str]] = []
    for c in cands:
        step_hints[c] = _top_steps_for_class(p, c, policy, avoid_sl_warnings=avoid_sl_warnings)
        tg = req + (c,)
        ev = eval_set(tg)
        if ev is not None:
            single_ranked.append((ev, c))
            if _satisfies_mid(p, tg):
                evaluated.append(ev)
    single_ranked.sort(key=lambda x: _rank_key(x[0]), reverse=True)

    # 2 额外职业：对单职业 Top-6 候选两两组合
    top_cands = [c for _, c in single_ranked[:6]]
    for c1, c2 in itertools.combinations(top_cands, 2):
        tg = req + (c1, c2)
        if not _satisfies_mid(p, tg):
            continue
        ev = eval_set(tg)
        if ev is not None:
            evaluated.append(ev)

    evaluated.sort(key=_rank_key, reverse=True)
    if not evaluated:
        raise RuntimeError(f"{p.name} 找不到任何满足硬约束的合法方案")

    # 无上限贪心继续扩展（尝试第 3、4... 个职业，直到任何新职业的边际增量都 < min_marginal_gain）
    best = evaluated[0]
    pool_ext = [c for _, c in single_ranked[:8]]
    while True:
        cur_set = set(best.targets)
        best_ext: EvaluatedPlan | None = None
        for c in pool_ext:
            if c in cur_set:
                continue
            tg = best.targets + (c,)
            ev = eval_set(tg)
            if ev is not None and (ev.breakdown.objective - best.breakdown.objective) >= policy.min_marginal_gain - 1e-6:
                if best_ext is None or _rank_key(ev) > _rank_key(best_ext):
                    best_ext = ev
        if best_ext is None:
            break
        evaluated.append(best_ext)
        best = best_ext

    # 反向边际检验：确保最终集合里每一个非必考职业，去掉它都会让目标函数下降 >= min_marginal_gain
    while True:
        extras = [c for c in best.targets if c not in req]
        if not extras:
            break
        pruned: EvaluatedPlan | None = None
        for c in extras:
            sub_tg = tuple(t for t in best.targets if t != c)
            if not _satisfies_mid(p, sub_tg):
                continue
            sub = eval_set(sub_tg)
            if sub is not None and (best.breakdown.objective - sub.breakdown.objective) < policy.min_marginal_gain - 1e-6:
                if pruned is None or _rank_key(sub) > _rank_key(pruned):
                    pruned = sub
        if pruned is None:
            break
        best = pruned

    evaluated.sort(key=_rank_key, reverse=True)
    return best, evaluated, by_set, step_hints


def compute_marginal_gains(
    p: Planner,
    best: EvaluatedPlan,
    policy: TierPolicy,
    step_hints: dict[str, list[int]],
    by_set: dict[frozenset[str], EvaluatedPlan],
) -> list[ClassMarginalGain]:
    """计算最终方案中每个目标职业的精确边际收益（含该职业最优 减 去掉该职业后的最优）。"""
    req_set = set(p.required)
    out: list[ClassMarginalGain] = []
    bb = best.breakdown
    for cls in best.targets:
        sub_tg = tuple(t for t in best.targets if t != cls)
        sub_key = frozenset(sub_tg)
        sub = by_set.get(sub_key)
        if sub is None:
            sub = optimize_exam_timings(p, sub_tg, policy, step_hints)
        used_lv = sum(1 for a, c in best.actions if a == "升级" and c == cls)
        if sub is None:
            # 去掉该职业后无合法方案（罕见），记相对 0 基准
            out.append(
                ClassMarginalGain(
                    cls=cls,
                    is_required=cls in req_set,
                    delta_pts=bb.raw_points,
                    delta_stat_vector=bb.stat_vector,
                    delta_stat_w=bb.stat_weighted + bb.physique_bonus,
                    delta_promo_floor_w=bb.promo_floor_weighted,
                    delta_mastery_lv=used_lv,
                    delta_gold=bb.gold,
                    delta_train_ranks=bb.train_ranks,
                    delta_net=bb.net_without_mastery,
                    delta_objective=bb.objective,
                    used_levels=used_lv,
                )
            )
            continue
        sb = sub.breakdown
        out.append(
            ClassMarginalGain(
                cls=cls,
                is_required=cls in req_set,
                delta_pts=bb.raw_points - sb.raw_points,
                delta_stat_vector=tuple(a - b for a, b in zip(bb.stat_vector, sb.stat_vector)),
                delta_stat_w=(bb.stat_weighted + bb.physique_bonus) - (sb.stat_weighted + sb.physique_bonus),
                delta_promo_floor_w=bb.promo_floor_weighted - sb.promo_floor_weighted,
                delta_mastery_lv=bb.mastery_levels - sb.mastery_levels,
                delta_gold=bb.gold - sb.gold,
                delta_train_ranks=bb.train_ranks - sb.train_ranks,
                delta_net=round(bb.net_without_mastery - sb.net_without_mastery, 2),
                delta_objective=round(bb.objective - sb.objective, 2),
                used_levels=used_lv,
            )
        )
    return out


def plan_two_stage(
    p: Planner,
    tier: str,
    policies: dict[str, TierPolicy] | None = None,
    include_timing_matrix: bool = True,
) -> TwoStageResult:
    """运行完整的以终为始两阶段规划，返回：
      - best              : 含 S/L 风险提醒的全局最优方案
      - safe_fallback     : 若 best 存在 S/L 提醒，同时产出不赌公式的稳过备选方案
      - marginal_gains    : 最佳方案里每个职业的精确边际收益拆解（含 9 项具体能力差）
      - timing_candidates : 每场考试相对其他时机的区间 [t1, t2] 四项拆解
    """
    policy = (policies or DEFAULT_TIER_POLICIES)[tier]
    best, evaluated, by_set, step_hints = _search_best_class_set(p, policy, avoid_sl_warnings=False)
    marginals = compute_marginal_gains(p, best, policy, step_hints, by_set)

    safe_fallback: EvaluatedPlan | None = None
    if best.sl_warnings:
        # 优先在当前最优职业集合及前 3 个候选集合上直接求稳过时机，兼顾完备性与速度
        safe_cands: list[EvaluatedPlan] = []
        seen_tgs: set[frozenset[str]] = set()
        for ev in [best, *evaluated[:3]]:
            fk = frozenset(ev.targets)
            if fk in seen_tgs:
                continue
            seen_tgs.add(fk)
            sf = optimize_exam_timings(p, ev.targets, policy, step_hints, avoid_sl_warnings=True)
            if sf is not None:
                safe_cands.append(sf)
        if safe_cands:
            safe_cands.sort(key=_rank_key, reverse=True)
            safe_fallback = safe_cands[0]
        else:
            try:
                safe_fallback, _, _, _ = _search_best_class_set(p, policy, avoid_sl_warnings=True)
            except RuntimeError:
                safe_fallback = None

    timing_candidates: dict[str, list[TimingIntervalDiff]] = {}
    if include_timing_matrix:
        for st_best, cls in sorted(best.exam_at.items()):
            diffs: list[TimingIntervalDiff] = []
            base_others = {k: v for k, v in best.exam_at.items() if v != cls}
            for st_alt in range(p.n_seeds):
                if st_alt == st_best or st_alt in base_others:
                    continue
                alt = simulate_fixed_exams(p, {**base_others, st_alt: cls}, policy, best.targets)
                if alt is None:
                    continue
                d = compare_timing_interval(
                    p, cls, best if st_best < st_alt else alt, alt if st_best < st_alt else best, policy
                )
                diffs.append(d)
            timing_candidates[cls] = diffs

    return TwoStageResult(
        name=p.name,
        policy=policy,
        best=best,
        safe_fallback=safe_fallback,
        marginal_gains=marginals,
        timing_candidates=timing_candidates,
        class_set_ranking=evaluated[:8],
    )
