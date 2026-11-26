"""迪托利希线商店表生成入口（薄封装：纯数据在 config/items_config.json，纯逻辑在 modules/items/catalog.py）。"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.items.catalog import build_catalog, export_csv  # noqa: E402


def main():
    cfg_path = os.path.join(ROOT, "config", "items_config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    cat = build_catalog(cfg, os.path.join(ROOT, cfg["weaponsTsv"]))
    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"towns": cat["towns"], "barter": cat["barter"], "materials": cat["materials"]},
            f,
            ensure_ascii=False,
        )
    export_csv(cat["csvRows"], os.path.join(HERE, "..", "shops.csv"))
    print(len(cat["towns"]), sum(len(t["items"]) for t in cat["towns"]), len(cat["barter"]))


if __name__ == "__main__":
    main()
