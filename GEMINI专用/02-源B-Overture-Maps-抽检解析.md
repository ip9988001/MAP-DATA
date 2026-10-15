# 源 B · Overture Maps Addresses 抽检与结构解析

> 抽检人：PI-Agent　时间：2026-10-15　用途：供 Gemini 参考 24 字段黄金表/合并规则的架构依据
> 数据文件（仓库内）：`data/dover/raw/overture_dover.geojson.gz`（**28,027 条 features**）
> 全量对应产物（GitHub Release `dover-raw-20261015-0450`）：`overture_addresses.geojson`（28,027 条，16.5 MB）

---

## 一、字段组成：11 列 = `feature.id` + 9 个 properties + 1 个 geometry

**properties 键并集（实测 9 个）**：`number, street, unit, postcode, postal_city, address_levels, country, sources, version`

| 列 | 非空率 | 唯一值 | 说明 / 格式 |
|---|---|---|---|
| `feature.id` | 100% | 28,027 | UUID4 36 位，**真主键**，例 `0dd867b2-4f90-4d29-9d43-d08bba9eb9c1` |
| `number` | **100%** | 3,065 | **字符串**类型（本批 100% 纯数字，如 `"455"`），**无前后缀概念** |
| `street` | **100%** | 1,354 | 整条街道名，**不分方向词/后缀字段** |
| `unit` | **0.19%** | 23（+1 脏值） | 极稀疏 |
| `postcode` | **100%** | 7 | 5 位 |
| `postal_city` | **100%** | 6 | 含大小写变体 |
| `address_levels` | **100%** | 13 | 嵌套数组（见下） |
| `country` | **100%** | 1 | 恒 `"US"` |
| `sources` | **100%** | 28,027 | 溯源数组（见下，**最关键**） |
| `version` | **100%** | 1 | 恒 `1`（schema 版本，**不是数据版本**） |
| `geometry` | **100%** | — | `Point`，**坐标在 geometry 里，不在 properties** |

---

## 二、规则 / 结构 / 格式（实测校验）

### ① `address_levels`：只有 `value`、没有 level 标签的数组
- 元素结构：`{"value": "DE"}` —— **完全没有 `admin_level` 字段**（专门 grep 过，0 命中）。
- 两种形态：
  - **2 项（26,375 条）** = `[{"value":"DE"}, {"value":"城市"}]`
  - **1 项（1,652 条）** = `[{"value":"DE"}]` —— **只有州、缺城市**
- 第 2 项取值分布：Dover 22,444 / Camden Wyoming 2,927 / Cheswold 602 / Magnolia 360 / **DOVER 15 / DOver 3（大小写脏值）** / Wyoming 13 / Camden 6
- ⚠️ **不能按 index 硬取**（1 项的那些会取到州名当城市），必须按 value 内容判定。

### ② `sources` 逐键拆解（每条 feature 恰好 1 个元素，10 个键）
```json
[{"property": "", "dataset": "NAD", "license": "LicenseRef-Public-Domain-US",
  "record_id": "61427C58-F858-44A1-8FA0-B077E12AA530",
  "update_time": "2026-09-18T19:39:08.275Z", "confidence": null, "between": null,
  "provider": "nad", "resource": "nad", "version": "20250924"}]
```
- **`dataset` 28,027 / 28,027 全部 = `"NAD"`**
- `provider` = `resource` = `nad`；`license` 全 `LicenseRef-Public-Domain-US`；`version` 全 `"20250924"`；`update_time` 全 `2026-09-18T19:39:08.275Z`
- `confidence` 与 `between` **全为 null**；`property` 为空串
- 🔴 **最重要发现：这片区域的 Overture 数据 100% 溯源到 NAD（美国交通部官方），不是独立第三方源。**
  → 24 字段里若用 "NAD + Overture 命中" 作为交叉验证证据，**属于自证**；四源中真正独立的是 **OpenAddresses**（民间）与 **TIGER**（官方号段/边界）。

### ③ 大小写与格式（与源 A 完全不同）
- `number`：字符串，无 `AddNum_Pre`/`AddNum_Suf` 概念。
- `street`：**混合大小写**，方向词全称首字母大写 + 核心名多大写 + 后缀首字母大写：
  `South STATE Street` / `MOOSE LODGE Road` / `NEO Circle` / `BEECHWOOD Avenue` / `WILLOW GROVE Road`
