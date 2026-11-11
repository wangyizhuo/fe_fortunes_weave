"""
火焰纹章 万紫千红 · 升级加点（随机成长模式）的 Python 实现

算法来源：fireemblem.top/growth-seed 页面的 JS（作者 Pser_hanser，
自称由游戏程序静态解析 + 70 组指令回放核对）。这里逐行改写成可读的 Python，
并用 Yizhuo 的观星记录做了回测（见 demo.py）。

核心概念
--------
* 每个角色存一个 31 位「成长种子」。
* 每升 1 级、或每参加 1 次转职考试（过没过都算），种子前进一步：
      新种子 = next_seed(旧种子)
* 观星看到的，就是用「当前种子」算出来的这一级加点。
* 换职业只改变成长率，不改变种子。

属性顺序
--------
游戏内部判定顺序是 HP 力 魔 技 速 幸 防 魔防 魅（技在速前面、幸在防前面）。
对外（输入/输出）一律用游戏界面的显示顺序 HP 力 魔 速 技 防 魔防 幸 魅，
转换只在 level_up() 里做一次。
"""

from __future__ import annotations

from dataclasses import dataclass, field

MASK32 = 0xFFFFFFFF
MASK31 = 0x7FFFFFFF

# 显示顺序（游戏界面、观星、本文件的所有输入输出）
STATS = ["HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅"]
# 内部判定顺序，用显示顺序的下标表示：HP 力 魔 技 速 幸 防 魔防 魅
INTERNAL_ORDER = [0, 1, 2, 4, 3, 7, 5, 6, 8]


# ----------------------------------------------------------------------
# 1. 乱数发生器：xorshift128，用类似梅森旋转的方式从 32 位种子展开 4 个状态字
# ----------------------------------------------------------------------
class Xorshift128:
    def __init__(self, seed: int):
        def spread(prev: int, i: int) -> int:
            return (0x6C078965 * (prev ^ (prev >> 30)) + i) & MASK32

        seed &= MASK32
        self.x = spread(seed, 0)
        self.y = spread(self.x, 1)
        self.z = spread(self.y, 2)
        self.w = spread(self.z, 3)

    def next(self) -> int:
        """返回下一个 32 位乱数。"""
        t = (self.x ^ (self.x << 11)) & MASK32
        result = (t ^ (t >> 8) ^ self.w ^ (self.w >> 19)) & MASK32
        self.x, self.y, self.z, self.w = self.y, self.z, self.w, result
        return result


def next_seed(seed: int) -> int:
    """种子前进一步：用当前种子展开乱数，取第一个数的低 31 位。"""
    return Xorshift128(seed).next() & MASK31


def exam_roll(seed: int) -> int:
    """转职考试判定值（0～999999）：同一种子展开后的第 2 个乱数。判定值 < 成功率×10000 则考试成功。
    考试无论成败，种子都前进一步（next_seed）。出处：fireemblem.top 成长种子模拟器 Ver1.1。"""
    r = Xorshift128(seed)
    r.next()
    return (r.next() & MASK31) % 1_000_000


def exam_passes(seed: int, chance_pct: float) -> bool:
    return exam_roll(seed) < chance_pct * 10_000


# ----------------------------------------------------------------------
# 2. 一次升级
# ----------------------------------------------------------------------
@dataclass
class LevelUpResult:
    gains: list[int]                      # 显示顺序，每项加几点
    rounds: int = 1                       # 一共判定了几轮（1 = 没有重抽）
    filled_by_floor: list[int] = field(default_factory=list)  # 被保底补上的属性（显示顺序下标）

    def names(self) -> str:
        parts = [STATS[i] + ("" if g == 1 else f"+{g}") for i, g in enumerate(self.gains) if g]
        return " ".join(parts) or "—"


