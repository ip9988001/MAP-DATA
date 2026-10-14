# Dover, DE 四源取样报告（自动生成）

> 生成时间：2026-10-14 18:41:30Z ｜ 运行位置：**GitHub Actions**（本机服务器零下载）
> 锚定参数：州 `DE`/FIPS `10`｜县 `Kent County`/FIPS `10001`｜市 `Dover`/Place FIPS `1021200`｜邮编 `19901`, `19904`｜BBox `[-75.6, 39.1, -75.45, 39.22]`

## 0. 四源状态

| 源 | 状态 | 关键数字 | 备注 |
|---|---|---|---|
| `overture` | ok | features_bbox=28027 / features_19901=24046 / main_state_hits=510 |  |
| `nad` | exception | - |  |
| `openaddresses` | ok | main_state_hits=414 / rows=92455 / rows_19901=29077 / targets=2 |  |
| `census_tiger` | ok | REST=zcta:2,place_dover:1,county_kent:1,state_de:0 |  |

## 1. 三源并排对齐样本（邮编 19901/19904 + 街道含 MAIN 或 STATE）

合计 **914** 行 → `data/dover/align_19901_main_state.csv`
各源命中：{"overture": 500, "nad_arcgis": 0, "openaddresses": 414}

## 2. 产物清单

- `data/dover/align_19901_main_state.csv` — 66,444 B
- `data/dover/align_src_openaddresses.csv` — 21,390 B
- `data/dover/align_src_overture.csv` — 34,794 B
- `data/dover/manifest.json` — 4,036 B
- `data/dover/openaddresses_19901.csv` — 27,236 B
- `data/dover/overture_19901.csv` — 33,707 B
- `data/dover/raw/openaddresses_city_of_dover.zip` — 310,206 B
- `data/dover/raw/openaddresses_kent.zip` — 1,908,081 B
- `data/dover/raw/overture_dover.geojson.gz` — 2,085,794 B
- `data/dover/raw/overture_dover.geojson.state` — 358 B
- `data/dover/raw/tiger_county_kent.json` — 99,118 B
- `data/dover/raw/tiger_place_dover.json` — 114,238 B
- `data/dover/raw/tiger_state_de.json` — 78 B
- `data/dover/raw/tiger_zcta.json` — 173,558 B
- `data/dover/raw/tl_2024_10001_addrfeat.zip` — 1,409,495 B
- `data/dover/raw/tl_2024_10_place.zip` — 444,861 B

## 3. 口径与已知边界

- NAD 官方图层（USDOT item `ddcaa5e1a9e24c27bff3c3ce16ea2944`）**拒绝匿名查询**，机器人自动回退到 ArcGIS Online 同名镜像 `USA_NAD_Addresses`；官方图层的失败原因已如实记入 `manifest.json`。
- OpenAddresses 的 run id 每次跑都可能变，机器人**每次现查首页**取最新 zip，不写死链接。
- 三源字段命名各异（Overture `number/street/postcode`、NAD `addr_*`、OA `NUMBER/STREET`），本报告只做**并排对齐**，不做合并——合成规则待架构师定稿。
- ZCTA 边界（19901）是**邮编多边形**，与本项目一直用的州 BBox 不同层级，不可混用。

