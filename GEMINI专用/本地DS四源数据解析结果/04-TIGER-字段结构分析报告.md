# Census TIGER 多佛数据 · 字段结构与格式分析报告

- 来源：GitHub Release `ip9988001/world-map-data-test` @ `dover-raw-20261015-0450`
- 6 个文件分**两类**：
  - **A 类·道路号段表（1 个）**：`tl_2024_10001_addrfeat.zip`
  - **B 类·边界多边形（5 个）**：`tl_2024_10_place.zip` + `tiger_state_de.geojson` + `tiger_county_kent.geojson` + `tiger_place_dover.geojson` + `tiger_zcta_19901_19904.geojson`
- 坐标系：全部 `GCS_North_American_1983` / `wkid=4326`（WGS84 经纬度）

---

# A 类 · 道路号段表 `tl_2024_10001_addrfeat.zip`

## A1. 文件构成（Shapefile 标准 7 件套）
```
tl_2024_10001_addrfeat.cpg        ← 编码声明
tl_2024_10001_addrfeat.dbf        ← 属性表（25 字段 / 11,072 记录）
tl_2024_10001_addrfeat.prj        ← 坐标系
tl_2024_10001_addrfeat.shp        ← 几何（线）
tl_2024_10001_addrfeat.shx        ← 几何索引
tl_2024_10001_addrfeat.shp.ea.iso.xml / .shp.iso.xml  ← 元数据
```

## A2. 字段组成：DBF 共 **25 个字段**（⚠️ 不含 geometry）

| 组 | 数 | 字段（名称 | 类型 | 长度） |
|---|---|---|---|
| 道路标识 | 6 | `TLID`(N,10) `TFIDL`(N,10) `TFIDR`(N,10) `ARIDL`(C,22) `ARIDR`(C,22) `LINEARID`(C,22) |
| 道路名 | 1 | `FULLNAME`(C,100) |
| **左侧**号段 | 6 | `LFROMHN`(C,12) `LTOHN`(C,12) `ZIPL`(C,5) `PARITYL`(C,1) `LFROMTYP`(C,1) `LTOTYP`(C,1) |
| **右侧**号段 | 6 | `RFROMHN`(C,12) `RTOHN`(C,12) `ZIPR`(C,5) `PARITYR`(C,1) `RFROMTYP`(C,1) `RTOTYP`(C,1) |
| 邮编加 4 | 2 | `PLUS4L`(C,4) `PLUS4R`(C,4) |
| 分类与偏移 | 4 | `EDGE_MTFCC`(C,5) `ROAD_MTFCC`(C,5) `OFFSETL`(C,1) `OFFSETR`(C,1) |

> ⚠️ **修正早前说法**：DBF 的 25 字段里**没有 `geometry`**——几何存在独立的 `.shp` 里（TIGER ADDRFEAT 的几何是**道路线**，不是点）。

## A3. 非空率（全量 11,072 条实测）

| 字段 | 非空率 | 条数 |
|---|---|---|
| `TLID` `TFIDL` `TFIDR` `LINEARID` `FULLNAME` `EDGE_MTFCC` `ROAD_MTFCC` `OFFSETL` `OFFSETR` | **100%** | 11,072 |
| `ARIDL` `LFROMHN` `LTOHN` `ZIPL` `PARITYL` | 81.09% | 8,978 |
| `ARIDR` `RFROMHN` `RTOHN` `ZIPR` `PARITYR` | 80.51% | 8,914 |
| `LTOTYP` | 16.44% | 1,820 |
| `LFROMTYP` | 15.91% | 1,762 |
| `RTOTYP` | 15.91% | 1,762 |
| `RFROMTYP` | 14.82% | 1,641 |
| **`PLUS4L` / `PLUS4R`** | **0.00%（全空）** | 0 |

