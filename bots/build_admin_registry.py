#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成全球行政编码注册表 `rules/geo/global_admin_registry.json`（一次性、可重跑、幂等）。

为什么放进仓库而不是 Release：
  这份表是**参考字典**（性质等同 rules/US/state_roster.yaml），不是抓来的数据载荷。
  读它的代码应当 `git checkout` 就能用，不该依赖"去网上下载一个附件"；放进 git 还能
  用 commit SHA 锁定版本、在 diff 里看清 ISO 每次更新动了哪几条。

数据源与口径（关键：两个体系不能混用）
  1) ISO 3166-1 / 3166-2  → pycountry（背后是 Debian iso-codes），**行政区以它为准**
  2) GeoNames countryInfo  → 只做**国家层增强**：电话区号前缀、邮编正则、大陆码、首都
  3) GeoNames admin1Codes  → 仅在"某国 ISO 完全没有一级行政区"时兜底填充，
     并明确标 source=geonames / in_iso3166_2=false
     ★ GeoNames 的 admin1 码在不少国家（如法国大区）**不等于** ISO 3166-2，
       硬混会造成"看起来像 ISO 其实不是"的脏码，所以绝不做无标记覆盖。

用法：
  python3 bots/build_admin_registry.py                  # 联网取 GeoNames 两个小文件后生成
  python3 bots/build_admin_registry.py --offline        # 只用 pycountry，跳过 GeoNames 增强
  python3 bots/build_admin_registry.py --geonames-dir /path/to/dump   # 用本地已下好的文件
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rules" / "geo" / "global_admin_registry.json"
GN = {
    "countryInfo": "https://download.geonames.org/export/dump/countryInfo.txt",
    "admin1CodesASCII": "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
}


def log(msg: str) -> None:
    print(f"[build_admin_registry] {msg}", file=sys.stderr, flush=True)


