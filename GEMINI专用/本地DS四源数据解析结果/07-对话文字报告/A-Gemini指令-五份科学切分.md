# 附录 A · Gemini 指令原文的五份科学切分

> 来源文件：`Gemini指令.txt`（项目根目录，93 行）
> 用途：原文件过长，按「内容语义 + 表格完整性 + 篇幅均衡」切成 5 份，每份可单独发送给另一个 AI，接收方按序号拼接即可还原全文。
> 说明：正文与原文件**逐字一致**（含链接与加粗），仅新增了 5 条分片头。

---

## 第 1/5 份 · 背景 + 数据源总览 + 源A（USDOT NAD）

```
════════ 第 1/5 份 ════════
主题：背景说明 + 数据源总览 + 源A：USDOT NAD（官方 60 列）
说明：这是一份分片文档的第 1 部分，后续还有 4 部分（第2份=源B/源C，第3份=源D，第4份=24字段黄金表，第5份=细节说明与下一步）。请按序号拼接阅读。
────────────────────────────
我刚刚重新仔细核对了邮箱中小鑫发来的 [[PI-BRIDGE] gempi.gtop.dev · PI-Agent 已交卷 (#8) · TASK-001 交付详见正文](https://mail.google.com/mail/?authuser=miaoxinxin9701@gmail.com#all/thread-f:1879057963594162410)，并结合 [USDOT NAD 官方字段规范](https://www.transportation.gov/sites/dot.gov/files/docs/mission/gis/national-address-database/308816/nad-schema-v2.pdf)、[Overture Maps 地址规范](https://docs.overturemaps.org/schema/reference/addresses/address/) 以及 [Census TIGER/Line 道路号段规范](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)，把 **4 个数据源各自的完整原始字段清单** 以及 **四合一去重合并后的“精品真实地址标准字段表”** 全部梳理出来了。

### 一、先看清现状：4 个数据源各自到底有多少个字段？

在小鑫的交卷邮件中，4 个数据源的原始列数合计达 **107 列**（60 + 11 + 11 + 25，另加 TIGER 边界图层字段）。之所以数量差异大，是因为各源对“同一个地址”的拆分颗粒度完全不同：

#### 1. 源 A：USDOT NAD（官方 60 列通道，Dover 实测 28,028 行，平均非空率 40.61%）

[USDOT NAD](https://www.transportation.gov/sites/dot.gov/files/docs/mission/gis/national-address-database/308816/nad-schema-v2.pdf) 是按照美国 911 应急调度标准（NENA CLDXF）设计的超细宽表，60 个字段分为 6 组：

* **门牌号拆分族（4 列）**：`AddNum_Pre`（门牌前缀）、`Add_Number`（核心门牌号，**100% 非空**，如 `5921`）、`AddNum_Suf`（门牌后缀，如 `1/2` 或 `A`）、`AddNo_Full`（完整门牌拼装）
* **街道名精细拆分族（10 列）**：`StN_PreMod`（前修饰词，如 `Old`）、`StN_PreDir` / `St_PreDir`（前方向词，如 `West`、`South`）、`StN_PreTyp`（前类型词，如 `US Highway`）、`StN_PreSep`（前介词）、`St_Name` / `StreetName`（核心路名，**100% 非空**，如 `DENNEYS`、`STATE`）、`St_PosTyp` / `StN_PosTyp`（街道后缀，如 `Road`、`Street`）、`StN_PosDir`（后方向词）、`StN_PosMod`（后修饰词）、`StNam_Full`（完整街道名，**100% 非空**，如 `West DENNEYS Road`）、`complete_street_address`（门牌+街道完整拼接）
* **建筑与公寓子地址族（6 列）**：`Building`（楼栋号）、`Floor`（楼层）、`Unit`（公寓/套房室号，如样本 `#1` 的 `APT I`、`APT D`）、`Room`（房间号）、`Seat`（工位号）、`Addtl_Loc`（附加位置说明）
* **地标与公路里程族（3 列）**：`LandmkPart`、`LandmkName`（建筑/商业地标名）、`Milepost`（公路里程标）
* **行政区划与邮编族（10 列）**：`State`（州简写 `DE`）、`County`（县名 `Kent`，**100% 非空**）、`Inc_Muni`（法定行政市名 `Dover`，**100% 非空**）、`Post_City` / `Post_Comm`（USPS 邮政城市名 `Dover`，**100% 非空**）、`Uninc_Comm`（非建制社区名）、`Nbrhd_Comm`（小区/街区名，如某庄园）、`Zip_Code`（5 位邮编 `19901`，**100% 非空**）、`Plus_4`（后 4 位邮编，Dover 实测 **0.00% 全空**）、`Bulk_Zip`、`Bulk_Plus4`（大宗机构专用邮编）
* **坐标、分类与系统溯源族（27 列）**：`Longitude`（经度，**100%**）、`Latitude`（纬度，**100%**）、`NatGrid`（国家网格坐标）、`Placement`（测绘落点方式，**100%**，如屋顶 Rooftop / 地块中心 Parcel）、`Addr_Type`（地址用途分类，**100% 非空**但 Dover 样本全填了 `"Unknown"`）、`AddrClass`、`AddrPoint`、`Parcel_ID`（税务地块号）、`UUID`（全局唯一 ID，**100%**）、`OID_`、`AddAuth`（赋码政府机构，**100%**）、`NAD_Source`（数据提交源，**100%**）、`DataSet_ID`、`DateUpdate`、`Effective`、`Expired`、`UniqWithin`、`country_code` 等系统管理字段。
```

---

## 第 2/5 份 · 源B（Overture）+ 源C（OpenAddresses）

```
════════ 第 2/5 份 ════════
主题：源B：Overture Maps（11 列）+ 源C：OpenAddresses us/de（11 列）
说明：这是分片文档的第 2 部分，接第 1 部分的“一、现状总览”，后续还有 3 部分。
────────────────────────────
#### 2. 源 B：Overture Maps Addresses（全量 11 列，Dover 实测 28,027 行，平均非空率 90.93%）

