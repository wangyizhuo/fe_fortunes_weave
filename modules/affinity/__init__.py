"""友好度培养模块（吃饭组合与支援挖角规划）。"""
from .planner import (
    SPK,
    compute_pair_weights,
    fmt_table,
    is_perfect,
    load_people,
    plan_meals,
    sparkle,
    table_score,
)
from .service import build_affinity_data

__all__ = [
    "SPK",
    "load_people",
    "sparkle",
    "is_perfect",
    "compute_pair_weights",
    "table_score",
    "plan_meals",
    "fmt_table",
    "build_affinity_data",
]
