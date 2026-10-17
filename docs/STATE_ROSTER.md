# 分州纯下载工厂 · 使用与维护

## 一句话

`bots/fetch_state_raw.py` = 通用单州四源全量原始下载入口；所有州特有知识都在 `rules/US/state_roster.yaml`。

## 加一个新州

只改配置档，不改代码：

```yaml
states:
  XX:
    name: Some State
    state_fips: "99"
    bbox: [W, S, E, N]
    zcta_range: ["12300", "12400"]
    counties:
      - {key: alpha, fips: "99001", name: Alpha}
    oa_priority: []
    places: []
```

`counties` 里的 `fips` 是 **5 位县 FIPS**（TIGER/Line 的 `addrfeat` 包名用它）；代码会自动派生出 3 位 `COUNTY` 码，用于 TIGERweb 边界查询。

## 本地 / 云端跑法

```bash
# 冒烟（只跑 NAD + TIGER，不上架）
python bots/fetch_state_raw.py --state DE --only nad,census_tiger --no-release

# 正式（全四源 + 建 Release）
python bots/fetch_state_raw.py --state DE --publish-release
```

云端走 `.github/workflows/fetch-state-raw.yml` 的 `workflow_dispatch`（入参：`state` / `tag` / `nad_max` / `overture_format` / `publish_release`）。

## 产物命名（Release 资产）

| 源 | 命名 |
|---|---|
| NAD | `nad_us_<州小写>_full.ndjson` + `nad_full_columns.json` + `nad_native_metadata.json` |
| Overture | `overture_us_<州小写>_addresses.parquet`（回落时 `.geojson`） |
| OpenAddresses | `openaddresses_us_<州小写>_<源名>.zip`（原名即数据提供者名） |
| TIGER 边界 | `tiger_<state\|county_*\|zcta\|place_*>.geojson` |
| TIGER 号段 | `tl_2024_<5位县FIPS>_addrfeat.zip` + `tl_2024_<2位州FIPS>_place.zip` |
| 清单 | `MANIFEST.json`（含 sha256/行数/分页模式/候选重试链）+ `RELEASE_NOTES.md` |

> ⚠️ 注意：产物名与旧版 `delaware_full_dump.py` 的命名不同（旧版是 `nad_de_full.ndjson` 等）。
> 下游 ETL（`scripts/delaware_statewide_coalesce.py` 的 `scope`）里写的是旧名，
> 接新命名时改 `scope` 的 `nad` / `overture` / `oa` / `counties[].addrfeat` 四个字段即可。

## 已修的三个实证 Bug

1. **NAD 深分页熔断（真因不是深度，是服务端抖动）**
   旧版用纯 `resultOffset` 翻页，全州在 `offset=8000` 被 Esri 返回
   `400 Cannot perform query / Invalid query parameters`，导致整源丢失且工作流不报红。
   2026-10-16 探针复测（同一图层、同一 bbox）得出真相：

   | 请求组合 | 结果 |
   |---|---|
   | `resultRecordCount=2` | ✅ |
   | `resultOffset=0`（不带 orderBy） | ❌ 400 |
   | `orderByFields=OBJECTID ASC` + rc=2 | ✅ |
   | `resultRecordCount=2000`（= maxRecordCount） | ❌ 400 |
   | rc=1000 + `resultOffset=0`（旧代码姿势） | ✅ 返回 1000 条 |

   **同一组参数时好时坏 → 不是深度分页熔断，是联邦视图服务端抖动。**
   修复 = 三件组合拳：
   · 改**游标分页**：`orderByFields=<OID> ASC` + `where="<OID> > last_id"`，全程不传 `resultOffset`；
   · **重试**：`_esri_query()` 指数退避重试 4 次（TIGER 边界 3 次）；
   · **缩页**：重试仍被拒则单页缩半（1000 → 500 → 250 → 125 → 100）；
   · 另加**4 分块自愈**：实拉行数少于官方 `returnCountOnly` 的 99% 时，把包围盒切 4 块重拉并按 OID 去重合并。
   另修一个自研新坑：整页都是重复行时游标不推进 → 反复重拉同一页（自检里真卡死过一次），
   现已加三条退出阀（本页不满 / 本页无净增 / 游标未前进）。

2. **县界 680 字节空壳**：旧版写成 `COUNTY='10001'`（5 位），而 TIGERweb 县图层字段 `COUNTY` 长度是 3，
   服务端静默返回 `features: []`，680 字节的空壳还被当资产上传。
   改成 3 位 `COUNTY='001'` —— **已在真服务上验证通过**（2026-10-16 实跑：三个县界全部非空）。
   另配 4 组候选重试链（含“整州取回本地筛”兜底），`features=0` 直接不落盘。
   同批修掉 ZCTA 图层的一个同类坑：该图层**没有 `STATE` 字段**，outFields 带 STATE 会被
   `400 Failed to execute query` 拒；去掉后同一个 where 返回 68 个 ZCTA。

3. **无门禁**：新增 `gate()` —— 缺源 / 空壳载荷 / 边界 features=0 / NAD 行数为 0，
   一律 `RuntimeError` 阻断发布（退出码 3），杜绝废资产上架。
   注意空壳判定**走结构不走体积**：合法的列清单 `nad_full_columns.json` 只有 908 字节，
   而真正的空壳是 680 字节、`features: []` 的 geojson —— 体积一样小，只能靠结构区分。

## NAD 抓取策略：ids 模式（主路径）

旧路径（`--nad-mode cursor`，游标翻页 `orderByFields + where OID > last`）在 RI 全州实测失败：
Providence 县缩页 1000→500→250→125→100 全被 400 拒，12 万条拿不到（缺 28.4%）。

**根因**：每次翻页都让服务端重算一次「空间矩形交集 + 按 OBJECTID 排序」，
数据密、框大、游标深时触发服务端成本熔断。这不是能靠重试治好的。

**新主路径（`--nad-mode ids`，默认）**：

1. `returnIdsOnly=true` → 一次拿回全量主键清单（轻量、无排序、无翻页）；
2. `objectIds` 每批 500 个点名取数 → **无游标、无 offset、成本恒定，服务端走主键索引秒回**；
3. 某批失败 → **立即拆半重试**（一直拆到单条），不原样重发；
4. 最后**硬对账**：已取 OID 集合必须 == `returnIdsOnly` 集合，差一条就报错、不发 Release。

⚠️ **两条铁坑**：
- `objectIds` 批取**必须走 HTTP POST**（表单 body）。500 个 8~9 位 ID 拼出来 4.5~9 KB，
  塞进 GET query string 会被前置网关直接 414 / 400 打回。
- 失败的完整响应体落 `nad/nad_http_errors.log`（不再只截 200 字符）。

**自适应降级链**（州级 `returnIdsOnly` 都拿不到时才启用）：
`县 → tract（vintage 2020，从 TIGER TRACT 小包算 bbox）→ 0.02° 网格`，
单块超过 `--nad-split-threshold`（默认 5 万行）也会自动降级。

**并发默认降到 2**：4 并发很可能撞上按 IP 的限速（Providence 跑得最久、最先被打）。

## 维护备忘

- 四源端点常量仍集中在 `bots/dover_fetch.py`（单一事实来源），换代只改那一处。
- Overture 目前仍走官方 CLI；`--overture-format parquet` 已把"整包 `json.loads` 进内存"的
  内存炸弹拆掉。**真正的大州攻坚**（自己写 DuckDB 查询 S3/R2 + 分片导出）尚未落地。
