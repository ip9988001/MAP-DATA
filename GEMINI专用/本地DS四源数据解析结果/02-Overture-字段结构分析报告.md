# Overture Maps 多佛数据 · 字段结构与格式分析报告

- 分析对象：`overture_addresses.geojson`
- 来源：GitHub Release `ip9988001/world-map-data-test` @ `dover-raw-20261015-0450`
- 文件大小：16,452,588 B（15.7 MB）
- 记录数：**28,027 个 Feature**
- 格式：GeoJSON `FeatureCollection`（无 `crs` 字段，默认 WGS84）
- 几何：**28,027 条全部为 `Point`**，`coordinates` = `[经度, 纬度]`

---

## 一、字段组成：3 层结构，9 个属性列

### 层级 1：顶层（FeatureCollection）
`type` + `features`（2 个键）

### 层级 2：每个 Feature 固定 4 键（28,027 条键组合唯一）
| 键 | 值 |
|---|---|
| `id` | UUID（28,027/28,027 全有） |
| `type` | 恒为 `"Feature"` |
| `geometry` | `{"type":"Point","coordinates":[lon,lat]}` |
| `properties` | 属性对象（见下） |

### 层级 3：`properties` —— 2 种变体（8 键 / 9 键）
| 变体 | 键数 | 条数 | 说明 |
|---|---|---|---|
| 基础版 | **8** | 27,975（99.81%） | 无 `unit` |
| 带单元版 | **9** | 52（0.19%） | 多一个 `unit` |

> 即：**地址属性共 9 个字段**（`unit` 为可选字段）。加上 `id` 与 `geometry`，一条 Feature 共 12 个数据位。

---

## 二、9 个属性字段逐项

| # | 字段 | JSON 类型 | 非空率 | 说明 |
|---|---|---|---|---|
| 1 | `street` | string | **100%** | 完整街道名（含类型/方向） |
| 2 | `number` | **string**（非数字） | **100%** | 门牌号，28,027 条全为纯数字 |
| 3 | `unit` | string | 0.19%（52） | 室号，**可选字段** |
| 4 | `postcode` | string | **100%** | 5 位邮编 |
| 5 | `postal_city` | string | **100%** | 邮政城市名 |
| 6 | `address_levels` | **array\<object\>** | **100%** | 行政层级数组 |
| 7 | `country` | string | **100%** | 恒为 `US` |
| 8 | `sources` | **array\<object\>** | **100%** | 溯源数组 |
| 9 | `version` | **int** | **100%** | 恒为 `1` |

> 只有 3 种值类型：`string` / `array` / `int`；无 `null`、无 `float`、无嵌套深层对象。

---

## 三、嵌套字段结构

### `address_levels`（数组，长度 2 或 1）
```json
[{"value": "DE"}, {"value": "Dover"}]     // 州 + 市（26,375 条）
[{"value": "DE"}]                          // 仅州（1,652 条）
```
- 长度分布：2 元素 26,375 条 / 1 元素 1,652 条
- 只有 `value` 一个键，**无 level 类型标记**（靠位置区分：第 0 位=州，第 1 位=市）

### `sources`（数组，每个 Feature 恒 1 条）
```json
[{
  "property": "",
  "dataset": "NAD",
  "license": "LicenseRef-Public-Domain-US",
  "record_id": "0F3629D8-FD1E-4108-89A3-7E177819182F",
  "update_time": "2026-09-18T19:39:08.275Z",
  "confidence": null,
  "between": null,
  "provider": "nad",
  "resource": "nad",
  "version": "20250924"
}]
```
- 9 个子键；`dataset` 全为 `NAD`、`provider` 全为 `nad`、`license` 全为 `LicenseRef-Public-Domain-US`
- `confidence` / `between` 恒为 `null`
- `record_id` 是 UUID；`update_time` 为 ISO8601 毫秒

---

## 四、地址拼装规则

