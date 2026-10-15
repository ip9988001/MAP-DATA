# OpenAddresses 多佛数据 · 字段结构与格式分析报告

- 来源：GitHub Release `ip9988001/world-map-data-test` @ `dover-raw-20261015-0450`
- 相关资产：**5 个 zip**（`city_of_dover` / `kent` / `city_of_newark` / `new_castle` / `sussex`）
- 每个 zip 内含 3 个文件：`README.txt` + `<name>.vrt` + `<name>.csv`（**真正的数据是 `.csv`**）
- 数据格式：**CSV**（UTF-8，逗号分隔，无引号，空值 = 连续逗号）

---

## 一、先厘清「哪些是 Dover 数据」

| zip | csv 数据行数 | 与 Dover 关系 |
|---|---|---|
| **`city_of_dover`** | **12,732** | ✅ 多佛市本体 |
| **`kent`** | **79,723** | ✅ 多佛所在的 Kent 县（含 CITY=Dover 26,674 行） |
| `city_of_newark` | 7,221 | ❌ 纽瓦克市（New Castle 县） |
| `new_castle` | 271,150 | ❌ New Castle 县 |
| `sussex` | 183,031 | ❌ Sussex 县 |
| **合计（5 个）** | **553,857** | — |

> **关键澄清**：早前报告里写的「OpenAddresses `us/de` 全量 **92,455** 行」，实际 = `city_of_dover.csv`(12,732) + `kent.csv`(79,723) = **92,455**。
> 也就是说，本批 OpenAddresses 的「多佛数据」= **city_of_dover + kent 两个文件，共 92,455 行**，而不是整个特拉华州（全州其实是 553,857 行）。
> 另：Dover bbox `[-75.6,39.1,-75.45,39.22]` 过滤后只有 40,215 行（city_of_dover 12,731 + kent 27,484），说明 **bbox 之外还有大量 Kent 县地址**。

---

## 二、字段组成：固定 11 列

CSV 表头（5 个文件完全一致）：
```
LON,LAT,NUMBER,STREET,UNIT,CITY,DISTRICT,REGION,POSTCODE,ID,HASH
```

**11 列，全部为字符串（无类型区分）**，**无嵌套、无对象**——是四源里最扁平的宽表。

| # | 列名 | 含义 | 合并后 92,455 行非空率 |
|---|---|---|---|
| 1 | `LON` | 经度 | **100.00%** |
| 2 | `LAT` | 纬度 | **100.00%** |
| 3 | `NUMBER` | 门牌号 | **99.30%**（91,808） |
| 4 | `STREET` | 完整街道名 | **99.96%**（92,421） |
| 5 | `UNIT` | 室号 | **0.62%**（577） |
| 6 | `CITY` | 城市名 | **80.41%**（74,340） |
| 7 | `DISTRICT` | 县/区 | **0.00%（全空）** |
| 8 | `REGION` | 州 | **0.00%（全空）** |
| 9 | `POSTCODE` | 5 位邮编 | **86.00%**（79,512） |
| 10 | `ID` | 原始记录 ID | **0.00%（全空）** |
| 11 | `HASH` | 去重哈希 | **100.00%** |

**分文件非空率**

| 列 | city_of_dover (12,732) | kent (79,723) |
|---|---|---|
| LON / LAT | 100% | 100% |
| NUMBER | 95.90% | 99.84% |
| STREET | 100% | 99.96% |
| UNIT | **0.00%** | 0.72% |
| CITY | **0.00%** | 93.25% |
| DISTRICT | 0% | 0% |
| REGION | 0% | 0% |
| POSTCODE | **0.00%** | 99.74% |
| ID | 0% | 0% |
| HASH | 100% | 100% |

> **重点**：`city_of_dover.csv` **完全没有** CITY / POSTCODE / REGION / UNIT（只有 门牌+街道+坐标+哈希）；只有 `kent.csv` 带 CITY 与 POSTCODE。所以做合并时，Dover 本体的城市/邮编必须靠空间落点或 kent 文件补齐。

---

## 三、地址信息的规则 / 架构 / 结构

