"""
成长路线规划：已知种子后，决定接下来每一步种子怎么用。

每一步种子只有两种用法（见 fe_growth.py）：
  * 升级：用某个「已有职业」升 1 级。已有职业之间随时换，不推进种子，
          所以每一级都可以临时换成最划算的已有职业（包括转回低级职业）。
  * 考试：吃掉这一步（不涨能力）。考的是一个新职业的话，假定考过，
          之后的升级就多了这个职业可以用（例如考土匪、恶棍）。
          不想要新职业时，考任意一个初级职业当作纯跳过。

目标：升到目标等级为止，Σ(权重 × 加点) 最大。
限制：考试次数 ≤ K。对 K = 0,1,2,... 分别求最优路线，再按「每多考一次能多拿几分」给建议。

注意：
  * 默认考试一定通过。实际通过率看游戏里考试画面显示的 %（等级、技能等级越高越容易过）。
    没过也会推进种子，但拿不到新职业。
  * 只按成长率算，没考虑职业的能力补正、最低能力、技能和兵种精通。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fe_growth import STATS, GrowthData, level_up, next_seed, exam_roll
import timing


@dataclass
class PlanRow:
    step: int                 # 第几步种子（从 0 数）
    seed: int
    action: str               # "升级" / "考试"
    cls: str                  # 升级用的职业 / 考的职业
    level_from: int | None    # 升级前等级（考试时为 None）
    gains: list[int]          # 升级时的加点；考试时为「这一步如果升级、用最好职业」的加点
    score: int
    compare: str              # 这一步各可用职业的得分
    alternatives: str = ""    # 换别的职业会涨「不同」的项（不是单纯少涨）
    balance_note: str = ""    # 均衡调整说明（为了补落后的能力，选了加权分不是最高的职业）
    bonus: int = 0            # 体格阈值加分：力量涨到 5 的倍数（体格 +1）时额外加的分
    str_note: str = ""
    floor: list = None        # 11-16：考进新职业时保底补上的项 [(能力, 原值, 补到)]
    skip_class: str = None    # 跳过时只能用会考过的初级考试 → 用掉的职业（11-16 Yizhuo：多拿职业不是好事）
    skip_fail: list = None    # 跳过时可以用、会考不过（不拿职业）的初级考试
    skip_left: int = None     # 跳过之后还剩几个没拿到的初级职业可以拿来跳过
    skip_none: bool = False   # 没有任何初级考试可以拿来跳过
    level_at: int = None      # 考试/跳过发生时的等级


@dataclass
class Plan:
    exams: int
    total: int
    rows: list[PlanRow]


def score(gains, weights):
    return sum(g * w for g, w in zip(gains, weights))


def gains_text(gains):
    return " ".join(STATS[i] + ("" if g == 1 else f"+{g}") for i, g in enumerate(gains) if g) or "—"



def exam_rate(d, g):
    """考试成功率公式（11-25 Yizhuo 游戏里读的数拟合，见 exam_rates_observed.json / checks E1）：
    技能都够、等级 ≥ 推荐等级 → 100%；否则 2 ×［(6 + 等级差) × (1 − 技能差段数 ÷ 6)］²，四舍五入，最高 100、最低 0。
    d = 等级 − 推荐等级，g = 技能还差几段（任选其一取差得最少的那项）。
    等级高于推荐且技能不够时没有游戏数据，保守按等级差 0 算。
    已知偏差：差的技能有两项时游戏比公式低（奇洛 轻骑兵 2% vs 4.5%，杨界 重装步兵 16% vs 18%），可能按技能经验算。"""
    if g <= 0 and d >= 0:
        return 100
    d = min(d, 0)   # 等级高于推荐、技能又不够：没有游戏数据，保守按刚好推荐等级算（Game8：差 1 段时 50～85%，公式给 50）
    x = (6 + d) * (1 - g / 6)
    if x <= 0:
        return 0
    return min(100, int(2 * x * x + 0.5))


class Planner:
    def __init__(self, data: GrowthData, name: str, seed: int, level: int, target_level: int,
                 owned: list[str], exam_options: list[str], weights: list[int], min_stats: int = 2,
                 required: list[str] = (), prefer: dict[str, float] | None = None,
                 stats: list[int] | None = None, balance_gap: int = 3, balance_step: float = 0.5,
                 exam_chance: dict[str, float] | None = None):
        self.data, self.name, self.weights, self.min_stats = data, name, weights, min_stats
        self.level, self.n_levels = level, target_level - level
        self.owned = tuple(owned)
        self.exam_options = tuple(c for c in exam_options if c not in owned)
        self.required = tuple(required)   # 一定要考到的职业（例如为了拿精通技能）
        # 想多用的职业 → 每用它升一级加的「虚拟分」（例如练恶棍的兵种精通）。
        # 只用来在得分接近时偏向它，表里显示的仍是真实加权分。
        self.prefer = prefer or {}
        self.seeds = [seed]
        # 成长均衡：当前能力（显示顺序）。高权重（≥4）的几项里，某项比最低的那项多出 balance_gap 点以上时，
        # 每多 1 点，它的权重 −balance_step，落后那项的权重 +balance_step（各最多 ±2）。
        # 只影响「同一级选哪个职业」，不影响什么时候考试。
        self.stats = list(stats) if stats else None
        self.balance_gap, self.balance_step = balance_gap, balance_step
        # 考试成功率（游戏里显示的 %）。考试成败由种子决定：判定值 exam_roll < 成功率×10000 才过。
        # 填了成功率的职业，只在「这一步考得过」时才算拿到；没填的默认能过（页面会标出判定值）。
        self.exam_chance = exam_chance or {}
        self.confident = set()
        self.exam_req = {}          # 职业 -> (推荐等级, 技能差几段)
        self.tiebreak = []          # 同分时优先的职业（按顺序）
        # 体格阈值（Yizhuo 11-07，所有角色）：力量每到 5 的倍数体格 +1，那一点力量额外 +STR_BONUS 分
        self.str_bonus = self.STR_BONUS
        self.str_start = self.stats[1] if self.stats else None
        self.require_mid = False    # 路线里至少要考进一个新的中级职业（Yizhuo 11-06）

    @property
    def keep_classes(self):
        """考了但没用来升级也照样保留（不显示成跳过）的职业：必考 + 「跳过时顺便考到」的（skip_take，11-25 伊欧战车兵）。"""
        return set(self.required) | set(getattr(self, "skip_take", ()) or ())

    def seed_at(self, step):
        while len(self.seeds) <= step:
            self.seeds.append(next_seed(self.seeds[-1]))
        return self.seeds[step]

    @lru_cache(maxsize=None)
    def result(self, step, level, cls):
        """第 step 步、等级 level 时用职业 cls 升级的 (得分, 加点)。"""
        g = level_up(self.seed_at(step), self.data.growth(self.name, cls, level), self.min_stats).gains
        return score(g, self.weights), tuple(g)

    def exam_value(self, step):
        """第 step 步考试的判定值（%）。"""
        return exam_roll(self.seed_at(step)) / 10_000

    # 没填游戏成功率的考试：判定值 ≥ UNKNOWN_CAP% 时保守按「过不了」算（要游戏显示接近 100% 才过），
    # 除非这个职业在 confident 里（技能、等级都够，预测 100%）。
    UNKNOWN_CAP = 90
    STR_BONUS = 3
    EARLY_EPS = 1e-4
    # 11-23 Yizhuo：考进新职业，早考和晚考差不多时越早越好（用它升级的级数多，熟练度更高）。
    # 「差不多」= 点数不少、金币不多、规划器内部分最多少这么多（约等于加权分 −3）
    EARLY_EXAM_TOL = 3.0

    def str_gain_bonus(self, cur_str, g):
        """当前力量 cur_str，这一级加点 g：跨过 5 的倍数几次 × STR_BONUS。"""
        if cur_str is None or not self.str_bonus or not g[1]:
            return 0
        return self.str_bonus * ((cur_str + g[1]) // 5 - cur_str // 5)

    def exam_pct(self, cls, level):
        """估计游戏显示的成功率（%）：填了游戏数字用游戏数字；否则按 exam_rate（等级差、技能差几段，见 run_plans.exam_req）。
        没有要求数据时返回 None。"""
        ch = self.exam_chance.get(cls)
        if ch is not None:
            return ch
        req = self.exam_req.get(cls)
        if cls in self.confident:
            if req is None:
                return 100
            req = (req[0], 0)     # 技能确认够了，但等级不够推荐等级时照样封顶
        if req is None:
            return None
        return exam_rate(level - req[0], req[1])

    def exam_ok(self, step, cls, level=None):
        pct = self.exam_pct(cls, self.level if level is None else level)
        roll = exam_roll(self.seed_at(step))
        if pct is None:
            return roll < self.UNKNOWN_CAP * 10_000
        return roll < pct * 10_000

    def ranked(self, step, level, classes):
        """按（真实分 + 偏好分）从高到低排；返回 [(真实分, 职业), ...]。"""
        rows = [(self.result(step, level, c)[0], c) for c in classes]
        # 同分时优先用阶级高的职业（中级 > 初级 > 基础），顺便练兵种精通
        return sorted(rows, key=lambda x: (-(x[0] + self.prefer.get(x[1], 0)), -_TIER_RANK.get(_TIER.get(x[1], ""), 0), self._tb(x[1])))

    def _tb(self, cls):
        """同分同阶级时按 tiebreak 列表的顺序优先（列表外的排后面）。"""
        return self.tiebreak.index(cls) if cls in self.tiebreak else len(self.tiebreak)

    def best_plan(self, max_exams: int) -> Plan:
        if getattr(self, "rule_based", False):
            return self.rule_plan()
        return self.dp_plan(max_exams)

    def dp_plan(self, max_exams: int) -> Plan:
        m0 = (self.str_start % 5) if self.str_start is not None else None

        @lru_cache(maxsize=None)
        def go(step, done, extra, exams_left, m, nb=0):
            """返回 (之后能拿的最高分, 动作列表)。extra = 考到手的新职业；m = 力量 mod 5（体格阈值用）。"""
            if done == self.n_levels:
                missing = [c for c in self.required if c not in extra]
                if self.require_mid and not any(_TIER_RANK.get(_TIER.get(c, ""), 0) >= 2 for c in extra):
                    missing.append("中级")
                return (0, ()) if not missing else (float("-inf"), ())
            usable = self.owned + extra
            fz = getattr(self, "forced", None)
            if fz and step < len(fz):   # 前面几步按给定的动作走（算「按 35 级路线走、之后再最优」用）
                a, c = fz[step]
                if a == "升级":
                    if c not in usable:
                        return (float("-inf"), ())
                    s, g = self.result(step, self.level + done, c)
                    b = self.str_gain_bonus(m, g) if m is not None else 0
                    m2 = (m + g[1]) % 5 if m is not None else None
                    rest, acts = go(step + 1, done + 1, extra, exams_left, m2, nb)
                    return (s + self.prefer.get(c, 0) + b + rest, (("升级", c),) + acts)
                if exams_left <= 0:
                    return (float("-inf"), ())
                new = None if c == "跳过" or not self.exam_ok(step, c, self.level + done) else c
                nxt = extra if new is None or new in extra else tuple(sorted(extra + (new,)))
                rest, acts = go(step + 1, done, nxt, exams_left - 1, m, nb + 1)
                return (rest, (("考试", c),) + acts)
            # 选项 1：用已有职业升级（考虑体格阈值：力量凑到 5 的倍数有加分，所以不一定只看这一级）
            best = (float("-inf"), ())
            for s, cls in self.ranked(step, self.level + done, usable):
                g = self.result(step, self.level + done, cls)[1]
                b = self.str_gain_bonus(m, g) if m is not None else 0
                m2 = (m + g[1]) % 5 if m is not None else None
                rest, acts = go(step + 1, done + 1, extra, exams_left, m2, nb)
                v = s + self.prefer.get(cls, 0) + b + rest
                if v > best[0]:
                    best = (v, (("升级", cls),) + acts)
            # 剩下的考试次数不够考完必考职业时，只能先考
            need = sum(1 for c in self.required if c not in extra)
            if need > exams_left:
                best = (float("-inf"), ())
            # 选项 2：考试（考一个新职业，或纯跳过）
            # Yizhuo 11-08（P2）：这一级升级的加权分 ≥ skip_below 时不跳过（纯跳过、或考一个初级职业当跳过都不行）
            sb = getattr(self, "skip_below", None)
            lv_best = max((s for s, _ in self.ranked(step, self.level + done, usable)), default=0) if sb is not None else None
            if exams_left > 0:
                for new in (None,) + tuple(sorted((c for c in self.exam_options if c not in extra),
                                                  key=lambda c: _TIER_RANK.get(_TIER.get(c, ""), 2))):
                    if new is not None and not self.exam_ok(step, new, self.level + done):
                        continue
                    ac = getattr(self, "adv_cap", None)
                    if ac is not None and new is not None and _TIER_RANK.get(_TIER.get(new, ""), 2) >= 3 and \
                            sum(_TIER_RANK.get(_TIER.get(x, ""), 2) >= 3 for x in extra) >= ac:
                        continue   # 上级职业每人只转一次
                    mc = getattr(self, "mid_cap", None)
                    if mc is not None and new is not None and _TIER_RANK.get(_TIER.get(new, ""), 2) >= 2 and \
                            sum(_TIER_RANK.get(_TIER.get(x, ""), 2) >= 2 for x in extra) >= mc:
                        continue   # 限制中级职业个数（算「多转一个中级值多少」用）
                    if sb is not None and lv_best >= sb and new not in self.required and \
                            (new is None or _TIER_RANK.get(_TIER.get(new, ""), 2) < 2):
                        continue   # 升级够 sb 分：不当跳过用   # 这一步考这个职业会失败（等于纯跳过，已由 None 覆盖）
                    basic = new is None or _TIER_RANK.get(_TIER.get(new, ""), 2) < 2
                    bc = getattr(self, "basic_cap", None)
                    if bc is not None and basic and nb >= bc:
                        continue   # 初级/跳过次数固定（算「多转一个中级值多少」用）
                    nxt = extra if new is None else tuple(sorted(extra + (new,)))
                    rest, acts = go(step + 1, done, nxt, exams_left - 1, m, nb + basic)
                    # Yizhuo 11-08：同分时，能考过的新职业优先于跳过，而且越早考越好（极小的虚拟分，只破平局）
                    # 同分的几个新职业里先取级别低的（手形便宜、门槛按初级算）
                    if new is not None:
                        rest += self.EARLY_EPS * (self.n_levels - done + 1)
                    gpp = getattr(self, "gold_per_pt", None)
                    if gpp:   # 11-08 晚：手形金币换成加权分扣掉（跳过按初级手形）
                        t = "初级" if new is None else _TIER.get(new, "中级")
                        rest -= self.permit_gold.get(t, self.permit_gold["中级"]) / gpp
                    if rest > best[0]:
                        best = (rest, (("考试", new or "跳过"),) + acts)
            return best

        best_score, actions = go(0, 0, (), max_exams, m0)
        if best_score == float("-inf"):
            return None   # 这个考试次数下满足不了必考条件（必考职业 / 至少一个中级）
        raw_actions = actions
        actions, notes = self.rebalance(actions)
        # Yizhuo 11-08：转职到的职业后面没用来升级（也不是必考的）→ 只是为了跳过，就写「跳过」
        used = {c for a, c in actions if a == "升级"}
        actions = tuple(("考试", "跳过") if a == "考试" and c != "跳过" and c not in used and c not in self.keep_classes else (a, c)
                        for a, c in actions)
        rows = self._rows(actions)
        for r in rows:
            r.balance_note = notes.get(r.step, "")
        total = sum(r.score + r.bonus for r in rows if r.action == "升级")
        pl = Plan(sum(a == "考试" for a, _ in actions), total, rows)
        pl.raw_actions = raw_actions
        return pl

    # ================= 11-08 晚：规则式规划（Yizhuo 定的逻辑，取代按 K 次转职求最优的 DP） =================
    # 每一级：先按「均衡后的权重 + 体格加分」挑已有职业里最好的升级；
    #   这一级最好的分 < 跳过阈值 → 不升级，用这个种子转职：有「要转的职业」且这一步能过就转职，否则跳过；
    #   要转的职业（必转 + 值得转的）如果一直遇不到低分级，就在「升级分 < 该职业手形价换算的分」的第一个能过的级转。
    # 要转哪些职业：从必转出发，逐个试加候选职业，净值（加权分 − 手形金币 ÷ 每分金币）变高才加。
    def _tie_terms(self):
        """同分时的微小偏好（阶级高 > 必考 > tiebreak 顺序），按职业记下来；required/tiebreak 变了会重算。"""
        key = (tuple(self.required), tuple(self.tiebreak))
        if self.__dict__.get("_tie_key") != key:
            self._tie_key, cache = key, {}
            def tie(c):
                v = cache.get(c)
                if v is None:
                    v = cache[c] = 1e-6 * _TIER_RANK.get(_TIER.get(c, ""), 0) + 5e-7 * (c in self.required) - 1e-9 * self._tb(c)
                return v
            self._tie_fn = tie
        return self._tie_fn

    def _future15(self, step, lv, owned, w, cur_str):
        """跳过条件②用的「未来 15 级」每级最好分（含均衡权重和体格加分）。
        同一组（步、等级、已有职业、权重、力量）在一次规划里会被反复算上万次，所以记下来（性能，11-26）。"""
        key = (step, lv, owned, w, cur_str, self.str_bonus, self.min_stats)
        memo = self.__dict__.setdefault("_fut_memo", {})
        hit = memo.get(key)
        if hit is not None:
            return hit
        fut, fs = [], cur_str
        for j in range(step + 1, step + 16):
            gs = [self.result(j, lv, x)[1] for x in owned]
            vals = [sum(a * b for a, b in zip(g, w)) + (self.str_gain_bonus(fs, g) if fs is not None else 0) for g in gs]
            k = max(range(len(vals)), key=vals.__getitem__)   # 和 max(owned, key=...) 一样取第一个最大
            fut.append(vals[k])
            if fs is not None:
                fs += gs[k][1]
        memo[key] = fut
        return fut

    def _sim(self, targets, t_class=None):
        tc = dict(t_class or {})
        gpp = getattr(self, "gold_per_pt", None) or 62.5
        pg = getattr(self, "permit_gold", {"初级": 300, "中级": 500, "上级": 3000})
        t_skip = getattr(self, "skip_threshold", 300 / gpp)
        no_skip = getattr(self, "no_skip_steps", set())
        forced = getattr(self, "forced", None) or ()
        owned, pend = list(self.owned), [c for c in targets]
        stats = list(self.stats) if self.stats else None
        cur_str = self.str_start
        acts, notes, step, done, gold = [], {}, 0, 0, 0
        timing.COUNTERS["模拟次数 _sim"] += 1
        reasons = notes["why"] = {}   # 每一步为什么这样走（检查和页面用）：step -> {s, avg15, c1, c2, want_skip, pick}
        budget = getattr(self, "seed_budget", None)   # 11-17 Yizhuo：按用掉的乱数个数比，不按等级
        ea = getattr(self, "exam_at", None) or {}
        rule = getattr(self, "skip_rule", None)
        nss = getattr(self, "no_skip_seeds", ()) or ()
        skip_take = tuple(getattr(self, "skip_take", ()) or ())
        while (done < self.n_levels if budget is None else step < budget) and step < 400:
            lv = self.level + done
            if step < len(forced):
                a, c = forced[step]
            else:
                w, why = self.balanced_weights(stats) if stats else ([float(x) for x in self.weights], "")
                tie = self._tie_terms()
                w0, w1, w2, w3, w4, w5, w6, w7, w8 = w
                res = self.result
                def val(c):
                    g = res(step, lv, c)[1]
                    return (g[0] * w0 + g[1] * w1 + g[2] * w2 + g[3] * w3 + g[4] * w4 + g[5] * w5 + g[6] * w6 + g[7] * w7 + g[8] * w8) \
                        + (self.str_gain_bonus(cur_str, g) if cur_str is not None else 0) + tie(c)
                best = max(owned, key=val)
                sbest = val(best)
                passable = [c for c in pend if c not in ea.values() and self.exam_ok(step, c, lv)]
                # 11-09 Yizhuo：跳过条件 = ①这一级 ≤ 绝对分数线 ②比未来 15 级平均低 ≥ 百分比；P0 满足其一，P1/P2 都满足
                if rule:
                    # 11-11 Yizhuo：跳过判断也用含均衡和体格加分的分（和选职业同一个分）
                    s_raw = sbest
                    fut = self._future15(step, lv, tuple(owned), tuple(w), cur_str)
                    c1 = s_raw <= rule["cap"] + 1e-6
                    c2 = s_raw <= sum(fut) / len(fut) * (1 - rule["pct"]) + 1e-6
                    want_skip = (c1 or c2) if rule["or"] else (c1 and c2)
                    reasons[step] = {"s": round(s_raw, 2), "avg15": round(sum(fut) / len(fut), 2), "c1": c1, "c2": c2}
                else:
                    want_skip = sbest < t_skip
                    reasons[step] = {"s": round(sbest, 2)}
                keep = self.seed_at(step) in nss   # Yizhuo 指定保留的级：不跳也不考
                if keep:
                    want_skip = False
                pick = None
                for c in ([] if keep else passable):   # 按 targets 的顺序（必转在前）
                    thr = tc.get(c, pg.get(_TIER.get(c, "中级"), 500) / gpp)
                    if want_skip or sbest < thr:
                        pick = c
                        break
                # 11-17：指定在这一步考（挑了用哪个种子考，见 _retime）
                if step in ea and not keep and ea[step] not in owned and self.exam_ok(step, ea[step], lv):   # 指定保留的种子不考
                    pick = ea[step]
                    pend = pend if pick in pend else pend + [pick]
                reasons[step].update(want_skip=want_skip, keep=keep, pick=pick)
                if pick is not None:
                    a, c = "考试", pick
                elif want_skip and step not in no_skip:
                    a, c = "考试", "跳过"
                    # 11-25 Yizhuo：伊欧要跳过时用「考战车兵」来跳，保证拿到这个职业（skip_take，能考过才用）
                    for x in skip_take:
                        if x not in owned and self.exam_ok(step, x, lv):
                            c = x
                            break
                else:
                    a, c = "升级", best
                    raw_best = why and max(owned, key=lambda x: (self.result(step, lv, x)[0] + (self.str_gain_bonus(cur_str, self.result(step, lv, x)[1]) if cur_str is not None else 0), x == best))
                    if why and raw_best != best:
                        g0, g1 = self.result(step, lv, raw_best)[1], self.result(step, lv, best)[1]
                        more = [STATS[i] for i in range(9) if g1[i] > g0[i]]
                        less = [STATS[i] for i in range(9) if g1[i] < g0[i]]
                        notes[step] = f"均衡：{why}，所以用{best}换{raw_best}（多 {' '.join(more) or '—'}、少 {' '.join(less) or '—'}）"
            if a == "考试":
                if c != "跳过" and c is not None and self.exam_ok(step, c, lv):
                    owned.append(c)
                    if c in pend:
                        pend.remove(c)
                    gold += pg.get(_TIER.get(c, "中级"), 500)
                else:
                    gold += pg["初级"]
                acts.append(("考试", c if c else "跳过"))
            else:
                g = self.result(step, lv, c)[1]
                if stats:
                    stats = [x + y for x, y in zip(stats, g)]
                if cur_str is not None:
                    cur_str += g[1]
                acts.append(("升级", c))
                done += 1
            step += 1
        total = 0
        cs = self.str_start
        st2 = 0
        for i, (a, c) in enumerate(acts):
            if a == "升级":
                sc, g = self.result(i, self.level + st2, c)
                total += sc + (self.str_gain_bonus(cs, g) if cs is not None else 0)
                if cs is not None:
                    cs += g[1]
                st2 += 1
        return tuple(acts), notes, total, gold, pend

    def rule_run(self, targets, must=()):
        """按规则走一遍（targets = 要转的职业，按优先顺序）；must 里的职业一定要转到（放宽转职分门槛直到转到）。
        返回 (动作, 均衡说明, 加权分, 手形金币, 没转到的) 或 None。"""
        gpp = getattr(self, "gold_per_pt", None) or 62.5
        must = set(self.required) | set(must)
        tc = {}
        for _ in range(40):
            acts, notes, total, gold, pend = self._sim(list(targets), tc)
            miss = [c for c in pend if c in must]
            if not miss:
                return acts, notes, total, gold, pend
            for c in miss:
                tc[c] = tc.get(c, self.permit_gold.get(_TIER.get(c, "中级"), 500) / gpp) + 2
        return None

    # 11-11 Yizhuo：考前练技能也有成本。每练 1 段（E→E+、E+→D…）扣 0.5 加权分（Yizhuo 定：米迦考弓箭手，分界 0.9）
    TRAIN_PTS_PER_RANK = 0.5

    def train_ranks(self, acts):
        """路线里真正考进并用来升级的职业，考前一共要练几段。"""
        used = {c for a, c in acts if a == "升级"}
        ranks = getattr(self, "exam_train_ranks", {}) or {}
        return sum(ranks.get(c, 0) for a, c in acts if a == "考试" and c in used)

    def floor_lifts(self, acts):
        """11-16：考进新职业时的保底。返回 {步: [(能力下标, 原值, 补到)]}，按裸能力比（raw_stats + 之前的加点）。"""
        raw = getattr(self, "raw_stats", None)
        floors = getattr(self, "floors", None) or {}
        if not raw or not floors:
            return {}
        st, owned, done, out = list(raw), set(self.owned), 0, {}
        for step, (a, c) in enumerate(acts):
            lv = self.level + done
            if a == "升级":
                st = [x + y for x, y in zip(st, self.result(step, lv, c)[1])]
                done += 1
            elif c not in (None, "跳过") and c not in owned and self.exam_ok(step, c, lv):
                owned.add(c)
                f = floors.get(c)
                if f:
                    lift = [(i, st[i], f[i]) for i in range(9) if f[i] > st[i]]
                    if lift:
                        out[step] = lift
                        for i, _, v in lift:
                            st[i] = v
        return out

    def floor_value(self, acts):
        """保底补上的点按权重算分（计入净值，不计入「加权分」）。"""
        return sum(self.weights[i] * (v - a) for lifts in self.floor_lifts(acts).values() for i, a, v in lifts)

    def plan_net(self, acts, total, gold):
        """净值 = 加权分 + 保底分 − 手形金币 ÷ 每分金币 − 训练段数 × 每段扣分。"""
        gpp = getattr(self, "gold_per_pt", None) or 62.5
        return total + self.floor_value(acts) - gold / gpp - self.train_ranks(acts) * self.TRAIN_PTS_PER_RANK

    def rule_plan(self):
        with timing.timed(f"规划 {self.name}"):
            return self._rule_plan_timed()

    def _rule_plan_timed(self):
        """11-17 Yizhuo：比较路线要按「用掉同样多的乱数」比，不按到同一级比（考试/跳过都会用掉一个乱数，
        按等级比时多考一次的路线会多算/少算边界上的一个种子）。做法：先照旧规划到目标级，记下用掉几个乱数 S；
        再在「前 S 个乱数」这个窗口里挑要考的职业；窗口跟着选出的路线更新，最多 3 轮；最后把选好的职业照常走到目标级。"""
        if not getattr(self, "equal_seeds", False):
            self.seed_budget = None
            return self._rule_plan()
        self.seed_budget = None
        pl = self._rule_plan()
        seen = set()
        for _ in range(3):
            if pl is None:
                break
            S = len(pl.raw_actions)
            if S in seen:
                break
            seen.add(S)
            self.seed_budget = S
            sel = self._rule_plan()
            self.seed_budget = None
            if sel is None:
                break
            pl = self._rule_plan(fixed=list(sel.targets), mid=getattr(self, "mid_trained", None))
        pl = self._pair_polish(pl)
        self.window = len(pl.raw_actions) if pl else None
        self.seed_budget = None
        mt = getattr(self, "mid_train", None) or {}
        pt = getattr(self, "_mid_patched", set())
        self.mid_trained = next((c for c in (pl.targets if pl else []) if c in pt), None)
        return pl

    PAIR_TOL = 1.0   # 和 checks.P12 同一个容差：差 1 分以内算一样

    def _pair_polish(self, pl):
        """11-25（重开后 P12 抓到艾丝、伊欧）：贪心 + 「必须考到中级」的补丁会漏掉更好的组合。
        最后把要考的职业整体换成任意 1～2 个职业（任意顺序），在现在路线用掉的乱数窗口里比净值（和 checks.P12 同一口径），
        高出 PAIR_TOL 以上、且完整走到目标级时每个职业都真的考到并用上，就换成最高的那个。"""
        import itertools
        if pl is None or getattr(self, "_polishing", False):
            return pl
        self._polishing = True
        sv_at, sv_win = getattr(self, "exam_at", None), getattr(self, "window", None)
        try:
            def own(x):
                self.window = len(x.raw_actions)
                r = self.window_value(x.targets, self.window)
                return r[3] if r else float("-inf")
            req = list(dict.fromkeys(self.required))
            cands = [c for c in self.exam_options if c not in req]
            mine = own(pl)
            best = None
            for k in (1, 2):
                for combo in itertools.combinations(cands, k):
                    for order in itertools.permutations(combo):
                        S = len(pl.raw_actions)
                        q = self.window_value(req + list(order), S)   # 先用便宜的窗口值筛
                        if q is None or q[3] <= mine + self.PAIR_TOL + 1e-9:
                            continue
                        self.exam_at = None
                        x = self._rule_plan(fixed=req + list(order), mid=getattr(self, "mid_trained", None))
                        if x is None or not all(any(a == "升级" and c2 == c for a, c2 in x.raw_actions) for c in combo):
                            continue
                        if getattr(self, "require_mid", False) and not any(
                                a == "考试" and _TIER_RANK.get(_TIER.get(c, ""), 0) == 2 and ("升级", c) in x.raw_actions
                                for a, c in x.raw_actions):
                            continue
                        v = q[3]   # 11-17 规则：和现在的路线按同样多的乱数（现在路线的窗口）比
                        if v > (best[0] if best else mine + self.PAIR_TOL) + 1e-9:
                            best = (v, x, dict(self.exam_at or {}))
            if best is None:
                self.exam_at, self.window = sv_at, sv_win
                return pl
            self.exam_at = best[2]
            return best[1]
        finally:
            self._polishing = False

    def window_value(self, targets, S=None, must=()):
        """同一个乱数窗口（前 S 个）里，按 targets 走的 (动作, 加权分, 金币, 净值)。"""
        sv, se = getattr(self, "seed_budget", None), getattr(self, "exam_at", None)
        self.seed_budget = S or getattr(self, "window", None)
        self.exam_at = {k: v for k, v in (se or {}).items() if v in targets}   # 选定的考试时机只对还在的职业有效
        try:
            r = self.rule_run(list(targets), tuple(must))
        finally:
            self.seed_budget, self.exam_at = sv, se
        if r is None:
            return None
        return r[0], r[2], r[3], self.plan_net(r[0], r[2], r[3])

    def _pts(self, acts):
        """路线的总加点数（不加权）。"""
        done, n = 0, 0
        for st, (a, c) in enumerate(acts):
            if a == "升级":
                n += sum(self.result(st, self.level + done, c)[1])
                done += 1
        return n

    def _retime(self, targets, cur, run, net, got):
        """11-17（审查）：考试用哪个种子考也要挑。
        ① 每个要考的职业，试着换到窗口里别的能过的种子考，同样多的乱数下分更高就换（努蒂奴土匪别吃掉好种子）；
        ② 考试和跳过挨着时，让跳过用判定值高的那个种子（更稳考不过，不会多拿职业），考试用低的（更稳考过），分不变才换（艾丝 Lv30）。"""
        if cur is None:
            return cur
        base_t = set(self.required)
        for c in list(targets):
            n = len(cur[0])
            for st in range(n):
                trial = dict(self.exam_at or {})
                trial = {k: v for k, v in trial.items() if v != c}
                trial[st] = c
                sv = self.exam_at
                self.exam_at = trial
                r = run(targets)
                self.exam_at = sv
                if r is not None and ("考试", c) in r[0] and list(r[0]).index(("考试", c)) == st \
                        and all(got(r, x) for x in targets if x not in base_t) and net(r) > net(cur) + 1e-9:
                    self.exam_at, cur = trial, r
        # ③ 11-23 Yizhuo：差不多时早考（熟练度更高）。每个要考的职业，从最早的种子开始试，第一个「差不多」的就用
        tol = getattr(self, "early_exam_tol", self.EARLY_EXAM_TOL)
        for c in list(targets):
            acts0 = list(cur[0])
            if ("考试", c) not in acts0:
                continue
            i = acts0.index(("考试", c))
            for st in range(i):
                if acts0[st][0] == "考试":
                    continue
                trial = {k: v for k, v in (self.exam_at or {}).items() if v != c}
                trial[st] = c
                sv, nk0 = self.exam_at, set(getattr(self, "no_skip_seeds", ()) or ())
                self.exam_at = trial
                r = run(targets)
                nk = nk0
                if r is not None and r[3] > cur[3]:
                    # 早考后规则又多跳过一次（多花钱）：再试「原来不跳的那几级照样不跳」，金币不变才算差不多
                    extra = {self.seed_at(k) for k, (a, x) in enumerate(r[0]) if a == "考试" and x == "跳过"
                             and k < len(cur[0]) and cur[0][k] != ("考试", "跳过")}
                    nk = nk0 | extra
                    self.no_skip_seeds = nk
                    r = run(targets)
                self.exam_at, self.no_skip_seeds = sv, nk0
                if r is not None and ("考试", c) in r[0] and list(r[0]).index(("考试", c)) == st \
                        and all(got(r, x) for x in targets if x not in base_t) and r[3] <= cur[3] \
                        and self._pts(r[0]) >= self._pts(cur[0]) and net(r) >= net(cur) - tol - 1e-9:
                    self.exam_at, self.no_skip_seeds, cur = trial, nk, r
                    break
        # ② 挨着的 考试/跳过 对调
        acts = list(cur[0])
        for i in range(len(acts) - 1):
            pair = (acts[i], acts[i + 1])
            if not all(a == "考试" for a, _ in pair):
                continue
            (a1, c1), (a2, c2) = pair
            if (c1 == "跳过") == (c2 == "跳过"):
                continue
            ex, sk = (i, i + 1) if c2 == "跳过" else (i + 1, i)
            if self.exam_value(sk) >= self.exam_value(ex):
                continue
            c = acts[ex][1]
            trial = {k: v for k, v in (self.exam_at or {}).items() if v != c}
            trial[sk] = c
            sv = self.exam_at
            self.exam_at = trial
            r = run(targets)
            self.exam_at = sv
            if r is not None and r[0][sk] == ("考试", c) and net(r) >= net(cur) - 1e-9:
                self.exam_at, cur = trial, r
                acts = list(cur[0])
        return cur

    def _rule_plan(self, fixed=None, mid=None):
        if fixed is None:
            self.exam_at = {}
            # ③ 早考时为了不多花钱锁住的「不跳」种子只属于那一次规划，重新规划时恢复原样
            if not hasattr(self, "_base_no_skip"):
                self._base_no_skip = set(getattr(self, "no_skip_seeds", ()) or ())
            self.no_skip_seeds = set(self._base_no_skip)
        gpp = getattr(self, "gold_per_pt", None) or 62.5
        base_t = list(dict.fromkeys(self.required))
        run = self.rule_run
        def net(r):
            return self.plan_net(r[0], r[2], r[3]) if r else float("-inf")
        def got(r, c):
            return r is not None and ("考试", c) in r[0] and any(a == "升级" and x == c for a, x in r[0])
        def margin(r, c):
            """这场考试的把握：估计成功率 − 判定值（%）。同分时选把握大的（11-25：杨界 萨满 100% 和 弓箭手 8% 同分时选萨满）。"""
            lv = self.level
            for st, (a, x) in enumerate(r[0]):
                if a == "升级":
                    lv += 1
                elif x == c:
                    pct = self.exam_pct(c, lv)
                    return (100 if pct is None else pct) - exam_roll(self.seed_at(st)) / 10_000
            return 0
        targets = list(base_t)
        cur = run(targets)
        cands = [c for c in self.exam_options if c not in targets]
        ac = getattr(self, "adv_cap", None)
        if fixed is not None:
            targets = list(fixed)
            cur = run(targets)
            if cur is None or not all(got(cur, c) for c in targets if c not in base_t):
                cur = run(targets, tuple(targets))
            cands = []
        while fixed is None:
            best, bv = None, net(cur)
            for c in cands:
                if c in targets:
                    continue
                if ac is not None and _TIER_RANK.get(_TIER.get(c, ""), 2) >= 3 and \
                        sum(_TIER_RANK.get(_TIER.get(x, ""), 2) >= 3 for x in targets) >= ac:
                    continue
                r = run(targets + [c])
                # 11-16：单独加这场考试至少要多 min_exam_gain 分净值（米迦战车兵 +0.8 那种不考）
                if got(r, c) and net(r) > bv + getattr(self, "min_exam_gain", 0) + 1e-9:
                    best, bv = (c, r), net(r)
            if best is None:
                # 11-16：单场都不够 min_exam_gain 时，再试两场一起（P12 抓到杨界「重装步兵+萨满」合起来 +7）
                mg = getattr(self, "min_exam_gain", 0)
                if mg <= 0:
                    break
                rest = [c for c in cands if c not in targets]
                for i, c1 in enumerate(rest):
                    for c2 in rest:
                        if c2 == c1:
                            continue
                        r = run(targets + [c1, c2])
                        if got(r, c1) and got(r, c2) and net(r) > bv + 2 * mg + 1e-9:
                            best, bv = ((c1, c2), r), net(r)
                if best is None:
                    break
                targets.extend(best[0]); cur = best[1]
                continue
            targets.append(best[0]); cur = best[1]
        self.mid_missing = False
        if fixed is None and getattr(self, "require_mid", False) and not any(
                _TIER_RANK.get(_TIER.get(c, ""), 0) >= 2 and got(cur, c) for c in targets):
            # 至少转进一个新的中级（并用它升级）：净值最高的那个，就算亏也加
            opts = []
            for c in cands:
                if _TIER_RANK.get(_TIER.get(c, ""), 0) == 2 and c not in targets:
                    # 11-11：也试「只要必考 + 这个中级」，免得前面加的初级职业把中级挤掉
                    for tg in (targets + [c], list(base_t) + [c]):
                        r = run(tg, (c,))
                        if got(r, c):
                            opts.append((net(r), c, r, tg))
            mt = getattr(self, "mid_train", None) or {}
            if not opts and mt:
                # 11-17 Yizhuo：每人都要考进中级。不练技能的档位（P1/P2）考不过任何中级时，
                # 只为这一个中级破例练技能（练的段数照样按本档每段扣分），挑净值最高的那个
                sv_req, sv_rk, sv_ch = dict(self.exam_req), dict(self.exam_train_ranks or {}), dict(self.exam_chance or {})
                for c, (rec, rk) in mt.items():
                    if c in targets:
                        continue
                    self.exam_req = dict(sv_req, **{c: (rec, 0)})
                    self.exam_train_ranks = dict(sv_rk, **{c: rk})
                    self.exam_chance = {k: v for k, v in sv_ch.items() if k != c}
                    for tg in (targets + [c], list(base_t) + [c]):
                        r = run(tg, (c,))
                        if got(r, c):
                            opts.append((net(r), c, r, tg))
                self.exam_req, self.exam_train_ranks, self.exam_chance = sv_req, sv_rk, sv_ch
                if opts:
                    v, c, r, tg = max(opts, key=lambda x: x[0])
                    rec, rk = mt[c]
                    self.exam_req = dict(sv_req, **{c: (rec, 0)})
                    self.exam_train_ranks = dict(sv_rk, **{c: rk})
                    self.exam_chance = {k: v for k, v in sv_ch.items() if k != c}
                    self.mid_trained = c
                    self._mid_patched = getattr(self, "_mid_patched", set()) | {c}
            if opts:
                v, c, r, tg = max(opts, key=lambda x: (round(x[0], 6), margin(x[2], x[1])))
                targets = list(tg); cur = r
            else:
                self.mid_missing = True
        if fixed is None and cur is not None:
            # 11-17：贪心先加的职业，后来别的职业加进来后可能已经没用了（米迦：猎兵+弓箭手 和 只考弓箭手 同分同金币）。
            # 去掉不减分的那个——多拿一个职业不是好事（Yizhuo 11-16）
            changed = True
            while changed:
                changed = False
                for c in [t for t in targets if t not in base_t]:
                    rest = [t for t in targets if t != c]
                    r = run(rest)
                    if r is not None and all(got(r, x) for x in rest if x not in base_t) and net(r) >= net(cur) - 1e-9 \
                            and (not getattr(self, "require_mid", False) or any(_TIER_RANK.get(_TIER.get(x, ""), 0) == 2 and got(r, x) for x in rest)
                                 or not any(_TIER_RANK.get(_TIER.get(x, ""), 0) == 2 and got(cur, x) for x in targets)):
                        targets, cur, changed = rest, r, True
                        break
        if fixed is None and cur is not None:
            cur = self._retime([t for t in targets], cur, run, net, got)
        if cur is None:
            return None
        acts, notes, total, gold, pend = cur
        # 转过去后面没用来升级、也不是必转的 → 显示成「跳过」（价格按实际买的手形）
        used = {c for a, c in acts if a == "升级"}
        shown = tuple(("考试", "跳过") if a == "考试" and c != "跳过" and c not in used and c not in self.keep_classes else (a, c) for a, c in acts)
        rows = self._rows(shown)
        for r in rows:
            r.balance_note = notes.get(r.step, "")
        total = sum(r.score + r.bonus for r in rows if r.action == "升级")
        pl = Plan(sum(a == "考试" for a, _ in acts), total, rows)
        pl.why = notes.get("why", {})
        # 11-11 Yizhuo：跳过 = 不学会新职业。考进去却从没用来升级（也不是必考）的职业，当成真正的跳过：不算学会，按初级手形算钱
        fixed = []
        for a, c in acts:
            if a == "考试" and c not in (None, "跳过") and c not in used and c not in self.keep_classes:
                gold -= self.permit_gold.get(_TIER.get(c, "中级"), 500) - self.permit_gold["初级"]
                targets = [t for t in targets if t != c]
                c = "跳过"
            fixed.append((a, c))
        acts = tuple(fixed)
        pl.raw_actions, pl.gold, pl.targets = acts, gold, list(targets)
        self.annotate(pl)
        return pl

    def skip_pct(self, cls, level):
        """跳过用的初级考试：按现在的真实技能估成功率（不假设先练）。"""
        req = (getattr(self, "skip_req", {}) or {}).get(cls)
        if req is None:
            return None
        return exam_rate(level - req[0], req[1])

    def annotate(self, pl):
        """11-16：每个考试/跳过行写上保底收益；跳过用哪场初级考试。
        Yizhuo 11-16：跳过时多拿一个职业不是好事（以后能拿来跳过的考试就少一个）→ 优先选这一步会「考不过」的初级考试，
        职业池不变；只有都会考过时才用掉一个，并记下还剩几个。"""
        lifts = self.floor_lifts(pl.raw_actions)
        owned, done = set(self.owned), 0
        pool = [c for c in (getattr(self, "skip_pool", None) or []) if c not in owned]
        roll_of = lambda st: exam_roll(self.seed_at(st))
        for r, (a, c) in zip(pl.rows, pl.raw_actions):
            lv = self.level + done
            if a == "升级":
                done += 1
                continue
            r.level_at = lv
            r.floor = [(STATS[i], x, v) for i, x, v in lifts.get(r.step, [])]
            if c == "跳过":
                fail, pas = [], []
                for x in pool:
                    pc = self.skip_pct(x, lv)
                    (pas if pc is not None and roll_of(r.step) < pc * 10_000 else fail).append(x)
                r.skip_fail, r.skip_class = fail, None
                if not fail and pas:
                    r.skip_class = pas[0]        # 只能用会考过的：用掉一个职业
                    pool.remove(pas[0])
                r.skip_none = not fail and not pas
                r.skip_left = len(pool)
            else:
                owned.add(c)
                if c in pool and self.exam_ok(r.step, c, lv):
                    pool.remove(c)

    def balanced_weights(self, stats):
        """按当前能力算出调整后的权重和说明。只看能力和权重设置，所以同样的输入记下来（性能，11-26）。"""
        key = (tuple(stats) if stats else None, tuple(self.weights), self.balance_gap, self.balance_step)
        memo = self.__dict__.setdefault("_bw_memo", {})
        hit = memo.get(key)
        if hit is None:
            hit = memo[key] = self._balanced_weights(stats)
        return list(hit[0]), hit[1]

    def _balanced_weights(self, stats):
        w = [float(x) for x in self.weights]
        if not stats:
            return w, ""
        # 11-08 Yizhuo：只在高权重的几项之间做均衡；11-11 扩到权重 4 和 5
        group = [i for i in range(9) if self.weights[i] >= 4]
        if len(group) < 2:
            return w, ""
        low = min(group, key=lambda i: stats[i])
        notes = []
        for i in group:
            for j in group:
                gap = stats[i] - stats[j]
                if gap > self.balance_gap:
                    d = min(2.0, (gap - self.balance_gap) * self.balance_step)
                    w[i] -= d / 2
                    w[j] += d / 2
                    notes.append(f"{STATS[i]}{stats[i]} 比 {STATS[j]}{stats[j]} 高 {gap}")
        return w, "；".join(notes)

    def rebalance(self, actions):
        """按成长均衡重选每一级的职业（考试位置不变），返回新动作和每步说明。"""
        if not self.stats:
            return actions, {}
        stats, usable, out, notes = list(self.stats), list(self.owned), [], {}
        done = 0
        for step, (act, cls) in enumerate(actions):
            if act != "升级":
                if cls in self.exam_options:
                    usable.append(cls)
                out.append((act, cls))
                continue
            lv = self.level + done
            w, why = self.balanced_weights(stats)
            def bal(c):
                g = self.result(step, lv, c)[1]
                return sum(a * b for a, b in zip(g, w)) + self.prefer.get(c, 0)
            cand = usable
            if self.str_start is not None and self.str_bonus:
                # 体格阈值：均衡只在「力量涨不涨」和原选择一样的职业里换，不打乱力量凑 5 的计划
                g_cls1 = self.result(step, lv, cls)[1][1]
                cand = [c for c in usable if self.result(step, lv, c)[1][1] == g_cls1] or usable
            pick = max(cand, key=lambda c: (round(bal(c), 9), c == cls, _TIER_RANK.get(_TIER.get(c, ""), 0), -self._tb(c)))
            boosted = [i for i in range(9) if w[i] > self.weights[i] + 1e-9]
            g0_, g1_ = self.result(step, lv, cls)[1], self.result(step, lv, pick)[1]
            if pick != cls and not any(g1_[i] > g0_[i] for i in boosted):
                pick = cls    # 换了也补不到落后的那项，不换
            if pick != cls and bal(pick) > bal(cls) + 1e-9:
                g0, g1 = self.result(step, lv, cls)[1], self.result(step, lv, pick)[1]
                more = [STATS[i] for i in range(9) if g1[i] > g0[i]]
                less = [STATS[i] for i in range(9) if g1[i] < g0[i]]
                notes[step] = f"均衡：{why}，所以用{pick}换{cls}（多 {' '.join(more) or '—'}、少 {' '.join(less) or '—'}）"
            else:
                pick = cls
            out.append((act, pick))
            stats = [a + b for a, b in zip(stats, self.result(step, lv, pick)[1])]
            done += 1
        return out, notes

    def _rows(self, actions):
        rows, done, usable = [], 0, list(self.owned)
        cur_str = self.str_start
        for step, (act, cls) in enumerate(actions):
            lv = self.level + done
            ranked = self.ranked(step, lv, usable)
            compare = "  ".join(f"{c}{s}" for s, c in ranked)
            if act == "升级":
                s, g = self.result(step, lv, cls)
                alts = []
                # 所有候选职业（已有 + 可考）里，有没有涨「不同项」的；没到手的标「需考」
                everyone = list(dict.fromkeys(usable + list(self.exam_options)))
                for s2, c2 in self.ranked(step, lv, everyone):
                    g2 = self.result(step, lv, c2)[1]
                    gained = [STATS[i] for i in range(9) if g2[i] > g[i]]
                    lost = [STATS[i] for i in range(9) if g2[i] < g[i]]
                    if c2 != cls and gained:      # 至少多涨了一项 → 不是单纯变差
                        alts.append(f"{c2}{'' if c2 in usable else '[需考]'}{s2}（+{' '.join(gained)}" + (f" −{' '.join(lost)}" if lost else "") + "）")
                row = PlanRow(step, self.seed_at(step), act, cls, lv, list(g), s, compare, "；".join(alts))
                row._best = ranked[0][0]
                if cur_str is not None:
                    row.bonus = self.str_gain_bonus(cur_str, g)
                    if row.bonus:
                        row.str_note = f"体格：力量 {cur_str}→{cur_str + g[1]}（5 的倍数，体格 +1），+{row.bonus} 分"
                    cur_str += g[1]
                rows.append(row)
                done += 1
            else:
                s, c = ranked[0]
                g = self.result(step, lv, c)[1]
                rows.append(PlanRow(step, self.seed_at(step), act, cls, None, list(g), s, compare))
                if cls in self.exam_options:
                    usable.append(cls)
        # 为了体格少拿分的级：这一级不是最高分、但多 1 点力量，让后面某一级力量到 5 的倍数
        ups = [r for r in rows if r.action == "升级"]
        for i, r in enumerate(ups):
            best = getattr(r, "_best", r.score)
            if r.score < best and r.gains[1] > 0 and not r.str_note:
                end = (cur_str if cur_str is not None else 0)
                if cur_str is None:
                    continue
                if end % 5 == 0:
                    r.str_note = (f"体格：这一级比最高分少 {best - r.score} 分，换 1 点力量。少了这 1 点，"
                                  f"力量到 Lv{self.level + self.n_levels} 只有 {end - 1}，拿不到 {end} 的体格 +1（+{self.str_bonus} 分）")
                else:
                    r.str_note = f"体格：这一级比最高分少 {best - r.score} 分，换 1 点力量，让力量更早到 5 的倍数（体格 +1）"
        return rows


def exam_tiers(planner, plan):
    """这条路线里每场考试的级别：新职业按 fw_classes 的级别，纯跳过按初级（考任意一个初级就行）。"""
    # 考到但路线里从没用来升级的职业 = 等于跳过（只是顺便拿到职业），门槛按初级算
    used = {r.cls for r in plan.rows if r.action == "升级"}
    return ["初级" if (r.cls not in planner.exam_options or r.cls not in used) else _TIER.get(r.cls, "中级")
            for r in plan.rows if r.action != "升级"]


def _load_tiers():
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fw_classes.json")
    try:
        return {c["name"]: c["tier"] for c in json.load(open(path, encoding="utf-8"))}
    except OSError:
        return {}


_TIER = _load_tiers()
_TIER_RANK = {"基础": 0, "初级": 1, "中级": 2, "高级": 3, "上级": 3, "最上级": 4}


def exam_gold(planner, tiers):
    """这些级别的转职要花多少手形金币。"""
    g = planner.permit_gold
    return sum(g.get(t, g["中级"]) for t in tiers)


def plan_gold(planner, plan):
    """一条路线实际花的手形金币：按考的那个职业的真实级别（考试当下就买手形）；纯跳过按初级。
    和 DP 里扣的完全一致（审查 11-08：以前最终净值把「没用上的中级」按初级算，两套成本）。"""
    acts = getattr(plan, "raw_actions", None) or tuple(("考试", r.cls) for r in plan.rows if r.action != "升级")
    return exam_gold(planner, ["初级" if c in (None, "跳过") else _TIER.get(c, "中级") for a, c in acts if a == "考试"])


def plan_all(planner: Planner, max_exams: int, min_gain_per_exam: int | None = None, min_gain_basic: int | None = None):
    """对每个考试上限求最优，再定建议考几次：
    多考的每一场，中级（及以上）要多 min_gain_per_exam 分、初级（含纯跳过）要多 min_gain_basic 分；
    可以一次多考几场（门槛相加），这样「先亏一点、再多考一场大赚」的组合不会漏掉。"""
    # 门槛默认用角色自己的（P0 角色 8/4，其他角色更高，省资源）
    th = getattr(planner, "thresholds", (8, 4))
    min_gain_per_exam = th[0] if min_gain_per_exam is None else min_gain_per_exam
    min_gain_basic = th[1] if min_gain_basic is None else min_gain_basic
    if getattr(planner, "rule_based", False):
        g = planner.rule_plan()
        plans = [None] * (g.exams + 1)
        plans[g.exams] = g
        if g.exams > 0:
            planner.rule_based = False
            try:
                p0 = planner.dp_plan(0)   # 不转职不跳过的对照（满足不了必转时为 None）
            finally:
                planner.rule_based = True
            plans[0] = p0
        return plans, g.exams
    plans = [planner.best_plan(k) for k in range(max_exams + 1)]
    ok = [p is not None and p.total > 0 for p in plans]
    if not any(ok) and getattr(planner, "require_mid", False):
        # 怎么考都进不了中级（考试都过不了）：放宽这条，照常规划，并记下来
        planner.require_mid, planner.mid_dropped = False, True
        plans = [planner.best_plan(k) for k in range(max_exams + 1)]
        ok = [p is not None and p.total > 0 for p in plans]
    if getattr(planner, "gold_per_pt", None) and any(ok):
        # 11-08 晚：目标 = 加权分 − 手形金币/（每分金币），规划时已经扣了；挑净值最高的（同分取转职少的）
        netv = lambda p: p.total - plan_gold(planner, p) / planner.gold_per_pt
        k = max((i for i in range(len(plans)) if ok[i]), key=lambda i: (round(netv(plans[i]), 6), -plans[i].exams, -i))
        return plans, k
    k = next((i for i, v in enumerate(ok) if v), 0)
    while True:
        base = exam_tiers(planner, plans[k])
        nxt, best = None, -1
        for m in range(k + 1, len(plans)):
            if not ok[m]:
                continue
            t = exam_tiers(planner, plans[m])
            if getattr(planner, "gold_per_pt", None):
                # 11-08 晚：按手形金币算（跳过按初级手形），换成加权分
                need = (exam_gold(planner, t) - exam_gold(planner, base)) / planner.gold_per_pt
            else:
                mid = max(0, sum(x != "初级" for x in t) - sum(x != "初级" for x in base))
                need = mid * min_gain_per_exam + (m - k - mid) * min_gain_basic
            surplus = plans[m].total - plans[k].total - need
            if surplus >= 0 and (nxt is None or surplus > best):
                nxt, best = m, surplus
        if nxt is None:
            return plans, k
        k = nxt
