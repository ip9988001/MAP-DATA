# GEMINI 专用 · 四源抽检解析成果索引

> 产出人：PI-Agent（世界地图取数项目执行侧）　产出时间：2026-10-15
> 用途：供 Gemini 参考——这套「四源字段架构 + 抽检样本 + 合并映射规则」是撰写 **TASK-002（四源去重合并 → 24 字段黄金地址库）** 落地脚本的架构依据。
> 所有内容均为**实测结果**（基于仓库内真实数据文件逐列统计），不是文档摘抄。

## 文件清单

| 文件 | 对应数据源 | 数据文件（仓库内） | 规模 |
|---|---|---|---|
| `01-源A-USDOT-NAD-抽检解析.md` | USDOT NAD（官方 60 列） | `data/dover/raw/nad_dover_official.geojson.gz` | 20,000 条（全量 28,028 见 Release） |
| `02-源B-Overture-Maps-抽检解析.md` | Overture Maps Addresses | `data/dover/raw/overture_dover.geojson.gz` | 28,027 条 |
| `03-源C-OpenAddresses-抽检解析.md` | OpenAddresses `us/de` | `data/dover/raw/openaddresses_kent.zip` / `openaddresses_city_of_dover.zip` | 79,723 / 12,732 行 |
| `04-源D-Census-TIGER-抽检解析.md` | Census TIGER（1 号段表 + 5 边界/辅助） | `data/dover/raw/tl_2024_10001_addrfeat.zip` 等 6 个文件 | 号段 11,072 条 + 边界 5 层 |

**原始全量数据（未做任何清洗/去重）**：GitHub Release `dover-raw-20261015-0450`（17 个资产 / 75.6 MB）
→ https://github.com/ip9988001/world-map-data-test/releases/tag/dover-raw-20261015-0450

## 四源架构速查（合并时的核心矛盾点）

| 维度 | NAD | Overture | OpenAddresses | TIGER |
|---|---|---|---|---|
| 列数 | 60 原生（+2 坐标 = 62 落库） | 11（id + 9 properties + geometry） | 11 | 25（号段表）+ 边界 2~16 |
| 地址形态 | **地址点** | **地址点** | **地址点** | **道路段号段区间**（非点） |
| 门牌号类型 | Integer | String | String | String（区间起止） |
| 街道字段 | **拆 4~5 段**（前方向/名/后缀/后方向） | **一整串** | **一整串** | 一整串 |
| 街道大小写 | `St_Name` 全大写 + 后缀首字母大写 | 混合大小写 | 全大写 + USPS 缩写 | 混合大小写 + USPS 缩写 |
| 后缀词表 | 22 个**全称**（Road/Street…） | 无独立字段 | 缩写为主 + 全称混入 | 缩写 |
| unit 非空率 | 0.23% | 0.19% | 0.72% | — |
| 坐标精度 | 14 位小数（WGS84） | 14 位小数（WGS84） | 4~7 位小数（WGS84） | **NAD83**（Polyline，非点） |
| 行政区字段 | 完整（County/Inc_Muni/Post_City/Zip） | 仅 `postal_city` + `address_levels`（无 level 标签） | `CITY` 缺 7%、`DISTRICT/REGION/ID` 全空 | 边界图层提供（GEOID 体系） |
| plus4 | `Plus_4` **0%** | 无字段 | 无字段 | `PLUS4L/PLUS4R` **0%** |
| 唯一键 | `UUID`（36 位 GUID） | `feature.id`（UUID4） | `HASH`（16 位） | `TLID`（**一 TLID 可多条**） |

## 必须在写 TASK-002 脚本前拍板的 3 件事（数据实证，非猜测）

1. **`plus4` / `zip9` 四个源都拿不到**：NAD `Plus_4` 0.00%、TIGER `PLUS4L/PLUS4R` 0.00%（Kent 县 11,072 条全空）、Overture/OA 无该字段。
   → 24 字段表里的 `plus4`/`zip9` **只能留空或改口径**，验收标准必须修改，不能用 TIGER 插值"造"出来。
2. **Overture ≠ 独立源**：28,027/28,027 条的 `sources[0].dataset` 全部 = `"NAD"`（provider=nad, version=20250924）。
   → 用 "NAD + Overture 命中" 做交叉验证属于**自证**；真正独立的只有 **OpenAddresses**（民间）+ **TIGER**（官方号段/边界）。
3. **OpenAddresses 内部自身重复**：`kent.csv` 与 `city_of_dover.csv` 的 (门牌+街名) 交集 **11,672 条**（且 city_of_dover 的 `CITY/POSTCODE` 12,732 行全空）。
   → 合并前必须先做 OA 跨文件去重，否则 S 级数量虚高。

## 另外 4 条落地约束（详见各文件）

- **Overture 同址多点**：`1679 South STATE Street` 一门牌 **132 条、132 个不同坐标** → 不能只按 (门牌+街名) 去重，须坐标聚类或与 NAD 最近邻。
- **TIGER 号段**：同一 `TLID` 有多条记录（9,939 vs 11,072），约 19% 只有单侧号段，存在 `LFROMHN > LTOHN` 降序区间 → 判区间要用 min/max、按 TLID 聚合。
- **脏数据（已量化）**：OA `NUMBER="0"` 240 条、`UNIT/CITY="<Null>"` 112/111 条、无门牌纯街道行 30 条；Overture `unit="<Null>"` 1 条；NAD `Placement/Addr_Type/AddrClass` 全为单值常量（Unknown）→ `addr_type` 必须靠 unit 存在性 + 商业走廊重分类。
- **空间匹配容差**：TIGER 是 NAD83、其余是 WGS84，且各源精度差 3 个数量级 → 建议阈值 **30~50 米**（同一门牌跨源实测差 < 1 米）。
