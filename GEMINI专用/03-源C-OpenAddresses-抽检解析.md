# 源 C · OpenAddresses（us/de）抽检与结构解析

> 抽检人：PI-Agent　时间：2026-10-15　用途：供 Gemini 参考 24 字段黄金表/合并规则的架构依据
> 数据文件（仓库内原始压缩包）：
> - `data/dover/raw/openaddresses_kent.zip` → `us/de/kent.csv`，**79,723 行**
> - `data/dover/raw/openaddresses_city_of_dover.zip` → `us/de/city_of_dover.csv`，**12,732 行**
> 全量对应产物（GitHub Release `dover-raw-20261015-0450`）：`us/de` **全部 5 个源**原始 zip（city_of_dover / kent / city_of_newark / new_castle / sussex）

---

## 一、包结构与列组成

**压缩包内 3 个成员**：
- `README.txt` → 打包时间 **2021-10-17**；**Website: Unknown；License: Unknown**（⚠️ 许可不明确，与 NAD 公有领域、Overture 标注 LicenseRef-Public-Domain-US 不同）
- `us/de/kent.vrt` → OGR VRT：`LayerSRS=EPSG:4326`，`GeometryField encoding="PointFromColumns" x="LON" y="LAT"`（几何由 LON/LAT 两列生成）
- `us/de/kent.csv` → 数据本体

**11 列，坐标打头**：`LON, LAT, NUMBER, STREET, UNIT, CITY, DISTRICT, REGION, POSTCODE, ID, HASH`

### 逐列实测（基于 kent.csv 79,723 行）
| 列 | 非空率 | 唯一值 | 格式 / 例 |
|---|---|---|---|
| `LON` | **100%** | 76,766 | 字符串，**4~7 位小数**（7位 71,764 / 6位 7,157 / 5位 733 / 4位 61 / 3位 8）例 `-75.589069` |
| `LAT` | **100%** | 77,174 | 同上，例 `39.3093249` |
| `NUMBER` | 99.84% | 6,733 | 纯数字字符串，1~5 位；**240 条 = `"0"`** |
| `STREET` | 99.96% | 3,769 | **全大写 + USPS 缩写**，例 `KING ST` / `W DENNEYS RD` |
| `UNIT` | 0.72% | 181 | **112 条为字面字符串 `<Null>`** |
| `CITY` | 93.00% | 43 | **111 条为字面 `<Null>`**，5,383 条真空 |
| `DISTRICT` | **0.00%** | 0 | 全空（本应是县） |
| `REGION` | **0.00%** | 0 | 全空（本应是州）→ **OA 里没有州字段**，州只能靠路径 `us/de/` 推断 |
| `POSTCODE` | 99.74% | 17 | 例 `19904` |
| `ID` | **0.00%** | 0 | 全空（OA 标准本应是 `us/de/kent:xxxxx`） |
| `HASH` | **100%** | 79,599 | 16 位十六进制（MD5 前缀），例 `897254e1c51b6384`，OA 自带去重键 |

**值分布**：
- `CITY` 前 8：Dover 26674 / Smyrna 10734 / Felton 6066 / Camden Wyoming 6014 / `''` 5383 / Magnolia 4823 / Harrington 4518 / Clayton 4103
- `POSTCODE` 前 10：19904 15465 / 19901 13612 / 19977 11628 / 19943 6618 / 19934 6132 / 19962 5518 / 19952 4846 / 19938 4291 / 19963 4139 / 19946 2324
- `UNIT` 前若干：`<Null>` 112 / `A` 69 / `B` 59 / `APT A` 41 / `APT B` 28 / `APT C` 13 / `APT 1` 13 / `C` 8 / `APT D` 5 / `APT 2` 5 / `D` 5 / `APT 3` 4
- 坐标范围：lon −75.7574925 ~ −75.3247364（**整个 Kent 县**，远大于 Dover bbox）

> ⚠️ 口径提醒：若引用「us/de 全州」聚合数字（NUMBER 99.30% / CITY 80.19% / POSTCODE 86.00% / 92,455 行），那是**另一份运行聚合**，与本地这份 `kent.csv`（79,723 行、CITY 93.00%、POSTCODE 99.74%）**不是同一份口径**，混用会出错。

---

## 二、规则 / 结构 / 格式（实测）