- `postal_city`：`Dover`(24239) / `Camden Wyoming`(2956) / `Magnolia`(429) / `Cheswold`(401) / **`DOVER`(1)** / `Little Creek`(1)
- `postcode`：19901 12093 / 19904 11953 / 19934 2958 / 19962 429 / 19936 373 / 19902 220 / 19961 1
- `unit`：23 个值（`APT A`9 / `APT B`8 / `STE B`3 / `STE A`3 / `A`3 / `APT C`3 / `STE C`2 / `B`2 / `APT 1`2 / `APT 2`2 / `APT E`2 / `APT D`2 / `STE D`1 / `D`1 / `APT RM09`1 / **`<Null>`1（字面字符串脏值）** / 其余各 1）
- `geometry`：`Point`，WGS84 十进制度，**最多 14 位小数**，范围 lon −75.6000055 ~ −75.4502063、lat 39.1000066 ~ 39.2199894

### ④ 重复度（本源最大的坑）
- 按 `(number, street, postcode, unit)` 四元组：唯一 **27,173**，**198 个重复组**
- 极端例：**`1679 South STATE Street, 19901` 有 132 条记录、132 个坐标各不相同**（沿街密集分布，全部 `unit=null`）；**`200 BEECHWOOD Avenue` 66 条 / 66 个不同坐标**
- 结论：Overture 把**同一门牌号的大地块/公寓群打散成多点**。→ **不能只按 (number+street) 去重**（会误判为 1 条或误杀 131 条），必须带**坐标聚类**或与 NAD 点做最近邻。

---

## 三、抽检 20 条完整原始记录

> 抽检构成：4 条带 `unit` + 4 条 `address_levels` 单层级（缺城市）+ 4 条落在已知重复门牌（`1679 South STATE Street`）+ 8 条普通。
> `sources` 除 `record_id` 外 20 条完全一致（NAD/nad/20250924/`2026-09-18T19:39:08.275Z`/LicenseRef-Public-Domain-US），完整 JSON 结构见上②；下表每条附 `record_id`。**Overture 每条只有这 11 列，未省略任何字段。**