**架构（极简三层）**
```
zip → 同名 csv（+ .vrt 空间声明 + README）
csv  → 每行 1 个地址点，11 列定长
坐标 → LON / LAT 两列直接给经纬度（无 geometry 字段）
```
`.vrt` 内容（OGR 虚拟图层声明，把 CSV 变成空间点图层）：
```xml
<OGRVRTDataSource>
  <OGRVRTLayer name="city_of_dover">
    <SrcDataSource relativeToVRT="1">city_of_dover.csv</SrcDataSource>
    <GeometryType>wkbPoint</GeometryType>
    <LayerSRS>EPSG:4326</LayerSRS>
    <GeometryField encoding="PointFromColumns" reportSrcColumn="FALSE" x="LON" y="LAT"/>
  </OGRVRTLayer>
</OGRVRTDataSource>
```

**拼装规则**
```
完整地址 = [NUMBER + " "] + STREET + [", " + UNIT] + [", " + CITY] + [", " + REGION] + [" " + POSTCODE]
```
> `STREET` 是**整串拼好的街道名**（含方向前缀与类型后缀），**不再拆分**，与 Overture 一致。

---

## 四、格式规范（写解析/合并代码必须遵守）

| 列 | 格式 | 示例 |
|---|---|---|
| `LON` / `LAT` | 十进制经纬度，约 7 位小数，**经度在前** | `-75.5004951` / `39.1477108` |
| `NUMBER` | 字符串，纯数字（92,455 条**无一条含字母**） | `835` `1207`（可空） |
| `STREET` | **全大写**；方向词用**单字母缩写** `N/S/E/W`；类型后缀**混用 USPS 缩写与全称** | `BAY RD` `W DENNEYS RD` `S LITTLE CREEK RD` `WYOMING AVE` |
| `UNIT` | `APT x` / 单字母；**有字面值 `<Null>`（kent 112 条）** | `APT I` `APT B` |
| `CITY` | Title Case（仅 kent 有） | `Dover` `Smyrna` |
| `DISTRICT` / `REGION` / `ID` | **恒空** | — |
| `POSTCODE` | 5 位字符串（仅 kent 有） | `19901` |
| `HASH` | **16 位十六进制**去重哈希 | `c85c28b35deef008` |

**STREET 类型后缀分布（暴露格式不一致）**
- `city_of_dover` 以 USPS 缩写为主：`DR` 3489 / `ST` 2175 / `RD` 1819 / `AVE` 1322 / `CT` 723 / `WAY` 710 / `PL` 602 / `LN` 510 / `BLVD` 384 / `CIR` 309 / `HWY` 253
- `kent` 缩写 + 全称 + 大小写混杂：`RD` 21102 / `DR` 18278 / `ST` 9085 / `LN` 7402 … 但也有 `DRIVE` 618 / `LANE` 538 / `COURT` 251 / `STREET` 201 / `ROAD` 199 / `AVENUE` 138，以及**大小写不规范**的 `Dr` 243、`Apt` 100

**方向词**：`kent` 首词 Top 为 `S` 3705 / `N` 3299 / `W` 2250 / `E` 1601（单字母缩写，与 NAD/Overture 的 `South/North` 全拼**不同**）。

---

## 五、数据质量提示

1. **`<Null>` 字面值**：`UNIT` 列有 112 条（kent）填的是字符串 `<Null>`，不是空值，解析时需专门清洗。
2. **STREET 后缀不统一**：同一批数据里 `RD`/`ROAD`、`AVE`/`AVENUE`、`Dr`/`DR` 混用，做四源合并前必须先归一化。
3. **city_of_dover 缺城市与邮编**：该文件 0% CITY、0% POSTCODE，合并时需靠 bbox / kent 兜底。
4. **DISTRICT / REGION / ID 三列全空**，是纯占位列。
5. **与 NAD 有重叠但来源不同**：例如 `5921 W DENNEYS RD APT I, Dover, 19901`、`3937 SEVEN HICKORIES RD APT B, Dover, 19904` 在两源都出现，可用作跨源核验样本。
6. **打包时间很旧**：README 显示 `city_of_dover` 打包于 **2021-10-10**、`kent` 于 **2021-10-17**，比 NAD（2025-09）旧约 4 年。

---

## 六、抽检 20 条原始记录

见 `openaddresses_sample20.csv`（原始 CSV，含表头）。
