#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自检：不联网，用假 http 层把 fetch_state_raw.py 的四源全流程跑一遍。

跑法：python3 tests/test_fetch_state_raw_offline.py     （无需第三方依赖，纯标准库）

六个场景：
  S1 cursor 四源齐全      → 门禁通过；游标分页 orderByFields=OBJECTID ASC、全程无 resultOffset
  S2 县界全空             → 门禁阻断（退出 3），且**不落空壳文件**
  S3 cursor 游标漏行      → 4 分块自愈补齐 → 门禁通过
  S4 cursor 按县切块      → 3 片并行、跨片按 OID 去重、县界只查一次（缓存共用）
  S5 ids 主路径           → returnIdsOnly + objectIds(POST) 批取；某批首次被拒 → 缩批后自恢复；
                            硬对账 official_ids == rows_fetched == 目标集合，全程不碰游标
  S6 ids 降级链           → 州级 returnIdsOnly 失败 → 自动降级到「县」块，仍能拿满并对账通过
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
PAD = "x" * 2000

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

COUNTY_RINGS = {
    "001": [[[0.0, 0.0], [0.1, 0.0], [0.1, 0.1], [0.0, 0.1], [0.0, 0.0]]],
    "003": [[[0.1, 0.0], [0.2, 0.0], [0.2, 0.1], [0.1, 0.1], [0.1, 0.0]]],
    "005": [[[0.2, 0.0], [0.3, 0.0], [0.3, 0.1], [0.2, 0.1], [0.2, 0.0]]],
}
SHARD_POOLS = [((0.0, 0.0, 0.1, 0.1), [1, 2]),
               ((0.1, 0.0, 0.2, 0.1), [3, 4]),
               ((0.2, 0.0, 0.3, 0.1), [5])]

CALLS = {"cursor": [], "tiger": [], "post": []}
FAKE = {"official": 5, "main_pool": [], "shard_pool": [], "county_ok": True,
        "ids_target": [], "ids_fail_state": False, "fail_min_batch": 0}


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


# ---------------- cursor 模式（GET / df.http_json）----------------
def fake_http_json(url, params=None, **kw):
    params = params or {}
    if "returnCountOnly" in params:
        return {"count": FAKE["official"]}
    if url.startswith(df.NAD_OFFICIAL):
        bb = _bbox_of(params)
        pool = _pool_for(bb)
        CALLS["cursor"].append({"where": params.get("where", ""), "bbox": bb,
                                "orderByFields": params.get("orderByFields"),
                                "offset": params.get("resultOffset"),
                                "rc": params.get("resultRecordCount")})
        cur = int(params["where"].split(">")[1].strip()) if ">" in params.get("where", "") else None
        avail = [o for o in pool if cur is None or o > cur]
        return {"features": nad_feats(avail[: int(params.get("resultRecordCount") or 2)])}

    where = params.get("where", "")
    CALLS["tiger"].append({"url": url, "where": where})
    pad = {"PAD": PAD}
    if "/State_County/MapServer/0" in url:
        return {"features": [{"attributes": {"STATE": "10", "NAME": "Delaware", **pad},
                              "geometry": {"rings": [[[0, 0], [0.1, 0], [0.1, 0.1]]]}}]}
    if "/State_County/MapServer/1" in url:
        if not FAKE["county_ok"]:
            return {"features": []}
        hits = [c for c in COUNTY_RINGS if f"COUNTY='{c}'" in where]
        if not hits and "COUNTY" not in where:
            hits = list(COUNTY_RINGS)
        return {"features": [{"attributes": {"COUNTY": c, "GEOID": "1000" + c[-1], **pad},
                              "geometry": {"rings": COUNTY_RINGS[c]}} for c in hits]}
    if "PUMA_TAD_TAZ_UGA_ZCTA" in url:
        return {"features": [{"attributes": {"ZCTA5": "19901", **pad}, "geometry": {"rings": []}}]}
    return {"features": [{"attributes": {"BASENAME": "Dover", **pad}, "geometry": {"rings": []}}]}


