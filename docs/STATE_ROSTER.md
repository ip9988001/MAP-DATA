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

1. **NAD 深分页熔断**：旧版纯 `resultOffset` 翻页，全州在 `offset=8000` 被 Esri 返回
   `400 Cannot perform query / Invalid query parameters`，导致整源丢失且工作流不报红。
   现在改为**游标分页**：`orderByFields=<OID> ASC` + `where="<OID> > last_id"`，深度无上限；
   另有自愈兜底 —— 若实拉行数少于官方 `returnCountOnly` 的 99%，自动把包围盒切 4 块重拉并按 OID 合并。
2. **县界空壳**：旧版写成 `COUNTY='10001'`（5 位），而 TIGERweb 县图层字段 `COUNTY` 长度是 3，
   服务端静默返回 `features: []`，680 字节的空壳还被当资产上传。现在用 3 位
   `COUNTY='001'`，并配 4 组候选（含"整州取回本地筛"的兜底），**features=0 直接不落盘**。
3. **无门禁**：新增 `gate()` —— 缺源 / 任何文本产物 <1KB / 边界 features=0 / NAD 行数为 0，
   一律 `RuntimeError` 阻断发布（退出码 3），杜绝废资产上架。

## 维护备忘

- 四源端点常量仍集中在 `bots/dover_fetch.py`（单一事实来源），换代只改那一处。
- Overture 目前仍走官方 CLI；`--overture-format parquet` 已把"整包 `json.loads` 进内存"的
  内存炸弹拆掉。**真正的大州攻坚**（自己写 DuckDB 查询 S3/R2 + 分片导出）尚未落地。