**① 只有"三段"信息，没有行政区划**：`NUMBER + STREET + UNIT` + 坐标；`DISTRICT/REGION/ID` 全空、`CITY` 缺 7%、`POSTCODE` 缺 0.26% → **县级/州级信息 OA 一个都给不了，只能靠 NAD + TIGER 回填**。

**② STREET 是"缩写为主 + 全称混入 + 大小写不统一"**：
- 末词 Top：`RD 21102 / DR 18278 / ST 9085 / LN 7402 / AVE 4348 / CT 4292 / CIR 2839 / WAY 2757 / BLVD 1637 / HWY 1442 / PL 867`
- 混入全称：`DRIVE 618 / RUN 605 / LANE 538 / TRL 528 / TER 409 / COURT 251 / STREET 201 / ROAD 199`
- 大小写异常：`Dr` 243 次；整条混合大小写例 `Hayes Cir`
→ **归一化必须同时处理「缩写↔全称」与「大小写」两个变体。**

**③ 脏值是字面字符串 `<Null>`**（不是真空）：`UNIT` 112 条、`CITY` 111 条。只判 `is null` 会漏，必须显式过滤 `"<Null>"`。（源 B Overture 的 `unit` 也有同样问题 1 条。）

**④ `NUMBER="0"` 是伪门牌**：240 条（例 `0 LIBORIO LN`、`0 CORNER LOT`）；另有 125 条门牌为空或 `<Null>`。**这正是"脏数据零容忍"的具体命中量。**

**⑤ 无门牌纯街道行**：如 `HAZLETTVILLE RD`（30 条 STREET 空 / 门牌空的街道行）——另一类必须丢弃的脏数据。

**⑥ 坐标精度低一档**：OA 4~7 位小数（≈1cm~10m），NAD/Overture 14 位 → **空间匹配别用"坐标完全相等"做键，要给容差**。

**⑦ 重复结构**：
- 全字段六元组（LON+LAT+NUMBER+STREET+UNIT+POSTCODE）唯一 **79,599**（`HASH` 唯一数也是 79,599）→ 80 个重复组 / 124 条重复
- 仅按 `(NUMBER, STREET)`：唯一 78,060、**818 个重复组**，最狠的 `("0","RIVER CHASE DR")` **78 条**、`("400","N DUPONT HWY")` 66 条、`("200","BEECHWOOD AVE")` 66 条 → 同一街上多个点，**单靠门牌+街名去重会误杀**

**⑧ 🔴 最大的坑：OA 自己两个文件内部就重复**
- `kent.csv`（门牌+街名）唯一 78,051；`city_of_dover.csv` 唯一 12,338；**交集 11,672 条**（几乎整个 city_of_dover 都在 kent 里）
- 且两者字段完整度天差地别：**`city_of_dover.csv` 的 `CITY` 与 `POSTCODE` 12,732 行全部为空**、`ID` 也全空
- → 不做跨文件合并去重，同一地址会算两遍

---

## 三、抽检 20 条完整原始记录

> 抽检构成：4 条 Dover+带 unit、3 条 `unit='<Null>'`（其 `CITY` 也是 `<Null>`）、2 条 `NUMBER='0'` 伪门牌、3 条缺城市、4 条普通 Dover 19901/19904、4 条来自 `city_of_dover.csv`（后 4 条 CITY/POSTCODE 全空）。**11 列全列输出，未省略。**

