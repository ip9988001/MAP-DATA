#!/usr/bin/env python3
"""TASK-004 · 特拉华全州三县（Kent / New Castle / Sussex）四源 ETL → 24 字段黄金地址库
================================================================================
本脚本是 `dover_golden_coalesce.py` 引擎的**全州驱动**：引擎只认 scope，本文件负责
把 scope 从「多佛单城」换成「全州三县」，其余判据（方案一铁律）完全一致：

  1. 独立源计票：有效独立源 = USDOT NAD / Census TIGER-Line / OpenAddresses；
     Overture 上游 100% 溯源 NAD，**不计独立票**（仅保留溯源列）。
  2. TIGER 校验必须叠加空间约束：号段区间命中 AND 点线距离 ≤ 60m AND 奇偶匹配。
  3. 漏斗四栏分开：范围外剔除 / 脏数据剔除 / 无官方背书孤儿淘汰 / 同址去重。
  4. 同址合并：同「门牌+街名+unit」只保留最佳代表行。

用法（在仓库根目录执行）：
    python scripts/delaware_statewide_coalesce.py \
        --input-dir data/delaware/task004/raw \
        --out-dir   data/delaware/task004 \
        --docs-dir  docs

输入（Release 资产，全部由 runner 侧下载，本脚本自身不联网）：
    nad_de_full.ndjson                    NAD 全州（三县）
    overture_de_addresses.geojson         Overture 全州
    openaddresses_us_de_{kent,new_castle,sussex}.zip + city_of_dover.zip
    tl_2024_{10001,10003,10005}_addrfeat.zip         三县 TIGER 号段
    tiger_county_{kent,new_castle,sussex}.geojson   三县行政边界
    tiger_state_de.geojson / tiger_zcta_de.geojson  州界 / ZCTA（可选）

缺任一必需文件时**不猜、不降级**：直接列出缺失清单并以退出码 2 结束，
由流水线上游补齐后重跑。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dover_golden_coalesce import run  # noqa: E402  （同目录引擎，判据唯一来源）

# ------------------------------------------------------------------ 全州三县 scope
SCOPE_DELAWARE = {
    "name": "delaware",
    "out_prefix": "delaware",
    "place_label": "State of Delaware（Kent / New Castle / Sussex 三县全境）",
    "doc_title": "TASK-004 · Delaware 全州三县黄金地址库",
    # 全州 bbox（含三县外接矩形；真正的范围裁剪由县边界多边形完成）
    "bbox": (-75.80, 38.44, -75.04, 39.85),
    "state_abbr": "DE", "state_name": "Delaware", "state_fips": "10",
    "nad": "nad_de_full.ndjson",
    "overture": "overture_de_addresses.geojson",
    "oa": [("kent", "openaddresses_us_de_kent.zip"),
           ("city_of_dover", "openaddresses_us_de_city_of_dover.zip"),
           ("new_castle", "openaddresses_us_de_new_castle.zip"),
           ("sussex", "openaddresses_us_de_sussex.zip")],
    "counties": [
        {"name": "Kent County", "fips": "10001",
         "addrfeat": "tl_2024_10001_addrfeat.zip", "boundary_key": "county_kent"},
        {"name": "New Castle County", "fips": "10003",
         "addrfeat": "tl_2024_10003_addrfeat.zip", "boundary_key": "county_new_castle"},
        {"name": "Sussex County", "fips": "10005",
         "addrfeat": "tl_2024_10005_addrfeat.zip", "boundary_key": "county_sussex"},
    ],
    "boundaries": {
        "county_kent": "tiger_county_kent.geojson",
        "county_new_castle": "tiger_county_new_castle.geojson",
        "county_sussex": "tiger_county_sussex.geojson",
        "state_de": "tiger_state_de.geojson",
        "zcta_de": "tiger_zcta_de.geojson",
    },
    "place_keys": [],            # 全州不做 place 内判定（县界即范围）
    "sample_zips": (),           # 全州样本不按邮编收窄
}

# 必需输入（缺任何一个就停，避免产出半成品）
REQUIRED = [SCOPE_DELAWARE["nad"], SCOPE_DELAWARE["overture"]] + \
           [f for _k, f in SCOPE_DELAWARE["oa"]] + \
           [c["addrfeat"] for c in SCOPE_DELAWARE["counties"]] + \
           [SCOPE_DELAWARE["boundaries"][c["boundary_key"]] for c in SCOPE_DELAWARE["counties"]]


def preflight(data: Path) -> list[str]:
    missing = [f for f in REQUIRED if not (data / f).exists()]
    present = [f for f in REQUIRED if (data / f).exists()]
    print(f"[preflight] 必需 {len(REQUIRED)} 项，已就位 {len(present)} 项，缺失 {len(missing)} 项")
    for f in missing:
        print(f"  ✗ 缺失 {f}")
    return missing


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", "--input-dir", dest="data", default="data/delaware/task004/raw")
    ap.add_argument("--out", "--out-dir", dest="out", default="data/delaware/task004")
    ap.add_argument("--docs-dir", dest="docs", default="docs")
    a = ap.parse_args(argv)

    data, out = Path(a.data), Path(a.out)
    missing = preflight(data)
    if missing:
        print("\n[stop] 原始资产不齐，拒绝产出半成品。请先跑 TASK-004 抓取流水线补齐后重跑。")
        return 2

    run(data, out, None, Path(a.docs) if a.docs else None, SCOPE_DELAWARE)
    summary = json.loads((out / "delaware_task_summary.json").read_text(encoding="utf-8"))
    print("\n== 全州结果 ==")
    print(json.dumps({"golden_total": summary["golden_total"], "tiers": summary["tiers"],
                      "dropped": summary["dropped"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
