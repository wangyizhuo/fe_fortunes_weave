"""统一网站构建入口：彻底分离「数据生成」与「网页静态资源部署」。

用法：
    python3 build_site.py              # 同时生成三大模块数据 + 部署前端静态资源
    python3 build_site.py --data-only  # 只重算业务数据（out/data/*.json + out/page_data.json）
    python3 build_site.py --web-only   # 只部署前端静态网页（web/ -> out/，不跑规划算法，耗时 <0.1s）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.affinity.service import build_affinity_data  # noqa: E402
from modules.items.service import build_items_data  # noqa: E402
from modules.route.service import build_route_data  # noqa: E402

WEB_SRC = ROOT / "web"
DEFAULT_OUT = Path(os.environ.get("FE_OUT_DIR") or (ROOT / "out"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def build_data(out_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    """数据层构建：按三大功能模块独立输出 JSON 数据文件（不接触任何 HTML 模板）。"""
    t0 = time.perf_counter()
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    affinity = build_affinity_data()
    items = build_items_data()
    route = build_route_data()

    manifest = {
        "schemaVersion": 2,
        "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "modules": {
            "affinity": {
                "path": "./data/affinity.json",
                "dishes": len(affinity["dishes"]),
                "perfectDishes": sum(1 for d in affinity["dishes"] if d["perfect"]),
            },
            "items": {
                "path": "./data/items.json",
                **items["summary"],
            },
            "route": {
                "path": "./data/route.json",
                "characters": len(route["chars"]),
                "decisions": len(route["decisions"]),
            },
        },
    }

    _write_json(data_dir / "manifest.json", manifest)
    _write_json(data_dir / "affinity.json", affinity)
    _write_json(data_dir / "items.json", items)
    _write_json(data_dir / "route.json", route)

    # file:// 离线打开回退用的纯数据脚本（仍在 out/data/ 下，不注入 HTML）
    bundle_payload = {"manifest": manifest, "affinity": affinity, "items": items, "route": route}
    with open(data_dir / "bundle_data.js", "w", encoding="utf-8") as f:
        f.write("window.FE_BUNDLE_DATA = ")
        json.dump(bundle_payload, f, ensure_ascii=False)
        f.write(";\n")

    # 兼容 checks.py 的 page_data.json（保留旧字段，同时新增 items / manifest）
    compat_page_data = {
        "schemaVersion": 2,
        "manifest": manifest,
        "options": route["options"],
        "reasons": route["reasons"],
        "meals": affinity,
        "items": items,
        "chars": route["chars"],
        "stats": route["stats"],
        "skills": route["skills"],
        "decisions": route["decisions"],
        "rulesMeta": route["rulesMeta"],
    }
    _write_json(out_dir / "page_data.json", compat_page_data)

    dt = time.perf_counter() - t0
    print(
        f"[data] ok ({dt:.2f}s) -> {data_dir} | "
        f"affinity:{len(affinity['dishes'])} dishes, "
        f"items:{items['summary']['townCount']} towns/{items['summary']['barterCount']} barter/{items['summary']['materialCount']} materials, "
        f"route:{len(route['chars'])} chars"
    )
    return bundle_payload


def build_web(out_dir: Path = DEFAULT_OUT) -> list[str]:
    """前端层构建：将纯静态前端 web/ 部署到 out/，完全不依赖业务数据与规划算法。"""
    t0 = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    for rel in ("index.html", "styles.css"):
        src = WEB_SRC / rel
        dst = out_dir / rel
        shutil.copy2(src, dst)
        copied.append(rel)

    # 同时保留 growth-route.html 别名，兼容原有链接与 check_layout.js
    shutil.copy2(WEB_SRC / "index.html", out_dir / "growth-route.html")
    copied.append("growth-route.html")

    js_src = WEB_SRC / "js"
    js_dst = out_dir / "js"
    if js_dst.exists():
        shutil.rmtree(js_dst)
    shutil.copytree(js_src, js_dst)
    for p in js_dst.rglob("*.js"):
        copied.append(str(p.relative_to(out_dir)))

    dt = time.perf_counter() - t0
    print(f"[web]  ok ({dt:.2f}s) -> {out_dir} ({len(copied)} static files)")
    return copied


def main() -> None:
    ap = argparse.ArgumentParser(description="构建万紫千红模块化网站（数据与网页生成逻辑分离）")
    ap.add_argument("--data-only", action="store_true", help="只重新生成 out/data/*.json 与 page_data.json")
    ap.add_argument("--web-only", action="store_true", help="只部署前端静态文件 web/ -> out/")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出目录（默认 out/）")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if args.data_only and args.web_only:
        ap.error("--data-only 和 --web-only 不能同时使用")

    if not args.web_only:
        build_data(out_dir)
    if not args.data_only:
        build_web(out_dir)


if __name__ == "__main__":
    main()
