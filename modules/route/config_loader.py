"""路线规划 · 纯配置加载器（将配置数据 config/route_config.json 与规划逻辑彻底解耦）。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTE_CONFIG = ROOT / "config" / "route_config.json"


@dataclass(frozen=True)
class RouteConfig:
    raw: dict[str, Any]
    shot_key: str
    horizon_min_level: int
    horizon_min_steps: int
    renown: int | None
    max_exams: int
    equal_seeds: bool
    train_to_pass: bool
    magic_min_weight: int
    min_exam_gain: float
    p2_skip_below: int
    order: list[str]
    p0: set[str]
    p2: set[str]
    permit_gold: dict[str, int]
    gold_per_pt: dict[str, float]
    skip_rule: dict[str, dict[str, Any]]
    train_allowed: dict[str, bool]
    train_pts: dict[str, float]
    physical: list[str]
    mounted: list[str]
    magic: list[str]
    all_classes: list[str]
    owned: dict[str, list[str]]
    exclude: dict[str, list[str]]
    required: dict[str, list[str]]
    skip_take: dict[str, list[str]]
    prefer: dict[str, dict[str, float]]
    confident: dict[str, list[str]]
    tiebreak: dict[str, list[str]]
    exam_at_override: dict[str, dict[str, int]]
    train_case: dict[str, list[str]]
    no_skip_seeds: dict[str, set[int]]
    mount: dict[str, tuple[str, Callable[[int], int]]]
    boost: dict[str, tuple[list[int], str]]
    level_fix: dict[str, int]
    extra_after: dict[str, list[dict[str, Any]]]
    record_fix: dict[str, dict[int, dict[str, Any]]]
    replan_from_shot: set[str]
    keep_after_shot: dict[str, int]
    hidden_done: dict[str, list[str]]
    hidden_note: dict[str, str]
    skills: list[str]
    ranks: list[str]
    adv_classes: dict[str, list[str]]


def _make_mount_fn(thresholds: list[dict[str, int]]) -> Callable[[int], int]:
    ordered = sorted(thresholds, key=lambda x: -x["minLevel"])

    def fn(lv: int) -> int:
        for t in ordered:
            if lv >= t["minLevel"]:
                return t["mountLevel"]
        return ordered[-1]["mountLevel"]

    return fn


def load_route_config(path: str | Path = DEFAULT_ROUTE_CONFIG) -> RouteConfig:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    owned = {n: list(cs) for n, cs in raw["owned"].items()}
    for n in owned:
        if "平民" not in owned[n]:
            owned[n].append("平民")

    cls_cfg = raw["classes"]
    physical = list(cls_cfg["physical"]) + list(cls_cfg["mounted"])
    mounted = list(cls_cfg["mounted"])
    magic = list(cls_cfg["magic"])
    all_classes = physical + magic

    adv_classes: dict[str, list[str]] = {}
    for n, grp in cls_cfg.get("advGroup", {}).items():
        base = list(cls_cfg.get(grp, []))
        extra = list(cls_cfg.get("advExtra", {}).get(n, []))
        adv_classes[n] = base + extra

    mount = {
        n: (m["id"], _make_mount_fn(m["levelThresholds"]))
        for n, m in raw.get("mount", {}).items()
    }
    boost = {
        n: (list(v["stats"]), v["note"])
        for n, v in raw.get("boost", {}).items()
    }
    record_fix = {
        n: {int(k): v for k, v in fixes.items()}
        for n, fixes in raw.get("recordFix", {}).items()
    }
    no_skip_seeds = {
        n: set(seeds)
        for n, seeds in raw.get("noSkipSeeds", {}).items()
    }

    return RouteConfig(
        raw=raw,
        shot_key=raw["shotKey"],
        horizon_min_level=raw["horizon"]["minLevel"],
        horizon_min_steps=raw["horizon"]["minSteps"],
        renown=raw.get("renown"),
        max_exams=raw["maxExams"],
        equal_seeds=bool(raw["equalSeeds"]),
        train_to_pass=bool(raw["trainToPass"]),
        magic_min_weight=raw["magicMinWeight"],
        min_exam_gain=float(raw["minExamGain"]),
        p2_skip_below=int(raw["p2SkipBelow"]),
        order=list(raw["order"]),
        p0=set(raw["tiers"]["P0"]),
        p2=set(raw["tiers"]["P2"]),
        permit_gold=dict(raw["permitGold"]),
        gold_per_pt=dict(raw["goldPerPt"]),
        skip_rule={k: dict(v) for k, v in raw["skipRule"].items()},
        train_allowed=dict(raw["trainAllowed"]),
        train_pts=dict(raw["trainPts"]),
        physical=physical,
        mounted=mounted,
        magic=magic,
        all_classes=all_classes,
        owned=owned,
        exclude={k: list(v) for k, v in raw.get("exclude", {}).items()},
        required={k: list(v) for k, v in raw.get("required", {}).items()},
        skip_take={k: list(v) for k, v in raw.get("skipTake", {}).items()},
        prefer={k: dict(v) for k, v in raw.get("prefer", {}).items()},
        confident={k: list(v) for k, v in raw.get("confident", {}).items()},
        tiebreak={k: list(v) for k, v in raw.get("tiebreak", {}).items()},
        exam_at_override={k: dict(v) for k, v in raw.get("examAtOverride", {}).items()},
        train_case={k: list(v) for k, v in raw.get("trainCase", {}).items()},
        no_skip_seeds=no_skip_seeds,
        mount=mount,
        boost=boost,
        level_fix=dict(raw.get("levelFix", {})),
        extra_after={k: list(v) for k, v in raw.get("extraAfter", {}).items()},
        record_fix=record_fix,
        replan_from_shot=set(raw.get("replanFromShot", [])),
        keep_after_shot=dict(raw.get("keepAfterShot", {})),
        hidden_done={k: list(v) for k, v in raw.get("hiddenDone", {}).items()},
        hidden_note=dict(raw.get("hiddenNote", {})),
        skills=list(raw["skills"]),
        ranks=list(raw["ranks"]),
        adv_classes=adv_classes,
    )