# ---------------- ids 模式（POST / fs._post_json）----------------
def fake_post(url, params, timeout=180):
    params = params or {}
    if str(params.get("returnIdsOnly", "")).lower() == "true":
        bb = _bbox_of(params)
        is_state = bb is not None and all(abs(a - b) < 1e-9 for a, b in zip(bb, STATE_BBOX))
        CALLS["post"].append({"kind": "ids_only", "bbox": bb, "state": is_state})
        if is_state and FAKE["ids_fail_state"]:
            return {"error": "HTTP 400 fake Cannot perform query"}
        return {"objectIds": list(FAKE["ids_target"])}
    if "objectIds" in params:
        ids = [int(x) for x in str(params["objectIds"]).split(",") if str(x).strip()]
        CALLS["post"].append({"kind": "batch", "n": len(ids)})
        # 模拟“批太大 → 400”：只要批大于阈值就拒（永远不会因重试而变好，只能拆半）
        if FAKE["fail_min_batch"] and len(ids) >= FAKE["fail_min_batch"]:
            return {"error": "HTTP 400 fake batch too big"}
        avail = [i for i in ids if i in set(FAKE["ids_target"])]
        return {"features": nad_feats(avail)}
    return {"error": "unexpected POST params"}


def fake_http_get(url, **kw):
    if url.rstrip("/") == df.OA_HOME.rstrip("/"):
        return (b'<a href="https://data.openaddresses.io/runs/1195302/us/de/new_castle.zip">n</a>'
                b'<a href="https://data.openaddresses.io/runs/1195369/us/de/kent.zip">k</a>'
                b'<a href="https://data.openaddresses.io/runs/9/us/ri/statewide.zip">ri</a>')
    return ZIP


def setup(official=5, main_pool=None, shard_pool=None, county_ok=True,
          ids_target=None, ids_fail_state=False, fail_min_batch=0):
    FAKE.update({"official": official, "county_ok": county_ok,
                 "main_pool": list(main_pool if main_pool is not None else range(1, official + 1)),
                 "shard_pool": list(shard_pool or []),
                 "ids_target": list(ids_target or []),
                 "ids_fail_state": ids_fail_state,
                 "fail_min_batch": fail_min_batch})
    for k in CALLS:
        CALLS[k].clear()
    df.nad_official_metadata = lambda: (
        {"maxRecordCount": 2, "objectIdField": "OBJECTID", "name": "nad", "type": "Feature Layer",
         "fields": [{"name": "OBJECTID"}, {"name": "Add_Number"}, {"name": "StNam_Full"}]},
        ["OBJECTID", "Add_Number", "StNam_Full"])
    df.http_json = fake_http_json
    df.http_get = fake_http_get
    fs._post_json = fake_post
    fs.shutil.which = lambda name: str(FAKE_CLI)


def scenario(name, out, mode="cursor", shards="none", extra=None, **kw):
    setup(**kw)
    argv = ["--state", "DE", "--out-dir", str(out), "--no-release",
            "--overture-format", "parquet", "--nad-mode", mode, "--nad-shards", shards]
    argv += (extra or [])
    rc = fs.main(argv)
    files = sorted(p for p in out.rglob("*") if p.is_file())
    print(f"\n===== {name} → exit {rc} =====")
    for p in files:
        print(f"   {p.stat().st_size:>9,}  {p.relative_to(out)}")
    return rc, files


def nad_of(out):
    m = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    return next(s for s in m["sources"] if s["source"] == "nad")


