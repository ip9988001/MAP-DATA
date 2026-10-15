# 四源多佛地址数据 · 字段结构分析成果合集

> 生成日期：2026-10-15
> 数据来源：GitHub Release `ip9988001/world-map-data-test` @ `dover-raw-20261015-0450`
> 分析方式：**全部文件下载到本地后逐行/逐字节解析实测**，字段名与填充率均以文件真实内容为准（非转述摘要）。

---

## 一、本次做了什么

对多佛（Dover, DE）四个数据源的**全量原始数据**逐一下载、解析、抽检 20 条完整原始记录，并梳理其字段组成、列数、地址拼装规则、数据结构与格式规范，最后汇总成四源字段对照总表。

| 轮次 | 内容 | 对应文件 |
|---|---|---|
| 1 | 切分 `Gemini指令.txt` 为 5 份 | `07-对话文字报告/A-...md` |
| 2 | 80 条样本按获取源分组（表格版） | `07-对话文字报告/B-...md` |
| 3 | 80 条样本逐字原始格式版 | `07-对话文字报告/C-...md` |
| 4 | GitHub Release 四源文件辨识 | `07-对话文字报告/D-...md` |
| 5 | **NAD** 抽检 20 条 + 字段结构分析 | `01-NAD-字段结构分析报告.md` + `06-样本/` |
| 6 | **Overture** 抽检 20 条 + 字段结构分析 | `02-Overture-字段结构分析报告.md` + `06-样本/` |
| 7 | **OpenAddresses** 抽检 20 条 + 字段结构分析 | `03-OpenAddresses-字段结构分析报告.md` + `06-样本/` |
| 8 | **TIGER** 抽检 20 条 + 字段结构分析 | `04-TIGER-字段结构分析报告.md` + `06-样本/` |
| 9 | 四源字段对照总表 | `05-四源字段对照总表.md` / `.csv` |

---

## 二、目录结构

```
四源分析成果-2026-10-15/
├── README.md                                   ← 本文件（总索引）
├── 01-NAD-字段结构分析报告.md                    ← 源A（60列宽表）
├── 02-Overture-字段结构分析报告.md               ← 源B（9属性）
├── 03-OpenAddresses-字段结构分析报告.md          ← 源C（11列）
├── 04-TIGER-字段结构分析报告.md                  ← 源D（25字段号段表+边界）
├── 05-四源字段对照总表.md                        ← 汇总（含反向映射表）
├── 05-四源字段对照总表.csv                       ← 汇总（机读版）
├── 06-样本/
│   ├── nad_sample20.ndjson                     ← NAD 20 条原始行
│   ├── nad_sample20_pretty.json                ← NAD 20 条美化版
│   ├── overture_sample20.geojson               ← Overture 20 条原始 Feature
│   ├── openaddresses_sample20.csv              ← OpenAddresses 20 条原始 CSV
│   ├── tiger_addrfeat_sample20.csv             ← TIGER 20 条原始 DBF 值
│   └── tiger_boundaries_summary.json           ← TIGER 边界文件结构汇总
└── 07-对话文字报告/
    ├── A-Gemini指令-五份科学切分.md
    ├── B-80条样本按获取源分组.md
    ├── C-80条样本-逐字原始版.md
    └── D-GitHub-Release-数据文件辨识.md
```

---

## 三、四源速览

| 项 | A · NAD | B · Overture | C · OpenAddresses | D · TIGER |
|---|---|---|---|---|
| 文件 | `nad_dover_full.ndjson` | `overture_addresses.geojson` | `city_of_dover.csv`+`kent.csv` | `addrfeat.zip`+5 边界 |
| 格式 | NDJSON | GeoJSON | CSV | Shapefile / **Esri JSON** |
| 规模 | 28,028 行 | 28,027 Feature | **92,455 行** | 11,072 记录 |
| 字段数 | 60 官方 +2 注入 = **62 键** | **9 属性** | **11 列** | **25 字段** |
| 几何 | 点 | 点 | 点 | **线 / 面** |
| 性质 | ✅ 地址点 | ✅ 地址点 | ✅ 地址点 | ❌ 号段表 + 边界 |
| 时效 | 2025-09 | 2026-09 | 2021-10 | 2024 |

---

## 四、核心结论（8 条）

1. **Overture ≈ NAD，不是独立源**：本批 Overture 的 `sources.dataset` 全为 `NAD`，28,026/28,027 的 `record_id` 与 NAD `UUID` 一一对应 → 去重合并时**不可当两条独立证据**。
2. **`plus4`（9 位邮编后 4 位）四源全部拿不到**：NAD `Plus_4` 全空、TIGER `PLUS4L/PLUS4R` 全空、Overture 与 OA 无此字段 → `zip9` 只能退化为 `zip5`。
3. **`building_floor` 与 `house_number_suffix` 无任何来源**，建议从黄金表删除或长期置 null。
4. **`addr_type` 名义有值但无信息量**：NAD `Addr_Type` 本批 100% 为 `Unknown`，`Placement` 同样全 `Unknown`。
5. **只有 NAD 原生拆好了街道**（`St_Name`/`St_PosTyp`/`St_PreDir`/`St_PosDir`）；Overture、OA、TIGER 的街道都是**一整串**，且**方向词粒度不一致**（NAD/Overture 全拼 `South`，OA/TIGER 单字母 `S`）、**后缀缩写不统一**（`Street` vs `ST` vs `Rd`）。
6. **`unit` 有脏值**：OA 的 `UNIT` 有字面值 `<Null>`（kent 112 条），Overture 也有 1 条 `<Null>`。
7. **`city_of_dover.csv` 缺 CITY/POSTCODE**（均 0%）→ 多佛本体的城市与邮编要靠空间落点或 `kent.csv` 补齐。
8. **TIGER 与另三源性质不同**：TIGER 是道路号段 + 行政多边形，**不能直接当点地址参与合并**；另外 **4 个 `.geojson` 边界文件实为 Esri JSON**（`attributes` + `geometry.rings`），不是标准 GeoJSON；`TLID` 也**不是唯一键**（11,072 行 / 9,939 个），号段区间存在降序（如 `8698→8618`），判断时须取 min/max。

**建议取值优先级**：`NAD > TIGER > Overture > OA`（Overture 与 NAD 同源，优先级等同，`source_confidence` 里合并计 1 票）。

---

## 五、注意事项

- 本合集中的 `06-样本/` 为**抽样**（每源 20 条），全量数据请以 Release `dover-raw-20261015-0450` 的原始资产为准。
- 三个源（NAD / Overture / OpenAddresses）**均为 Kent 县 bbox 范围**，不是纯多佛市；只有 TIGER 的 `place_dover` 是精确市界。
- 本合集中的分析脚本未随附；如需复现，可按各报告中的字段定义重新解析。
