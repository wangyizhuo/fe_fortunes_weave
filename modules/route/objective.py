"""路线规划 · 统一目标函数与区间对比模型（以终为始 Objective + Good/Bad 判据）。

核心思想（Yizhuo 11-26）：
  1. 两阶段解耦：先确定目标初级/中级职业集合 T，再在固定乱数预算 N 内为 T 找全局最优考试时机与跳过。
  2. 区间不变性定理：固定职业 c，比较早考 t1 与晚考 t2 (t1 < t2)：
     在 t2 之后，两条路线消耗的乱数、所处等级、已有职业集合完全一致。
     因此真实差异严格来自区间 [t1, t2] 内的四项：
       ① 乱数置换差（吃掉 t1、保住已拥有 c 的 t2）
       ② 区间 (t1, t2) 提前拥有 c 带来的升级增量
       ③ 更早转职带来的保底增量（Floor）
       ④ 早转职多练的职业精通级数（Mastery）与金币/风险变化
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TierPolicy:
    """P0 / P1 / P2 统一策略参数（同一套算法，仅参数不同，告别特例补丁）。"""
    tier: str
    gold_per_pt: float            # 每 1 加权分折合多少手形金币
    train_pts_per_rank: float     # 每练 1 段技能折合扣多少加权分
    train_allowed: bool           # 是否允许自由为考试练技能（P1/P2 仅特批或中级兜底）
    max_optional_classes: int     # 除必考外最多额外考几个职业（P0=2, P1=1, P2=1）
    min_class_gain: float         # 额外多考一个职业（非必考/非中级底线）要求的最低净增量
    mastery_pts_per_lv: float     # 早转 1 级目标职业（用它升级）的职业精通等效加权分
    min_est_margin: float         # 非游戏读数（公式估计）考试时，pct - roll 的安全余量（%）
    skip_cap: float               # 额外纯跳过的绝对分数线
    skip_pct: float               # 额外纯跳过相对未来 15 级均分的低出比例
    skip_or: bool                 # True=满足其一即跳（P0），False=两条件同时满足才跳（P1/P2）


DEFAULT_TIER_POLICIES: dict[str, TierPolicy] = {
    "P0": TierPolicy(
        tier="P0",
        gold_per_pt=500 / 8,       # 62.5 G/分
        train_pts_per_rank=0.5,
        train_allowed=True,
        max_optional_classes=2,
        min_class_gain=2.0,
        mastery_pts_per_lv=0.25,   # 同等收益下每多 4 级目标职业使用 ≈ +1 分，自然偏好早转
        min_est_margin=3.0,        # 公式估计成功率需至少比判定值高 3% 才算稳过
        skip_cap=8.0,
        skip_pct=0.35,
        skip_or=True,
    ),
    "P1": TierPolicy(
        tier="P1",
        gold_per_pt=500 / 12,      # 41.67 G/分
        train_pts_per_rank=2.0,
        train_allowed=False,
        max_optional_classes=1,
        min_class_gain=2.0,
        mastery_pts_per_lv=0.20,
        min_est_margin=3.0,
        skip_cap=8.0,
        skip_pct=0.50,
        skip_or=False,
    ),
    "P2": TierPolicy(
        tier="P2",
        gold_per_pt=500 / 16,      # 31.25 G/分
        train_pts_per_rank=3.0,
        train_allowed=False,
        max_optional_classes=1,
        min_class_gain=2.0,
        mastery_pts_per_lv=0.15,
        min_est_margin=3.0,
        skip_cap=6.0,
        skip_pct=0.60,
        skip_or=False,
    ),
}


@dataclass(frozen=True)
class ObjectiveBreakdown:
    """以终为始的统一目标函数拆解（所有项分开保留，便于报告与校验）。"""
    stat_weighted: float          # 升级加权分（不含体格）
    physique_bonus: float         # 体格阈值加分（每跨过 5 的倍数力量 +3）
    floor_weighted: float         # 转职保底加权分
    mastery_levels: int           # 目标职业用来升级的级数（反映职业精通进度）
    mastery_bonus: float          # 精通等效分 = mastery_levels * policy.mastery_pts_per_lv
    gold: int                     # 实际手形金币
    gold_penalty: float           # 金币折算扣分 = gold / policy.gold_per_pt
    train_ranks: int              # 考前训练段数
    train_penalty: float          # 训练折算扣分 = train_ranks * policy.train_pts_per_rank
    raw_points: int               # 不加权总点数（含保底点数）
    stat_vector: tuple[int, ...]  # 9 项总增量（升级 + 保底）
    end_level: int                # 窗口结束等级
    skips: int                    # 纯跳过次数

    @property
    def pure_stat_score(self) -> float:
        """纯能力加权分 = 升级 + 体格 + 保底（不含金币/训练/精通虚拟分）。"""
        return self.stat_weighted + self.physique_bonus + self.floor_weighted

    @property
    def net_without_mastery(self) -> float:
        """与旧 Planner.plan_net 完全对齐的净值（不含精通虚拟分）。"""
        return self.pure_stat_score - self.gold_penalty - self.train_penalty

    @property
    def objective(self) -> float:
        """统一目标值 J(π)。"""
        return self.net_without_mastery + self.mastery_bonus


@dataclass(frozen=True)
class TimingIntervalDiff:
    """早考 t1 vs 晚考 t2 (t1 < t2) 的精确区间 [t1, t2] 归因拆解（早考减晚考）。"""
    cls: str
    t_early: int
    t_late: int
    lv_early: int
    lv_late: int
    # ① 乱数置换差：保住 t2（已拥有 c）减 牺牲 t1（未拥有 c）
    seed_swap_pts: int
    seed_swap_w: int
    # ② 区间 (t1, t2) 提前拥有 c 带来的升级增量
    interval_class_pts: int
    interval_class_w: int
    # ③ 区间外（> t2）因体格/均衡进位导致的残差（理论上通常为 0）
    post_carryover_pts: int
    post_carryover_w: int
    # ④ 保底增量（早考裸能力更低 -> 往往 >= 0）
    floor_pts: int
    floor_w: int
    # ⑤ 职业精通级数差与金币/风险差
    mastery_lv_delta: int
    gold_delta: int
    early_margin: float | None    # 早考的 (pct - roll) 余量（%）；None 表示未知
    late_margin: float | None
    verdict: str                  # "GOOD_EARLY" | "RISKY_EARLY" | "GOOD_LATE" | "TRADE_OFF"
    reason: str

    @property
    def total_pts(self) -> int:
        return self.seed_swap_pts + self.interval_class_pts + self.post_carryover_pts + self.floor_pts

    @property
    def total_w(self) -> int:
        return self.seed_swap_w + self.interval_class_w + self.post_carryover_w + self.floor_w


def classify_timing_choice(
    total_w: int,
    total_pts: int,
    gold_delta: int,
    mastery_lv_delta: int,
    early_margin: float | None,
    min_est_margin: float = 3.0,
) -> tuple[str, str]:
    """Good / Bad 统一判据（早考 t1 相对晚考 t2）：
    - RISKY_EARLY : 即使早考账面更好，但成功率余量 < min_est_margin（公式拟合误差内，实机易翻车）
    - GOOD_EARLY  : 稳过，且早考在加权分、点数、金币均不劣（或小让步换显著精通）
    - GOOD_LATE   : 晚考明显更优（早考吃掉好乱数、或触发额外跳过多花钱）
    - TRADE_OFF   : 属性与金币/精通存在实质权衡，需人工拍板
    """
    if early_margin is not None and early_margin < min_est_margin:
        return (
            "RISKY_EARLY",
            f"早考虽然账面 {total_pts:+d} 点 / {total_w:+d} 分，但估计余量仅 {early_margin:.2f}%（<{min_est_margin:.0f}% 拟合误差线），实战易翻车",
        )
    if total_w >= 0 and total_pts >= 0 and gold_delta <= 0:
        return (
            "GOOD_EARLY",
            f"早考全面占优：{total_pts:+d} 点 / {total_w:+d} 分，金币 {gold_delta:+d}G，多 {mastery_lv_delta:+d} 级目标职业精通",
        )
    if total_w <= -3 and gold_delta >= 0:
        return (
            "GOOD_LATE",
            f"早考吃亏（{total_pts:+d} 点 / {total_w:+d} 分，金币 {gold_delta:+d}G），应晚考以保住关键好乱数或合并跳过",
        )
    if gold_delta > 0 and total_w <= 2:
        return (
            "GOOD_LATE",
            f"早考会额外触发跳过多花 {gold_delta}G，而成长收益仅 {total_w:+d} 分，不划算",
        )
    return (
        "TRADE_OFF",
        f"存在取舍：早考 {total_pts:+d} 点 / {total_w:+d} 分、金币 {gold_delta:+d}G、精通 {mastery_lv_delta:+d} 级",
    )