[Overture Maps](https://docs.overturemaps.org/schema/reference/addresses/address/) 将地址精简为 11 个云原生字段（不做街道前缀/后缀拆分）：

* **地址主体（4 列）**：`number`（门牌号，**100%**，如 `1870`）、`street`（完整街道名，**100%**，如 `South STATE Street`）、`unit`（室号，实测仅 **0.19%** 即 52 条非空）、`postcode`（5 位邮编，**100%**，如 `19901`）
* **行政层级与国家（3 列）**：`postal_city`（邮政城市）、`address_levels`（嵌套 JSON 数组，**100%**，内含州 `DE` 与城市 `Dover`）、`country`（国家 `US`，**100%**）
* **空间坐标与元数据（4 列）**：`lon`（经度，**100%**）、`lat`（纬度，**100%**）、`id`（Overture 唯一 ID）、`sources`（上游数据源溯源 JSON，**100%**）

#### 3. 源 C：OpenAddresses `us/de`（标准 11 列，全州 92,455 行，平均非空率 60.55%）

小鑫在邮件中完整打印了 OpenAddresses 的全部 11 列非空率：

* **有效业务字段（7 列）**：`NUMBER`（门牌号，**99.30%**）、`STREET`（完整街道名，**99.96%**，全大写缩写如 `835 BAY RD`）、`UNIT`（室号，**0.62%** 共 577 条）、`CITY`（城市名，**80.19%**）、`POSTCODE`（5 位邮编，**86.00%**）、`LON`（经度，**100%**）、`LAT`（纬度，**100%**）
* **全空或系统字段（4 列）**：`DISTRICT`（县名，**0.00% 全空**）、`REGION`（州名，**0.00% 全空**）、`ID`（原始 ID，**0.00% 全空**）、`HASH`（去重哈希值，**100%**）
```

---

## 第 3/5 份 · 源D（Census TIGER）

```
════════ 第 3/5 份 ════════
主题：源D：Census TIGER（道路号段表 25 列 + 5 大空间边界图层）
说明：这是分片文档的第 3 部分，接第 2 部分，至此“一、现状总览”结束。后续还有 2 部分。
────────────────────────────
#### 4. 源 D：Census TIGER（道路号段表 25 列 + 5 大空间边界图层，平均非空率 70.84%）

[Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) 提供的是**道路号段区间**与**官方行政多边形边界**：

* **`addrfeat.dbf` 道路号段表（25 列）**：
* **道路标识（6 列）**：`TLID`（道路段永久 ID，**100%**）、`FULLNAME`（完整道路名，**100%**，如 `W Denneys Rd`）、`TFIDL`、`TFIDR`、`PAFLAG`、`MTFCC`
* **道路左侧号段与 9 位邮编（6 列）**：`LFROMHN`（左起门牌）、`LTOHN`（左止门牌）、`PARITYL`（左奇偶性）、`ZIPL`（左 5 位邮编）、`PLUS4L`（**左后 4 位邮编 Plus_4**）、`ARIDL`
* **道路右侧号段与 9 位邮编（6 列）**：`RFROMHN`（右起门牌）、`RTOHN`（右止门牌）、`PARITYR`（右奇偶性）、`ZIPR`（右 5 位邮编）、`PLUS4R`（**右后 4 位邮编 Plus_4**）、`ARIDR`
* **偏移与类型控制（7 列）**：`LFROMTYP`、`LTOTYP`、`RFROMTYP`、`RTOTYP`、`OFFSETL`、`OFFSETR`、`geometry`


* **5 大行政与邮编边界图层**：提供 `STATEFP`（州 FIPS `10`）、`STUSPS`（州简写 `DE`）、`NAME`（州全称 `Delaware` / 县名 `Kent` / 市名 `Dover`）、`COUNTYFP`（县 FIPS `001`）、`GEOID`（县完整 FIPS `10001`、市代码 `1021200`、邮编 `ZCTA5 19901/19904`）。
```

---

## 第 4/5 份 · 24 字段黄金地址表

```
════════ 第 4/5 份 ════════
主题：二、四合一去重合并后的“24 字段（十大维度）黄金地址表结构”
说明：这是分片文档的第 4 部分（核心部分），后续还有 1 部分。本部分含一张完整表格，请勿拆断。
────────────────────────────
### 二、四合一去重合并后：一条“精品完整真实地址”由哪几个字段组成？

把上面 4 个源的 107 个字段拿来对比，剔除纯内部系统垃圾字段（如 `OID_`、`TFIDL`、`Bulk_Zip`、`HASH`），并将重复概念四合一合并后，一条完美覆盖 **“1234567890”十大维度** 的黄金真实地址数据，建议定型为 **22 个标准字段**（以样本 `#1`：`5921 West Denneys Road, Apt I, Dover, DE 19901` 为例）：

| 所属维度 (1-10) | 序号 | 标准字段名 (英文) | 字段中文名 | 合并后真实样本值示例 | 四合一提取与互补优先级规则 (Coalesce) |
| --- | --- | --- | --- | --- | --- |
| **1. 门牌号** | 1 | `house_number` | 门牌号主体 | `5921` | **NAD** `Add_Number` → **Overture** `number` → **OA** `NUMBER`（过滤空值） |
| **1. 门牌号** | 2 | `house_number_suffix` | 门牌前后缀 | `null` (或 `1/2`, `A`) | **NAD** `AddNum_Pre` / `AddNum_Suf`（无则留空） |
| **2. 精细街道** | 3 | `street_pre_dir` | 街道前方向词 | `W` (或 `West`) | **NAD** `StN_PreDir` → 从 `FULLNAME` / `street` 正则拆解标准化 |
| **2. 精细街道** | 4 | `street_name` | 核心街道名 | `Denneys` | **NAD** `St_Name`（转 Title Case，把 `DENNEYS` 规范为 `Denneys`） |
| **2. 精细街道** | 5 | `street_post_type` | 街道后缀类型 | `Rd` (或 `Road`) | **NAD** `St_PosTyp`（统一映射 USPS 标准简写 `Rd`/`St`/`Ave` 与全称） |
| **2. 精细街道** | 6 | `street_post_dir` | 街道后方向词 | `null` | **NAD** `StN_PosDir` |
| **2. 精细街道** | 7 | `street_full` | 完整标准街道名 | `W Denneys Rd` | 由字段 3+4+5+6 标准拼装，与 **NAD** `StNam_Full` / **Overture** `street` / **TIGER** `FULLNAME` 交叉核验 |
| **3. 公寓室号** | 8 | `unit` | 公寓/套房/室号 | `APT I` | **NAD** `Unit` → **OA** `UNIT` → **Overture** `unit`（独立屋为 `null`） |
| **3. 公寓室号** | 9 | `building_floor` | 楼栋/楼层/地标名 | `null` | **NAD** `Building` / `Floor` / `LandmkName` |
| **4. 城市名称** | 10 | `postal_city` | USPS 邮政城市名 | `Dover` | **NAD** `Post_City` → **Overture** `postal_city` → **OA** `CITY`（写信/填表必用） |
| **4. 城市名称** | 11 | `municipal_city` | 行政建制市/社区 | `Dover` | **NAD** `Inc_Muni` / `Nbrhd_Comm` → **TIGER** `Place` 边界空间落点兜底 (`GEOID=1021200`) |
| **5. 县与 FIPS** | 12 | `county_name` | 县名 | `Kent County` | **NAD** `County` (`Kent`) + **TIGER** `County` 边界兜底，规范为 `Kent County` |
| **5. 县与 FIPS** | 13 | `county_fips` | 5 位县级 FIPS 码 | `10001` | **TIGER** `County` 边界 `GEOID` (`STATE=10` + `COUNTY=001` = `10001`) |
| **6. 州名与代码** | 14 | `state_abbr` | 2 位州简写 | `DE` | **NAD** `State` → **Overture** `address_levels` → **TIGER** `State` 边界 |
| **6. 州名与代码** | 15 | `state_name` | 州英文全称 | `Delaware` | **TIGER** `State` 边界 `NAME` + 官方州代码映射表 (`DE` → `Delaware`) |
| **6. 州名与代码** | 16 | `state_fips` | 2 位州级 FIPS 码 | `10` | **TIGER** `State` 边界 `STATEFP` (`10`) |
| **7. 九位邮编** | 17 | `zip5` | 5 位标准邮编 | `19901` | **NAD** `Zip_Code` → **Overture** `postcode` → **OA** `POSTCODE` → **TIGER** `ZCTA5` 边界兜底 |
| **7. 九位邮编** | 18 | `plus4` | 后 4 位精确邮编 | `2245` (示例) | **TIGER `addrfeat**` 按道路名与门牌奇偶落入 `[LFROMHN, LTOHN]` / `[RFROMHN, RTOHN]` 提取 `PLUS4L`/`PLUS4R` → **NAD** `Plus_4` |
| **7. 九位邮编** | 19 | `zip9` | 完整 9 位邮编 | `19901-2245` | 由 `zip5` + `-` + `plus4` 自动合成（若该路段无 `plus4` 则退化保留 `zip5`） |
| **8. 屋顶坐标** | 20 | `latitude` / `longitude` | 屋顶级纬度 / 经度 | `39.203320, -75.558524` | **NAD** `Latitude`/`Longitude` → **Overture** `lat`/`lon` → **OA** `LAT`/`LON`（附带 `Placement` 精度标签） |
| **9. 住商分类** | 21 | `addr_type` | 住宅/商业属性分类 | `Residential` | **NAD** `Addr_Type`（若为 `Unknown`，则含 `APT/UNIT` 判为 `Residential (Multi-Unit)`，匹配商业 POI 判为 `Commercial`，其余默认 `Residential`） |
| **10. 区号与时区** | 22 | `area_code` & `timezone` | 电话区号与标准时区 | `302` / `America/New_York` | 基于州/县/邮编映射表确定性赋予（区号 `302`，时区 `America/New_York`，`EST/EDT UTC-5/UTC-4`） |

*（注：除以上 22 个核心业务字段外，建议额外保留 2 个质检溯源字段：`full_formatted_address`【拼好的一行标准美式地址，如 `5921 W Denneys Rd Apt I, Dover, DE 19901-2245`】和 `source_confidence`【记录该地址被哪几个源交叉命中，如 `S-Tier: NAD+Overture+OA+TIGER`】，共计 **24 个字段**。）*
```

---

## 第 5/5 份 · 细节说明与下一步建议

```
════════ 第 5/5 份 ════════
主题：三、小鑫上封邮件的细节说明 + TASK-002 推进建议 + 待确认问题
说明：这是分片文档的最后一部分（第 5/5 份）。读完后请对“24 字段表结构”与“TASK-002 验收要求”给出确认意见。
────────────────────────────
### 三、小鑫上封邮件的一个细节说明与下一步建议

看小鑫上次发来的 [[PI-BRIDGE] 交卷 (#8) 邮件正文](https://mail.google.com/mail/?authuser=miaoxinxin9701@gmail.com#all/thread-f:1879057963594162410)，有两个细节需要留意：

1. **上次 4 个源抽的不是同一批门牌**：小鑫在 NAD 抽了 `5921 W Denneys Rd` 和 `1991–2297 S State St`，在 Overture 抽了 `1622–1870 S State St`，在 OpenAddresses 抽了 `835 Bay Rd` 等其他路，且在邮件里只打印了单行摘要，把 60 列的完整原始键值对放在了仓库文件 `task001_records.jsonl` 里。
2. **TIGER 的门牌号段与 Plus_4 在上次抽样中显示为 `None**`：如前所述，小鑫脚本写错了列名（没用 `LFROMHN`/`RFROMHN`/`PLUS4L`/`PLUS4R`）。

**接下来的推进建议：**

1. 你先看上面这套 **“24 字段（十大维度）四合一黄金地址表结构”**，有没有哪个字段是你觉得多余想删掉的，或者还有哪个类似 `meiguodizhi.com` 页面展示需要的字段（比如街道全拼/简写双字段、县 FIPS 等）需要微调？
2. 你确认这套字段清单后，我就去 [Task Relay Notes](https://docs.google.com/document/d/1DV2ph7smxUOJQg8lODnKpEP89oW9zSdNkIweVWGHXpA/edit) 下发 **TASK-002**，直接要求小鑫：
* 第一步：专门挑 **5 个在 4 大数据源全部同时命中的同一门牌地址**（例如 `1870 S State St` 等），在交卷邮件正文里把这 5 个地址在 4 个源里的**全部非空原始字段键值对**原原本本展示出来，并修复 TIGER `PLUS4L`/`PLUS4R` 提取；
* 第二步：严格按我们定下的 **分级留存策略（S/A 级保留，民间孤儿点与无门牌脏数据丢弃）** 和 **24 个黄金字段表结构**，先把 Dover（或整个特拉华州 DE）跑通一版去重合并结果，在邮件正文汇报总留存行数、丢弃行数、各字段 100% 填充率及 50 条合并后的完整黄金样本。



你觉得这 **24 个合并后字段** 和 **TASK-002 的验收要求** 可以吗？确认后我立刻写入 Google Doc！
```
