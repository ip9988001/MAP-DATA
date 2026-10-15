# NAD（USDOT 官方地址点）多佛数据 · 字段结构与格式分析报告

- 分析对象：`nad_dover_full.ndjson`
- 来源：GitHub Release `ip9988001/world-map-data-test` @ `dover-raw-20261015-0450`
- 文件大小：40,501,682 B（38.6 MB）
- 记录数：**28,028 行**（每行 1 条 JSON 记录，NDJSON，UTF-8，解析失败 0 条）
- 配套文件：`nad_full_columns.json`（官方列清单）、`nad_native_metadata.json`（ArcGIS FeatureServer 元数据）
- 上游服务：`Address_Points_from_National_Address_Database`（Feature Layer），版权方含 **Kent County Delaware**

---

## 一、字段组成：60 官方列 + 2 注入列 = 62 键

| 项 | 值 |
|---|---|
| 官方字段数 | **60**（`nad_full_columns.json` 的 `fields_n = 60`） |
| ndjson 实际键数 | **62** |
| 多出的 2 个 | `_lon`、`_lat`（导出脚本注入的几何坐标副本，非官方字段） |
| 键集合一致性 | 28,028 行**只有 1 种键组合**、顺序完全固定 → 严格定长宽表 |
| 值类型 | 仅 4 种：`string` / `int` / `float` / `null` |

> 注意：官方 60 列里已有 `Longitude` / `Latitude`（属性坐标），`_lon` / `_lat` 是几何坐标，两者数值**接近但不相等**（如 `-75.58606037592598` vs `-75.58606037576688`）。

---

## 二、60 字段分 10 组（功能分组）

| 组 | 组名 | 字段数 | 字段 |
|---|---|---|---|
| 1 | 标识与溯源 | 11 | `OBJECTID` `UUID` `DataSet_ID` `AddAuth` `NAD_Source` `AddrRefSys` `DateUpdate` `Effective` `Expire` `Lifecycle` `AnomStatus` |
| 2 | 门牌号 | 4 | `AddNum_Pre` `Add_Number` `AddNum_Suf` `AddNo_Full` |
| 3 | 街道名 | 9 | `St_PreMod` `St_PreDir` `St_PreTyp` `St_PreSep` `St_Name` `St_PosTyp` `St_PosDir` `St_PosMod` `StNam_Full` |
| 4 | 子地址/单元 | 7 | `Building` `Floor` `Unit` `Room` `Seat` `Addtl_Loc` `SubAddress` |
| 5 | 地标 | 1 | `LandmkName` |
| 6 | 行政区划 | 12 | `County` `Inc_Muni` `Post_City` `Census_Plc` `Uninc_Comm` `Nbrhd_Comm` `NatAmArea` `NatAmSub` `Urbnztn_PR` `PlaceOther` `PlaceNmTyp` `State` |
| 7 | 邮编 | 2 | `Zip_Code` `Plus_4` |
| 8 | 坐标与网格 | 6 | `Longitude` `Latitude` `NatGrid` `Elevation` `Placement` `AddrPoint` |
| 9 | 地址分类 | 3 | `AddrClass` `Addr_Type` `DeliverTyp` |
| 10 | 关联与地块 | 5 | `Related_ID` `RelateType` `ParcelSrc` `Parcel_ID` `LocatnDesc` |

合计 11+4+9+7+1+12+2+6+3+5 = **60** ✓

---

## 三、填充率三档（基于全量 28,028 行实测）

### A. 100% 恒有字段（25 个）
`OBJECTID` `Add_Number` `AddNo_Full` `St_Name` `StNam_Full` `County` `Inc_Muni` `Post_City` `Nbrhd_Comm` `State` `Zip_Code` `UUID` `AddAuth` `Longitude` `Latitude` `NatGrid` `Placement` `AddrPoint` `AddrClass` `DateUpdate` `Addr_Type` `NAD_Source` `DataSet_ID` `_lon` `_lat`

