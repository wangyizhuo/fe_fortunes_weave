"""路线规划 · 数据服务层（纯数据生成，彻底与 HTML 模板解耦）。

负责将规划器结果与辅助 JSON（detail / summary / choices / plan45 / longview / options / reasons / decisions）
组装为干净、结构化的 route.json，供独立前端动态加载，不接触任何 HTML 字符串或 DOM。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RNG_DIR = ROOT / "levelup" / "rng"
if str(RNG_DIR) not in sys.path:
    sys.path.insert(0, str(RNG_DIR))

from fe_growth import STATS, exam_roll, level_up  # noqa: E402
from planner import _TIER, _TIER_RANK, plan_all, score  # noqa: E402
import run_plans as R  # noqa: E402
from .config_loader import load_route_config  # noqa: E402


def gain_names(g: list[int] | tuple[int, ...]) -> list[str]:
    return [STATS[i] + ("" if v == 1 else f"+{v}") for i, v in enumerate(g) if v]


def step_routes(name: str, p: Any, step: int, lv: int, have: list[str]) -> dict[str, Any]:
    """每一级的四种走法（正常/转职/考试/跳过），使用精确 exam_ok 避免浮点舍入偏差。"""
    roll = round(p.exam_value(step), 2)
    exams = []
    for cls in R.EXAM_OPTIONS[name]:
        if cls in have:
            continue
        pct = p.exam_pct(cls, lv)
        sc = p.result(step, lv, cls)[0]
        exams.append({
            "cls": cls,
            "tier": _TIER.get(cls, "中级"),
            "pct": pct,
            "pass": None if pct is None else p.exam_ok(step, cls, lv),
            "s": sc,
        })
    exams.sort(key=lambda e: (e["pass"] is not True, -(e["pct"] or 0)))
    fut = [max(p.result(j, lv, c)[0] for c in have) for j in range(step + 1, step + 16)]
    return {
        "roll": roll,
        "exams": exams,
        "avg10": round(sum(fut[:10]) / 10, 1),
        "avg15": round(sum(fut) / 15, 1),
        "thr": round(p.skip_threshold, 1),
    }


def grouped_options(
    name: str,
    seed: int,
    level: int,
    classes: list[str],
    have: list[str],
    w: list[int],
) -> list[dict[str, Any]]:
    """这一步种子下每个职业的加点，加点完全相同的并成一组。"""
    groups: dict[tuple[int, ...], list[str]] = {}
    for cls in classes:
        try:
            g = tuple(level_up(seed, R.data.growth(name, cls, level), 2).gains)
        except Exception:
            continue
        groups.setdefault(g, []).append(cls)
    out = [
        {
            "classes": cs,
            "owned": [c in have for c in cs],
            "gains": gain_names(g),
            "cnt": sum(g),
            "score": score(g, w),
        }
        for g, cs in groups.items()
    ]
    out.sort(key=lambda o: (-o["score"], -o["cnt"]))
    return out


def _load_json(name: str, default: Any = None) -> Any:
    path = RNG_DIR / name
    if not path.exists():
        return {} if default is None else default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_rules_meta(cfg: Any) -> dict[str, Any]:
    """把当前生效的规则元数据导出给前端说明区，避免 HTML 模板硬编码过时规则。"""
    p0_list = [n for n in cfg.order if n in cfg.p0]
    p2_list = [n for n in cfg.order if n in cfg.p2]
    p1_list = [n for n in cfg.order if n not in cfg.p0 and n not in cfg.p2]
    return {
        "shotKey": cfg.shot_key,
        "renown": cfg.renown,
        "tiers": {"P0": p0_list, "P1": p1_list, "P2": p2_list},
        "skipRule": cfg.skip_rule,
        "permitGold": cfg.permit_gold,
        "trainAllowed": cfg.train_allowed,
        "trainCase": cfg.train_case,
        "requireMidRule": True,
        "balanceMinWeight": 4,
    }


def build_route_data() -> dict[str, Any]:
    """构建路线规划模块的完整纯数据结构（route.json）。"""
    cfg = load_route_config()
    detail_map = _load_json("detail.json", {})
    summary_map = _load_json("summary.json", {})
    text_map = _load_json("summary_text.json", {"chars": {}})
    choices_map = _load_json("choices.json", {})
    plan45_map = _load_json("plan45.json", {})
    guide_map = _load_json("guide_hanse.json", {})
    long_map = _load_json("longview.json", {})
    options_map = _load_json("options.json", {})
    reasons_map = _load_json("reasons.json", {})
    decisions = _load_json("decisions.json", [])

    chars: list[dict[str, Any]] = []
    for name in R.ORDER:
        shot = R.shot(name)
        w = R.W[name]
        # 严格以 R.OWNED 为单一数据源（移除已过时的 CUR_CLASS_EXTRA 脏补丁）
        owned = list(dict.fromkeys(R.OWNED.get(name, [])))
        opts_pool = list(dict.fromkeys(owned + R.EXAM_OPTIONS.get(name, [])))
        c: dict[str, Any] = {
            "name": name,
            "level": shot.get("level"),
            "curClass": shot.get("class"),
            "stats": shot.get("stats"),
            "boosted": shot.get("boosted", []),
            "skills": shot.get("skills", {}),
            "owned": owned,
            "classChoices": opts_pool,
            "weights": w,
            "required": R.REQUIRED.get(name, []),
            "steps": [],
        }

        # 1) 观星历史记录
        if name in R.units:
            recs = R.records(name)
            for r in recs:
                exam = r["ok"] is not True
                cls = r["cls"]
                pool = list(dict.fromkeys(opts_pool + ([cls] if cls else [])))
                c["steps"].append({
                    "key": f"h{r['idx']}",
                    "src": "record",
                    "exam": exam,
                    "cls": cls if not exam else "",
                    "seenCls": cls,
                    "frm": r["frm"],
                    "gains": gain_names(r["gains"]),
                    "cnt": sum(r["gains"]),
                    "score": score(r["gains"], w),
                    "hidden": r["ok"] is None,
                    "inferred": bool(r.get("inferred")),
                    "note": r.get("note", ""),
                    "opts": grouped_options(name, r["seed"], r["frm"], pool, owned, w) if r["seed"] is not None else [],
                    "roll": round(exam_roll(r["seed"]) / 1e4, 2) if r["seed"] is not None else None,
                })
            for i, r in enumerate(recs):
                if r["ok"] is None and i + 1 < len(recs) and recs[i + 1]["cls"] == shot.get("class") and recs[i + 1]["cls"] != r["cls"]:
                    for st in c["steps"]:
                        if st["key"] == f"h{r['idx']}":
                            st["autoDone"] = True
            lv_shot = shot.get("level")
            if lv_shot is not None and R._cut(name) is not None:
                for st in c["steps"]:
                    if st["src"] == "record" and not st["exam"] and st["frm"] is not None and st["frm"] >= lv_shot:
                        st.update(
                            exam=True,
                            cls="",
                            hidden=True,
                            autoDone=True,
                            note="按截图为准：这个乱数在截图前已经用掉，但等级没涨（当时是考试或跳过），算已完成",
                        )
            for st in c["steps"]:
                if st["key"] in cfg.hidden_done.get(name, []):
                    st["autoDone"] = True
                    if name == "乌尔坦德" and st["key"] in cfg.hidden_note:
                        st["note"] = cfg.hidden_note[st["key"]]

        # 2) 未来规划路线
        if name in R.OWNED:
            p = R.make_planner(name, R.TARGET[name])
            plans, k = plan_all(p, R.MAX_EXAMS)
            plan = plans[k]
            c.update({
                "planFrom": p.level,
                "planTo": p.level + sum(r.action == "升级" for r in plan.rows),
                "seeds": p.n_seeds,
                "planTotal": plan.total,
                "exams": plan.exams,
                "thr": list(p.thresholds),
            })

            # 多转一个中级对比（统一使用 p.plan_net 口径）
            gpp = p.gold_per_pt
            tg = list(getattr(plan, "targets", []))
            base_net = p.plan_net(plan.raw_actions, plan.total, plan.gold)
            mg = []
            for cls in [x for x in p.exam_options if _TIER_RANK.get(_TIER.get(x, ""), 0) == 2 and x not in tg]:
                r = p.rule_run(tg + [cls], (cls,))
                if r is None or not any(a == "升级" and x == cls for a, x in r[0]):
                    continue
                used = sum(1 for a, x in r[0] if a == "升级" and x == cls)
                g_new, lv_ = [0] * 9, p.level
                for i_, (a_, x_) in enumerate(r[0]):
                    if a_ == "升级":
                        g_new = [u + v for u, v in zip(g_new, p.result(i_, lv_, x_)[1])]
                        lv_ += 1
                g_old = [0] * 9
                for rr in plan.rows:
                    if rr.action == "升级":
                        g_old = [u + v for u, v in zip(g_old, rr.gains)]
                dg = [u - v for u, v in zip(g_new, g_old)]
                pts_r = "、".join(f"{STATS[i_]}{dg[i_]:+d}" for i_ in range(9) if dg[i_]) or "能力一样"
                net_new = p.plan_net(r[0], r[2], r[3])
                mg.append({
                    "cls": cls,
                    "total": r[2],
                    "gold": r[3],
                    "net": round(net_new, 1),
                    "dsc": r[2] - plan.total,
                    "dnet": round(net_new - base_net, 1),
                    "used": used,
                    "diff": pts_r,
                    "dpts": sum(dg),
                })
            mg.sort(key=lambda x: -x["dnet"])
            c["midGain"] = mg[:5]
            c["planGold"], c["planNet"], c["targets"], c["gpp"] = plan.gold, round(base_net, 1), tg, round(gpp, 1)
            c["examWarn"] = plan.exams > 4
            c["p0"] = name in R.P0

            bal = []
            for r in plan.rows:
                note = getattr(r, "balance_note", "")
                if not note:
                    continue
                m = re.search(r"均衡：(.*)，所以用(\S+?)换(\S+?)（多 (.*?)、少 (.*?)）", note)
                if m:
                    why, pick, orig, more, less = m.groups()
                    s1, s0 = p.result(r.step, r.level_from, pick)[0], p.result(r.step, r.level_from, orig)[0]
                    bal.append({
                        "lv": f"Lv{r.level_from}→{r.level_from + 1}",
                        "pick": pick,
                        "orig": orig,
                        "more": more,
                        "less": less,
                        "why": why,
                        "dsc": s1 - s0,
                    })
            c["balance"] = bal

            cur_cls = next(
                (st["cls"] for st in reversed(c["steps"]) if st["src"] == "record" and not st["exam"] and st["cls"]),
                shot.get("class"),
            )
            stay = [0] * 9
            for i in range(p.n_seeds):
                _, g = p.result(i, p.level + i, cur_cls)
                stay = [a + b for a, b in zip(stay, g)]
            p0 = plans[0] if plans[0] is not None and plans[0].total > 0 else None
            best0 = None
            if p0:
                best0 = [0] * 9
                for r in p0.rows:
                    if r.action == "升级":
                        best0 = [a + b for a, b in zip(best0, r.gains)]

            seg: list[list[Any]] = []
            lv2 = p.level
            for r in plan.rows:
                if r.action == "升级":
                    if seg and seg[-1][0] == "up" and seg[-1][1] == r.cls:
                        seg[-1][3] = lv2 + 1
                    else:
                        seg.append(["up", r.cls, lv2, lv2 + 1])
                    lv2 += 1
                else:
                    real = r.cls in R.EXAM_OPTIONS[name]
                    pc = p.exam_pct(r.cls, lv2) if real else None
                    seg.append(["exam", r.cls if real else "", round(p.exam_value(r.step), 2), pc])

            have_, lv_, rows_ = list(R.OWNED[name]), p.level, []
            for r in plan.rows:
                rows_.append((r, lv_, list(have_)))
                if r.action == "升级":
                    lv_ += 1
                elif r.cls in R.EXAM_OPTIONS[name] and r.cls not in have_:
                    have_.append(r.cls)
            for x in seg:
                if x[0] != "exam" or not x[1]:
                    continue
                cls_ = x[1]
                n_use, dg, dsc = 0, [0] * 9, 0
                for r, lvr, hv in rows_:
                    if r.action == "升级" and r.cls == cls_:
                        alts = [k_ for k_ in hv if k_ != cls_]
                        if not alts:
                            continue
                        alt = max(alts, key=lambda k_: p.result(r.step, lvr, k_)[0])
                        ga = p.result(r.step, lvr, alt)[1]
                        n_use += 1
                        dg = [u + v - w_ for u, v, w_ in zip(dg, r.gains, ga)]
                        dsc += r.score - p.result(r.step, lvr, alt)[0]
                txt = "、".join(f"{STATS[i]}{dg[i]:+d}" for i in range(9) if dg[i]) or "能力一样"
                x.extend([n_use, txt, dsc])
            use_info = {x[1]: x[4:7] for x in seg if x[0] == "exam" and x[1] and len(x) > 4}

            c["route"] = seg
            c["trend"] = {"cur": cur_cls, "n": p.n_seeds, "stay": stay, "best0": best0}
            c["planTotal"] = plan.total
            c["tier"] = R.tier_of(name)
            c["str0"] = p.str_start

            have = list(R.OWNED[name])
            lv = p.level
            for r in plan.rows:
                exam = r.action != "升级"
                pool = list(dict.fromkeys(have + list(R.EXAM_OPTIONS[name])))
                opts = grouped_options(name, p.seed_at(r.step), lv, pool, have, w)
                have_before = list(have)
                if exam and r.cls in R.EXAM_OPTIONS[name] and r.cls not in have:
                    have.append(r.cls)
                pct = p.exam_pct(r.cls, lv) if exam and r.cls in R.EXAM_OPTIONS[name] else None
                routes = step_routes(name, p, r.step, lv, have_before)
                c["steps"].append({
                    "routes": routes,
                    "key": str(r.step + 1),
                    "src": "plan",
                    "exam": exam,
                    "pct": pct,
                    "cls": r.cls if (not exam or r.cls in R.EXAM_OPTIONS[name]) else "",
                    "frm": lv if not exam else None,
                    "gains": gain_names(r.gains) if not exam else [],
                    "cnt": sum(r.gains) if not exam else 0,
                    "score": r.score if not exam else 0,
                    "note": "；".join(x for x in (r.balance_note, r.str_note) if x),
                    "opts": opts,
                    "ownedAfter": list(have),
                    "roll": round(p.exam_value(r.step), 2),
                    "use": use_info.get(r.cls) if exam else None,
                    "train": (getattr(p, "exam_train", {}) or {}).get(r.cls) if exam else None,
                    "trainOk": bool(
                        R.TRAIN_ALLOWED[R.tier_of(name)]
                        or r.cls == getattr(p, "mid_trained", None)
                        or (getattr(p, "exam_train_ranks", {}) or {}).get(r.cls)
                    ),
                    "trainLv": lv if exam else None,
                    "floor": [f"{a} {x}→{v}" for a, x, v in (r.floor or [])] if exam else None,
                    "skipCls": r.skip_class if exam else None,
                    "skipFail": r.skip_fail if exam else None,
                    "skipLeft": r.skip_left if exam else None,
                    "skipNone": bool(r.skip_none) if exam else False,
                    "renown": (getattr(p, "renown_req", {}) or {}).get(r.cls) if exam else None,
                    "eq": (
                        [
                            k_
                            for k_ in have_before
                            if _TIER.get(k_) == _TIER.get(r.cls)
                            and list(level_up(p.seed_at(r.step), R.data.growth(name, k_, lv), 2).gains) == list(r.gains)
                        ]
                        if not exam
                        else None
                    ),
                })
                if not exam:
                    lv += 1

            used = {r.cls for r in plan.rows if r.action == "升级"}
            c["trainPlan"] = [
                {
                    "key": s_["key"],
                    "lv": s_["trainLv"],
                    "cls": s_["cls"],
                    "train": s_["train"],
                    "ranks": (getattr(p, "exam_train_ranks", {}) or {}).get(s_["cls"], 0),
                }
                for s_ in c["steps"]
                if s_.get("src") == "plan" and s_["exam"] and s_.get("train") and s_["trainOk"] and s_["cls"] in used
            ]

        # 3) 合并档案、期望、长线、Lv45、攻略与长期选择
        if name in plan45_map:
            c["l45"] = plan45_map[name]
        if name in guide_map:
            c["guide"] = guide_map[name]
        d = detail_map.get(name)
        sm = summary_map.get(name)
        tx = (text_map.get("chars") or {}).get(name)
        if d:
            ps = [s for s in c["steps"] if s["src"] == "plan"]
            assert len(ps) == len(d["future"])
            avg = {(r["lv"], r["cls"]): r for r in (sm or {}).get("rows", [])}
            for s, f in zip(ps, d["future"]):
                assert s["exam"] == (f["kind"] == "考试")
                if f.get("why"):
                    s["why"] = f["why"]
                if f.get("pred"):
                    s["pred"] = f["pred"]
                a = avg.get((f.get("lv"), f.get("cls")))
                if a:
                    s["es"] = a["es"]
            c["hist"] = {
                k: d[k]
                for k in ("join", "gap", "past", "now", "exam_benefit", "plan_scores", "total", "end", "wtotal", "options")
            }
        if sm:
            c["avg"] = {k: sm[k] for k in ("exp", "act", "ws", "wexp")}
            if c.get("planTotal") is not None:
                c["avg"]["ws"] = c["planTotal"]
        if tx:
            c["text"] = tx
        if d and sm and "trend" in c:
            exp, act, flags = sm["exp"], d["total"], []
            to_lv = c.get("planTo", 35)
            for i, k_stat in enumerate(STATS):
                e, a, st0 = exp[i], act[i], c["trend"]["stay"][i]
                wt = c["weights"][i]
                tag = f"（权重 {wt}）" if wt <= 2 else ""
                if a - e <= -2 and a <= 0.65 * e:
                    flags.append({
                        "lv": "bad",
                        "t": f"{k_stat}到 Lv{to_lv} 只涨 {a}，平均 {e}{tag}，明显偏低"
                        + (f"；一直用现在的职业也只涨 {st0}" if st0 <= a else f"；一直用现在的职业反而能涨 {st0}"),
                    })
                elif a - e >= 3 and a >= 1.5 * e:
                    flags.append({"lv": "good", "t": f"{k_stat}到 Lv{to_lv} 涨 {a}，平均 {e}{tag}，明显偏高"})
                if st0 - e <= -2.5 and st0 <= 0.5 * e and not (a - e <= -2 and a <= 0.65 * e):
                    flags.append({
                        "lv": "warn",
                        "t": f"一直用现在的职业的话{k_stat}只涨 {st0}（平均 {e}）{tag}，推荐路线补到 {a}",
                    })
            c["trend"]["flags"] = flags
        if name in choices_map:
            c["choices"] = choices_map[name]["opts"]
        if name in long_map:
            c["long"] = long_map[name]

        chars.append(c)

    return {
        "module": "route",
        "schemaVersion": 1,
        "stats": list(STATS),
        "skills": list(cfg.skills),
        "rulesMeta": build_rules_meta(cfg),
        "chars": chars,
        "options": options_map,
        "reasons": reasons_map,
        "decisions": decisions,
    }
