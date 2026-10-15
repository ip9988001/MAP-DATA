# 附录 D · GitHub Release「四源多佛全量数据」文件辨识

> 仓库：`ip9988001/world-map-data-test`
> 页面：https://github.com/ip9988001/world-map-data-test/releases
> 结论时间：2026-10-15

---

## 一、该仓库目前只有 1 个 Release

| 项 | 值 |
|---|---|
| Tag | `dover-raw-20261015-0450` |
| 标题 | Dover DE 四源全量原始数据 dover-raw-20261015-0450 |
| 发布时间 | 2026-10-15T04:51:01Z（= 北京时间 12:51） |
| 发布者 | github-actions（workflow run `38683529370`） |
| 资产数 | **17 个文件**（+2 个自动生成的 Source code zip/tar.gz = 页面显示 19） |

**口径声明（Release 原文）**：
> 范围：州 `DE`/FIPS `10`｜县 `Kent County`/FIPS `10001`｜市 `Dover`/Place FIPS `1021200`｜邮编 `19901`, `19904`｜BBox `[-75.6, 39.1, -75.45, 39.22]`
> 口径：源里给什么就是什么 —— **不做清洗、不去重、不合并、不裁剪字段**。全部下载在 GitHub Actions runner 上发生（本地服务器零下载）。

---

## 二、四个数据源对应的文件

### 源 A · USDOT NAD（官方 60 列通道）— 3 个文件

| 文件 | 大小 | 说明 |
|---|---|---|
| **`nad_dover_full.ndjson`** | 40,501,682 B（38.6 MB） | **核心地址数据**，28,028 行 / 60 列 |
| `nad_full_columns.json` | 908 B | 60 个字段名清单 |
| `nad_native_metadata.json` | 1,206,272 B（1.15 MB） | ArcGIS 原生元数据 |

### 源 B · Overture Maps — 1 个文件

| 文件 | 大小 | 说明 |
|---|---|---|
| **`overture_addresses.geojson`** | 16,452,588 B（15.7 MB） | **核心地址数据**，28,027 个 features |

### 源 C · OpenAddresses `us/de` — 5 个文件（按辖区拆分）

| 文件 | 大小 | 行数（含表头） |
|---|---|---|
| `openaddresses_us_de_city_of_dover.zip` | 310,206 B | 12,733 |
| `openaddresses_us_de_kent.zip` | 1,908,081 B | 79,725 |
| `openaddresses_us_de_city_of_newark.zip` | 182,712 B | 7,222 |
| `openaddresses_us_de_new_castle.zip` | 8,143,092 B | 271,151 |
| `openaddresses_us_de_sussex.zip` | 4,401,991 B | 183,032 |

### 源 D · Census TIGER — 6 个文件（1 号段表 + 5 边界/辅助）

| 文件 | 大小 | 说明 |
|---|---|---|
| `tl_2024_10001_addrfeat.zip` | 1,409,495 B | **道路号段表**，11,072 条 / 25 列（Kent County） |
| `tl_2024_10_place.zip` | 444,861 B | DE 州 Place 边界 |
| `tiger_zcta_19901_19904.geojson` | 173,558 B | 邮编区 19901 / 19904 边界 |
| `tiger_place_dover.geojson` | 114,238 B | Dover 市界 |
| `tiger_county_kent.geojson` | 99,118 B | Kent 县界 |
| `tiger_state_de.geojson` | 220,318 B | DE 州界 |

### 非数据源文件（发布元数据）

- `MANIFEST.json`（6,460 B，全资产清单 + sha256）
- `RELEASE_NOTES.md`（4,878 B）

---

## 三、三个必须说清的坑

1. **真正算「地址点数据」的只有 3 份**：`nad_dover_full.ndjson`、`overture_addresses.geojson`、以及 5 个 OpenAddresses zip。TIGER 的 `addrfeat.zip` 是**道路门牌号区间表**，不是点地址，性质不同、不可直接合并。
2. **只有 NAD 和 Overture 是按 Dover bbox 过滤的**；OpenAddresses 那 5 个是**整个县/州**的文件（kent / new_castle / sussex 等），TIGER addrfeat 也是**整 Kent 县**——文件放在 `data/dover/full/` 路径下只是命名习惯，并不代表内容已裁到多佛市。
3. 80 条样本所在的 `task001_records.jsonl` **不在这个 Release 里**，它是仓库里的单独文件，别混。