def main():
    base = Path(tempfile.mkdtemp(prefix="fsr-test-"))
    results = {}

    # ---------- S1 cursor 四源齐全 ----------
    rc1, f1 = scenario("S1 cursor 四源齐全", base / "s1", mode="cursor",
                       official=5, main_pool=range(1, 6))
    nd1 = base / "s1" / "nad" / "nad_us_de_full.ndjson"
    n1 = len(nd1.read_text().splitlines()) if nd1.exists() else 0
    n_cnty = len([p for p in f1 if p.name.startswith("tiger_county")])
    n_oa = len([p for p in f1 if p.name.startswith("openaddresses_us_de_")])
    n_ov = len([p for p in f1 if p.name.startswith("overture")])
    results["S1"] = (rc1 == 0 and n1 == 5 and n_cnty == 3 and n_oa == 2 and n_ov == 1
                     and all(c["orderByFields"] == "OBJECTID ASC" for c in CALLS["cursor"])
                     and all(c["offset"] is None for c in CALLS["cursor"])
                     and CALLS["cursor"][1]["where"] == "OBJECTID > 2")
    print(f"NAD 行数={n1}｜县界={n_cnty}｜OA={n_oa}｜Overture={n_ov}")
    print("S1 判定：", "✅ 通过" if results["S1"] else "❌ 失败")

    # ---------- S2 县界全空 ----------
    rc2, f2 = scenario("S2 县界全空", base / "s2", mode="cursor",
                       official=5, main_pool=range(1, 6), county_ok=False)
    empty = [p.name for p in f2 if p.name.startswith("tiger_county")]
    results["S2"] = (rc2 == 3 and not empty)
    print(f"S2 判定：{'✅ 通过' if results['S2'] else '❌ 失败'}｜退出={rc2}（期望3）｜残留空壳={empty}")

    # ---------- S3 cursor 游标漏行 → 4 分块自愈 ----------
    rc3, _ = scenario("S3 cursor 游标漏行→自愈", base / "s3", mode="cursor",
                      official=10, main_pool=range(1, 6), shard_pool=range(6, 11))
    nd3 = base / "s3" / "nad" / "nad_us_de_full.ndjson"
    n3 = len(nd3.read_text().splitlines()) if nd3.exists() else 0
    nad3 = nad_of(base / "s3")
    results["S3"] = (rc3 == 0 and n3 == 10 and nad3.get("truncated") is False
                     and (nad3.get("repair") or {}).get("rows_added") == 5)
    print(f"NAD 行数={n3}（期望10）｜repair={nad3.get('repair')}")
    print("S3 判定：", "✅ 通过" if results["S3"] else "❌ 失败")

    # ---------- S4 cursor 按县切块并发 ----------
    rc4, f4 = scenario("S4 cursor 按县切块", base / "s4", mode="cursor", shards="county",
                       official=5, main_pool=[])
    nd4 = base / "s4" / "nad" / "nad_us_de_full.ndjson"
    n4 = len(nd4.read_text().splitlines()) if nd4.exists() else 0
    nad4 = nad_of(base / "s4")
    cnt_layer = len([c for c in CALLS["tiger"] if "/State_County/MapServer/1" in c["url"]])
    results["S4"] = (rc4 == 0 and n4 == 5 and nad4.get("shard_count") == 3
                     and cnt_layer == 3 and not list((base / "s4" / "nad").glob("nad_part_*")))
    print(f"NAD 行数={n4}｜分片={nad4.get('shard_count')}｜县界请求={cnt_layer}（期望3）")
    print("S4 判定：", "✅ 通过" if results["S4"] else "❌ 失败")

    # ---------- S5 ids 主路径（含缩批自恢复）----------
    rc5, f5 = scenario("S5 ids 主路径 + 缩批自恢复", base / "s5", mode="ids",
                       official=10, main_pool=[], ids_target=range(1, 11),
                       fail_min_batch=3, extra=["--nad-ids-batch", "10"])
    nd5 = base / "s5" / "nad" / "nad_us_de_full.ndjson"
    n5 = len(nd5.read_text().splitlines()) if nd5.exists() else 0
    nad5 = nad_of(base / "s5")
    batches = [c for c in CALLS["post"] if c["kind"] == "batch"]
    results["S5"] = (rc5 == 0 and n5 == 10
                     and nad5.get("mode") == "ids"
                     and nad5.get("official_ids") == 10
                     and nad5.get("rows_fetched") == 10
                     and nad5.get("missing_ids") == 0
                     and nad5.get("shrinks", 0) >= 1
                     and not CALLS["cursor"])
    print(f"NAD 行数={n5}（期望10）｜mode={nad5.get('mode')}｜官方IDS={nad5.get('official_ids')}｜"
          f"实取={nad5.get('rows_fetched')}｜缺={nad5.get('missing_ids')}｜缩批={nad5.get('shrinks')}｜"
          f"批次数={len(batches)}｜游标调用={len(CALLS['cursor'])}（期望0）")
    print("S5 判定：", "✅ 通过" if results["S5"] else "❌ 失败")

    # ---------- S6 ids 降级链（州级失败 → 县块）----------
    rc6, _ = scenario("S6 ids 降级链", base / "s6", mode="ids", shards="county",
                      official=10, main_pool=[], ids_target=range(1, 11),
                      ids_fail_state=True, extra=["--nad-ids-batch", "5"])
    nd6 = base / "s6" / "nad" / "nad_us_de_full.ndjson"
    n6 = len(nd6.read_text().splitlines()) if nd6.exists() else 0
    nad6 = nad_of(base / "s6")
    kinds = [c["kind"] for c in CALLS["post"]]
    results["S6"] = (rc6 == 0 and n6 == 10 and nad6.get("missing_ids") == 0
                     and str(nad6.get("fallback") or "").startswith("adaptive")
                     and kinds.count("ids_only") >= 2)
    print(f"NAD 行数={n6}（期望10）｜fallback={nad6.get('fallback')}｜"
          f"ids_only 调用={kinds.count('ids_only')}（州级失败后逐县重试）")
    print("S6 判定：", "✅ 通过" if results["S6"] else "❌ 失败")

    shutil.rmtree(base, ignore_errors=True)
    print("\n总判定：", "✅ 六个场景全部符合预期" if all(results.values()) else f"❌ {results}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
