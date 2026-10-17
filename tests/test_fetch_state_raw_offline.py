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
  S7 ids 400k 静默截断    → 州级 ids 被服务端截到上限（count 更大）→ 四象限递归切分 →
                            叶子逐个对齐、汇总 == 州级 count、门禁放行（模拟真实 RI 事故）
  S8 四源自证 + 元数据   → MANIFEST 的 completeness（四源对账）/ quality（State 分布）/
                            row_counts / 全文 sha256 全部到位（P0+P2）
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
        "ids_target": [], "ids_by_bbox": {}, "ids_cap": 0,
        "ids_fail_state": False, "fail_min_batch": 0}


def kk(bb):
    """BBox → 可哈希 key（6 位小数）。生产端用 str(float) 拼串，回读后取整一致。"""
    return tuple(round(float(v), 6) for v in bb) if bb else None


def _ids_for(bb):
    """某 BBox 的**真实**主键全集（未截断）；未登记的 BBox 回退 ids_target。"""
    if bb is None:
        return []
    hit = FAKE["ids_by_bbox"].get(kk(bb))
    return list(hit) if hit is not None else list(FAKE["ids_target"])


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("us/de/x.csv",
                    "number,street,unit,city,region,postcode,lon,lat\n"
                    + "".join(f"{i} Main St,,Dover,DE,19901,-75.5,39.1\n" for i in range(30)))
        zf.writestr("us/de/x.shp", b"\x00" * 3000)
        # 真 .dbf/.shx 头：给 TIGER 双头对账（.dbf 记录数 == .shx 记录数）用
        nrec, hlen = 30, 33 + 32
        dbf = bytearray(32 + 32 + 1)
        dbf[0] = 3
        dbf[4:8] = nrec.to_bytes(4, "little")
        dbf[8:10] = hlen.to_bytes(2, "little")
        dbf[10:12] = (1 + 12).to_bytes(2, "little")
        dbf[32:43] = b"TLID\x00\x00\x00\x00\x00\x00\x00"
        dbf[64] = 0x0D
        zf.writestr("us/de/x.dbf", bytes(dbf))
        zf.writestr("us/de/x.shx", b"\x00" * (100 + nrec * 8))
    return buf.getvalue()


ZIP = make_zip()