> ⚠️⚠️ **两条重大修正**：
> 1. **`ZIPL`/`ZIPR` 实际有值（约 81%）**——早前报告写「ZIP=None」是因为脚本用了错误列名（`ZIP`），真实列名是 **`ZIPL`/`ZIPR`**。
> 2. **`PLUS4L`/`PLUS4R` 实测确实 100% 全空**——**不是脚本列名写错，而是本文件本身就没有 Plus_4**。因此「修复列名即可拿到 Plus_4」的假设**不成立**，9 位邮编的 `plus4` **无法从本 TIGER 文件取得**，需另找数据源。

## A4. 取值分布（关键字段）

| 字段 | 取值分布 |
|---|---|
| `EDGE_MTFCC` | `S1400` 9,564（地方道路）/ `S1200` 1,492（次干道）/ `P0001` 16 |
| `ROAD_MTFCC` | `S1400` 9,576 / `S1200` 1,496 |
| `PARITYL` | `O` 5,733 / `E` 3,241 / 空 2,094 / `B` 4 |
| `PARITYR` | `E` 5,712 / `O` 3,200 / 空 2,158 / `B` 2 |
| `LFROMTYP` / `LTOTYP` | 空 或 `I`（表示端点落在交叉口） |
| `OFFSETL` | `N` 11,059 / `Y` 13 |
| `ZIPL` Top | `19901` 1,561 / `19904` 1,559 / `19977` 1,129 / `19943` 848 / `19934` 818 / `19952` 651 / `19962` 531 … |
| 去重计数 | `TLID` **9,939** / `FULLNAME` **3,535** / `LINEARID` **3,906**（总记录 11,072） |

> **`TLID` 不是唯一键**：11,072 行只对应 9,939 个不同 `TLID` → **同一个 TLID 可有多条记录**（同一条路的不同号段/邮编段），合并时不能拿 TLID 当主键去重。

## A5. 规则 / 架构 / 格式

**架构**：每条记录 = **一条道路的一侧或两侧号段区间**，不是地址点。
```
记录 = { TLID(边ID), FULLNAME(路名),
         左侧: LFROMHN~LTOHN, ZIPL, PARITYL, LFROMTYP/LTOTYP, PLUS4L,
         右侧: RFROMHN~RTOHN, ZIPR, PARITYR, RFROMTYP/RTOTYP, PLUS4R }
几何 → .shp（LineString）
```

**FULLNAME 格式**：Title Case + 缩写方向词 + 缩写类型
```
W Denneys Rd   N State St   S State St   S Dupont Hwy   Upper King Rd   Central Church Rd
```
- 方向词用**单字母** `N/S/E/W`；类型后缀用**缩写** `Rd/St/Ave/Ct/Hwy/Blvd`
- 含 Denneys 的：`W Denneys Rd` 38 条、`E Denneys Rd` 7 条；含 State 的：`S State St` 72 条、`N State St` 18 条

**号段区间规则（重要坑）**
- 左/右两侧**独立**，一侧可以完全为空（如只有右侧 `RFROMHN`/`RTOHN`）
- **`FROMHN` 可能大于 `TOHN`**（降序），例如 `8698→8618`、`120→108`、`22→15`、`459→699` → 判断"门牌是否落在区间内"必须取 `min/max`，不能假设升序
- `PARITYL/R`：`O`=奇数侧、`E`=偶数侧、`B`=两侧通用、空=未知
- `OFFSETL/R`：`N`=无偏移、`Y`=有偏移（本文件仅 13 条 Y）

**用途（唯一正确的用法）**
```
给定 (FULLNAME, 门牌号, 奇偶) → 在 addrfeat 里按路名匹配，
落入 [LFROMHN,LTOHN] 判为左侧、[RFROMHN,RTOHN] 判为右侧，
据此推断 ZIPL/ZIPR（5 位邮编）与道路等级 MTFCC。
Plus_4 不可得（全空）。
```

---

# B 类 · 5 个边界/辅助文件

## B1. `tl_2024_10_place.zip`（Shapefile，DE 州全部 Place）