```
完整地址 = number + " " + street + [", " + unit] + ", " + postal_city + ", " + address_levels[0] + " " + postcode
```
示例：
- `401` + `NORTHDOWN Drive` + `Dover, DE 19901` → **401 NORTHDOWN Drive, Dover, DE 19901**
- `11540` + `WILLOW GROVE Road` + `STE B` + `Camden Wyoming, DE 19934` → **11540 WILLOW GROVE Road, STE B, Camden Wyoming, DE 19934**

**街道名内嵌规则**：`street` 是**拼好的一整串**，不再拆分：
```
street = [方向词(全拼)] + " " + 核心路名(全大写) + " " + 类型词(Title Case)
```
- 方向前缀共 4,804 条：`South` 1956 / `North` 1675 / `West` 632 / `East` 541（如 `South STATE Street`、`East NOCK Lane`）
- 类型词 Top：`Drive` 7877 / `Road` 4395 / `Street` 3781 / `Avenue` 2577 / `Court` 2021 / `Lane` 1990 / `Way` 1130 / `Circle` 893 / `Place` 843 / `Boulevard` 753 / `Highway` 550 …
- 有 93 条末尾是 `HALL`（无标准类型后缀，如地名式街道）

---

## 五、格式规范（写解析/合并代码必须遵守）

| 字段 | 规则 | 示例 |
|---|---|---|
| `id` | UUID 字符串 | `aab767eb-5a80-405c-85e8-e92f39d11b4b` |
| `geometry` | `Point`，`[lon, lat]` | `[-75.56340680224665, 39.10176111483698]` |
| `number` | **字符串**（不是 int） | `"11540"` |
| `street` | 全大写路名 + Title Case 类型 | `WILLOW GROVE Road` `South STATE Street` |
| `unit` | `APT x` / `STE x` / `LOT 268` / 单字母 | `STE B`（注意有 1 条字面值 `"<Null>"`） |
| `postcode` | 5 位字符串 | `19934` |
| `postal_city` | Title Case | `Dover` `Camden Wyoming`（1 条 `DOVER`） |
| `address_levels` | `[{"value":州},{"value":市}]` | `[{"value":"DE"},{"value":"Dover"}]` |
| `country` | 恒为 | `US` |
| `version` | 恒为 | `1` |

---

## 六、⚠️ 重大发现：Overture 本批数据 100% 源自 NAD

用 `record_id` 与 NAD 的 `UUID` 逐一比对（28,027 vs 28,028）：

| 比对项 | 结果 |
|---|---|
| `sources.dataset` 取值 | **全部 = `NAD`**（28,027/28,027） |
| `sources.provider` | **全部 = `nad`** |
| Overture `record_id` ∩ NAD `UUID` | **28,026 / 28,027 完全命中** |
| 唯一不同的一条 | `46 WILDBERRY Drive`（record_id `7A6334FF-...` 不在本批 NAD 中） |
| NAD 有而 Overture 无 | 2 条：`890 South STATE Street`、`889 South STATE Street` |
| `(number, street)` 去重集合 | NAD 27,128 / Overture 27,129，交集 27,128 |

**结论：本批 Overture 的多佛地址数据不是独立第三方源，而是 NAD 的再包装（re-packaging）**。
- 对去重合并任务而言，**Overture 与 NAD 不能视为两条独立证据**，若按"多源交叉命中提升置信度"计算，会把同一份 NAD 数据重复计数。
- 邮编分布也几乎与 NAD 逐项一致（19901: 12093、19904: 11953 vs NAD 11954、19934: 2958、19962: 429、19936: 373、19902: 220、19961: 1）。
- 覆盖范围同样**是 Kent 县 bbox**，非纯多佛市（`postal_city` 含 Camden Wyoming 2956 / Magnolia 429 / Cheswold 401 / Little Creek 1）。

---

## 七、抽检 20 条原始记录

见 `overture_sample20.geojson`。
