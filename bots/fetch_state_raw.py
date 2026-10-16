#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用单州四源【全量原始】数据下载入口（World-US-Map-Data）

把前两代脚本（`dover_fetch.py` 取样版 / `delaware_full_dump.py` 单州全量版）收敛成
一个「按州调度」的通用入口：州特有知识全部搬进 `rules/US/state_roster.yaml`，
本文件里不再出现任何州特有常量。

四源与适配规则（延续项目铁律：源里给什么就落什么，不清洗 / 不去重 / 不裁剪字段）：

  A. USDOT NAD       官方 GeoServices REST（动态全字段）
                     ★ 翻页改用「游标分页」：orderByFields=OBJECTID ASC + where=OBJECTID > last_id
                       旧版纯 resultOffset 深分页会在 offset=8000 被 Esri 熔断返回 400
  B. Overture Maps   官方 CLI 云端按 bbox 切（parquet 优先，失败自动回落 geojson）
  C. OpenAddresses   首页正则**动态枚举**该州全部源（run id 是 7 位流水号，不能写死）
  D. Census TIGER    TIGERweb REST 导边界 + TIGER/Line 号段小包
                     ★ 县界查询用 3 位 COUNTY 码（图层字段 COUNTY 长度=3，旧版错填 5 位导致空壳）

铁律：
  1) 所有下载都发生在 GitHub Actions runner 上（本机零下载）
  2) 产物不进 git，只作为 Release 资产
  3) 缺源不猜：单源失败如实记账
  4) **发布门禁**：任何源缺失 / 空壳产物（<1KB）/ 边界 features=0 → 直接阻断发布，绝不把空壳当资产上传

用法：
  python bots/fetch_state_raw.py --state DE --publish-release
  python bots/fetch_state_raw.py --state RI --no-release
  python bots/fetch_state_raw.py --state DE --only nad,tiger --tag raw-US-DE-v1-repair
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "bots") not in sys.path:
    sys.path.insert(0, str(ROOT / "bots"))

# 复用四源端点与 http 基建 —— 单一事实来源，换代只需改 dover_fetch.py
import dover_fetch as df  # noqa: E402

ROSTER_PATH = ROOT / "rules" / "US" / "state_roster.yaml"
MIN_ASSET_BYTES = 1024                      # 数据载荷（geojson/ndjson/zip）的空壳体量阈值
PAYLOAD_SUFFIXES = (".geojson", ".ndjson", ".zip", ".csv", ".parquet")
REQUIRED_SOURCES = ("nad", "overture", "openaddresses", "census_tiger")
STAMP = time.strftime("%Y%m%d-%H%M", time.gmtime())


def log(msg: str) -> None:
    print(f"[fetch_state_raw] {msg}", flush=True)


def die(msg: str, code: int = 2):
    log("FATAL " + msg)
    raise SystemExit(code)