---

## 四、每个 Release 资产对应的仓库内路径（Release Notes 原文「资产清单」）

| 仓库路径 | 对应 Release 资产 |
|---|---|
| `data/dover/full/nad/nad_native_metadata.json` | `nad_native_metadata.json` |
| `data/dover/full/nad/nad_dover_full.ndjson` | `nad_dover_full.ndjson` |
| `data/dover/full/nad/nad_full_columns.json` | `nad_full_columns.json` |
| `data/dover/full/overture/overture_addresses.geojson` | `overture_addresses.geojson` |
| `data/dover/full/openaddresses/openaddresses_us_de_city_of_dover.zip` | 同名 |
| `data/dover/full/openaddresses/openaddresses_us_de_kent.zip` | 同名 |
| `data/dover/full/openaddresses/openaddresses_us_de_city_of_newark.zip` | 同名 |
| `data/dover/full/openaddresses/openaddresses_us_de_new_castle.zip` | 同名 |
| `data/dover/full/openaddresses/openaddresses_us_de_sussex.zip` | 同名 |
| `data/dover/full/tiger/tiger_zcta_19901_19904.geojson` | 同名 |
| `data/dover/full/tiger/tiger_place_dover.geojson` | 同名 |
| `data/dover/full/tiger/tiger_county_kent.geojson` | 同名 |
| `data/dover/full/tiger/tiger_state_de.geojson` | 同名 |
| `data/dover/full/tiger/tl_2024_10001_addrfeat.zip` | 同名 |
| `data/dover/full/tiger/tl_2024_10_place.zip` | 同名 |

---

## 五、各源抓取结果（Release Notes 原文 JSON 摘要）

```json
[
 {"source":"nad","status":"ok","channel":"A-official-rest",
  "endpoint":"https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/Address_Points_from_National_Address_Database_view/FeatureServer/0",
  "fields_n":60,"rows_fetched":28028,"official_count_in_bbox":28028,"truncated":false},
 {"source":"overture","status":"ok","bbox":"-75.6,39.1,-75.45,39.22","features":28027},
 {"source":"openaddresses","status":"ok","sources_total":5,"downloaded":5,
  "detail":[
   {"src":"city_of_dover","run":"1191307","bytes":310206,"native_rows":12733},
   {"src":"kent","run":"1195369","bytes":1908081,"native_rows":79725},
   {"src":"city_of_newark","run":"748737","bytes":182712,"native_rows":7222},
   {"src":"new_castle","run":"1195302","bytes":8143092,"native_rows":271151},
   {"src":"sussex","run":"1195200","bytes":4401991,"native_rows":183032}]},
 {"source":"census_tiger","status":"ok",
  "detail":[
   {"key":"zcta_19901_19904","where":"ZCTA5='19901' OR ZCTA5='19904'","features":2},
   {"key":"place_dover","where":"STATE='10' AND BASENAME='Dover'","features":1},
   {"key":"county_kent","where":"STATE='10' AND COUNTY='001'","features":1},
   {"key":"state_de","where":"STATE='10'","features":1},
   {"file":"tl_2024_10001_addrfeat.zip","bytes":1409495},
   {"file":"tl_2024_10_place.zip","bytes":444861},
   {"file":"tl_2024_10001_addrfeat.zip","dbf_records":11072,
    "dbf_fields":["TLID","TFIDL","TFIDR","ARIDL","ARIDR","LINEARID","FULLNAME","LFROMHN","LTOHN",
                  "RFROMHN","RTOHN","ZIPL","ZIPR","EDGE_MTFCC","ROAD_MTFCC","PARITYL","PARITYR",
                  "PLUS4L","PLUS4R","LFROMTYP","LTOTYP","RFROMTYP","RTOTYP","OFFSETL","OFFSETR"]}]}
]
```

> 注：Release Notes 的 `native_rows` 计的是**含表头的总行数**（如 city_of_dover 12,733），实际数据行 = 该数 − 1。