def nad_feats(oids):
    return [{"attributes": {"OBJECTID": o, "Add_Number": str(o), "StNam_Full": "MAIN ST",
                            "State": "DE", "Pad": "y" * 200},
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
    if str(params.get("returnCountOnly", "")).lower() == "true":
        bb = _bbox_of(params)
        CALLS["post"].append({"kind": "count", "bbox": bb})
        return {"count": len(_ids_for(bb))}
    if str(params.get("returnIdsOnly", "")).lower() == "true":
        bb = _bbox_of(params)
        is_state = bb is not None and all(abs(a - b) < 1e-9 for a, b in zip(bb, STATE_BBOX))
        CALLS["post"].append({"kind": "ids_only", "bbox": bb, "state": is_state})
        if is_state and FAKE["ids_fail_state"]:
            return {"error": "HTTP 400 fake Cannot perform query"}
        pool = _ids_for(bb)
        # 模拟 Esri 服务端静默上限：不报错，只少给
        if FAKE["ids_cap"] and len(pool) > FAKE["ids_cap"]:
            pool = pool[:FAKE["ids_cap"]]
        return {"objectIds": list(pool)}
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
          ids_target=None, ids_fail_state=False, fail_min_batch=0,
          ids_by_bbox=None, ids_cap=0):
    FAKE.update({"official": official, "county_ok": county_ok,
                 "main_pool": list(main_pool if main_pool is not None else range(1, official + 1)),
                 "shard_pool": list(shard_pool or []),
                 "ids_target": list(ids_target or []),
                 "ids_by_bbox": dict(ids_by_bbox or {}),
                 "ids_cap": ids_cap,
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

    # ---------- S7 ids 400k 静默截断 → 四象限递归切分 ----------
    # 真事故复刻：RI 整州 count=569,222 但 returnIdsOnly 只给 400,000（不报错）。
    # 这里用更小的数：整州 12 条、上限 6 条 → 4 个象限各 3 条（低于上限）。
    w, s0, e, n = STATE_BBOX
    mx, my = (w + e) / 2.0, (s0 + n) / 2.0
    quads = [(w, s0, mx, my), (mx, s0, e, my), (w, my, mx, n), (mx, my, e, n)]
    ids_map = {kk(STATE_BBOX): list(range(1, 13))}
    for i, q in enumerate(quads):
        ids_map[kk(q)] = [i * 3 + 1, i * 3 + 2, i * 3 + 3]
    rc7, _ = scenario("S7 ids 上限截断→四象限递归", base / "s7", mode="ids",
                      official=12, main_pool=[], ids_target=range(1, 13),
                      ids_by_bbox=ids_map, ids_cap=6, extra=["--nad-ids-batch", "10"])
    nd7 = base / "s7" / "nad" / "nad_us_de_full.ndjson"
    n7 = len(nd7.read_text().splitlines()) if nd7.exists() else 0
    nad7 = nad_of(base / "s7")
    kinds7 = [c["kind"] for c in CALLS["post"]]
    results["S7"] = (rc7 == 0 and n7 == 12
                     and nad7.get("rows_fetched") == 12
                     and nad7.get("official_count") == 12
                     and nad7.get("coverage_pct") == 100.0
                     and nad7.get("missing_ids") == 0
                     and nad7.get("ids_cap_hits", 0) >= 1
                     and nad7.get("ids_leaves") == 4
                     and kinds7.count("ids_only") == 5)   # 1 州级 + 4 象限
    print(f"NAD 行数={n7}（期望12）｜official_count={nad7.get('official_count')}｜"
          f"覆盖率={nad7.get('coverage_pct')}%｜叶子={nad7.get('ids_leaves')}（期望4）｜"
          f"上限命中={nad7.get('ids_cap_hits')}｜ids_only 调用={kinds7.count('ids_only')}（期望5）")
    print("S7 判定：", "✅ 通过" if results["S7"] else "❌ 失败")

    # ---------- S8 四源自证完整 + 元数据（P0/P2）----------
    rc8, _ = scenario("S8 四源自证 + 元数据", base / "s8", mode="ids", official=4,
                      main_pool=[], ids_target=range(1, 5))
    man8 = json.loads((base / "s8" / "MANIFEST.json").read_text(encoding="utf-8"))
    comp8 = man8.get("completeness") or {}
    q8 = man8.get("quality") or {}
    dist8 = q8.get("state_distribution") or {}
    res = {
        "退出0": rc8 == 0,
        "四源齐": set(comp8) == {"note", "nad", "overture", "openaddresses", "census_tiger"},
        "nad对账": comp8.get("nad", {}).get("evidence_1_full") is True,
        "tiger双头对账": comp8.get("census_tiger", {}).get("evidence_1_full") is True,
        "oa行数": comp8.get("openaddresses", {}).get("local_rows", 0) > 0,
        "state分布": dist8.get("DE") == 4 and sum(dist8.values()) == 4,
        "sha256全文64位": all(len(a.get("sha256", "")) == 64 for a in man8["assets"]),
        "sha256_head16位": all(len(a.get("sha256_head", "")) == 16 for a in man8["assets"]),
        "row_counts": bool(man8.get("row_counts")),
    }
    results["S8"] = all(res.values())
    print(f"  completeness.nad={comp8.get('nad', {}).get('upstream_declared_rows')}→{comp8.get('nad', {}).get('local_rows')}｜"
          f"state_distribution={dist8}｜资产摘要长度={len(man8['assets'][0].get('sha256', ''))}/"
          f"{len(man8['assets'][0].get('sha256_head', ''))}｜row_counts键={len(man8.get('row_counts') or {})}")
    bad8 = [k for k, v in res.items() if not v]
    print("S8 判定：", "✅ 通过" if results["S8"] else f"❌ 失败 {bad8}")

    shutil.rmtree(base, ignore_errors=True)
    print("\n总判定：", "✅ 八个场景全部符合预期" if all(results.values()) else f"❌ {results}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