def rel(p) -> str:
    """相对仓库根的可读路径；--out-dir 指到仓外（本地自检）时原样返回绝对路径。"""
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def _esri_query(url: str, params: dict, tries: int = 4, label: str = "", timeout: int = 120) -> dict:
    """Esri / 联邦视图查询：**必须重试**，不能一次 400 就判死刑。

    2026-10-16 探针实证（DOT NAD 联邦视图，同一图层同一 bbox）：
      · `resultRecordCount=2`                          → ✅
      · `resultOffset=0` 单独带上（无 orderBy）           → ❌ 400 Cannot perform query
      · `orderByFields=OBJECTID ASC` + rc=2            → ✅
      · `resultRecordCount=2000`（=maxRecordCount）     → ❌ 400
      · rc=1000 + resultOffset=0（旧代码姿势）            → ✅ 返回 1000 条
    同一组参数时好时坏 → 这就是为什么旧版在 offset=8000 上“偶然”撞上 400、
    而换一组参数又在第 1 页撞上 —— 不是深度分页熔断，是服务端抖动。
    对策：重试（指数退避）+ 失败时缩页，最后仍失败才算真失败。
    """
    delay = 2.0
    last = ""
    for i in range(1, tries + 1):
        try:
            payload = df.http_json(url, params, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            payload = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        err = payload.get("error")
        if not err:
            return payload
        last = str(err)[:200]
        if i < tries:
            log(f"⚠️ {label} 第 {i}/{tries} 次被拒：{last[:110]} → {delay:.0f}s 后重试")
            time.sleep(delay)
            delay = min(delay * 2, 30)
    return {"error": last}


# --------------------------------------------------------------------------- 配置档
def load_roster(path: Path | None = None) -> dict:
    path = path or ROSTER_PATH
    if not path.exists():
        die(f"州配置档不存在：{path}")
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        die("缺少 PyYAML（requirements.txt 里应有 pyyaml）")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not (data.get("states") or {}):
        die(f"配置档里没有 states：{path}")
    return data


def state_cfg(roster: dict, code: str) -> dict:
    """取某州配置，并把 fips/bbox 归一化成代码里好用的形态。"""
    code = str(code).strip().upper()
    states = roster["states"]
    if code not in states:
        die(f"配置档里没有州 {code}。现有：" + ", ".join(sorted(states)))
    cfg = dict(states[code])
    cfg["state"] = code
    cfg["state_fips"] = str(cfg["state_fips"]).zfill(2)
    bbox = [float(v) for v in cfg["bbox"]]
    if len(bbox) != 4:
        die(f"{code}.bbox 必须是 [W,S,E,N] 四个数")
    cfg["bbox"] = bbox
    cfg["bbox_str"] = ",".join(str(v) for v in bbox)
    counties = []
    for c in cfg.get("counties") or []:
        fips = str(c["fips"]).zfill(5)
        counties.append({"key": str(c["key"]), "name": c.get("name") or str(c["key"]),
                         "fips": fips, "fips3": fips[2:]})
    if not counties:
        die(f"{code} 没有 counties，TIGER 号段包无法枚举")
    cfg["counties"] = counties
    lo_hi = [str(v) for v in (cfg.get("zcta_range") or [])]
    cfg["zcta_lo"] = lo_hi[0] if len(lo_hi) > 0 else ""
    cfg["zcta_hi"] = lo_hi[1] if len(lo_hi) > 1 else ""
    cfg["places"] = [str(p) for p in (cfg.get("places") or [])]
    cfg["oa_priority"] = [str(p) for p in (cfg.get("oa_priority") or [])]
    return cfg


# --------------------------------------------------------------------------- 调度器
class Fetcher:
    """一次州级抓取的上下文：产物目录、记账、问题清单。"""

    def __init__(self, cfg: dict, out: Path, args: argparse.Namespace):
        self.cfg = cfg
        self.out = out
        self.args = args
        self.ledger: list[dict] = []        # 全量记账（含中间事件）
        self.status: dict[str, dict] = {}   # 每源最终状态
        self.problems: list[str] = []       # 门禁问题（缺源/空壳/边界空）
        self.files: list[Path] = []
        self.cache: dict = {}               # 跨源共享（县界多边形：NAD 切块与 TIGER 导出共用）

    # -- 记账 ----------------------------------------------------------------
    def note(self, source: str, status: str, **kw) -> dict:
        rec = {"source": source, "status": status, **kw}
        self.ledger.append(rec)
        self.status[source] = rec
        return rec

    def problem(self, msg: str) -> None:
        self.problems.append(msg)
        log("⛔ " + msg)

    def add(self, *paths) -> None:
        for p in paths:
            p = Path(p)
            if p.exists():
                self.files.append(p)

    # -- 目录 ----------------------------------------------------------------
    def dir(self, name: str) -> Path:
        d = self.out / name
        d.mkdir(parents=True, exist_ok=True)
        return d


# --------------------------------------------------------------------------- A. NAD
def _nad_bbox_pull(fx: Fetcher, bbox_str: str, fields: list[str], oid: str,
                   limit: int, page: int, fh, seen: set, tag: str = "") -> tuple[int, int]:
    """★ 游标分页：orderByFields + `WHERE OBJECTID > last_id`，彻底绕开深分页熔断。

    旧实现用 resultOffset 翻页，跑到 offset=8000 就被 Esri 以
    `400 Cannot perform query / Invalid query parameters` 拒掉（全州实测）。
    探针复测后确认那其实是**服务端抖动**（同一组参数时好时坏），所以除了游标，
    这里还叠了 _esri_query 的指数退避重试 + 连续被拒时缩页。

    内存纪律：**流式直接写 ndjson**，只在内存里留一个 OID 集合做去重
    （40 万行 ≈ 30MB，而不是把 40 万个 39 字段字典全揣在内存里）。
    返回 (新增行数, 页数)。
    """
    added = 0
    cursor = None
    pages = 0
    while added < limit:
        batch = min(page, limit - added)
        params = {
            "where": "1=1" if cursor is None else f"{oid} > {cursor}",
            "outFields": ",".join(fields),
            "geometry": bbox_str,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outSR": "4326",
            "orderByFields": f"{oid} ASC",   # 游标分页的前提：服务端稳定排序
            "resultRecordCount": batch,       # 不再传 resultOffset
            "f": "json",
        }
        payload = _esri_query(f"{df.NAD_OFFICIAL}/query", params, tries=4,
                              label=f"NAD{tag} page {pages + 1}（cursor={cursor} rc={batch}）",
                              timeout=fx.args.nad_timeout)
        if payload.get("error"):
            # 连续重试仍被拒 → 单页缩半再试（1000 → 500 → 250 → 125 → 100）
            if batch > 100:
                page = max(100, batch // 2)
                log(f"⚠️ NAD{tag} 连续被拒 → 单页缩到 {page} 再试")
                continue
            raise RuntimeError(f"query error {str(payload['error'])[:200]} | cursor={cursor} page={pages + 1} rc={batch}")
        feats = payload.get("features") or []
        pages += 1
        if not feats:
            break
        last = cursor
        newly = 0
        for feat in feats:
            attrs = dict(feat.get("attributes") or {})
            oid_val = attrs.get(oid)
            # ★ 游标必须跟每一条的 OID 前进（包括重复行），否则整页都是重复行时
            #   last 永远不推进 → cursor 原地不动 → 无限重拉同一页（自检里真实卡死过一次）
            dup = oid_val is not None and oid_val in seen
            if oid_val is not None:
                if last is None or oid_val > last:
                    last = oid_val
                if not dup:
                    seen.add(oid_val)
            if dup:
                continue
            geom = feat.get("geometry") or {}
            attrs["_lon"], attrs["_lat"] = geom.get("x"), geom.get("y")
            fh.write(json.dumps(attrs, ensure_ascii=False) + "\n")
            added += 1
            newly += 1
        # 三条退出阀：本页不满 / 本页全重复（无净增）/ 游标未前进
        if len(feats) < batch or newly == 0:
            break
        if cursor is not None and last == cursor:
            log(f"⚠️ NAD{tag} 游标未前进（{oid}={cursor}）→ 退出防死循环")
            break
        if last is None:
            log(f"⚠️ NAD{tag} 本页没有任何 {oid}，无法推进游标 → 退出防死循环")
            break
        cursor = last
    return added, pages


def _nad_official_count(fx: Fetcher, bbox_str: str):
    payload = _esri_query(f"{df.NAD_OFFICIAL}/query", {
        "where": "1=1", "geometry": bbox_str, "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true", "f": "json"}, tries=3, label="NAD 官方计数",
        timeout=fx.args.nad_timeout)
    return payload.get("count")


def _geojson_bbox(payload: dict):
    """从 Polygon / MultiPolygon 的 rings 里算包围盒（只取坐标，不碰属性）。"""
    xs, ys = [], []
    for feat in payload.get("features") or []:
        geom = feat.get("geometry") or {}
        rings = geom.get("rings") or []
        if not rings and geom.get("type") == "MultiPolygon":
            rings = [r for poly in (geom.get("coordinates") or []) for r in poly]
        for ring in rings:
            for pt in ring:
                try:
                    xs.append(float(pt[0]))
                    ys.append(float(pt[1]))
                except (TypeError, ValueError, IndexError):
                    continue
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _nad_shards(fx: Fetcher) -> list[dict]:
    """★ 按县切块：每个县一个独立 bbox，多个县并发翻页。

    为什么快：
      1) 并发 —— 3 个县 = 3 条流水线同时翻，整州顺次翻是 400+ 次串行往返；
      2) 小框 —— 单个县的 envelope 比整州小一个量级，服务端单次响应明显更快。
    为什么不会漏：
      每个县的多边形都被自己的 bbox 包住 → 县 bbox 的并集 ⊇ 整州；框重叠只会产生
      重复行，重复行在合并阶段按 OID 去掉 —— 是「超集 + 去重」，不是「近似」。
    """
    mode = fx.args.nad_shards
    if mode == "none":
        return [{"key": "whole", "bbox": tuple(fx.cfg["bbox"])}]
    if mode == "grid":
        n = max(2, int(fx.args.nad_grid))
        W, S, E, N = fx.cfg["bbox"]
        xs = [W + (E - W) * i / n for i in range(n + 1)]
        ys = [S + (N - S) * j / n for j in range(n + 1)]
        return [{"key": f"grid_{i}{j}", "bbox": (xs[i], ys[j], xs[i + 1], ys[j + 1])}
                for i in range(n) for j in range(n)]
    # county（默认）
    bnd = _county_boundaries(fx)          # 县界同时给 TIGER 用 → 只查一次
    shards = []
    for c in fx.cfg["counties"]:
        rec = bnd.get(f"county_{c['key']}")
        if not rec:
            continue
        bb = _geojson_bbox(rec["payload"])
        if bb:
            shards.append({"key": f"cty_{c['key']}", "bbox": bb})
    if len(shards) < 2:
        log(f"⚠️ 可用县界只有 {len(shards)} 个 → 退回「州 bbox 切 2×2 网格」并发")
        fx.args.nad_shards = "grid"
        fx.args.nad_grid = 2
        return _nad_shards(fx)
    return shards


def _nad_shard_worker(fx: Fetcher, shard: dict, fields: list[str], oid: str,
                      page: int, limit: int) -> dict:
    """单个分片的独立翻页：写自己的 part 文件，线程之间零共享。"""
    bbox_str = ",".join(str(v) for v in shard["bbox"])
    part = fx.dir("nad") / f"nad_part_{shard['key']}.ndjson"
    seen: set = set()
    t0 = time.time()
    with part.open("w", encoding="utf-8") as fh:
        added, pages = _nad_bbox_pull(fh=fh, seen=seen, fx=fx, bbox_str=bbox_str, fields=fields,
                                      oid=oid, limit=limit, page=page,
                                      tag=f"[{shard['key']}]")
    return {"shard": shard["key"], "bbox": bbox_str, "rows": added, "pages": pages,
            "bytes": part.stat().st_size, "elapsed": round(time.time() - t0, 1), "part": part}


def harvest_nad(fx: Fetcher) -> None:
    t0 = time.time()
    d = fx.dir("nad")
    df.nad_guard()                                  # 黑名单守卫：绝不回退第三方阉割镜像

    meta, fields = df.nad_official_metadata()
    (d / "nad_native_metadata.json").write_text(
        json.dumps({k: meta[k] for k in ("name", "type", "maxRecordCount", "objectIdField",
                                         "description", "copyrightText", "fields") if k in meta},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    oid = str(meta.get("objectIdField") or "OBJECTID")
    if oid not in fields:
        fields = [oid] + fields
    maxrc = int(meta.get("maxRecordCount") or 2000)
    # ★ 单页硬上限 1000：实测 rc=2000（=maxRecordCount）会被 400 拒，rc=1000 稳定返回满页
    page = int(fx.args.nad_page) if fx.args.nad_page else min(maxrc, 1000)
    page = max(1, min(page, maxrc, 1000))

    shards = _nad_shards(fx)
    workers = max(1, min(int(fx.args.nad_workers), len(shards)))
    official = _nad_official_count(fx, fx.cfg["bbox_str"])
    log(f"NAD 切块={fx.args.nad_shards}｜分片={len(shards)}｜并发={workers}｜单页={page}｜"
        f"官方 count(整州)={official}｜分片：{[s['key'] for s in shards]}")

    # ---- 分片并发抓取（单分片失败不拖垮整轮，留待整州自愈兜底）----
    parts, shard_detail = [], []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_nad_shard_worker, fx, s, fields, oid, page, fx.args.nad_max): s
                for s in shards}
        for fut in as_completed(futs):
            s = futs[fut]
            try:
                info = fut.result()
                parts.append(info.pop("part"))
                shard_detail.append(info)
            except Exception as exc:  # noqa: BLE001
                shard_detail.append({"shard": s["key"], "bbox": list(s["bbox"]),
                                     "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                log(f"⚠️ NAD 分片 {s['key']} 失败：{str(exc)[:160]}（交由整州自愈兜底）")

    # ---- 合并去重（县 bbox 互相重叠 → 必须按 OID 去重）----
    ndjson = d / f"nad_us_{fx.cfg['state'].lower()}_full.ndjson"
    seen: set = set()
    with ndjson.open("w", encoding="utf-8") as out:
        for part in parts:
            with part.open(encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    o = json.loads(line).get(oid)
                    if o is not None:
                        if o in seen:
                            continue
                        seen.add(o)
                    out.write(line if line.endswith("\n") else line + "\n")
        added = len(seen)
        dup_dropped = sum(x.get("rows", 0) for x in shard_detail) - added

        # ---- 整州自愈：合并后仍少于官方 count 的 99% → 4 分块重拉补缺口 ----
        repair = None
        if official and added < int(official) * 0.99:
            W, S, E, N = fx.cfg["bbox"]
            midx, midy = (W + E) / 2, (S + N) / 2
            tiles = [(W, S, midx, midy), (midx, S, E, midy), (W, midy, midx, N), (midx, midy, E, N)]
            extra_rows = extra_pages = 0
            for tl in tiles:
                n, p = _nad_bbox_pull(fh=out, seen=seen, fx=fx,
                                      bbox_str=",".join(str(v) for v in tl), fields=fields,
                                      oid=oid, limit=fx.args.nad_max, page=page, tag="[repair]")
                extra_rows += n
                extra_pages += p
            added += extra_rows
            repair = {"tiles": 4, "pages": extra_pages, "rows_added": extra_rows, "after": added}
    for p in parts:
        p.unlink(missing_ok=True)

    (d / "nad_full_columns.json").write_text(
        json.dumps({"fields": fields, "fields_n": len(fields), "object_id_field": oid},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    truncated = bool(official) and added < int(official)
    fx.add(d / "nad_native_metadata.json", ndjson, d / "nad_full_columns.json")
    fx.note("nad", "warn-truncated" if truncated else "ok",
            channel="A-official-rest", endpoint=df.NAD_OFFICIAL,
            pagination=f"cursor: orderByFields={oid} ASC + where {oid} > last_id",
            shard_mode=fx.args.nad_shards, shard_count=len(shards), workers=workers,
            shard_detail=shard_detail, cross_shard_dup_dropped=max(0, dup_dropped),
            page_size=page, repair=repair, streamed_to=rel(ndjson),
            fields_n=len(fields), rows_fetched=added, official_count_in_bbox=official,
            truncated=truncated, bytes=ndjson.stat().st_size, elapsed=round(time.time() - t0, 1))
    if truncated:
        fx.problem(f"NAD 拉取 {added} 行 < 官方 count {official}（已尝试分片 + 4 分块自愈）")
    if added == 0:
        fx.problem("NAD 一行都没拉到")

# --------------------------------------------------------------------------- B. Overture
def _count_parquet(path: Path) -> int | None:
    try:
        import duckdb  # noqa: PLC0415
    except ImportError:
        return None
    try:
        con = duckdb.connect()
        return int(con.execute("select count(*) from read_parquet(?)", [str(path)]).fetchone()[0])
    except Exception:  # noqa: BLE001
        return None


def harvest_overture(fx: Fetcher) -> None:
    t0 = time.time()
    cli = shutil.which("overturemaps")
    if not cli:
        raise RuntimeError("overturemaps CLI 未安装（requirements.txt 里应有 overturemaps）")
    d = fx.dir("overture")
    state_lc = fx.cfg["state"].lower()
    bbox = fx.cfg["bbox_str"]

    # 优先 parquet（流式、不做 json.loads 全量进内存），失败自动回落 geojson
    prefs = ["parquet", "geojson"] if fx.args.overture_format == "parquet" else ["geojson"]
    target, used, tail, tries = None, None, "", []
    for fmt in prefs:
        cand = d / f"overture_us_{state_lc}_addresses.{fmt}"
        cmd = [cli, "download", f"--bbox={bbox}", "-f", fmt, "--type=address", "-o", str(cand)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=fx.args.overture_timeout)
        tail = ((proc.stdout or "")[-300:] + (proc.stderr or "")[-400:]).strip()
        ok = proc.returncode == 0 and cand.exists() and cand.stat().st_size >= MIN_ASSET_BYTES
        tries.append({"format": fmt, "rc": proc.returncode, "ok": bool(ok),
                      "bytes": cand.stat().st_size if cand.exists() else 0, "tail": tail[-200:]})
        if ok:
            target, used = cand, fmt
            break
        if cand.exists():
            cand.unlink()          # 不留下半成品/空壳
    if not target:
        raise RuntimeError(f"overturemaps 两种格式都失败：{json.dumps(tries, ensure_ascii=False)[:400]}")

    feats = None
    if used == "geojson":
        try:
            feats = len((json.loads(target.read_text(encoding="utf-8")).get("features") or []))
        except Exception:  # noqa: BLE001
            feats = None
    else:
        feats = _count_parquet(target)

    fx.add(target)
    fx.note("overture", "ok", bbox=bbox, format=used, features=feats,
            bytes=target.stat().st_size, tries=tries, elapsed=round(time.time() - t0, 1))
    if feats == 0:
        fx.problem("Overture 产物 features=0")


# --------------------------------------------------------------------------- C. OpenAddresses
def _count_zip_rows(blob: bytes) -> int:
    n = 0
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for info in zf.infolist():
                if not info.filename.lower().endswith((".csv", ".ndjson")):
                    continue
                with zf.open(info) as fh:
                    n += sum(1 for _ in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        pass
    return n


def discover_oa_sources(state_lc: str) -> dict[str, tuple[str, str, str]]:
    """★ 动态枚举：首页正则抽全部 us/<州>/ 源 zip，取最新 run。

    OA 的 run id 是 7 位流水号，源名是**数据提供者名**（kent / city_of_dover / sussex…）
    而不是州名 —— 所以每个州的源清单都不一样，只能动态发现，绝不写死。
    """
    home = df.http_get(df.OA_HOME, timeout=120).decode("utf-8", "replace")
    found = re.findall(r"https://data\.openaddresses\.io/runs/(\d+)/us/([a-z]{2})/([a-z0-9_]+)\.zip", home)
    latest: dict[str, tuple[str, str, str]] = {}
    for run, st, name in found:
        if st == state_lc:
            latest.setdefault(name, (run, st, name))   # 首页只列最新 run → 取首次出现
    return latest


def harvest_openaddresses(fx: Fetcher) -> None:
    t0 = time.time()
    d = fx.dir("openaddresses")
    state_lc = fx.cfg["state"].lower()
    latest = discover_oa_sources(state_lc)
    if not latest:
        raise RuntimeError(f"results.openaddresses.io 首页未发现 us/{state_lc} 的任何源 zip")

    priority = [n for n in fx.cfg["oa_priority"] if n in latest]
    order = priority + [n for n in sorted(latest) if n not in priority]
    files, detail, fail = [], [], []
    for name in order[:fx.args.oa_max_files]:
        run, st, src = latest[name]
        url = df.OA_RUN.format(run=run, st=st, src=src)
        try:
            blob = df.http_get(url, timeout=fx.args.oa_timeout)
            if len(blob) > fx.args.oa_max_mb * 1024 * 1024:
                detail.append({"src": name, "run": run, "skipped": f"{len(blob) / 1e6:.1f}MB 超过 {fx.args.oa_max_mb}MB 上限"})
                continue
            path = d / f"openaddresses_us_{state_lc}_{name}.zip"
            path.write_bytes(blob)
            detail.append({"src": name, "run": run, "url": url, "bytes": len(blob),
                           "native_rows": _count_zip_rows(blob),
                           "file": rel(path)})
            files.append(path)
        except Exception as exc:  # noqa: BLE001
            fail.append({"src": name, "run": run, "url": url, "error": str(exc)[:200]})
    fx.add(*files)
    status = "ok" if files else "error"
    fx.note("openaddresses", status, state=state_lc, sources_total=len(latest),
            downloaded=len(files), detail=detail, failures=fail,
            elapsed=round(time.time() - t0, 1))
    if not files:
        fx.problem("OpenAddresses 一个源包都没下到")


# --------------------------------------------------------------------------- D. Census TIGER
def _geojson_local_field(key: str) -> str:
    """本地兜底过滤时用哪个字段判值。"""
    if key == "zcta":
        return "ZCTA5"
    if key.startswith("county_"):
        return "COUNTY"
    if key.startswith("place_"):
        return "BASENAME"
    return "STATE"


def _tiger_boundary_queries(cfg: dict) -> list[tuple[str, str, list[tuple[str, str, str | None]]]]:
    """州界 / ZCTA / 市界的候选查询链。

    返回 (key, layer, [(where, outFields, local_filter_value), ...])，多组候选依次重试。
    县界不在这里 —— 它单独走 `_county_boundaries()`，因为 NAD 的按县切块也要用同一份
    县界多边形，两边共用缓存，只查一次。

    ★ 县界用 3 位 COUNTY 码（图层元数据实证：字段 COUNTY 长度=3）：
        STATE='10' AND COUNTY='001'   ✅
        STATE='10' AND COUNTY='10001' ❌ → 服务端静默返回 features=[] 空壳
    ★ ZCTA 图层**没有 STATE 字段**（实证：带 STATE → 400 Failed to execute query），
       只能 "ZCTA5,GEOID"。
    """
    t = cfg["_endpoints"]
    s2 = cfg["state_fips"]
    q = []

    # 州界
    q.append(("state",
              f"{t['tigerweb']}/State_County/MapServer/0",
              [(f"STATE='{s2}'", "GEOID,STATE,STUSAB,BASENAME,NAME", None),
               (f"STUSAB='{cfg['state']}'", "GEOID,STATE,STUSAB,BASENAME,NAME", None),
               ("1=1", "GEOID,STATE,STUSAB,BASENAME,NAME", s2)]))

    # ZCTA5 邮编区（本州邮编段）
    if cfg["zcta_lo"] and cfg["zcta_hi"]:
        q.append(("zcta",
                  f"{t['tigerweb']}/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1",
                  [(f"ZCTA5>='{cfg['zcta_lo']}' AND ZCTA5<='{cfg['zcta_hi']}'", "ZCTA5,GEOID", None),
                   ("1=1", "ZCTA5,GEOID", f"{cfg['zcta_lo']}:{cfg['zcta_hi']}")]))

    # 市界（可选）
    pfields = "GEOID,NAME,BASENAME,STATE,PLACE,CENTLAT,CENTLON"
    for p in cfg["places"]:
        key = "place_" + re.sub(r"[^a-z0-9]+", "_", p.lower()).strip("_")
        q.append((key,
                  f"{t['tigerweb']}/Places_CouSub_ConCity_SubMCD/MapServer/4",
                  [(f"STATE='{s2}' AND BASENAME='{p}'", pfields, None),
                   (f"STATE='{s2}'", pfields, p)]))
    return q


def _local_filter(feats: list, field: str, value: str) -> list:
    """本地兜底过滤：整州取回来后在内存里筛（ZCTA 用 "lo:hi" 段，其余精确匹配）。"""
    if field == "ZCTA5" and ":" in value:
        lo, hi = value.split(":", 1)
        return [f for f in feats if lo <= str(((f.get("attributes") or {}).get(field)) or "") <= hi]
    return [f for f in feats if str(((f.get("attributes") or {}).get(field)) or "") == value]


def _tiger_boundary_one(fx: Fetcher, key: str, layer: str,
                        attempts: list[tuple[str, str, str | None]]) -> tuple[dict | None, dict]:
    """查一条边界：多组候选（含"整州取回本地筛"兜底）+ 重试。

    返回 (payload | None, detail)。失败时 detail 里带完整候选重试链，便于事后归因。
    """
    tried = []
    for where, fields, local in attempts:
        try:
            payload = _esri_query(f"{layer}/query", {
                "where": where, "outFields": fields, "returnGeometry": "true",
                "outSR": "4326", "f": "json"}, tries=3, label=f"TIGER {key}",
                timeout=fx.args.tiger_timeout)
        except Exception as exc:  # noqa: BLE001
            tried.append({"where": where, "error": str(exc)[:150]})
            continue
        if payload.get("error"):
            tried.append({"where": where, "esri_error": str(payload["error"])[:160]})
            continue
        feats = payload.get("features") or []
        if local is not None:
            feats = _local_filter(feats, _geojson_local_field(key), local)
            payload = {**payload, "features": feats}
        if not feats:
            tried.append({"where": where, "features": 0})
            continue
        return payload, {"key": key, "layer": layer, "where": where, "features": len(feats)}
    return None, {"key": key, "layer": layer, "status": "all_attempts_failed", "tried": tried}


def _county_boundaries(fx: Fetcher) -> dict:
    """取本州全部县界多边形：落盘 + 缓存，供 NAD 按县切块与 TIGER 边界导出**共用**。

    返回 {county_<key>: {"payload":…, "detail":…, "path": Path}}。
    """
    cached = fx.cache.get("county_boundaries")
    if cached is not None:
        return cached
    d = fx.dir("tiger")
    s2 = fx.cfg["state_fips"]
    layer = f"{fx.cfg['_endpoints']['tigerweb']}/State_County/MapServer/1"
    fields_c = "GEOID,BASENAME,STATE,COUNTY,NAME"
    out: dict = {}
    for c in fx.cfg["counties"]:
        key = f"county_{c['key']}"
        attempts = [(f"STATE='{s2}' AND COUNTY='{c['fips3']}'", fields_c, None),
                    (f"STATE='{s2}' AND COUNTY='{c['fips']}'", fields_c, None),
                    (f"STATEFP='{s2}' AND COUNTYFP='{c['fips3']}'", fields_c, None),
                    (f"STATE='{s2}'", fields_c, c["fips3"])]
        payload, detail = _tiger_boundary_one(fx, key, layer, attempts)
        if not payload:
            detail["reason"] = "县界候选链全部失败/空壳"
            fx.cache.setdefault("county_misses", []).append(detail)
            continue
        path = d / f"tiger_{key}.geojson"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        size = path.stat().st_size
        if size < MIN_ASSET_BYTES:            # ★ 空壳绝不当资产上传，也不参与切块
            path.unlink()
            fx.cache.setdefault("county_misses", []).append(
                {**detail, "reason": f"产物仅 {size}B < {MIN_ASSET_BYTES}B，按空壳丢弃"})
            continue
        out[key] = {"payload": payload, "detail": detail, "path": path}
    fx.cache["county_boundaries"] = out
    return out


def harvest_tiger(fx: Fetcher) -> None:
    t0 = time.time()
    d = fx.dir("tiger")
    files, detail, misses = [], [], []
    base = fx.cfg["_endpoints"]["tiger_base"]

    # 1) 县界（NAD 按县切块可能已经先取过 → 直接复用缓存，不重复请求）
    cached = _county_boundaries(fx)
    for key, rec in cached.items():
        files.append(rec["path"])
        detail.append(rec["detail"])
    misses.extend(fx.cache.get("county_misses") or [])
    for c in fx.cfg["counties"]:
        if f"county_{c['key']}" not in cached:
            misses.append({"key": f"county_{c['key']}", "reason": "县界未取到（候选链全挂 / 空壳）"})

    # 2) 州界 / ZCTA / 市界
    for key, layer, attempts in _tiger_boundary_queries(fx.cfg):
        payload, dd = _tiger_boundary_one(fx, key, layer, attempts)
        if not payload:
            misses.append(dd)
            continue
        path = d / f"tiger_{key}.geojson"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        size = path.stat().st_size
        if size < MIN_ASSET_BYTES:
            path.unlink()
            misses.append({**dd, "reason": f"产物仅 {size}B < {MIN_ASSET_BYTES}B，按空壳丢弃"})
            continue
        files.append(path)
        detail.append({**dd, "file": rel(path)})

    # 3) 号段小包：每县一个（包名用 5 位县 FIPS）
    for c in fx.cfg["counties"]:
        name = f"tl_2024_{c['fips']}_addrfeat.zip"
        url = f"{base}/ADDRFEAT/{name}"
        try:
            blob = df.http_get(url, timeout=fx.args.tiger_timeout)
            path = d / name
            path.write_bytes(blob)
            files.append(path)
            detail.append({"file": name, "county": c["key"], "bytes": len(blob), "url": url})
        except Exception as exc:  # noqa: BLE001
            misses.append({"file": name, "url": url, "error": str(exc)[:200]})

    # 州级 PLACE 小包
    pname = f"tl_2024_{fx.cfg['state_fips']}_place.zip"
    purl = f"{base}/PLACE/{pname}"
    try:
        blob = df.http_get(purl, timeout=fx.args.tiger_timeout)
        path = d / pname
        path.write_bytes(blob)
        files.append(path)
        detail.append({"file": pname, "bytes": len(blob), "url": purl})
    except Exception as exc:  # noqa: BLE001
        misses.append({"file": pname, "url": purl, "error": str(exc)[:200]})

    # ADDRFEAT 行数/列名（只读元信息，不改数据）
    for c in fx.cfg["counties"]:
        addrfeat = d / f"tl_2024_{c['fips']}_addrfeat.zip"
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

    fx.add(*files)
    fx.note("census_tiger", "ok" if files and not misses else "error",
            detail=detail, missed=misses, counties=len(fx.cfg["counties"]),
            elapsed=round(time.time() - t0, 1))
    for m in misses:
        fx.problem(f"TIGER 缺失/空壳：{m.get('key') or m.get('file')} → "
                   f"{json.dumps(m.get('tried') or m.get('error') or m.get('reason'), ensure_ascii=False)[:200]}")


# --------------------------------------------------------------------------- 门禁 / 打包
def _asset_sanity(p: Path) -> str | None:
    """产物空壳检测：**走结构，不靠体积**。返回问题描述，None = 正常。

    为什么不能一刀切拿 1KB 卡体积：实测 `nad_full_columns.json` 只有 908 字节，
    是**完全合法**的元信息（只是一串列名）；而真正的空壳是 680 字节、`features: []`
    的县界 geojson —— 体积一样小，必须靠结构区分。
    规则：数据载荷（geojson/ndjson/zip/csv）既要过 1KB 线，又要过结构校验；
         元信息 json / md 只要求非 0 字节。
    """
    size = p.stat().st_size
    if size == 0:
        return "0 字节空文件"
    if p.suffix.lower() in PAYLOAD_SUFFIXES and size < MIN_ASSET_BYTES:
        return f"过小产物（{size}B < {MIN_ASSET_BYTES}B）"
    if p.suffix.lower() == ".geojson":
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return f"geojson 无法解析：{str(exc)[:100]}"
        if isinstance(obj, dict) and not obj.get("features"):
            return "geojson features 为空（空壳）"
    if p.suffix.lower() == ".ndjson":
        with p.open(encoding="utf-8") as fh:
            if not any(line.strip() for line in fh):
                return "ndjson 0 行"
    return None


def gate(fx: Fetcher) -> None:
    """★ 发布门禁：缺源 / 空壳 / 边界为 0 → 直接阻断，绝不把废资产推上架。"""
    errs = list(fx.problems)
    for src in REQUIRED_SOURCES:
        st = fx.status.get(src)
        if not st:
            errs.append(f"源 {src} 未执行（--only 漏了？）")
        elif st.get("status") not in ("ok", "warn-truncated"):
            errs.append(f"源 {src} 状态异常：{st.get('status')}")
    for p in fx.files:
        bad = _asset_sanity(p)
        if bad:
            errs.append(f"{bad}：{rel(p)}")
    if errs:
        raise RuntimeError("发布门禁未通过，共 %d 项：\n  - %s" % (len(errs), "\n  - ".join(errs)))


def build_manifest(fx: Fetcher) -> Path:
    def asset(p: Path) -> dict:
        return {"path": rel(p), "bytes": p.stat().st_size,
                "sha256": df.sha256_head(p)}
    cfg = fx.cfg
    m = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runner": os.environ.get("GITHUB_RUN_ID", "local"),
        "generator": "bots/fetch_state_raw.py",
        "roster": str(ROSTER_PATH.relative_to(ROOT)),
        "scope": {"country": "US", "state": cfg["state"], "state_name": cfg.get("name"),
                  "state_fips": cfg["state_fips"], "bbox": cfg["bbox"],
                  "counties": [{"key": c["key"], "fips": c["fips"], "name": c["name"]} for c in cfg["counties"]],
                  "note": "四源全量【原始】数据 —— 未做任何清洗 / 去重 / 过滤 / 裁剪"},
        "assets": [asset(p) for p in sorted(fx.files)],
        "sources": list(fx.status.values()),
        "ledger": fx.ledger,
    }
    p = fx.out / "MANIFEST.json"
    p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def release_notes(manifest_path: Path, fx: Fetcher, tag: str) -> Path:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    sc = m["scope"]
    lines = [
        f"# US {sc['state']}（{sc['state_name']}）四源全量原始数据 · `{tag}`",
        "",
        f"**范围**：州 `{sc['state']}`/FIPS `{sc['state_fips']}`｜"
        f"{len(sc['counties'])} 县（{', '.join(c['name'] for c in sc['counties'])}）｜"
        f"BBox `[{', '.join(str(v) for v in sc['bbox'])}]`",
        "",
        "**口径**：源里给什么就是什么 —— **不做清洗、不去重、不合并、不裁剪字段**。"
        "全部下载在 GitHub Actions runner 上发生（本地服务器零下载）。",
        "",
        f"生成时间：{m['generated_at']}　run：`{m['runner']}`　生成器：`{m['generator']}`",
        "",
        "## 资产清单",
        "",
        "| 资产 | 大小 | 说明 |",
        "|---|---|---|",
    ]
    detail_by_file = {}
    for s in m["sources"]:
        for dd in (s.get("detail") or []):
            if isinstance(dd, dict) and dd.get("file"):
                detail_by_file[dd["file"]] = dd
    for a in m["assets"]:
        dd = detail_by_file.get(a["path"], {})
        extra = ""
        if dd.get("native_rows"):
            extra = f"{dd['native_rows']:,} 行"
        elif dd.get("features"):
            extra = f"{dd['features']:,} feature"
        elif dd.get("bytes"):
            extra = ""
        lines.append(f"| `{Path(a['path']).name}` | {a['bytes']:,} B | {extra} |")
    lines += ["", "## 各源抓取结果（含分页模式 / 候选重试链）", "", "```json",
              json.dumps(m["sources"], ensure_ascii=False, indent=1)[:8000], "```", ""]
    if fx.problems:
        lines += ["", "## ⚠️ 门禁问题（已阻断发布）", ""] + [f"- {p}" for p in fx.problems]
    p = fx.out / "RELEASE_NOTES.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def create_release(files: list[Path], notes: Path, tag: str) -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        log("缺少 GITHUB_TOKEN / GITHUB_REPOSITORY → 跳过上传（本地模式）")
        return
    env = {**os.environ, "GH_TOKEN": token}
    cmd = ["gh", "release", "create", tag, "--repo", repo,
           "--title", tag, "--notes-file", str(notes), "--latest"] + [str(p) for p in files]
    log(f"gh release create {tag}（{len(files)} 个资产）")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=7200)
    log(f"gh rc={proc.returncode} out={(proc.stdout or '')[-400:]} err={(proc.stderr or '')[-600:]}")
    if proc.returncode != 0:
        raise RuntimeError("Release 创建失败")


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="通用单州四源全量原始下载（World-US-Map-Data）")
    ap.add_argument("--state", required=True, help="州简称，如 DE / RI")
    ap.add_argument("--tag", default="", help="Release tag，留空 = raw-US-<州>-v1")
    ap.add_argument("--out-dir", default="", help="产物目录，留空 = data/raw/US-<州>")
    ap.add_argument("--roster", default=str(ROSTER_PATH), help="州配置档路径")
    ap.add_argument("--only", default="", help="只跑指定源，逗号分隔：nad,overture,openaddresses,census_tiger")
    ap.add_argument("--publish-release", action="store_true", help="建 Release 并上架资产")
    ap.add_argument("--no-release", action="store_true", help="只抓取不上架（本地自检）")
    ap.add_argument("--skip-gate", action="store_true", help="跳过发布门禁（仅排障用，禁止在正式跑里用）")
    # 四源参数
    ap.add_argument("--nad-max", type=int, default=800000)
    ap.add_argument("--nad-page", type=int, default=0, help="留空 = 用图层 maxRecordCount（硬上限 1000）")
    ap.add_argument("--nad-timeout", type=int, default=300)
    ap.add_argument("--nad-shards", choices=["county", "grid", "none"], default="county",
                    help="NAD 切块方式：county=按县并发（默认）｜grid=按州 bbox 网格并发｜none=整州单框顺次")
    ap.add_argument("--nad-grid", type=int, default=2, help="--nad-shards grid 时的 N（N×N）")
    ap.add_argument("--nad-workers", type=int, default=4, help="NAD 分片并发数（网络 IO 密集，4~8 都安全）")
    ap.add_argument("--overture-format", choices=["parquet", "geojson"], default="parquet")
    ap.add_argument("--overture-timeout", type=int, default=7200)
    ap.add_argument("--oa-max-mb", type=int, default=800)
    ap.add_argument("--oa-max-files", type=int, default=60)
    ap.add_argument("--oa-timeout", type=int, default=1800)
    ap.add_argument("--tiger-timeout", type=int, default=900)
    args = ap.parse_args(argv)

    roster = load_roster(Path(args.roster))
    cfg = state_cfg(roster, args.state)
    cfg["_endpoints"] = (roster.get("endpoints") or {})
    state = cfg["state"]
    tag = args.tag or f"raw-US-{state}-v1"
    out = Path(args.out_dir) if args.out_dir else (ROOT / "data" / "raw" / f"US-{state}")
    out.mkdir(parents=True, exist_ok=True)

    log(f"目标：US-{state}（{cfg.get('name')}）｜{len(cfg['counties'])} 县｜"
        f"BBox {cfg['bbox_str']}｜tag={tag}｜out={rel(out)}")

    fx = Fetcher(cfg, out, args)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    jobs = [("nad", harvest_nad), ("overture", harvest_overture),
            ("openaddresses", harvest_openaddresses), ("census_tiger", harvest_tiger)]
    for name, fn in jobs:
        if only and name not in only:
            fx.note(name, "skipped", note="未在 --only 里")
            continue
        try:
            fn(fx)
        except Exception as exc:  # noqa: BLE001 单源失败不拖垮整轮，但如实记账
            fx.note(name, "exception", error=f"{type(exc).__name__}: {str(exc)[:400]}")
            fx.problem(f"源 {name} 抛异常：{type(exc).__name__}: {str(exc)[:200]}")

    manifest = build_manifest(fx)
    fx.files.append(manifest)
    notes = release_notes(manifest, fx, tag)
    fx.files.append(notes)
    total = sum(p.stat().st_size for p in fx.files)
    log(f"产物 {len(fx.files)} 个，合计 {total / 1e6:.1f} MB")
    log("各源状态：" + json.dumps({k: v.get("status") for k, v in fx.status.items()}, ensure_ascii=False))

    if not args.skip_gate:
        try:
            gate(fx)
            log("✅ 发布门禁通过")
        except RuntimeError as exc:
            log("❌ " + str(exc))
            return 3
    if args.no_release or not args.publish_release:
        log("（--no-release 或未指定 --publish-release）跳过上架")
        return 0
    create_release(fx.files, notes, tag)
    log("完成：" + json.dumps({k: v.get("status") for k, v in fx.status.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
