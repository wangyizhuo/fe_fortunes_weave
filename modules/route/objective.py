"""路线规划 · 以终为始的统一目标函数、边际收益拆解与 S/L 风险预警模型。

核心原则（按 Yizhuo 11-26 审阅意见彻底去补丁化）：
  1. 真正以终为始：不人工锁单颗种子（no_skip_seeds），不设初级/中级职业数量上限，
     不强制「考完必须用来升级」，也不对 P1/P2 禁训练——全部由统一目标函数 J(π) 与边际成本/收益说了算。
  2. 严格区分「升级保底」与「转职保底」（全文禁止笼统简称）：
     - 升级保底：单次升级时至少涨 2 项属性（fe_growth.py `level_up(min_stats=2)`，已内含在每次升级结果中）。
     - 转职保底：转职瞬间若裸属性低于目标职业最低线（fw_classes.json `minStats`），永久补足到该线（planner.py `floor_lifts`）。
  3. 每个额外职业必须算清「边际收益（Marginal Gain）」：去掉这一个职业会少拿多少属性/转职保底/精通、省多少金币和训练；
     P2 提高边际门槛（≥6.0 分），减少 P2 角色的无谓手形金币与操作时间投入。
  4. 职业精通进度由用户 case by case 决定，不计入虚拟加权分（mastery_pts_per_lv = 0.0），仅在同净值同成本下作破平局参考。
  5. 不因公式可能不准而硬杀好方案：不设 3% 禁考红线；对「非实测、非 100%、公式估值接近判定值」的考试，
     发出明确的「⚠️ 需提前 NS Online S/L 实测」预警并附稳过备选；实机测完若不准直接校准公式或录入实测值。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TierPolicy:
    """P0 / P1 / P2 统一策略参数（同一套算法，全员可训练、初级中级不限职业数，仅成本权重与边际门槛不同）。"""
    tier: str
    gold_per_pt: float            # 每 1 加权分折合多少手形金币
    train_pts_per_rank: float     # 每练 1 段技能折合扣多少加权分（全档位均可自由训练，靠成本权衡）
    min_marginal_gain: float      # 多考 1 个非必考职业时，该职业自身至少要带来的净增量（P2 提高门槛以省金币与时间）
    mastery_pts_per_lv: float     # 默认 0.0（精通价值由用户 case by case 决定，不折算进虚拟加权分）
    sl_warn_margin: float         # 非实测、非 100% 考试时，(公式估% - 判定值%) < 该值则标 ⚠️ 建议提前 S/L 实测（但不禁止）
    skip_cap: float               # 额外纯跳过的绝对分数线
    skip_pct: float               # 额外纯跳过相对未来 15 级均分的低出比例
    skip_or: bool                 # True=满足其一即跳，False=两条件同时满足才跳


DEFAULT_TIER_POLICIES: dict[str, TierPolicy] = {
    "P0": TierPolicy(
        tier="P0",
        gold_per_pt=0.0,           # P0 不计手形金币成本，预设数值最高的选择
        train_pts_per_rank=0.5,    # 练 1 段 ≈ 0.5 分
        min_marginal_gain=2.0,     # P0 多考 1 个非必考职业至少净赚 2.0 分
        mastery_pts_per_lv=0.0,    # 精通由用户 case by case 决定，不计入虚拟加权分
        sl_warn_margin=5.0,        # 公式估值离判定值不到 5% 时提醒提前 S/L 实测
        skip_cap=8.0,
        skip_pct=0.35,
        skip_or=False,             # 必须同时低于 8 分且低于均分 35% 才纯跳过，彻底避免误跳过 5 点/10 分种子
    ),
    "P1": TierPolicy(
        tier="P1",
        gold_per_pt=500 / 12,      # 41.67 G/分（500G ≈ 12 分）
        train_pts_per_rank=2.0,    # 照常可练，但每练 1 段按 2 分计成本
        min_marginal_gain=3.0,     # P1 多考 1 个非必考职业至少净赚 3.0 分
        mastery_pts_per_lv=0.0,    # 精通由用户 case by case 决定
        sl_warn_margin=5.0,
        skip_cap=8.0,
        skip_pct=0.50,
        skip_or=False,
    ),
    "P2": TierPolicy(
        tier="P2",
        gold_per_pt=500 / 16,      # 31.25 G/分（500G ≈ 16 分）
        train_pts_per_rank=3.0,    # 照常可练，但每练 1 段按 3 分计成本
        min_marginal_gain=6.0,     # P2 显著提高额外职业门槛（≥6.0 分），减少金币与操作时间成本
        mastery_pts_per_lv=0.0,    # 精通由用户 case by case 决定
        sl_warn_margin=5.0,
        skip_cap=6.0,
        skip_pct=0.60,
        skip_or=False,
    ),
}


@dataclass(frozen=True)
class SLTestWarning:
    """考试公式估值接近判定值时的提前 S/L 实测提醒（不拒绝方案，提醒尽早用 NS Online 存档验证）。"""
    step: int
    level: int
    cls: str
    est_pct: float                # 公式估计成功率（%）
    roll: float                   # 该种子考试判定值（0~100）
    margin: float                 # est_pct - roll（%）

    @property
    def message(self) -> str:
        return (
            f"Lv{self.level}(第{self.step + 1}步) 考「{self.cls}」：公式估 {self.est_pct:.1f}% vs 判定值 {self.roll:.2f}%"
            f"（仅高 {self.margin:.2f}%），建议尽早用 NS Online 存档 S/L 实测；若不准请录入实测值校准公式"
        )


@dataclass(frozen=True)
class ObjectiveBreakdown:
    """以终为始的统一目标函数拆解（所有项独立保留，分开汇报）。"""
    stat_weighted: float          # 升级加权分（已包含单次升级保底，不含体格）
    physique_bonus: float         # 体格阈值加分（力量每跨过 5 的倍数补 +3）
    promo_floor_weighted: float   # 转职保底加权分（转职瞬间裸属性补足到职业 minStats 的永久收益）
    mastery_levels: int           # 目标职业在窗口内用来升级的级数（反映精通进度；允许为 0）
    mastery_bonus: float          # 精通等效分 = mastery_levels * policy.mastery_pts_per_lv
    gold: int                     # 实际手形金币
    gold_penalty: float           # 金币折算扣分 = gold / policy.gold_per_pt
    train_ranks: int              # 考前训练段数
    train_penalty: float          # 训练折算扣分 = train_ranks * policy.train_pts_per_rank
    raw_points: int               # 不加权总点数（升级点数 + 转职保底点数）
    stat_vector: tuple[int, ...]  # 9 项总增量（升级 + 转职保底）
    end_level: int                # 窗口结束等级
    skips: int                    # 纯跳过次数

    @property
    def pure_stat_score(self) -> float:
        """纯能力加权分 = 升级 + 体格 + 转职保底（不含金币/训练/精通虚拟分）。"""
        return self.stat_weighted + self.physique_bonus + self.promo_floor_weighted

    @property
    def net_without_mastery(self) -> float:
        """与 Planner.plan_net 完全对齐的净值（不含精通虚拟分）。"""
        return self.pure_stat_score - self.gold_penalty - self.train_penalty

    @property
    def objective(self) -> float:
        """统一目标值 J(π)。"""
        return self.net_without_mastery + self.mastery_bonus


@dataclass(frozen=True)
class ClassMarginalGain:
    """单个额外职业的边际收益拆解（含该职业最优路线 减 去掉该职业后的最优路线）。"""
    cls: str
    is_required: bool
    delta_pts: int                # 多拿多少总点数
    delta_stat_vector: tuple[int, ...]  # 9 项具体能力差（升级 + 转职保底）
    delta_stat_w: float           # 升级+体格加权分差
    delta_promo_floor_w: float    # 转职保底加权分差
    delta_mastery_lv: int         # 多拿多少级目标职业精通
    delta_gold: int               # 多花多少金币（0 表示替换了原本 300G 的纯跳过）
    delta_train_ranks: int        # 多练多少段技能
    delta_net: float              # 扣除金币和训练后的纯能力净增量
    delta_objective: float        # 含精通激励的总目标增量
    used_levels: int              # 该职业在窗口内用来升级的次数（0 表示纯为转职保底/技能/替跳过而考）


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
    # ③ 区间外（> t2）残差（区间不变性定理：通常严格为 0）
    post_carryover_pts: int
    post_carryover_w: int
    # ④ 转职保底差（早转裸属性更低 -> 转职瞬间往往白嫖更多永久属性）
    promo_floor_pts: int
    promo_floor_w: int
    # ⑤ 职业精通级数差、金币差、以及是否需要提前 S/L 实测
    mastery_lv_delta: int
    gold_delta: int
    early_margin: float | None    # None 表示 100% 满概率或已有实机截图读数
    late_margin: float | None
    needs_sl_test: bool           # True 表示早考公式估值接近判定值，建议提前 S/L 验证
    verdict: str                  # "GOOD_EARLY" | "GOOD_EARLY_NEEDS_SL" | "GOOD_LATE" | "TRADE_OFF"
    reason: str

    @property
    def total_pts(self) -> int:
        return self.seed_swap_pts + self.interval_class_pts + self.post_carryover_pts + self.promo_floor_pts

    @property
    def total_w(self) -> int:
        return self.seed_swap_w + self.interval_class_w + self.post_carryover_w + self.promo_floor_w


def classify_timing_choice(
    total_w: int,
    total_pts: int,
    gold_delta: int,
    mastery_lv_delta: int,
    early_margin: float | None,
    sl_warn_margin: float = 5.0,
) -> tuple[str, str]:
    """Good / Bad 统一判据（早考 t1 相对晚考 t2）：
    - GOOD_EARLY          : 早考稳过（100% / 实测 / 差值充足），且加权分、点数、金币均不劣
    - GOOD_EARLY_NEEDS_SL : 早考全面占优，但公式估值接近判定值（差值 < sl_warn_margin），
                            不否决方案，提醒尽早用 NS Online 存档 S/L 实测，不准则校准公式
    - GOOD_LATE           : 晚考明显更优（早考吃掉好乱数，或导致后续仍需额外花钱纯跳过）
    - TRADE_OFF           : 属性与金币/精通存在取舍，由目标函数 J(π) 权衡
    """
    needs_sl = early_margin is not None and early_margin < sl_warn_margin
    if total_w >= 0 and total_pts >= 0 and gold_delta <= 0:
        if needs_sl:
            return (
                "GOOD_EARLY_NEEDS_SL",
                f"早考全面占优（{total_pts:+d} 点 / {total_w:+d} 分，金币 {gold_delta:+d}G，精通 {mastery_lv_delta:+d} 级），"
                f"但公式估测仅比判定值高 {early_margin:.2f}%，建议提前用 NS Online 存档 S/L 实测",
            )
        return (
            "GOOD_EARLY",
            f"早考稳过且全面占优：{total_pts:+d} 点 / {total_w:+d} 分，金币 {gold_delta:+d}G，多 {mastery_lv_delta:+d} 级精通",
        )
    if total_w <= -3 and gold_delta >= 0:
        return (
            "GOOD_LATE",
            f"早考吃亏（{total_pts:+d} 点 / {total_w:+d} 分，金币 {gold_delta:+d}G），应晚考以保住好乱数或合并跳过",
        )
    if gold_delta > 0 and total_w <= 2:
        return (
            "GOOD_LATE",
            f"早考会多触发纯跳过多花 {gold_delta}G，而成长仅 {total_w:+d} 分，不划算",
        )
    return (
        "TRADE_OFF",
        f"存在取舍：早考 {total_pts:+d} 点 / {total_w:+d} 分、金币 {gold_delta:+d}G、精通 {mastery_lv_delta:+d} 级",
    )