def fetch_text(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "world-us-map-data/registry-builder"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_country_info(text: str) -> dict:
    """GeoNames countryInfo.txt：国家层增强（电话区号 / 邮编正则 / 大陆码 / 首都）。"""
    cols = ["iso", "iso3", "iso_numeric", "fips", "country", "capital", "area", "population",
            "continent", "tld", "currency_code", "currency_name", "phone", "postal_format",
            "postal_regex", "languages", "geonameid", "neighbours", "equiv_fips"]
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        row = dict(zip(cols, parts))
        iso = (row.get("iso") or "").strip().upper()
        if not iso:
            continue
        out[iso] = {
            "phone_prefix": (row.get("phone") or "").strip() or None,
            "postal_code_format": (row.get("postal_format") or "").strip() or None,
            "postal_code_regex": (row.get("postal_regex") or "").strip() or None,
            "continent_code": (row.get("continent") or "").strip() or None,
            "capital": (row.get("capital") or "").strip() or None,
            "geoname_id": int(row["geonameid"]) if (row.get("geonameid") or "").isdigit() else None,
        }
    return out


def parse_admin1(text: str) -> dict:
    """GeoNames admin1CodesASCII.txt：'US.RI\\tRhode Island\\tRhode Island\\t5224323'"""
    out: dict = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2 or "." not in parts[0]:
            continue
        cc, _, code = parts[0].partition(".")
        out.setdefault(cc.strip().upper(), []).append({
            "admin_division_code": code,
            "admin_division_name": parts[1].strip(),
            "geoname_id": int(parts[3]) if len(parts) > 3 and parts[3].strip().isdigit() else None,
        })
    return out


def build(geonames_dir: Path | None, offline: bool) -> dict:
    import pycountry

    country_info: dict = {}
    admin1: dict = {}
    if not offline:
        try:
            if geonames_dir:
                ci = (geonames_dir / "countryInfo.txt").read_text(encoding="utf-8", errors="replace")
                a1 = (geonames_dir / "admin1CodesASCII.txt").read_text(encoding="utf-8", errors="replace")
            else:
                ci, a1 = fetch_text(GN["countryInfo"]), fetch_text(GN["admin1CodesASCII"])
            country_info = parse_country_info(ci)
            admin1 = parse_admin1(a1)
            log(f"GeoNames 增强：{len(country_info)} 国 / {sum(len(v) for v in admin1.values())} 条 admin1")
        except Exception as exc:  # noqa: BLE001
            log(f"⚠️ GeoNames 增强失败（{type(exc).__name__}: {str(exc)[:120]}），只产出 ISO 部分")
            country_info, admin1 = {}, {}

    countries = []
    for c in sorted(pycountry.countries, key=lambda x: x.alpha_2):
        extra = country_info.get(c.alpha_2) or {}
        countries.append({
            "country_code": c.alpha_2,
            "country_name": c.name,
            "country_name_common": getattr(c, "common_name", None),
            "country_name_official": getattr(c, "official_name", None),
            "alpha_3": c.alpha_3,
            "numeric": getattr(c, "numeric", None),
            "source": "iso-codes",
            **extra,
        })

    divisions = []
    iso_countries = set()
    for s in sorted(pycountry.subdivisions, key=lambda x: x.code):
        iso_countries.add(s.country_code)
        divisions.append({
            "iso_3166_2": s.code,
            "country_code": s.country_code,
            "admin_division_code": s.code.split("-", 1)[1] if "-" in s.code else s.code,
            "admin_division_name": s.name,
            "admin_division_type": getattr(s, "type", None),
            "parent_code": getattr(s, "parent_code", None),
            "in_iso3166_2": True,
            "source": "iso-codes",
        })

    # ISO 完全没给一级行政区的国家 → GeoNames 兜底（明确标记，不进 ISO 字段）
    filled = 0
    for cc, rows in sorted(admin1.items()):
        if cc in iso_countries or cc not in {c["country_code"] for c in countries}:
            continue
        for r in rows:
            divisions.append({
                "iso_3166_2": None,
                "country_code": cc,
                "admin_division_code": r["admin_division_code"],
                "admin_division_name": r["admin_division_name"],
                "admin_division_type": None,
                "parent_code": None,
                "in_iso3166_2": False,
                "geoname_id": r["geoname_id"],
                "source": "geonames",
            })
            filled += 1

    try:
        import importlib.metadata as md
        isocodes_ver = md.version("pycountry")
    except Exception:  # noqa: BLE001
        isocodes_ver = None

    used_cc = {c["country_code"] for c in countries} & set(country_info)
    return {
        "schema": "global_admin_registry/v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generated_by": "bots/build_admin_registry.py",
        "sources": {
            "iso_3166_1_2": {"provider": "Debian iso-codes via pycountry", "version": isocodes_ver,
                             "license": "LGPL-2.1+（数据来自 ISO 3166 官方文本）"},
            "geonames_countryInfo": {"provider": "GeoNames export/dump", "enriched_countries": len(used_cc),
                                     "license": "CC-BY 4.0",
                                     "note": "只用于国家层增强（电话区号/邮编正则/大陆码/首都）"},
            "geonames_admin1": {"provider": "GeoNames export/dump", "fallback_rows": filled,
                                "license": "CC-BY 4.0",
                                "note": "仅在某国 ISO 完全没有一级行政区时兜底；这类行 iso_3166_2=null、"
                                        "in_iso3166_2=false，绝不当 ISO 码用"},
        },
        "counts": {
            "countries": len(countries),
            "admin_divisions_iso3166_2": len([d for d in divisions if d["in_iso3166_2"]]),
            "admin_divisions_geonames_fallback": filled,
            "countries_with_iso3166_2": len(iso_countries),
        },
        "countries": countries,
        "admin_divisions": divisions,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成全球行政编码注册表（ISO 3166-1/2 + GeoNames 增强）")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--offline", action="store_true", help="跳过 GeoNames，只出 ISO 部分")
    ap.add_argument("--geonames-dir", default="", help="用本地已下好的 countryInfo.txt / admin1CodesASCII.txt")
    args = ap.parse_args(argv)

    data = build(Path(args.geonames_dir) if args.geonames_dir else None, args.offline)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                   encoding="utf-8")
    log(f"✅ {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}  "
        f"（{out.stat().st_size / 1024:.0f} KB / 国家 {data['counts']['countries']} / "
        f"区划 {data['counts']['admin_divisions_iso3166_2']} ISO + "
        f"{data['counts']['admin_divisions_geonames_fallback']} GeoNames 兜底）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