```
#1  id=aab767eb-5a80-405c-85e8-e92f39d11b4b | number='11540' | street='WILLOW GROVE Road' | unit='STE B' | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.56340680224665 lat=39.10176111483698 | sources.record_id=0F3629D8-FD1E-4108-89A3-7E177819182F
#2  id=1f62ef75-9055-486b-87bb-fa56d56287b9 | number='11540' | street='WILLOW GROVE Road' | unit='STE A' | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.56340680224665 lat=39.10176111483698 | sources.record_id=3A759C97-CEC7-4167-A80F-80814C519A61
#3  id=0bdc4325-89b7-4c95-ae7c-c521f8bceb46 | number='11550' | street='WILLOW GROVE Road' | unit='STE C' | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.56379288715878 lat=39.102142298897576 | sources.record_id=B8A30598-4AAE-4CEF-B77C-5017276BC853
#4  id=6a3d3c62-40f1-4a73-bdea-a6858da06f9d | number='11550' | street='WILLOW GROVE Road' | unit='STE A' | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.56379288715878 lat=39.102142298897576 | sources.record_id=A13E0B3A-33AA-4F68-8AB3-8C9A03F60A69
#5  id=51b8cb8a-61ee-43a4-a686-79e93c07b3cb | number='12173' | street='WILLOW GROVE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"}] ← 单层级缺城市 | lon=-75.55787534831364 lat=39.11014801382173 | sources.record_id=5C4539D7-2E7F-4D94-A19D-5B2D076CE75E
#6  id=853ad2c7-211a-412c-b0ce-aa3dd01298aa | number='333' | street='WYNSOME Boulevard' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.56162683282119 lat=39.111497255085254 | sources.record_id=C509D07F-DBD1-4E1D-A2AE-1060220B7593
#7  id=6f04db18-b645-4a3b-8c39-36857ac70090 | number='329' | street='WYNSOME Boulevard' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.56165238289569 lat=39.111425723519616 | sources.record_id=A75A8FE3-FE33-40E2-85E4-9728930D5BB9
#8  id=7c2693c6-1d37-4205-a777-07ddeda5c50a | number='309' | street='WYNSOME Boulevard' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.56174725025733 lat=39.1111453288603 | sources.record_id=D8E83554-B358-4197-AE21-E56069D1F225
#9  id=f6f9e127-d6d5-4487-94f9-8a73a24c70c6 | number='1679' | street='South STATE Street' | unit=None | postal_city='Dover' | postcode='19901' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.51734346746412 lat=39.1295876163482 | sources.record_id=A3605EB3-1BEA-49FA-9AAC-7CC92A7CDDB1
#10 id=91af85b3-7237-44e5-8bdf-cc23a8a37dd8 | number='1679' | street='South STATE Street' | unit=None | postal_city='Dover' | postcode='19901' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.51719969051172 lat=39.12961634045743 | sources.record_id=78C9793F-C29A-4208-859D-171F093F458C
#11 id=889cbf3e-4412-4b38-8fa7-91a29bbbd46d | number='1679' | street='South STATE Street' | unit=None | postal_city='Dover' | postcode='19901' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.51686017657919 lat=39.12971434898367 | sources.record_id=2F236D31-4820-4946-A121-021FA0CB5FDB
#12 id=bedf99e1-56dc-47bb-8a63-a62563b261a8 | number='1679' | street='South STATE Street' | unit=None | postal_city='Dover' | postcode='19901' | country='US' | version=1 | address_levels=[{"value":"DE"}] | lon=-75.51748558124777 lat=39.129835487942806 | sources.record_id=E63E25F2-3F70-4858-A5B1-1331FBED94D7
     ↑ #9~#12 属于"132 条同址不同坐标"的极端例：同一门牌号，坐标各不相同
#13 id=0dd867b2-4f90-4d29-9d43-d08bba9eb9c1 | number='455' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.5843265232578 lat=39.100539161446044 | sources.record_id=61427C58-F858-44A1-8FA0-B077E12AA530
#14 id=6384c3b3-d38c-4398-a8f5-0a49d5a60eb2 | number='591' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.5863637630371 lat=39.10052021917413 | sources.record_id=9D2B4F54-A70B-4B13-9304-03458F780DD5
#15 id=bd68dd27-130a-4454-b37f-f8a625ac5bd1 | number='643' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.58883086229955 lat=39.10101358134956 | sources.record_id=45919889-85C2-4C94-BDAD-6E4A3A184C80
#16 id=7825fa90-7bbc-4dc2-8666-5d548facc661 | number='657' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.59109036870981 lat=39.10448637341052 | sources.record_id=C172E5D0-918C-444E-8F9E-B534FAB31081
#17 id=7d5ecf48-49bf-48cd-9b10-d63669c1f4b3 | number='25' | street='NEO Circle' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.58283847947078 lat=39.10187464517025 | sources.record_id=A7E20386-ECE5-4498-934D-18165A1D2335
#18 id=5e578961-610a-414a-9957-6cef5da81bdd | number='597' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.58353115914579 lat=39.10216273963741 | sources.record_id=B4190A35-DB0A-44B1-A58D-B5C658F95BEC
#19 id=61456884-dc40-48cb-98ec-a0eb5420e495 | number='603' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.58188484699689 lat=39.10252195858388 | sources.record_id=DAEE1C3D-0F33-4E8D-8E98-C329A64D2A8E
#20 id=c1c84d59-fb63-4981-aaad-04366fef3c27 | number='561' | street='MOOSE LODGE Road' | unit=None | postal_city='Camden Wyoming' | postcode='19934' | country='US' | version=1 | address_levels=[{"value":"DE"},{"value":"Camden Wyoming"}] | lon=-75.58207921138221 lat=39.101986657484005 | sources.record_id=8C31D63D-8D1F-400A-BB21-D9207EFC0186
```

---

## 四、对 24 字段合并的结论（供 Gemini 参考）

1. **Overture ≠ 独立源**：28,027 条全部 `dataset=NAD`，是 NAD 的下游衍生物。S 级"多源交叉验证"实际只有 **OpenAddresses** 一个民间独立源 + TIGER 官方号段/边界做空间校验。**必须在交付里写明，否则 S 级可信度虚高。**
2. **不能按 (门牌 + 街名) 去重 Overture**：`1679 South STATE Street` 一门牌 132 条 / 132 个不同坐标（无 unit）。要么坐标聚类，要么以 NAD 点为准做最近邻匹配。
3. **两源对齐前必须规范化**（差异是硬伤）：
   - NAD：`number` 是 Integer + 街道拆 4 段 + `St_Name` 全大写 + 22 个受控全称后缀 + 方向词全称
   - Overture：`number` 字符串 + 街道一整串混合大小写 + 无前/后缀拆分 + `address_levels` 无 level 标签且 1,652 条缺城市 + `unit` 有字面 `"<Null>"` 脏值
   - 直接字符串比较命中率会极低，必须先统一为「门牌 + 归一化街名（去方向词/后缀变体）+ 归一化 unit」