def level_up(seed: int, growths: list[int], min_stats: int = 2,
             capped: list[bool] | None = None) -> LevelUpResult:
    """
    用当前种子算出这一级的加点。

    growths   : 9 项有效成长率（%），显示顺序。已含职业、坐骑、技能等加成。
    min_stats : 保底项数。第一、二部 = 2，第三部起 = 0。
    capped    : 9 项是否已到上限（到上限的项不参与）。
    """
    capped = capped or [False] * 9
    g = [max(0, growths[i]) for i in INTERNAL_ORDER]
    dead = [capped[i] for i in INTERNAL_ORDER]

    # 只有成长率 ≥ 1 且未封顶的属性参加判定
    candidates = [k for k in range(9) if g[k] >= 1 and not dead[k]]
    gains = [0] * 9
    if not candidates:
        return LevelUpResult(_to_display(gains), 0)

    rng = Xorshift128(seed)
    floor = min(min_stats, len(candidates))   # 实际保底项数
    target = max(floor, 1)                    # 重抽的目标：至少这么多项上涨

    # --- 第一轮判定 + 最多 3 次整轮重抽 ---
    rounds = 0
    for attempt in range(4):
        rounds += 1
        gains = [0] * 9
        for k in candidates:
            sure, remainder = divmod(g[k], 100)   # 整数部分必涨，余数部分判定
            gains[k] = sure
            if remainder > 0:                      # 余数为 0 时不消耗乱数
                roll = (rng.next() & MASK31) % 1_000_000
                if roll < remainder * 10_000:
                    gains[k] += 1
        grown = sum(1 for k in candidates if gains[k])
        if grown >= target or attempt == 3:
            break

    # --- 仍不够保底：从没涨的属性里按成长率加权补 +1 ---
    filled = []
    missing = floor - sum(1 for k in candidates if gains[k])
    while missing > 0:
        pool = [k for k in candidates if gains[k] == 0]
        total_weight = sum(100 * g[k] for k in pool)
        if total_weight <= 0:
            break
        pick = (rng.next() & MASK31) % total_weight
        for k in pool:
            pick -= 100 * g[k]
            if pick < 0:
                gains[k] = 1
                filled.append(INTERNAL_ORDER[k])
                break
        missing -= 1

    return LevelUpResult(_to_display(gains), rounds, filled)


def _to_display(internal_gains: list[int]) -> list[int]:
    out = [0] * 9
    for k, stat in enumerate(INTERNAL_ORDER):
        out[stat] = internal_gains[k]
    return out


# ----------------------------------------------------------------------
# 3. 成长率：个人 + 职业 + 坐骑 × 倍率 + 之道（战车兵/战象兵）
# ----------------------------------------------------------------------
class GrowthData:
    def __init__(self, path: str):
        import json
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        self.characters = d["characters"]
        self.classes = d["classes"]
        self.class_ids = d["class_ids"]
        self.mounts = d["mounts"]

    def growth(self, character: str, cls: str, level: int = 1,
               mount_id: str | None = None, mount_level: int = 0,
               extra: list[int] | None = None) -> list[int]:
        """有效成长率（显示顺序）。level 是升级前的等级，只影响之道加成。"""
        personal = self.characters[character]
        c = self.classes[cls]
        rate = [personal[i] + c["mod"][i] for i in range(9)]
        if mount_id and c["mount"] and mount_level:
            stage = self.mounts[mount_id]["growthStages"][mount_level - 1]
            rate = [rate[i] + stage[i] * c["mountX"] for i in range(9)]
        for min_level, bonus in c["pathGrowth"]:      # 高等级的条目在前
            if level >= min_level:
                rate = [rate[i] + bonus[i] for i in range(9)]
                break
        if extra:
            rate = [rate[i] + extra[i] for i in range(9)]
        return [max(0, r) for r in rate]


# ----------------------------------------------------------------------
# 4. 往后推演
# ----------------------------------------------------------------------
@dataclass
class Step:
    growths: list[int]
    exams_before: int = 0      # 这一级之前考了几次试（每次推进一步种子）


def forecast(seed: int, steps: list[Step], min_stats: int = 2):
    """按计划逐级推演，返回 [(这一级用的种子, LevelUpResult), ...]。"""
    out = []
    for step in steps:
        for _ in range(step.exams_before):
            seed = next_seed(seed)
        out.append((seed, level_up(seed, step.growths, min_stats)))
        seed = next_seed(seed)
    return out