```
#1  LON=-75.5960475 LAT=39.2156463 NUMBER='3937' STREET='SEVEN HICKORIES RD' UNIT='APT B' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='fdabfccf46ca5a94'
#2  LON=-75.5958687 LAT=39.2154692 NUMBER='3947' STREET='SEVEN HICKORIES RD' UNIT='APT B' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='aafa592fa4a40d2e'
#3  LON=-75.5585222 LAT=39.2033125 NUMBER='5921' STREET='W DENNEYS RD' UNIT='APT I' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19901' ID='' HASH='d335990dd5e3b058'
#4  LON=-75.5585222 LAT=39.2033125 NUMBER='5921' STREET='W DENNEYS RD' UNIT='APT D' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19901' ID='' HASH='2d1f81ead3d985f0'
    ↑ #3/#4 与源 A NAD 的 5921 W DENNEYS Road APT I/D 同址：NAD 坐标 (-75.55852402540219, 39.20332040984156)，OA 坐标 (-75.5585222, 39.2033125)，**相差不到 1 米**
#5  LON=-75.5895488 LAT=39.2304202 NUMBER='17' STREET='DOLOMITE CT' UNIT='<Null>' CITY='<Null>' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='725d0271d59641ea'
#6  LON=-75.5897007 LAT=39.2306497 NUMBER='27' STREET='DOLOMITE CT' UNIT='<Null>' CITY='<Null>' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='8e40fe9d486214f1'
#7  LON=-75.5878812 LAT=39.2309376 NUMBER='27' STREET='PUMICE DR' UNIT='<Null>' CITY='<Null>' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='1e01e77333a7e860'
#8  LON=-75.6064442 LAT=39.2770966 NUMBER='0' STREET='LIBORIO LN' UNIT='' CITY='Smyrna' DISTRICT='' REGION='' POSTCODE='19977' ID='' HASH='c3496df3d54edc11'
#9  LON=-75.5349584 LAT=39.151342 NUMBER='0' STREET='CORNER LOT' UNIT='' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='92caa0ca19e20777'
#10 LON=-75.5487606 LAT=39.0578226 NUMBER='107' STREET='HUNTERS RUN BLVD' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='19943' ID='' HASH='e908ae0401aaff72'
#11 LON=-75.4847495 LAT=39.0911327 NUMBER='687' STREET='W BIRDIE LN' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='19962' ID='' HASH='deaa654e850697dc'
#12 LON=-75.5040771 LAT=39.0249312 NUMBER='129' STREET='ROMANZI ST' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='19946' ID='' HASH='d1a6bcfd959ef21e'
#13 LON=-75.5873729 LAT=39.1838571 NUMBER='2905' STREET='KENTON RD' UNIT='' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='4454f3faf4190afe'
#14 LON=-75.5692219 LAT=39.2065519 NUMBER='192' STREET='SALT CREEK DR' UNIT='' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='f6713cb0f257c83f'
#15 LON=-75.6020661 LAT=39.1744599 NUMBER='2614' STREET='W DENNEYS RD' UNIT='' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='5679511e596b20db'
#16 LON=-75.5767727 LAT=39.2071125 NUMBER='45' STREET='GUARD HOUSE LN' UNIT='' CITY='Dover' DISTRICT='' REGION='' POSTCODE='19904' ID='' HASH='2d3cd9b00250caca'
#17 LON=-75.5597279 LAT=39.1492736 NUMBER='' STREET='HAZLETTVILLE RD' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='' ID='' HASH='6b5c6a91304fe499'   ← 无门牌纯街道行
#18 LON=-75.5004951 LAT=39.1477108 NUMBER='835' STREET='BAY RD' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='' ID='' HASH='c85c28b35deef008'
#19 LON=-75.5571213 LAT=39.1745631 NUMBER='15' STREET='PIN OAK DR' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='' ID='' HASH='0e2a3ecd6a36df5e'
#20 LON=-75.5278239 LAT=39.1642163 NUMBER='213' STREET='N BRADFORD ST' UNIT='' CITY='' DISTRICT='' REGION='' POSTCODE='' ID='' HASH='2caceb081e443a0'
    ↑ #17~#20 来自 city_of_dover.csv：CITY / POSTCODE / ID 全空
```

---

## 四、对 24 字段合并的结论（供 Gemini 参考）

1. **OA 是唯一真正独立的民间源**（另三源中 Overture 溯源 NAD），S 级的"交叉验证"重量全压在它身上 → **必须先把 OA 内部两份文件合并去重**（kent ∩ city_of_dover = **11,672 条重叠**），否则 S 级数量虚高。
2. **匹配键只能是「门牌 + 归一化街名 + 归一化 unit」，且必须给坐标容差**；`CITY/POSTCODE/DISTRICT/REGION/ID` 五列不可靠或全空，行政信息靠 NAD/TIGER 回填。
3. **可写成脚本硬规则的脏数据清单（已量化）**：`NUMBER="0"` 240 条、`NUMBER` 空 `<Null>` 125 条、`UNIT="<Null>"` 112 条、`CITY="<Null>"` 111 条、`STREET` 空 30 条、无门牌纯街道行（如 `HAZLETTVILLE RD`）。
4. **同址坐标可用于验证匹配**：OA `5921 W DENNEYS RD APT I` 与 NAD 同址相差 **< 1 米** → 「门牌 + 街名归一化」+「坐标容差」双条件匹配在两源间可行，直接支撑 S 级判定逻辑。
5. **许可提醒**：该源 `License: Unknown`，最终数据集若对外发布需在文档里如实标注来源与许可状态。
