"""
反推成长种子：把 0 ~ 2^31-1 的种子全部试一遍，留下能把「连续几次观星记录」全部算对的种子。

做法（numpy 向量化，一次处理 1600 多万个种子）：
  1. 只算「第一轮判定」。真种子要么第一轮就和记录一致，
     要么第一轮涨得不够保底（之后会重抽/补点），两种都先留下。
  2. 留下的种子前进一步，用下一条记录再筛。几步之后只剩极少数。
  3. 剩下的用 fe_growth.level_up() 完整核对每一条记录（含重抽和保底）。

tolerance > 0 时，允许最多这么多个「单项」对不上（用来容忍记录笔误，
或某一项成长率数据有误）。此时第 1 步的粗筛会放宽，速度会慢一些。
"""

from __future__ import annotations

import numpy as np

from fe_growth import INTERNAL_ORDER, MASK31, level_up, next_seed

U32 = np.uint32


def _spread(prev, i):
    return (U32(0x6C078965) * (prev ^ (prev >> U32(30))) + U32(i)).astype(U32)


class _VecRng:
    """Xorshift128 的 numpy 版，同时跑很多个种子。"""

    def __init__(self, seeds):
        self.x = _spread(seeds, 0)
        self.y = _spread(self.x, 1)
        self.z = _spread(self.y, 2)
        self.w = _spread(self.z, 3)

    def next(self):
        t = self.x ^ (self.x << U32(11))
        r = t ^ (t >> U32(8)) ^ self.w ^ (self.w >> U32(19))
        self.x, self.y, self.z, self.w = self.y, self.z, self.w, r
        return r


def _vec_next_seed(seeds):
    return _VecRng(seeds).next() & U32(MASK31)


def _first_round_ok(seeds, growths, observed, min_stats, tolerance):
    """第一轮判定是否可能和记录一致（返回布尔数组）。"""
    g = [max(0, growths[i]) for i in INTERNAL_ORDER]
    obs = [observed[i] > 0 for i in INTERNAL_ORDER]
    rng = _VecRng(seeds)
    mismatches = np.zeros(seeds.shape, dtype=np.int32)
    grown = np.zeros(seeds.shape, dtype=np.int32)
    for k in range(9):
        if g[k] < 1:
            continue
        sure, rem = divmod(g[k], 100)
        if rem > 0:
            hit = (rng.next() & U32(MASK31)) % U32(1_000_000) < U32(rem * 10_000)
        else:
            hit = np.zeros(seeds.shape, dtype=bool)
        up = hit | (sure > 0)
        grown += up
        mismatches += up != obs[k]
    needs_reroll = grown < max(min(min_stats, sum(1 for x in g if x >= 1)), 1)
    return (mismatches <= tolerance) | needs_reroll


def solve(records, min_stats=2, tolerance=0, prefilter_steps=4,
          batch_bits=24, progress=True):
    """
    records: [(growths, gains_or_None), ...] 连续的种子步（每次升级或考试各一步）。
             gains 为 9 项加点（显示顺序），None 表示这一步没记录。
    返回 [(seed, 对不上的项数), ...]
    """
    usable = [i for i, (_, gains) in enumerate(records) if gains is not None]
    filter_idx = usable[:prefilter_steps]
    found = []
    total = 1 << 31
    batch = 1 << batch_bits
    for start in range(0, total, batch):
        seeds0 = np.arange(start, start + batch, dtype=np.uint64).astype(U32)
        cur, keep = seeds0, seeds0
        for i in range(filter_idx[-1] + 1):
            growths, gains = records[i]
            if i in filter_idx:
                ok = _first_round_ok(cur, growths, gains, min_stats, tolerance)
                cur, keep = cur[ok], keep[ok]
            cur = _vec_next_seed(cur)
        for s0 in keep.tolist():
            miss = _count_mismatches(s0, records, min_stats, tolerance)
            if miss is not None:
                found.append((s0, miss))
        if progress:
            print(f"\r  搜索 {100 * (start + batch) / total:5.1f}%  已找到 {len(found)}", end="", flush=True)
    if progress:
        print()
    return found


def _count_mismatches(seed, records, min_stats, tolerance):
    miss = 0
    for growths, gains in records:
        if gains is not None:
            pred = level_up(seed, growths, min_stats).gains
            miss += sum((p > 0) != (o > 0) for p, o in zip(pred, gains))
            if miss > tolerance:
                return None
        seed = next_seed(seed)
    return miss
