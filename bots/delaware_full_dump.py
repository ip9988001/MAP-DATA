#!/usr/bin/env python3
"""Delaware 全州三县（Kent / New Castle / Sussex）四源【全量原始】数据抓取 → GitHub Releases。

TASK-004 前置：为 `scripts/delaware_statewide_coalesce.py` 准备原始资产。

纪律（与项目铁律一致）：
  * 所有下载都发生在 **GitHub Actions runner** 上 —— 本地服务器零下载。
  * **不做任何清洗、去重、过滤、字段裁剪** —— 源里给什么，就原样落什么。
  * 产物体积大 → **不进 git**，只作为 Release 资产上传。
  * 缺源不猜：单源失败如实记账，不伪造数据。

四源：
  A. USDOT NAD        官方正牌通道 A（交通部 GeoServices REST，动态全字段 + envelope 分页）
  B. Overture Maps    overturemaps CLI 按 bbox 云端切
  C. OpenAddresses    results.openaddresses.io 上 us/de 全部源 zip（原始压缩包）
  D. Census TIGER     三县 ADDRFEAT zip + 三县/州/ZCTA 官方边界图层 REST JSON

资产名与 ETL 约定一一对应（ETL 按文件名读，改名前先改 ETL scope）：
  nad_de_full.ndjson / overture_de_addresses.geojson
  openaddresses_us_de_{kent,city_of_dover,new_castle,sussex}.zip
  tl_2024_{10001,10003,10005}_addrfeat.zip
  tiger_county_{kent,new_castle,sussex}.geojson / tiger_state_de.geojson / tiger_zcta_de.geojson

用法：
  python bots/delaware_full_dump.py                 # 抓取 + 生成 MANIFEST + 建 Release
  python bots/delaware_full_dump.py --no-release     # 只抓取，不上传（自检用）
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dover_fetch as df  # noqa: E402  复用 TASK-001 已验证的四源正牌通道助手

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "delaware" / "task004" / "raw"
STAMP = time.strftime("%Y%m%d-%H%M", time.gmtime())
TAG_DEFAULT = f"delaware-raw-{STAMP}"

# ---------------------------------------------------------------- 全州范围
STATE, STATE_FIPS = "DE", "10"
BBOX = (-75.80, 38.44, -75.04, 39.85)        # 三县外接矩形（真正的范围裁剪由县界多边形做）
COUNTIES = [("kent", "10001", "Kent"), ("new_castle", "10003", "New Castle"),
            ("sussex", "10005", "Sussex")]

# 让复用的助手按全州范围工作（助手内部读模块级 BBOX / RAW）
df.BBOX = BBOX
df.STATE = STATE
df.STATE_FIPS = STATE_FIPS
df.RAW = OUT
BBOX_STR = ",".join(str(v) for v in BBOX)

NAD_MAX = int(os.environ.get("DE_NAD_MAX", "800000"))
OA_MAX_MB = int(os.environ.get("DE_OA_MAX_MB", "800"))
OA_MAX_FILES = int(os.environ.get("DE_OA_MAX_FILES", "60"))
RESULTS: list[dict] = []


def log(msg: str) -> None:
    print(f"[de-full] {msg}", flush=True)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            blob = fh.read(chunk)
            if not blob:
                break
            h.update(blob)
    return h.hexdigest()


def count_lines(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def note(source: str, status: str, **kw) -> None:
    RESULTS.append({"source": source, "status": status, **kw})
    log(f"{source} {status}: {json.dumps({k: v for k, v in kw.items() if k != 'files'}, ensure_ascii=False)[:400]}")


def asset(path: Path, **extra) -> dict:
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
            "sha256": sha256_file(path), **extra}


# ---------------------------------------------------------------- A. USDOT NAD（全州三县）
def harvest_nad() -> list[Path]:
    d = OUT / "nad"
    d.mkdir(parents=True, exist_ok=True)
    meta, fields = df.nad_official_metadata()
    payload = {k: meta[k] for k in ("name", "type", "maxRecordCount", "description",
                                    "copyrightText", "fields") if k in meta}
    (d / "nad_native_metadata.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    count = df.http_json(f"{df.NAD_OFFICIAL}/query", {
        "where": "1=1", "geometry": BBOX_STR, "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true", "f": "json"}, timeout=180)
    official_total = count.get("count")

    rows = df.nad_official_pull(fields, limit=NAD_MAX)
    ndjson = d / "nad_de_full.ndjson"
    with ndjson.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (d / "nad_full_columns.json").write_text(
        json.dumps({"fields": fields, "fields_n": len(fields)}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    truncated = bool(official_total) and len(rows) < int(official_total)
    note("nad", "ok", channel="A-official-rest", endpoint=df.NAD_OFFICIAL,
         fields_n=len(fields), rows_fetched=len(rows), official_count_in_bbox=official_total,
         truncated=truncated)
    if truncated:
        note("nad", "warn-truncated", detail="拉取条数少于官方 count，全州规模下请提高 DE_NAD_MAX 重跑")
    return [d / "nad_native_metadata.json", ndjson, d / "nad_full_columns.json"]


# ---------------------------------------------------------------- B. Overture Maps（全州）
def harvest_overture() -> list[Path]:
    cli = shutil.which("overturemaps")
    if not cli:
        raise RuntimeError("overturemaps CLI 未安装（requirements.txt / workflow 里应有）")
    d = OUT / "overture"
    d.mkdir(parents=True, exist_ok=True)
    target = d / "overture_de_addresses.geojson"
    cmd = [cli, "download", f"--bbox={BBOX_STR}", "-f", "geojson", "--type=address", "-o", str(target)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0 or not target.exists():
        raise RuntimeError(f"overturemaps rc={proc.returncode} tail={(proc.stderr or '')[-300:]}")
    feats = 0
    try:
        feats = len((json.loads(target.read_text(encoding="utf-8")).get("features") or []))
    except Exception:  # noqa: BLE001
        pass
    note("overture", "ok", bbox=BBOX_STR, features=feats)
    return [target]


# ---------------------------------------------------------------- C. OpenAddresses（us/de 全部源，原始 zip）
OA_PRIORITY = ["kent", "city_of_dover", "new_castle", "sussex"]


def harvest_openaddresses() -> list[Path]:
    d = OUT / "openaddresses"
    d.mkdir(parents=True, exist_ok=True)
    home = df.http_get(df.OA_HOME, timeout=120).decode("utf-8", "replace")
    found = re.findall(r"https://data\.openaddresses\.io/runs/(\d+)/us/([a-z]{2})/([a-z0-9_]+)\.zip", home)
    latest: dict[str, tuple[str, str, str]] = {}
    for run, st, name in found:
        if st == STATE.lower():
            latest.setdefault(name, (run, st, name))     # 首页是最新 run，取首次出现
    if not latest:
        raise RuntimeError("results.openaddresses.io 首页未发现 us/de 的任何源 zip")
    order = [n for n in OA_PRIORITY if n in latest] + \
            [n for n in sorted(latest) if n not in OA_PRIORITY]
    files: list[Path] = []
    detail = []
    for name in order[:OA_MAX_FILES]:
        run, st, src = latest[name]
        url = df.OA_RUN.format(run=run, st=st, src=src)
        try:
            blob = df.http_get(url, timeout=1800)
            if len(blob) > OA_MAX_MB * 1024 * 1024:
                detail.append({"src": name, "skipped": f"{len(blob)/1e6:.1f}MB 超过 {OA_MAX_MB}MB 上限"})
                continue
            path = d / f"openaddresses_us_de_{name}.zip"
            path.write_bytes(blob)
            rows = 0
            try:
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    for info in zf.infolist():
                        if info.filename.lower().endswith((".csv", ".ndjson")):
                            with zf.open(info) as fh:
                                rows += sum(1 for _ in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                pass
            detail.append({"src": name, "run": run, "bytes": len(blob), "native_rows": rows,
                           "file": str(path.relative_to(ROOT))})
            files.append(path)
        except Exception as exc:  # noqa: BLE001
            detail.append({"src": name, "url": url, "error": str(exc)[:200]})
    note("openaddresses", "ok" if files else "error", sources_total=len(latest),
         downloaded=len(files), detail=detail)
    return files


# ---------------------------------------------------------------- D. Census TIGER（三县原始小包 + 边界图层）
TIGER_BASE = "https://www2.census.gov/geo/tiger/TIGER2024"


def tiger_queries() -> list[tuple[str, str, list[tuple[str, str]]]]:
    q = []
    for key, fips, base in COUNTIES:
        q.append((f"county_{key}", df.TIGER_COUNTY,
                  [(f"STATE='{STATE_FIPS}' AND COUNTY='{fips}'", "GEOID,BASENAME,STATE,COUNTY,NAME"),
                   (f"STATEFP='{STATE_FIPS}' AND COUNTYFP='{fips}'", "GEOID,BASENAME,STATEFP,COUNTYFP,NAME")]))
    # ⚠️ State 图层真实字段是 STATE / STUSAB（没有 STATEFP / STUSPS），带错字段直接 400
    q.append(("state_de", df.TIGER_STATE,
              [(f"STATE='{STATE_FIPS}'", "GEOID,STATE,STUSAB,BASENAME,NAME"),
               (f"STUSAB='{STATE}'", "GEOID,STATE,STUSAB,BASENAME,NAME")]))
    # DE 邮编段 19700–19980，避开 PA 的 19xxx
    q.append(("zcta_de", df.TIGER_ZCTA,
              [("ZCTA5>='19700' AND ZCTA5<='19980'", "ZCTA5,GEOID,STATE"),
               ("ZCTA5>='19700' AND ZCTA5<='19980'", "ZCTA5,GEOID")]))
    return q


def tiger_files() -> list[tuple[str, str]]:
    f = [(f"tl_2024_{fips}_addrfeat.zip", f"{TIGER_BASE}/ADDRFEAT/tl_2024_{fips}_addrfeat.zip")
         for _key, fips, _b in COUNTIES]
    f.append(("tl_2024_10_place.zip", f"{TIGER_BASE}/PLACE/tl_2024_10_place.zip"))
    return f


def harvest_tiger() -> list[Path]:
    d = OUT / "tiger"
    d.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    detail = []
    for key, layer, attempts in tiger_queries():
        got = None
        for where, fields in attempts:
            try:
                payload = df.http_json(f"{layer}/query", {
                    "where": where, "outFields": fields, "returnGeometry": "true",
                    "outSR": "4326", "f": "json"}, timeout=180)
                if not payload.get("error"):
                    got = (where, payload)
                    break
                detail.append({"key": key, "layer": layer, "where": where,
                               "esri_error": str(payload["error"])[:160]})
            except Exception as exc:  # noqa: BLE001
                detail.append({"key": key, "layer": layer, "where": where, "error": str(exc)[:150]})
        if not got:
            detail.append({"key": key, "layer": layer, "status": "all_attempts_failed",
                           "tried": [w for w, _ in attempts]})
            continue
        where, payload = got
        path = d / f"tiger_{key}.geojson"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        files.append(path)
        detail.append({"key": key, "layer": layer, "where": where,
                       "features": len(payload.get("features") or [])})
    for name, url in tiger_files():
        try:
            blob = df.http_get(url, timeout=1800)
            path = d / name
            path.write_bytes(blob)
            files.append(path)
            detail.append({"file": name, "bytes": len(blob), "url": url})
        except Exception as exc:  # noqa: BLE001
            detail.append({"file": name, "url": url, "error": str(exc)[:200]})
    # 顺带把各县 ADDRFEAT 的行数/列名如实记进 manifest（只读元信息，不改数据）
    for _key, fips, _b in COUNTIES:
        addrfeat = d / f"tl_2024_{fips}_addrfeat.zip"
        if not addrfeat.exists():
            continue
        try:
            with zipfile.ZipFile(addrfeat) as zf:
                dbf = next((n for n in zf.namelist() if n.endswith(".dbf")), None)
                if dbf:
                    b = zf.read(dbf)
                    nrec = int.from_bytes(b[4:8], "little")
                    hlen = int.from_bytes(b[8:10], "little")
                    names = [b[32 + i * 32:32 + i * 32 + 11].split(b"\x00")[0].decode()
                             for i in range((hlen - 33) // 32)]
                    detail.append({"file": addrfeat.name, "dbf_records": nrec, "dbf_fields": names})
        except Exception as exc:  # noqa: BLE001
            detail.append({"file": addrfeat.name, "dbf_error": str(exc)[:150]})
    note("census_tiger", "ok" if files else "error", detail=detail)
    return files


# ---------------------------------------------------------------- Release
def build_manifest(files: list[Path]) -> Path:
    manifest = {
        "scope": {
            "note": "Delaware 全州三县 —— 四源全量【原始】数据，未做任何清洗/去重/过滤/裁剪",
            "state": STATE, "state_fips": STATE_FIPS,
            "counties": [{"key": k, "fips": f, "name": n} for k, f, n in COUNTIES],
            "bbox": list(BBOX),
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runner": os.environ.get("GITHUB_RUN_ID", "local"),
        "commit": os.environ.get("GITHUB_SHA", ""),
        "sources": RESULTS,
        "assets": [],
    }
    for path in files:
        info = asset(path)
        if path.suffix in (".ndjson", ".csv"):
            info["rows"] = count_lines(path)
        manifest["assets"].append(info)
    out = OUT / "MANIFEST.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def release_notes(manifest_path: Path) -> Path:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    lines = [
        f"# Delaware 全州三县四源全量原始数据（{TAG}）",
        "",
        f"**范围**：州 `{STATE}`/FIPS `{STATE_FIPS}`｜三县 "
        f"`Kent 10001` / `New Castle 10003` / `Sussex 10005`｜"
        f"BBox `[{', '.join(str(v) for v in m['scope']['bbox'])}]`",
        "",
        "**口径**：源里给什么就是什么 —— **不做清洗、不去重、不合并、不裁剪字段**。"
        "全部下载在 GitHub Actions runner 上发生（本地服务器零下载）。",
        "",
        f"生成时间：{m['generated_at']}　run：`{m['runner']}`",
        "",
        "## 资产清单",
        "",
        "| 资产 | 大小 | 行数/说明 |",
        "|---|---|---|",
    ]
    for a in m["assets"]:
        extra = f"{a['rows']:,} 行" if a.get("rows") else ""
        lines.append(f"| `{a['path']}` | {a['bytes']:,} B | {extra} |")
    lines += ["", "## 各源抓取结果", "", "```json",
              json.dumps(m["sources"], ensure_ascii=False, indent=1)[:6000], "```", ""]
    p = OUT / "RELEASE_NOTES.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def create_release(files: list[Path], notes: Path) -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        log("缺少 GITHUB_TOKEN / GITHUB_REPOSITORY → 跳过上传（本地模式）")
        return
    env = {**os.environ, "GH_TOKEN": token}
    cmd = ["gh", "release", "create", TAG, "--repo", repo,
           "--title", f"Delaware 全州三县四源全量原始数据 {TAG}",
           "--notes-file", str(notes), "--latest"] + [str(p) for p in files]
    log(f"gh release create {TAG}（{len(files)} 个资产）")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=7200)
    log(f"gh rc={proc.returncode} out={(proc.stdout or '')[-400:]} err={(proc.stderr or '')[-600:]}")
    if proc.returncode != 0:
        raise RuntimeError("Release 创建失败")


def main(argv: list[str] | None = None) -> int:
    global TAG
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-release", action="store_true", help="只抓取不上传（本地自检）")
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG") or TAG_DEFAULT)
    args = parser.parse_args(argv)
    TAG = args.tag

    OUT.mkdir(parents=True, exist_ok=True)
    log(f"目标：Delaware 全州三县｜BBox {BBOX_STR}｜tag={TAG}")
    files: list[Path] = []
    for fn in (harvest_nad, harvest_overture, harvest_openaddresses, harvest_tiger):
        try:
            files += fn()
        except Exception as exc:  # noqa: BLE001 单源失败不拖垮整轮，但如实记账
            note(fn.__name__.replace("harvest_", ""), "exception",
                 error=f"{type(exc).__name__}: {str(exc)[:300]}")

    manifest = build_manifest(files)
    files.append(manifest)
    notes = release_notes(manifest)
    files.append(notes)
    total = sum(p.stat().st_size for p in files)
    log(f"产物 {len(files)} 个，合计 {total/1e6:.1f} MB")
    if not args.no_release:
        create_release(files, notes)
    log("完成：" + json.dumps({i["source"]: i["status"] for i in RESULTS}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