### B. 部分填充字段（7 个）
| 字段 | 非空率 | 条数 | 说明 |
|---|---|---|---|
| `St_PosTyp` | 99.38% | 27,853 | 175 条无街道后缀（如 `CORBIN'S CLOSE`） |
| `St_PreDir` | 17.15% | 4,806 | South 1958 / North 1675 / West 632 / East 541 |
| `Census_Plc` | 16.38% | 4,590 | 如 `Highland Acres CDP` `Dover Base Housing CDP` |
| `NatAmArea` | 2.77% | 776 | 仅 `Lenape Indian Tribe of Delaware SDTSA` |
| `St_PosDir` | 0.29% | 82 | West 33 / Northeast 27 / South 11 / Southwest 10 / North 1 |
| `Unit` | 0.19% | 52 | APT/STE 为主 |
| `SubAddress` | 0.19% | 52 | 与 `Unit` **完全同值** |

### C. 全空（死）字段（30 个）
`AddNum_Pre` `AddNum_Suf` `St_PreMod` `St_PreTyp` `St_PreSep` `St_PosMod` `Building` `Floor` `Room` `Seat` `Addtl_Loc` `LandmkName` `Uninc_Comm` `NatAmSub` `Urbnztn_PR` `PlaceOther` `PlaceNmTyp` `Plus_4` `AddrRefSys` `Elevation` `Related_ID` `RelateType` `ParcelSrc` `Parcel_ID` `Lifecycle` `Effective` `Expire` `AnomStatus` `LocatnDesc` `DeliverTyp`

> 25 + 7 + 30 = 62 ✓

---

## 四、地址拼装规则

```
门牌号   AddNo_Full  = AddNum_Pre + Add_Number + AddNum_Suf        （后两段实测全空）
街道名   StNam_Full  = St_PreDir + St_Name + St_PosTyp + St_PosDir （前修饰/前类型/后修饰实测全空）
子地址   SubAddress  = Unit
完整地址 = AddNo_Full + " " + StNam_Full + [", " + SubAddress] + ", " + Inc_Muni + ", " + State + " " + Zip_Code
```

示例：
- `1991` + `South STATE Street` → **1991 South STATE Street, Dover, DE 19901**
- `5921` + `West DENNEYS Road` + `APT I` → **5921 West DENNEYS Road, APT I, Dover, DE 19901**
- `10` + `BAY Circle South` → 后方向词在末尾：**10 BAY Circle South, Dover, DE 19904**

---

## 五、格式规范（写代码解析时必须遵守）

| 字段 | 格式 | 示例 |
|---|---|---|
| `Add_Number` | 整数 | `1991` |
| `St_Name` | **全大写**，不含方向词/后缀 | `STATE` `DENNEYS` `COMMERCE` |
| `St_PosTyp` | **Title Case 全称**，非 USPS 缩写 | `Street` `Road` `Drive` `Highway` `Way` |
| `St_PreDir` / `St_PosDir` | **全拼**方向词 | `South` `North` `West` `East` |
| `Zip_Code` | 5 位字符串 | `19901` |
| `NatGrid` | 美国国家网格，15 位 | `18SVJ5545330177` |
| `AddrPoint` | `"经度 纬度"` 空格分隔 | `-75.51531368210591 39.11962309843974` |
| `DateUpdate` | epoch **毫秒** | `1760659200000` |
| `DataSet_ID` | `{` + UUID + `}` | `{7fc165b9-d2a7-483d-83ff-c6023d50acb6}` |
| `AddrClass` | 恒为 | `Numbered Thoroughfare Address` |
| `Placement` / `Addr_Type` | 恒为 | `Unknown` |
| `AddAuth` / `NAD_Source` | 恒为 | `Kent County Delaware` |

---

## 六、数据质量提示

1. **`Inc_Muni` 有脏值**：`DOVER` `DOver` `Dpver` `Dover6` 等拼写错误，说明上游未做规范化。
2. **覆盖范围 > 多佛市**：Zip 除 `19901`(12093) / `19904`(11954) 外，还有 `19934`(2958) `19962`(429) `19936`(373) `19902`(220) `19961`(1)；`Inc_Muni` 含 Camden Wyoming / Cheswold / Magnolia / Unincorporated 等 → 该文件是 **Kent 县 bbox 范围**，不是纯 Dover 市。
3. **30 个字段全空**：`Plus_4` 全空（9 位邮编需靠 TIGER 补齐）、`Unit` 仅 0.19% —— 与早前摘要一致。
4. `Placement` / `Addr_Type` 全为 `Unknown`，无法据此判断屋顶/地块精度与住商属性。

---

## 七、抽检 20 条原始记录

见 `nad_sample20.ndjson`（原始行）与 `nad_sample20_pretty.json`（美化版）。