- DBF：**16 字段 / 79 条记录**（整个特拉华州的 Place 边界），100% 非空
- 字段：`STATEFP` `PLACEFP` `PLACENS` `GEOID` `GEOIDFQ` `NAME` `NAMELSAD` `LSAD` `CLASSFP` `PCICBSA` `MTFCC` `FUNCSTAT` `ALAND` `AWATER` `INTPTLAT` `INTPTLON`
- **Dover 那条记录**（原文）：
```json
{"STATEFP":"10","PLACEFP":"21200","PLACENS":"02390583","GEOID":"1021200",
 "GEOIDFQ":"1600000US1021200","NAME":"Dover","NAMELSAD":"Dover city",
 "LSAD":"25","CLASSFP":"C1","PCICBSA":"Y","MTFCC":"G4110","FUNCSTAT":"A",
 "ALAND":"61685012","AWATER":"788869","INTPTLAT":"+39.1606016","INTPTLON":"-075.5216592"}
```

## B2. 4 个 `.geojson` —— ⚠️ 实际是 **Esri JSON，不是标准 GeoJSON**

**重大结构发现**：这 4 个文件虽然扩展名是 `.geojson`，但**不是标准 GeoJSON**，而是 **ArcGIS REST 返回的 Esri FeatureSet**：
- 顶层键：`displayFieldName` / `fieldAliases` / `geometryType` / `spatialReference` / `fields` / `features`
- 要素属性键是 **`attributes`**（不是 `properties`）
- 几何键是 **`rings`**（不是 `coordinates`），`geometryType = esriGeometryPolygon`
- Esri ring 规则：外环顺时针、内环（洞）逆时针

| 文件 | features | geometryType | 字段 | attributes 原文 |
|---|---|---|---|---|
| `tiger_state_de.geojson` | 1 | esriGeometryPolygon | `GEOID` `STATE` `STUSAB` `BASENAME` `NAME` | `{"GEOID":"10","STATE":"10","STUSAB":"DE","BASENAME":"Delaware","NAME":"Delaware"}` |
| `tiger_county_kent.geojson` | 1 | esriGeometryPolygon | `GEOID` `BASENAME` `STATE` `COUNTY` `NAME` | `{"GEOID":"10001","BASENAME":"Kent","STATE":"10","COUNTY":"001","NAME":"Kent County"}` |
| `tiger_place_dover.geojson` | 1 | esriGeometryPolygon | `GEOID` `NAME` `BASENAME` `STATE` `PLACE` `CENTLAT` `CENTLON` | `{"GEOID":"1021200","NAME":"Dover city","BASENAME":"Dover","STATE":"10","PLACE":"21200","CENTLAT":"+39.1612747","CENTLON":"-075.5205838"}` |
| `tiger_zcta_19901_19904.geojson` | **2** | esriGeometryPolygon | `ZCTA5` `GEOID` | `{"ZCTA5":"19904","GEOID":"19904"}` / `{"ZCTA5":"19901","GEOID":"19901"}` |

> 解析时**必须按 Esri JSON 处理**（读 `attributes` + `geometry.rings`），直接按标准 GeoJSON 的 `properties`/`coordinates` 读会全部报错。

---

## C. 总结：TIGER 与另三源的本质差异

1. **TIGER 本批没有「地址点」**：addrfeat 是**道路号段区间表**（几何是线），5 个边界文件是**行政/邮编多边形**——**性质与 NAD/Overture/OA 的「点地址」完全不同，不可直接合并**。
2. **能用它做什么**：给已有点地址**补 5 位邮编（ZIPL/ZIPR）**、补**行政归属**（Place/County/State 多边形空间落点）、补**道路等级**（MTFCC）。
3. **不能用它做什么**：拿不到 **Plus_4（全空）**、拿不到楼栋/室号/坐标精度标签。
4. **多佛本体的行政码**（可用于关联）：`STATE=10` / `STUSAB=DE` / `COUNTY=001` / `PLACE=21200` / `GEOID=1021200` / `ZCTA5=19901,19904`。
