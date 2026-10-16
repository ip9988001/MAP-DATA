#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自检：不联网，用假 http 层把 fetch_state_raw.py 的四源全流程跑一遍。

跑法：python3 tests/test_fetch_state_raw_offline.py     （无需第三方依赖，纯标准库）

覆盖四个场景：
  S1 四源齐全（整州单框）→ 门禁通过（退出 0）；NAD 走游标分页（orderByFields + where OID > last），全程无 resultOffset
  S2 县界全空            → 门禁阻断（退出 3），且**不落空壳文件**（空壳绝不当资产上传）
  S3 NAD 游标漏行        → 触发 4 分块自愈补齐 → 门禁通过（退出 0），行数与官方 count 对齐
  S4 按县切块并发        → 3 个县分片并行抓、跨片重复按 OID 去重、行数与官方 count 对齐；
                           且县界只查一次（NAD 切块与 TIGER 导出共用缓存）

注：本文件是纯假数据回放，不产生任何网络请求，可在本机/CI 里随便跑。
"""
import io
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bots"))
import fetch_state_raw as fs  # noqa: E402
import dover_fetch as df  # noqa: E402

FULL_BBOX = "-75.8,38.44,-75.04,39.85"
STATE_BBOX = (-75.8, 38.44, -75.04, 39.85)
PAD = "x" * 2000          # 把假边界撑过 1KB（真实边界资产是 99KB~220KB）

# 假 overturemaps CLI：parquet 写占位字节，geojson 写真 features
FAKE_CLI_SRC = '''#!/usr/bin/env python3
import sys
a = sys.argv[1:]
if not a or a[0] != "download":
    sys.exit(1)
out = a[a.index("-o") + 1]
fmt = a[a.index("-f") + 1]
if fmt == "geojson":
    feats = ",".join(
        '{"type":"Feature","properties":{"number":"%d","street":"MAIN ST"},'
        '"geometry":{"type":"Point","coordinates":[-75.5,39.1]}}' % i for i in range(3))
    open(out, "w").write('{"type":"FeatureCollection","features":[' + feats + ']}')
else:
    open(out, "wb").write(b"PAR1" + b"\\x00" * 2048)
'''
FAKE_CLI = Path(tempfile.mkdtemp(prefix="fakebin-")) / "overturemaps"
FAKE_CLI.write_text(FAKE_CLI_SRC, encoding="utf-8")
FAKE_CLI.chmod(0o755)

# 三个县各自的假多边形 → 三个互不重叠的 bbox（复刻"按县切块"的真实几何关系）
COUNTY_RINGS = {
    "001": [[[0.0, 0.0], [0.1, 0.0], [0.1, 0.1], [0.0, 0.1], [0.0, 0.0]]],
    "003": [[[0.1, 0.0], [0.2, 0.0], [0.2, 0.1], [0.1, 0.1], [0.1, 0.0]]],
    "005": [[[0.2, 0.0], [0.3, 0.0], [0.3, 0.1], [0.2, 0.1], [0.2, 0.0]]],
}
SHARD_POOLS = [((0.0, 0.0, 0.1, 0.1), [1, 2]),
               ((0.1, 0.0, 0.2, 0.1), [3, 4]),
               ((0.2, 0.0, 0.3, 0.1), [5])]

CALLS = {"nad": [], "tiger": []}
FAKE = {"official": 5, "main_pool": [], "shard_pool": [], "county_ok": True}


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("us/de/x.csv",
                    "number,street,unit,city,region,postcode,lon,lat\n"
                    + "".join(f"{i} Main St,,Dover,DE,19901,-75.5,39.1\n" for i in range(30)))
        zf.writestr("us/de/x.shp", b"\x00" * 3000)
    return buf.getvalue()


ZIP = make_zip()


def nad_feats(oids):
    # 真实 NAD 一行 ≈1.4KB（39 字段），把假行撑到同一量级，
    # 免得被"数据载荷 ≥1KB"的载荷门禁当成空壳（那条规矩是给空壳 geojson 用的）
    return [{"attributes": {"OBJECTID": o, "Add_Number": str(o), "StNam_Full": "MAIN ST",
                            "Pad": "y" * 200},
             "geometry": {"x": -75.5, "y": 39.1}} for o in oids]


def _bbox_of(params):
    try:
        vals = tuple(float(x) for x in str(params.get("geometry", "")).split(","))
        return vals if len(vals) == 4 else None
    except ValueError:
        return None


def _pool_for(bb):
    if bb is None:
        return []
    if all(abs(a - b) < 1e-9 for a, b in zip(bb, STATE_BBOX)):
        return FAKE["main_pool"]
    for ref, pool in SHARD_POOLS:
        if all(abs(a - b) < 1e-9 for a, b in zip(bb, ref)):
            return pool
    return FAKE["shard_pool"]


def fake_http_json(url, params=None, **kw):
    params = params or {}
    if "returnCountOnly" in params:
        return {"count": FAKE["official"]}
    if url.startswith(df.NAD_OFFICIAL):
        where = params.get("where", "")
        bb = _bbox_of(params)
        pool = _pool_for(bb)
        CALLS["nad"].append({"where": where, "bbox": bb,
                             "kind": ("full" if pool is FAKE["main_pool"] else "shard"),
                             "orderByFields": params.get("orderByFields"),
                             "offset": params.get("resultOffset"),
                             "rc": params.get("resultRecordCount")})
        cur = int(where.split(">")[1].strip()) if ">" in where else None
        avail = [o for o in pool if cur is None or o > cur]
        return {"features": nad_feats(avail[: int(params.get("resultRecordCount") or 2)])}

    where = params.get("where", "")
    CALLS["tiger"].append({"url": url, "where": where})
    pad = {"PAD": PAD}
    if "/State_County/MapServer/0" in url:
        return {"features": [{"attributes": {"STATE": "10", "NAME": "Delaware", **pad},
                              "geometry": {"rings": [[[0, 0], [0.1, 0], [0.1, 0.1]]]}}]}
    if "/State_County/MapServer/1" in url:
        # 县界：只认 3 位 COUNTY 码；5 位必须返回空（复刻线上 680 字节空壳故障）
        if not FAKE["county_ok"]:
            return {"features": []}
        hits = [c for c in COUNTY_RINGS if f"COUNTY='{c}'" in where]
        if not hits and "COUNTY" not in where:          # 整州取回的兜底路径
            hits = list(COUNTY_RINGS)
        return {"features": [{"attributes": {"COUNTY": c, "GEOID": "1000" + c[-1], **pad},
                              "geometry": {"rings": COUNTY_RINGS[c]}} for c in hits]}
    if "PUMA_TAD_TAZ_UGA_ZCTA" in url:
        return {"features": [{"attributes": {"ZCTA5": "19901", **pad}, "geometry": {"rings": []}}]}
    return {"features": [{"attributes": {"BASENAME": "Dover", **pad}, "geometry": {"rings": []}}]}


def fake_http_get(url, **kw):
    if url.rstrip("/") == df.OA_HOME.rstrip("/"):
        return (b'<a href="https://data.openaddresses.io/runs/1195302/us/de/new_castle.zip">n</a>'
                b'<a href="https://data.openaddresses.io/runs/1195369/us/de/kent.zip">k</a>'
                b'<a href="https://data.openaddresses.io/runs/9/us/ri/statewide.zip">ri</a>')
    return ZIP


def setup(official=5, main_pool=None, shard_pool=None, county_ok=True):
    FAKE.update({"official": official, "county_ok": county_ok,
                 "main_pool": list(main_pool if main_pool is not None else range(1, official + 1)),
                 "shard_pool": list(shard_pool or [])})
    CALLS["nad"].clear()
    CALLS["tiger"].clear()
    df.nad_official_metadata = lambda: (
        {"maxRecordCount": 2, "objectIdField": "OBJECTID", "name": "nad", "type": "Feature Layer",
         "fields": [{"name": "OBJECTID"}, {"name": "Add_Number"}, {"name": "StNam_Full"}]},
        ["OBJECTID", "Add_Number", "StNam_Full"])
    df.http_json = fake_http_json
    df.http_get = fake_http_get
    fs.shutil.which = lambda name: str(FAKE_CLI)


def scenario(name, out, shards="none", **kw):
    setup(**kw)
    rc = fs.main(["--state", "DE", "--out-dir", str(out), "--no-release", "--nad-shards", shards,
                  "--overture-format", "parquet"])
    files = sorted(p for p in out.rglob("*") if p.is_file())
    print(f"\n===== {name} → exit {rc} =====")
    for p in files:
        print(f"   {p.stat().st_size:>9,}  {p.relative_to(out)}")
    return rc, files


def main():
    base = Path(tempfile.mkdtemp(prefix="fsr-test-"))
    results = {}

    # ---------- S1 四源齐全（整州单框）----------
    rc1, f1 = scenario("S1 四源齐全 / 整州单框", base / "s1", official=5, main_pool=range(1, 6))
    nd1 = base / "s1" / "nad" / "nad_us_de_full.ndjson"
    n1 = len(nd1.read_text().splitlines()) if nd1.exists() else 0
    n_cnty = len([p for p in f1 if p.name.startswith("tiger_county")])
    n_oa = len([p for p in f1 if p.name.startswith("openaddresses_us_de_")])
    n_ov = len([p for p in f1 if p.name.startswith("overture")])
    print(f"NAD 行数={n1}｜县界={n_cnty}｜OA={n_oa}｜Overture={n_ov}")
    print("游标链：", [(c["where"], c["orderByFields"], c["offset"], c["rc"]) for c in CALLS["nad"]])
    results["S1"] = (rc1 == 0 and n1 == 5 and n_cnty == 3 and n_oa == 2 and n_ov == 1
                     and all(c["orderByFields"] == "OBJECTID ASC" for c in CALLS["nad"])
                     and all(c["offset"] is None for c in CALLS["nad"])
                     and CALLS["nad"][1]["where"] == "OBJECTID > 2")
    print("S1 判定：", "✅ 通过" if results["S1"] else "❌ 失败")

    # ---------- S2 县界全空 ----------
    rc2, f2 = scenario("S2 县界全空", base / "s2", official=5, main_pool=range(1, 6), county_ok=False)
    empty = [p.name for p in f2 if p.name.startswith("tiger_county")]
    results["S2"] = (rc2 == 3 and not empty)
    print(f"S2 判定：{'✅ 通过' if results['S2'] else '❌ 失败'}｜退出={rc2}（期望3）｜残留空壳={empty}")

    # ---------- S3 游标漏行 → 4 分块自愈 ----------
    rc3, f3 = scenario("S3 游标漏行→4分块自愈", base / "s3",
                       official=10, main_pool=range(1, 6), shard_pool=range(6, 11))
    nd3 = base / "s3" / "nad" / "nad_us_de_full.ndjson"
    n3 = len(nd3.read_text().splitlines()) if nd3.exists() else 0
    nad3 = next(s for s in json.loads((base / "s3" / "MANIFEST.json").read_text(encoding="utf-8"))["sources"]
                if s["source"] == "nad")
    print(f"NAD 行数={n3}（期望10）｜官方count={nad3.get('official_count_in_bbox')}｜"
          f"truncated={nad3.get('truncated')}｜repair={nad3.get('repair')}")
    results["S3"] = (rc3 == 0 and n3 == 10 and nad3.get("truncated") is False
                     and (nad3.get("repair") or {}).get("rows_added") == 5)
    print("S3 判定：", "✅ 通过" if results["S3"] else "❌ 失败")

    # ---------- S4 按县切块并发 ----------
    rc4, f4 = scenario("S4 按县切块并发", base / "s4", shards="county", official=5, main_pool=[])
    nd4 = base / "s4" / "nad" / "nad_us_de_full.ndjson"
    n4 = len(nd4.read_text().splitlines()) if nd4.exists() else 0
    man4 = json.loads((base / "s4" / "MANIFEST.json").read_text(encoding="utf-8"))
    nad4 = next(s for s in man4["sources"] if s["source"] == "nad")
    cnt_layer = len([c for c in CALLS["tiger"] if "/State_County/MapServer/1" in c["url"]])
    parts_left = list((base / "s4" / "nad").glob("nad_part_*.ndjson"))
    print(f"NAD 行数={n4}（期望5）｜切块={nad4.get('shard_mode')}｜分片={nad4.get('shard_count')}｜"
          f"跨片去重={nad4.get('cross_shard_dup_dropped')}｜县界图层请求次数={cnt_layer}（期望3，缓存共用）")
    print("分片明细：", json.dumps(nad4.get("shard_detail"), ensure_ascii=False))
    results["S4"] = (rc4 == 0 and n4 == 5 and nad4.get("shard_mode") == "county"
                     and nad4.get("shard_count") == 3 and cnt_layer == 3
                     and not parts_left and nad4.get("truncated") is False)
    print("S4 判定：", "✅ 通过" if results["S4"] else "❌ 失败")

    shutil.rmtree(base, ignore_errors=True)
    print("\n总判定：", "✅ 四个场景全部符合预期" if all(results.values()) else f"❌ {results}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
