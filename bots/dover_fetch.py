#!/usr/bin/env python3
"""Dover, DE 四源取样机器人（跑在 GitHub Actions 上，绝不在本地服务器下载）

锚定参数（四源统一口径）：
  州  DE / FIPS 10       县  Kent County / FIPS 10001
  市  Dover / Place FIPS 1021200        邮编 19901（扩展 19904）
  BBox [-75.60, 39.10, -75.45, 39.22]  = [西经, 南纬, 东经, 北纬]

四个数据源（全部走"切片/过滤/小包"，绝不下全美总包）：
  1. Overture Maps (addresses)  —— `overturemaps download --bbox=...` 云端按框切
  2. USDOT NAD (ArcGIS REST)    —— FeatureServer query + 分页（官方图层不可匿名查询时
                                   自动回退到 ArcGIS Online 同名镜像）
  3. OpenAddresses.io           —— us/de 州级小包（自动发现最新 run id）
  4. Census TIGERweb (REST)     —— ZCTA5 / Incorporated Places / Counties / States
                                   + TIGER/Line 小包（tl_2024_10_place.zip 等）

产物（全部落在仓库里，由 workflow 提交回 main）：
  data/dover/raw/*              各源原始产物
  data/dover/*.csv              各源 19901 抽样（≤500 条）
  data/dover/align_19901_main_state.csv  三源并排对齐样本
  data/dover/manifest.json      每个源的状态/耗时/条数/字节/sha256/错误
  docs/dover_report.md          人类可读报告
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------- 锚定参数
STATE = os.environ.get("DOVER_STATE", "DE").upper()
STATE_FIPS = os.environ.get("DOVER_STATE_FIPS", "10")
COUNTY = os.environ.get("DOVER_COUNTY", "Kent County")
COUNTY_FIPS = os.environ.get("DOVER_COUNTY_FIPS", "001")
CITY = os.environ.get("DOVER_CITY", "Dover")
CITY_PLACE_FIPS = os.environ.get("DOVER_PLACE_FIPS", "1021200")
ZIP_MAIN = os.environ.get("DOVER_ZIP", "19901")
ZIP_ALT = os.environ.get("DOVER_ZIP_ALT", "19904")
BBOX = tuple(float(x) for x in os.environ.get("DOVER_BBOX", "-75.60,39.10,-75.45,39.22").split(","))
W, S, E, N = BBOX
ZIPS = [ZIP_MAIN, ZIP_ALT]

SAMPLE_N = int(os.environ.get("DOVER_SAMPLE_N", "500"))
NAD_PAGE = 2000
NAD_MAX = int(os.environ.get("DOVER_NAD_MAX", "30000"))

UA = {"User-Agent": "Mozilla/5.0 (compatible; dover-bot/1.0; +https://github.com/ip9988001/world-map-data-test)",
      "Accept": "*/*"}

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dover"
RAW = OUT / "raw"
DOCS = ROOT / "docs"

# TIGERweb 端点（已探明：全部可匿名查询）
TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"
TIGER_ZCTA = f"{TIGER}/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1"          # 2020 Census ZIP Code Tabulation Areas
TIGER_PLACES = f"{TIGER}/Places_CouSub_ConCity_SubMCD/MapServer/4"  # Incorporated Places
TIGER_COUNTY = f"{TIGER}/State_County/MapServer/1"                  # Counties
TIGER_STATE = f"{TIGER}/State_County/MapServer/0"                   # States

# OpenAddresses：源详情页 + 成品 zip 的 run 目录
OA_HOME = "https://results.openaddresses.io/"
OA_RUN = "https://data.openaddresses.io/runs/{run}/us/{st}/{src}.zip"
OA_TARGETS = ["city_of_dover", "kent"]      # 先试市域源，再退县级源
OA_MAX_ZIP_MB = 300                          # 防 zip bomb / 误抓大包

# NAD：官方图层（探明无法匿名查询，作为首选尝试并如实记账）+ ArcGIS Online 镜像
NAD_ITEM = "ddcaa5e1a9e24c27bff3c3ce16ea2944"     # ArcGIS Online item：National Address Database
NAD_OFFICIAL = ("https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/"
                "Address_Points_from_National_Address_Database_view/FeatureServer/0")
NAD_MIRROR = ("https://services6.arcgis.com/Do88DoK2xjTUCXd1/arcgis/rest/services/"
              "USA_NAD_Addresses/FeatureServer/0")
NAD_MIRROR_FIELDS = {"number": "addr_housenumber", "street": "addr_street", "city": "addr_city",
                     "state": "addr_state", "postcode": "addr_postcode"}

RESULTS: list[dict] = []


def log(msg: str) -> None:
    print(f"[bot] {msg}", flush=True)


def http_get(url: str, *, timeout: int = 60, retries: int = 3, headers: dict | None = None) -> bytes:
    """带 UA / 重试 / 退避的 GET。Cloudflare 与 GitHub 都会 403 掉无 UA 的裸请求。"""
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read()[:200].decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
            last = RuntimeError(f"HTTP {exc.code} {body}")
            if exc.code in (400, 401, 403, 404):
                break                      # 4xx 重试无意义，直接放弃
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"{url} → {last}")


def http_json(url: str, params: dict | None = None, **kw) -> dict:
    query = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    return json.loads(http_get(query, **kw).decode("utf-8", "replace"))


def sha256_head(path: Path, limit: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        h.update(fh.read(limit))
    return h.hexdigest()[:16]


def norm_zip(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))[:5]


def in_bbox(lon: float, lat: float) -> bool:
    return W <= lon <= E and S <= lat <= N


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def record(source: str, status: str, **kw) -> dict:
    item = {"source": source, "status": status, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kw}
    RESULTS.append(item)
    log(f"{source}: {status} {json.dumps({k: v for k, v in kw.items() if k != 'samples'}, ensure_ascii=False)[:300]}")
    return item


# ---------------------------------------------------------------- 1. Overture
OVERTURE_KEYS = ("number", "street", "unit", "postcode", "postcode_ext", "city",
                 "district", "region", "country", "id")


def fetch_overture() -> dict:
    t0 = time.time()
    target = RAW / "overture_dover.geojson"
    target.parent.mkdir(parents=True, exist_ok=True)
    cli = shutil.which("overturemaps")
    if not cli:
        return record("overture", "skipped", note="未安装 overturemaps CLI（workflow 里 pip install overturemaps）")
    cmd = [cli, "download", f"--bbox={W},{S},{E},{N}", "-f", "geojson", "--type=address", "-o", str(target)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    tail = (proc.stdout or "")[-400:] + (proc.stderr or "")[-400:]
    if proc.returncode != 0 or not target.exists():
        return record("overture", "error", cmd=" ".join(cmd), rc=proc.returncode, tail=tail,
                      elapsed=round(time.time() - t0, 1))

    data = json.loads(target.read_text(encoding="utf-8"))
    feats = data.get("features") or []
    rows: list[dict] = []
    for feat in feats:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None]
        rows.append({
            "number": props.get("number", ""), "street": props.get("street", ""),
            "unit": props.get("unit", ""), "city": props.get("city", ""),
            "state": props.get("region", ""), "postcode": props.get("postcode", ""),
            "lon": coords[0], "lat": coords[1],
        })
    rows_19901 = [r for r in rows if norm_zip(r["postcode"]) in ZIPS]
    write_csv(OUT / "overture_19901.csv", rows_19901[:SAMPLE_N],
              ["number", "street", "unit", "city", "state", "postcode", "lon", "lat"])
    return record("overture", "ok", bbox=list(BBOX), features_bbox=len(rows), features_19901=len(rows_19901),
                  sample=SAMPLE_N, bytes=target.stat().st_size, sha256=sha256_head(target),
                  file=str(target.relative_to(ROOT)), elapsed=round(time.time() - t0, 1))


# ---------------------------------------------------------------- 2. NAD
def nad_query(layer: str, where: str, limit: int, fmt: str = "geojson") -> list[dict]:
    """分页拉取。优先 f=geojson，服务不支持时自动降级成 Esri JSON。"""
    out: list[dict] = []
    offset = 0
    while len(out) < limit:
        batch = min(NAD_PAGE, limit - len(out))
        params = {"where": where, "outFields": "*", "returnGeometry": "true",
                  "outSR": "4326", "resultOffset": offset, "resultRecordCount": batch, "f": fmt}
        try:
            payload = http_json(f"{layer}/query", params, timeout=120, retries=2)
        except Exception:  # noqa: BLE001
            if fmt != "json":
                fmt = "json"
                continue
            raise
        if payload.get("error"):
            raise RuntimeError(f"ArcGIS error: {str(payload['error'])[:200]}")
        feats = payload.get("features") or []
        if not feats:
            break
        for feat in feats:
            geom = feat.get("geometry") or {}
            if "attributes" in feat:                      # Esri JSON 格式
                props = dict(feat["attributes"])
                props["_lon"], props["_lat"] = geom.get("x"), geom.get("y")
            else:                                          # GeoJSON 格式
                props = dict(feat.get("properties") or {})
                coords = geom.get("coordinates") or [None, None]
                props["_lon"], props["_lat"] = coords[0], coords[1]
            out.append(props)
        offset += len(feats)
        if len(feats) < batch:
            break
    return out


def fetch_nad() -> dict:
    t0 = time.time()
    notes: list[str] = []
    # 先按架构师给的官方 item 取真实图层 URL，再试官方图层（探明其拒绝匿名查询，如实记账）
    try:
        meta = http_json(f"https://www.arcgis.com/sharing/rest/content/items/{NAD_ITEM}", {"f": "json"})
        notes.append(f"item.url={meta.get('url')}")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"item 元数据失败：{exc}")
    official_error = ""
    try:
        http_json(f"{NAD_OFFICIAL}/query", {"where": f"State='{STATE}' AND Zip_Code='{ZIP_MAIN}'",
                                           "returnCountOnly": "true", "f": "json"}, timeout=60)
        notes.append("官方图层可匿名查询")
    except Exception as exc:  # noqa: BLE001
        official_error = str(exc)[:180]
        notes.append(f"官方图层不可匿名查询（已自动回退镜像）：{official_error}")

    layer = NAD_MIRROR
    rows_zip = nad_query(layer, f"{NAD_MIRROR_FIELDS['state']}='{STATE}' AND {NAD_MIRROR_FIELDS['postcode']}='{ZIP_MAIN}'", NAD_MAX)
    rows_city = nad_query(layer, f"{NAD_MIRROR_FIELDS['state']}='{STATE}' AND {NAD_MIRROR_FIELDS['city']}='{CITY}'", NAD_MAX)
    seen, merged = set(), []
    for row in rows_zip + rows_city:
        key = (row.get("addr_housenumber"), row.get("addr_street"), row.get("_lon"), row.get("_lat"))
        if key not in seen:
            seen.add(key)
            merged.append(row)

    mapped = [{
        "number": row.get(NAD_MIRROR_FIELDS["number"], ""), "street": row.get(NAD_MIRROR_FIELDS["street"], ""),
        "unit": row.get("addr_unit", ""), "city": row.get(NAD_MIRROR_FIELDS["city"], ""),
        "state": row.get(NAD_MIRROR_FIELDS["state"], ""), "postcode": row.get(NAD_MIRROR_FIELDS["postcode"], ""),
        "lon": row.get("_lon"), "lat": row.get("_lat"), "source_dataset": row.get("source", ""),
    } for row in merged]
    write_csv(OUT / "nad_dover_19901.csv", mapped[:SAMPLE_N],
              ["number", "street", "unit", "city", "state", "postcode", "lon", "lat", "source_dataset"])
    (RAW / "nad_dover_19901.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {k: v for k, v in r.items() if not k.startswith("_")},
             "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]}} for r in mapped]},
        ensure_ascii=False), encoding="utf-8")
    return record("nad_arcgis", "ok", layer=layer, where_zip=f"{STATE}+{ZIP_MAIN}",
                  where_city=f"{STATE}+{CITY}", rows_zip=len(rows_zip), rows_city=len(rows_city),
                  rows_dedup=len(merged), sample=SAMPLE_N, official_query_error=official_error,
                  notes=notes, elapsed=round(time.time() - t0, 1))


# ---------------------------------------------------------------- 3. OpenAddresses
def fetch_openaddresses() -> dict:
    t0 = time.time()
    home = http_get(OA_HOME, timeout=90).decode("utf-8", "replace")
    found = re.findall(r"https://data\.openaddresses\.io/runs/(\d+)/us/([a-z]{2})/([a-z0-9_]+)\.zip", home)
    targets: list[tuple[str, str]] = []
    for src in OA_TARGETS:
        for run, st, name in found:
            if st == STATE.lower() and name == src:
                targets.append((src, OA_RUN.format(run=run, st=st, src=name)))
                break
    if not targets:
        return record("openaddresses", "error", note=f"results 首页里没找到 us/{STATE.lower()} 的 {OA_TARGETS}",
                      discovered=len(found), elapsed=round(time.time() - t0, 1))

    all_rows: list[dict] = []
    detail = []
    for src, url in targets:
        try:
            blob = http_get(url, timeout=600)
            if len(blob) > OA_MAX_ZIP_MB * 1024 * 1024:
                detail.append({"src": src, "url": url, "skipped": f"{len(blob)/1e6:.1f}MB > 上限"})
                continue
            (RAW / f"openaddresses_{src}.zip").write_bytes(blob)
            rows, files = parse_oa_zip(blob)
            all_rows.extend(rows)
            detail.append({"src": src, "url": url, "bytes": len(blob), "csv_members": files,
                           "rows": len(rows), "rows_19901": sum(1 for r in rows if norm_zip(r["postcode"]) in ZIPS)})
        except Exception as exc:  # noqa: BLE001
            detail.append({"src": src, "url": url, "error": str(exc)[:200]})

    hit = [r for r in all_rows if norm_zip(r["postcode"]) in ZIPS]
    if not hit:      # postcode 空值兜底：按 BBox 过滤
        hit = [r for r in all_rows if r.get("lon") and in_bbox(float(r["lon"]), float(r["lat"]))]
    write_csv(OUT / "openaddresses_19901.csv", hit[:SAMPLE_N],
              ["number", "street", "unit", "city", "state", "postcode", "lon", "lat"])
    status = "ok" if all_rows else "error"
    return record("openaddresses", status, targets=len(targets), rows=len(all_rows),
                  rows_19901=len(hit), sample=SAMPLE_N, detail=detail, elapsed=round(time.time() - t0, 1))


def parse_oa_zip(blob: bytes) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    members: list[str] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for info in zf.infolist():
            if info.file_size > OA_MAX_ZIP_MB * 1024 * 1024:
                continue
            name = info.filename.lower()
            if not (name.endswith(".csv") or name.endswith(".ndjson") or name.endswith(".geojson")):
                continue
            members.append(info.filename)
            with zf.open(info) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
                if name.endswith(".csv"):
                    reader = csv.DictReader(text)
                    for rec in reader:
                        low = {str(k).strip().lower(): v for k, v in rec.items()}
                        rows.append({
                            "number": low.get("number", "") or low.get("housenumber", ""),
                            "street": low.get("street", ""), "unit": low.get("unit", ""),
                            "city": low.get("city", ""), "state": low.get("region", "") or low.get("state", ""),
                            "postcode": low.get("postcode", ""), "lon": low.get("lon", ""), "lat": low.get("lat", ""),
                        })
    return rows, members


# ---------------------------------------------------------------- 4. Census TIGER
TIGER_QUERIES = [
    ("zcta", TIGER_ZCTA, f"ZCTA5='{ZIP_MAIN}' OR ZCTA5='{ZIP_ALT}'", "ZCTA5,GEOID", True),
    ("place_dover", TIGER_PLACES, f"STATE='{STATE_FIPS}' AND BASENAME='{CITY}'", "GEOID,NAME,BASENAME,STATE,PLACE,CENTLAT,CENTLON", True),
    ("county_kent", TIGER_COUNTY, f"STATE='{STATE_FIPS}' AND COUNTY='{COUNTY_FIPS}'", "GEOID,BASENAME,STATE,COUNTY,NAME", True),
    ("state_de", TIGER_STATE, f"STATE='{STATE_FIPS}'", "GEOID,STUSPS,NAME,BASENAME", True),
]
TIGER_FILES = [
    ("tl_2024_10_place.zip", "https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_10_place.zip"),
    ("tl_2024_10001_addrfeat.zip", "https://www2.census.gov/geo/tiger/TIGER2024/ADDRFEAT/tl_2024_10001_addrfeat.zip"),
]


def fetch_tiger() -> dict:
    t0 = time.time()
    detail = []
    for key, layer, where, fields, geom in TIGER_QUERIES:
        try:
            payload = http_json(f"{layer}/query", {
                "where": where, "outFields": fields, "returnGeometry": "true" if geom else "false",
                "outSR": "4326", "f": "json"}, timeout=90)
            feats = payload.get("features") or []
            target = RAW / f"tiger_{key}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            detail.append({"key": key, "layer": layer, "where": where, "count": len(feats),
                           "file": str(target.relative_to(ROOT))})
        except Exception as exc:  # noqa: BLE001
            detail.append({"key": key, "layer": layer, "where": where, "error": str(exc)[:180]})

    shp = []
    for name, url in TIGER_FILES:
        try:
            blob = http_get(url, timeout=300)
            target = RAW / name
            target.write_bytes(blob)
            info = {"file": name, "bytes": len(blob), "url": url}
            try:                                        # 有 pyshp 就顺手统计记录数（不装 GDAL）
                import shapefile                          # noqa: PLC0415
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    dbf_name = next((n for n in zf.namelist() if n.endswith(".dbf")), None)
                    if dbf_name:
                        reader = shapefile.Reader(dbf=io.BytesIO(zf.read(dbf_name)))
                        info["dbf_records"] = len(reader)
                        info["dbf_fields"] = [f[0] for f in reader.fields if f[0] != "DeletionFlag"][:12]
            except Exception as exc:  # noqa: BLE001
                info["dbf_note"] = str(exc)[:120]
            shp.append(info)
        except Exception as exc:  # noqa: BLE001
            shp.append({"file": name, "url": url, "error": str(exc)[:180]})

    ok = sum(1 for d in detail if "count" in d)
    return record("census_tiger", "ok" if ok else "error", rest_queries=detail, tiger_line_files=shp,
                  elapsed=round(time.time() - t0, 1))


# ---------------------------------------------------------------- 对齐样本
ALIGN_FIELDS = ["source", "number", "street", "city", "state", "postcode", "lon", "lat"]


def read_sample(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_alignment() -> dict:
    picked: list[dict] = []
    stats = {}
    for source, name in (("overture", "overture_19901.csv"), ("nad_arcgis", "nad_dover_19901.csv"),
                         ("openaddresses", "openaddresses_19901.csv")):
        rows = [r for r in read_sample(OUT / name)
                if norm_zip(r.get("postcode")) in ZIPS
                and re.search(r"\b(MAIN|STATE)\b", str(r.get("street", "")).upper())]
        rows.sort(key=lambda r: (str(r.get("street", "")), str(r.get("number", ""))))
        stats[source] = len(rows)
        for row in rows[:SAMPLE_N]:
            picked.append({"source": source, **{k: row.get(k, "") for k in ALIGN_FIELDS[1:]}})
    write_csv(OUT / "align_19901_main_state.csv", picked, ALIGN_FIELDS)
    return {"rows": len(picked), "per_source": stats, "file": "data/dover/align_19901_main_state.csv"}


# ---------------------------------------------------------------- 报告
def write_report(align: dict) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Dover, DE 四源取样报告（自动生成）",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())} ｜ 运行位置：**GitHub Actions**（本机服务器零下载）",
        f"> 锚定参数：州 `{STATE}`/FIPS `{STATE_FIPS}`｜县 `{COUNTY}`/FIPS `{STATE_FIPS}{COUNTY_FIPS}`｜"
        f"市 `{CITY}`/Place FIPS `{CITY_PLACE_FIPS}`｜邮编 `{'`, `'.join(ZIPS)}`｜"
        f"BBox `[{W}, {S}, {E}, {N}]`",
        "",
        "## 0. 四源状态",
        "",
        "| 源 | 状态 | 关键数字 | 备注 |",
        "|---|---|---|---|",
    ]
    for item in RESULTS:
        key_bits = []
        for k in ("features_bbox", "features_19901", "rows_zip", "rows_city", "rows_dedup",
                  "rows", "rows_19901", "targets"):
            if k in item:
                key_bits.append(f"{k}={item[k]}")
        if "rest_queries" in item:
            key_bits.append("REST=" + ",".join(f"{d['key']}:{d.get('count', d.get('error', '?'))}"
                                               for d in item["rest_queries"]))
        note = item.get("note") or item.get("official_query_error") or ""
        lines.append(f"| `{item['source']}` | {item['status']} | {' / '.join(key_bits) or '-'} | {str(note)[:160]} |")

    lines += [
        "",
        f"## 1. 三源并排对齐样本（邮编 {'/'.join(ZIPS)} + 街道含 MAIN 或 STATE）",
        "",
        f"合计 **{align['rows']}** 行 → `{align['file']}`",
        f"各源命中：{json.dumps(align['per_source'], ensure_ascii=False)}",
        "",
        "## 2. 产物清单",
        "",
    ]
    for path in sorted(OUT.rglob("*")):
        if path.is_file():
            lines.append(f"- `{path.relative_to(ROOT)}` — {path.stat().st_size:,} B")
    lines += [
        "",
        "## 3. 口径与已知边界",
        "",
        "- NAD 官方图层（USDOT item `ddcaa5e1a9e24c27bff3c3ce16ea2944`）**拒绝匿名查询**，机器人自动回退到 "
        "ArcGIS Online 同名镜像 `USA_NAD_Addresses`；官方图层的失败原因已如实记入 `manifest.json`。",
        "- OpenAddresses 的 run id 每次跑都可能变，机器人**每次现查首页**取最新 zip，不写死链接。",
        "- 三源字段命名各异（Overture `number/street/postcode`、NAD `addr_*`、OA `NUMBER/STREET`），"
        "本报告只做**并排对齐**，不做合并——合成规则待架构师定稿。",
        "- ZCTA 边界（19901）是**邮编多边形**，与本项目一直用的州 BBox 不同层级，不可混用。",
        "",
    ]
    (DOCS / "dover_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    log(f"目标：{CITY}, {STATE}｜邮编 {ZIPS}｜BBox {BBOX}")
    for fn in (fetch_overture, fetch_nad, fetch_openaddresses, fetch_tiger):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 单源失败绝不拖垮整轮
            record(fn.__name__.replace("fetch_", ""), "exception", error=f"{type(exc).__name__}: {str(exc)[:300]}")
    align = build_alignment()
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "anchors": {"state": STATE, "state_fips": STATE_FIPS, "county": COUNTY,
                    "county_fips": f"{STATE_FIPS}{COUNTY_FIPS}", "city": CITY,
                    "place_fips": CITY_PLACE_FIPS, "zips": ZIPS, "bbox": list(BBOX)},
        "runner": os.environ.get("GITHUB_RUN_ID", "local"),
        "sources": RESULTS, "alignment": align,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(align)
    log("完成：" + json.dumps({i["source"]: i["status"] for i in RESULTS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
