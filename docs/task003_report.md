# TASK-003 · Dover, DE 四源全量自动化 ETL 与 24 字段黄金地址库投产报告

> 生成时间（UTC）：2026-10-15T07:28:07Z　运行环境：GitHub Actions runner（本地服务器零下载）
> 脚本：`scripts/dover_golden_coalesce.py`　输入：GitHub Release `dover-raw-20261015-0450`
> 范围：bbox `[-75.6, 39.1, -75.45, 39.22]`　Kent County(10001) / Dover city(1021200) / ZCTA 19901·19904

## 一、输入资产与规模（runner 侧下载，全量）

| 源 | 文件 | 原始规模 |
|---|---|---|
| USDOT NAD | `nad_dover_full.ndjson` | 28,028 行 / 60 列 |
| Overture Maps | `overture_addresses.geojson` | 28,027 features |
| OpenAddresses | `openaddresses_us_de_kent.zip` | 79,723 行 |
| OpenAddresses | `openaddresses_us_de_city_of_dover.zip` | 12,732 行 |
| Census TIGER | `tl_2024_10001_addrfeat.zip` | 11,072 号段行 / 25 列（NAD83） |
| Census TIGER | 4 个边界图层 + `tl_2024_10_place.zip` | Kent County / Dover city / DE / ZCTA19901·19904 |

## 二、过滤漏斗表（Dover Filtering Funnel）

| 阶段 | 计数 |
|---|---|
| NAD 原始行数（Release nad_dover_full.ndjson） | 28028 |
| Overture 原始 features | 28027 |
| OpenAddresses kent.csv 原始行数 | 79723 |
| OpenAddresses city_of_dover.csv 原始行数 | 12732 |
| OA 跨文件内部去重丢弃（优先保留 kent.csv；归一化键） | 11938 |
| 　（对账口径）字面 (NUMBER, STREET) 配对交集 | 11659 |
| 　（对账口径）city_of_dover 命中 kent 字面配对的条数 | 11747 |
| OA 脏数据丢弃（合计，含 <Null>/无门牌/NUMBER=0） | 53146 |
| 　其中 NUMBER="0" | 240 |
| 　其中 无门牌纯街道行 | 643 |
| 　其中 空门牌（非街道行） | 4 |
| 　其中 UNIT="<Null>" | 112 |
| 　其中 CITY="<Null>" | 111 |
| 　其中 坐标越界/缺失 | 52002 |
| OA 清洗后可用于匹配 | 27486 |
| 　OA 清洗后分文件剩余（kent / city_of_dover） | {'kent': 27214, 'city_of_dover': 272} |
| 四源全命中候选（NAD+Overture+OA+TIGER range）可用于 5 例对照 | 23411 |
| OA → NAD 命中（成为独立第二票） | 25662 |
| B-Tier 丢弃：仅存在于 OA 的孤儿 | 1824 |
| Overture → NAD 命中（自证票） | 26702 |
| B-Tier 丢弃：仅存在于 Overture 的孤儿 | 1324 |
| NAD 脏数据丢弃（无门牌/无街名/坐标越界） | 0 |
| NAD 边界外丢弃（不在 Kent County 面内） | 0 |
| NAD 合并后重复丢弃（同 门牌+街+单元） | 865 |
| **S-Tier 保留** | 25018 |
| **A-Tier 保留** | 2145 |
| **最终去重后 Dover 黄金地址总量** | 27163 |

### 2.1 关键实证事实（与既有实测一致，未做任何『修补』）

- **Overture 100% 溯源 NAD**：本批 features 的上游 dataset 统计 = `{'NAD': 28027}` → `NAD+Overture` 只能算 **1 票官方票**；真正独立第二票是 OpenAddresses。
- **OA 逐文件脏数据**：`{"kent": {"coord_out_of_bbox": 52002, "unit_ltnull": 112, "city_ltnull": 111, "number_zero": 240, "street_empty": 34, "street_only_no_number": 121, "number_empty": 4}, "city_of_dover": {"street_only_no_number": 522}}`（同一行可能命中多因，合计与唯一丢弃数见上方漏斗）。
- **OA 内部重叠**：kent/city_of_dover 跨文件重复丢弃 `11,938` 条（优先保留 kent.csv，因为 city_of_dover 的 CITY/POSTCODE 全空）。
- **plus4 四源全空**：NAD `Plus_4` 非空率见填充率表；TIGER `PLUS4L/PLUS4R` 非空率 `0.0`（0）→ **`plus4` 如实为 null，`zip9` 降级为 `zip5`**，未做任何插值/编造。
- **TIGER 号段**：按 `TLID`/`FULLNAME` 聚合、降序区间取 `min/max`、允许单侧（本批 11,072 条号段 → 6588 个街道匹配键）。
- **addr_type**：NAD 原始 GROUP BY（共 28,028 行）=`{'Unknown | Unknown': 28028}`，`AddrClass` = `{'Numbered Thoroughfare Address': 28028}` → 官方字段无判别力，按下述**显式规则**重分类。

### 2.1.1 与既有实测口径对账（逐条核验，不做掩盖）

| 核验项 | 既有实测口径（TASK-002/抽检） | 本批 runner 实测 | 差异说明 |
|---|---|---|---|
| NAD 行数 | 28,028 | 28,028 | 一致 |
| Overture features | 28,027 | 28,027 | 一致 |
| Overture 上游 dataset | 100% NAD | {'NAD': 28027} | 一致 → 不构成独立第二票 |
| OA kent.csv 行数 | 79,723 | 79,723 | 一致 |
| OA city_of_dover.csv 行数 | 12,732 | 12,732 | 一致 |
| OA NUMBER=="0" | 240 | 240 | 一致 |
| OA 空 NUMBER | 125 | kent 125 / city 522 | 125 = kent.csv 口径；city_of_dover 另有 522 条纯街道行 |
| OA 纯街道行（无门牌） | 30 | city 643 / kent 121 | 口径不同（旧值疑为某子集；本批按全文件实测） |
| OA UNIT=="<Null>" | 112 | 112 | 一致 |
| OA CITY=="<Null>" | 111 | 111 | 一致 |
| OA 跨文件重叠 | 11,672 | 字面 11,659 / 归一化去重丢弃 11,938 | 去重键口径差异（是否归一门牌/街名与空值处理），非数据差异 |
| TIGER addrfeat 行数 | 11,072 | 11,072 | 一致 |
| TIGER PLUS4L/PLUS4R | 0.00% | 0.0 | 一致 → plus4 合法为空 |
| NAD Addr_Type / Placement | 全为 Unknown | {'Unknown | Unknown': 28028} | 一致 |

### 2.2 分级定义（本脚本可执行口径）

- **S-Tier**：NAD 主干 + TIGER 街道/号段校验通过 + 命中 OA（或 Overture）。 细分：独立双证 `NAD+TIGER+OA` = 24,485；仅 Overture 自证 = 533。
- **A-Tier**：NAD + TIGER 校验（含仅街道命中），但无 OA/Overture 佐证 → 保留官方权威地址，保住多单元公寓（APT B/C/D/I）与新建房屋。合计 2,145。
- **B-Tier 丢弃**：仅存在于 OA 或 Overture、NAD 无对应 → OA 孤儿 1,824 + Overture 孤儿 1,324。
- **脏数据/重复丢弃**：OA 53,146 + NAD 0 + 边界外 0 + 合并后重复 865。
- **TIGER 校验分布**：range 命中 23,857 / 仅街道命中 1,253 / 无该街名 2,053。

## 三、24 字段非空填充率（最终黄金库）

| 字段 | 非空条数 | 非空率 |
|---|---|---|
| house_number | 27163 | 100.00% |
| house_number_suffix | 0 | 0.00% |
| street_pre_dir | 4446 | 16.37% |
| street_name | 27163 | 100.00% |
| street_post_type | 27004 | 99.41% |
| street_post_dir | 82 | 0.30% |
| street_full | 27163 | 100.00% |
| unit | 51 | 0.19% |
| building_floor | 0 | 0.00% |
| postal_city | 27163 | 100.00% |
| municipal_city | 27163 | 100.00% |
| county_name | 27163 | 100.00% |
| county_fips | 27163 | 100.00% |
| state_abbr | 27163 | 100.00% |
| state_name | 27163 | 100.00% |
| state_fips | 27163 | 100.00% |
| zip5 | 27163 | 100.00% |
| plus4 | 0 | 0.00% |
| zip9 | 27163 | 100.00% |
| latitude | 27163 | 100.00% |
| longitude | 27163 | 100.00% |
| addr_type | 27163 | 100.00% |
| area_code | 27163 | 100.00% |
| timezone | 27163 | 100.00% |
| full_formatted_address | 27163 | 100.00% |
| source_confidence | 27163 | 100.00% |

### 3.1 重点字段

| 重点字段 | 覆盖率 | 说明 |
|---|---|---|
| `plus4` | 0.00% | NAD Plus_4 0% + TIGER PLUS4L/R 0% + Overture/OA 无该字段 → 合法为空，不造数据 |
| `zip9` | 100.00% | plus4 缺失 → 降级为 zip5（19901/19904 等） |
| `unit` | 0.19% | 多单元地址 51 条，涉及 21 栋楼 |
| `addr_type` | 100.00% | 规则重分类：{'Residential (Multi-Unit)': 51, 'Residential': 26456, 'Commercial': 656} |
| `latitude/longitude` | 100.00% | NAD 屋顶级坐标（14 位小数，WGS84） |
| `source_confidence` | 100.00% | {'S-Tier': 25018, 'A-Tier': 2145} |

### 3.2 分布

| 维度 | 分布 |
|---|---|
| zip5 | {'19936': 369, '19904': 11731, '19962': 429, '19901': 11465, '19934': 2950, '19902': 218, '19961': 1} |
| tier | {'S-Tier': 25018, 'A-Tier': 2145} |
| tiger_verify | {'range': 23857, 'none': 2053, 'street': 1253} |
| addr_type | {'Residential (Multi-Unit)': 51, 'Residential': 26456, 'Commercial': 656} |
| 边界命中 | {'in_kent_county': 28028, 'in_zcta_19901_19904': 24287, 'in_dover_place': 14285} |

## 四、5 条同址四源原始 KV 对照 + 合并后 24 字段黄金记录

### 4.1 `179 COMMERCE Street Apt A`（归一化键 `COMMERCE|ST`）

**NAD 原始（非空字段全列）**
```json
{
 "OBJECTID": 98139018,
 "Add_Number": 179,
 "AddNo_Full": "179",
 "St_Name": "COMMERCE",
 "St_PosTyp": "Street",
 "StNam_Full": "COMMERCE Street",
 "Unit": "APT A",
 "SubAddress": "APT A",
 "County": "Kent",
 "Inc_Muni": "Cheswold",
 "Post_City": "Cheswold",
 "Nbrhd_Comm": "Cheswold",
 "State": "DE",
 "Zip_Code": "19936",
 "UUID": "054d8a30-b88b-4211-8ae0-684d1b53e864",
 "AddAuth": "Kent County Delaware",
 "Longitude": -75.58606037592598,
 "Latitude": 39.21829360455592,
 "NatGrid": "18SVJ4940841164",
 "Placement": "Unknown",
 "AddrPoint": "-75.58606037592598 39.21829360455592",
 "AddrClass": "Numbered Thoroughfare Address",
 "DateUpdate": 1613735141000,
 "Addr_Type": "Unknown",
 "NAD_Source": "Kent County Delaware",
 "DataSet_ID": "{054d8a30-b88b-4211-8ae0-684d1b53e864}",
 "_lon": -75.58606037576688,
 "_lat": 39.21829360505618
}
```
**Overture 原始**
```json
{
 "street": "COMMERCE Street",
 "number": "179",
 "unit": "APT E",
 "postcode": "19936",
 "postal_city": "Cheswold",
 "address_levels": [
  {
   "value": "DE"
  },
  {
   "value": "Cheswold"
  }
 ],
 "country": "US",
 "sources": [
  {
   "property": "",
   "dataset": "NAD",
   "license": "LicenseRef-Public-Domain-US",
   "record_id": "F4A058D6-F9C0-4E3F-8E48-69AB5E24A719",
   "update_time": "2026-09-18T19:39:08.275Z",
   "confidence": null,
   "between": null,
   "provider": "nad",
   "resource": "nad",
   "version": "20250924"
  }
 ],
 "version": 1,
 "_lon": -75.58606037592598,
 "_lat": 39.21829360455592,
 "_id": "591951fc-53c1-4191-87cb-a84a3d1ac913",
 "_upstream": "NAD"
}
```
**OpenAddresses 原始**
```json
{
 "LON": "-75.5860585",
 "LAT": "39.2182857",
 "NUMBER": "179",
 "STREET": "COMMERCE ST",
 "UNIT": "APT E",
 "CITY": "Cheswold",
 "POSTCODE": "19936",
 "HASH": "504ab53b222bbf79"
}
```
**TIGER 号段原始**
```json
[
 {
  "TLID": "68110055",
  "FULLNAME": "Commerce St",
  "LFROMHN": "39",
  "LTOHN": "27",
  "RFROMHN": "42",
  "RTOHN": "24",
  "PARITYL": "O",
  "PARITYR": "E",
  "ZIPL": "19952",
  "ZIPR": "19952",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1200",
  "EDGE_MTFCC": "S1200",
  "matched_key": "COMMERCE|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    27,
    39,
    "O"
   ],
   [
    24,
    42,
    "E"
   ]
  ]
 },
 {
  "TLID": "68082227",
  "FULLNAME": "Commerce St",
  "LFROMHN": "99",
  "LTOHN": "49",
  "RFROMHN": "98",
  "RTOHN": "46",
  "PARITYL": "O",
  "PARITYR": "E",
  "ZIPL": "19952",
  "ZIPR": "19952",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1200",
  "EDGE_MTFCC": "S1200",
  "matched_key": "COMMERCE|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    49,
    99,
    "O"
   ],
   [
    46,
    98,
    "E"
   ]
  ]
 },
 {
  "TLID": "68082243",
  "FULLNAME": "Commerce St",
  "LFROMHN": "199",
  "LTOHN": "101",
  "RFROMHN": "198",
  "RTOHN": "100",
  "PARITYL": "O",
  "PARITYR": "E",
  "ZIPL": "19952",
  "ZIPR": "19952",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1200",
  "EDGE_MTFCC": "S1200",
  "matched_key": "COMMERCE|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    101,
    199,
    "O"
   ],
   [
    100,
    198,
    "E"
   ]
  ]
 }
]
```
**合并后黄金记录（24 字段）**
```json
{
 "house_number": "179",
 "house_number_suffix": null,
 "street_pre_dir": null,
 "street_name": "Commerce",
 "street_post_type": "St",
 "street_post_dir": null,
 "street_full": "Commerce St",
 "unit": "Apt A",
 "building_floor": null,
 "postal_city": "Cheswold",
 "municipal_city": "Cheswold",
 "county_name": "Kent County",
 "county_fips": "10001",
 "state_abbr": "DE",
 "state_name": "Delaware",
 "state_fips": "10",
 "zip5": "19936",
 "plus4": null,
 "zip9": "19936",
 "latitude": 39.2182936,
 "longitude": -75.5860604,
 "addr_type": "Residential (Multi-Unit)",
 "area_code": "302",
 "timezone": "America/New_York",
 "full_formatted_address": "179 Commerce St Apt A, Cheswold, DE 19936",
 "source_confidence": "S-Tier: NAD+OVERTURE+OA+TIGER[range]"
}
```

### 4.2 `2871 West DENNEYS Road`（归一化键 `DENNEYS|RD`）

**NAD 原始（非空字段全列）**
```json
{
 "OBJECTID": 98136763,
 "Add_Number": 2871,
 "AddNo_Full": "2871",
 "St_PreDir": "West",
 "St_Name": "DENNEYS",
 "St_PosTyp": "Road",
 "StNam_Full": "West DENNEYS Road",
 "County": "Kent",
 "Inc_Muni": "Dover",
 "Post_City": "Dover",
 "Nbrhd_Comm": "Dover",
 "State": "DE",
 "Zip_Code": "19904",
 "UUID": "5723d5c1-1fdd-4fe5-b5ce-c42da2899272",
 "AddAuth": "Kent County Delaware",
 "Longitude": -75.59955526909282,
 "Latitude": 39.17877170251683,
 "NatGrid": "18SVJ4821436786",
 "Placement": "Unknown",
 "AddrPoint": "-75.59955526909282 39.17877170251683",
 "AddrClass": "Numbered Thoroughfare Address",
 "DateUpdate": 1760659200000,
 "Addr_Type": "Unknown",
 "NAD_Source": "Kent County Delaware",
 "DataSet_ID": "{5723d5c1-1fdd-4fe5-b5ce-c42da2899272}",
 "_lon": -75.59955526861353,
 "_lat": 39.17877170286764
}
```
**Overture 原始**
```json
{
 "street": "West DENNEYS Road",
 "number": "2871",
 "postcode": "19904",
 "postal_city": "Dover",
 "address_levels": [
  {
   "value": "DE"
  },
  {
   "value": "Dover"
  }
 ],
 "country": "US",
 "sources": [
  {
   "property": "",
   "dataset": "NAD",
   "license": "LicenseRef-Public-Domain-US",
   "record_id": "5723D5C1-1FDD-4FE5-B5CE-C42DA2899272",
   "update_time": "2026-09-18T19:39:08.275Z",
   "confidence": null,
   "between": null,
   "provider": "nad",
   "resource": "nad",
   "version": "20250924"
  }
 ],
 "version": 1,
 "_lon": -75.59955526909282,
 "_lat": 39.17877170251683,
 "_id": "5dfa0219-155e-4971-a405-22852c75b1a4",
 "_upstream": "NAD"
}
```
**OpenAddresses 原始**
```json
{
 "LON": "-75.5995534",
 "LAT": "39.1787638",
 "NUMBER": "2871",
 "STREET": "W DENNEYS RD",
 "CITY": "Dover",
 "POSTCODE": "19904",
 "HASH": "49829403a19017e5"
}
```
**TIGER 号段原始**
```json
[
 {
  "TLID": "641078146",
  "FULLNAME": "W Denneys Rd",
  "LFROMHN": "4201",
  "LTOHN": "4257",
  "RFROMHN": "4200",
  "RTOHN": "4298",
  "PARITYL": "O",
  "PARITYR": "E",
  "ZIPL": "19904",
  "ZIPR": "19904",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1200",
  "EDGE_MTFCC": "S1200",
  "matched_key": "W|DENNEYS|RD",
  "normalized_ranges(min/max,不含方向)": [
   [
    4201,
    4257,
    "O"
   ],
   [
    4200,
    4298,
    "E"
   ]
  ]
 },
 {
  "TLID": "68087633",
  "FULLNAME": "W Denneys Rd",
  "LFROMHN": "4001",
  "LTOHN": "4199",
  "RFROMHN": null,
  "RTOHN": null,
  "PARITYL": "O",
  "PARITYR": null,
  "ZIPL": "19904",
  "ZIPR": null,
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1200",
  "EDGE_MTFCC": "S1200",
  "matched_key": "W|DENNEYS|RD",
  "normalized_ranges(min/max,不含方向)": [
   [
    4001,
    4199,
    "O"
   ]
  ]
 },
 {
  "TLID": "68113338",
  "FULLNAME": "W Denneys Rd",
  "LFROMHN": "4401",
  "LTOHN": "4499",
  "RFROMHN": "4300",
  "RTOHN": "4498",
  "PARITYL": "O",
  "PARITYR": "E",
  "ZIPL": "19904",
  "ZIPR": "19904",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1200",
  "EDGE_MTFCC": "S1200",
  "matched_key": "W|DENNEYS|RD",
  "normalized_ranges(min/max,不含方向)": [
   [
    4401,
    4499,
    "O"
   ],
   [
    4300,
    4498,
    "E"
   ]
  ]
 }
]
```
**合并后黄金记录（24 字段）**
```json
{
 "house_number": "2871",
 "house_number_suffix": null,
 "street_pre_dir": "W",
 "street_name": "Denneys",
 "street_post_type": "Rd",
 "street_post_dir": null,
 "street_full": "W Denneys Rd",
 "unit": null,
 "building_floor": null,
 "postal_city": "Dover",
 "municipal_city": "Dover",
 "county_name": "Kent County",
 "county_fips": "10001",
 "state_abbr": "DE",
 "state_name": "Delaware",
 "state_fips": "10",
 "zip5": "19904",
 "plus4": null,
 "zip9": "19904",
 "latitude": 39.1787717,
 "longitude": -75.5995553,
 "addr_type": "Residential",
 "area_code": "302",
 "timezone": "America/New_York",
 "full_formatted_address": "2871 W Denneys Rd, Dover, DE 19904",
 "source_confidence": "S-Tier: NAD+OVERTURE+OA+TIGER[range]"
}
```

### 4.3 `1 North AMERICAN Avenue`（归一化键 `AMERICAN|AVE`）

**NAD 原始（非空字段全列）**
```json
{
 "OBJECTID": 98170435,
 "Add_Number": 1,
 "AddNo_Full": "1",
 "St_PreDir": "North",
 "St_Name": "AMERICAN",
 "St_PosTyp": "Avenue",
 "StNam_Full": "North AMERICAN Avenue",
 "County": "Kent",
 "Inc_Muni": "Dover",
 "Post_City": "Dover",
 "Nbrhd_Comm": "Dover",
 "State": "DE",
 "Zip_Code": "19901",
 "UUID": "a955f773-4b51-4e74-be90-cb24de9f2586",
 "AddAuth": "Kent County Delaware",
 "Longitude": -75.52447090193627,
 "Latitude": 39.16221041644114,
 "NatGrid": "18SVJ5468834908",
 "Placement": "Unknown",
 "AddrPoint": "-75.52447090193627 39.16221041644114",
 "AddrClass": "Numbered Thoroughfare Address",
 "DateUpdate": 1760659200000,
 "Addr_Type": "Unknown",
 "NAD_Source": "Kent County Delaware",
 "DataSet_ID": "{a955f773-4b51-4e74-be90-cb24de9f2586}",
 "_lon": -75.5244709016223,
 "_lat": 39.16221041571502
}
```
**Overture 原始**
```json
{
 "street": "North AMERICAN Avenue",
 "number": "1",
 "postcode": "19901",
 "postal_city": "Dover",
 "address_levels": [
  {
   "value": "DE"
  },
  {
   "value": "Dover"
  }
 ],
 "country": "US",
 "sources": [
  {
   "property": "",
   "dataset": "NAD",
   "license": "LicenseRef-Public-Domain-US",
   "record_id": "A955F773-4B51-4E74-BE90-CB24DE9F2586",
   "update_time": "2026-09-18T19:39:08.275Z",
   "confidence": null,
   "between": null,
   "provider": "nad",
   "resource": "nad",
   "version": "20250924"
  }
 ],
 "version": 1,
 "_lon": -75.52447090193627,
 "_lat": 39.16221041644114,
 "_id": "ac3edd50-aa65-43f6-9d0d-eaf117c0f81f",
 "_upstream": "NAD"
}
```
**OpenAddresses 原始**
```json
{
 "LON": "-75.5244691",
 "LAT": "39.1622025",
 "NUMBER": "1",
 "STREET": "N AMERICAN AVE",
 "CITY": "Dover",
 "POSTCODE": "19901",
 "HASH": "647cb7684e9af346"
}
```
**TIGER 号段原始**
```json
[
 {
  "TLID": "68110937",
  "FULLNAME": "American Ave",
  "LFROMHN": "100",
  "LTOHN": "198",
  "RFROMHN": "101",
  "RTOHN": "139",
  "PARITYL": "E",
  "PARITYR": "O",
  "ZIPL": "19901",
  "ZIPR": "19901",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "AMERICAN|AVE",
  "normalized_ranges(min/max,不含方向)": [
   [
    100,
    198,
    "E"
   ],
   [
    101,
    139,
    "O"
   ]
  ]
 },
 {
  "TLID": "68088219",
  "FULLNAME": "American Ave",
  "LFROMHN": null,
  "LTOHN": null,
  "RFROMHN": "17",
  "RTOHN": "99",
  "PARITYL": null,
  "PARITYR": "O",
  "ZIPL": null,
  "ZIPR": "19901",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "AMERICAN|AVE",
  "normalized_ranges(min/max,不含方向)": [
   [
    17,
    99,
    "O"
   ]
  ]
 },
 {
  "TLID": "68110938",
  "FULLNAME": "American Ave",
  "LFROMHN": "200",
  "LTOHN": "212",
  "RFROMHN": "141",
  "RTOHN": "199",
  "PARITYL": "E",
  "PARITYR": "O",
  "ZIPL": "19901",
  "ZIPR": "19901",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "AMERICAN|AVE",
  "normalized_ranges(min/max,不含方向)": [
   [
    200,
    212,
    "E"
   ],
   [
    141,
    199,
    "O"
   ]
  ]
 }
]
```
**合并后黄金记录（24 字段）**
```json
{
 "house_number": "1",
 "house_number_suffix": null,
 "street_pre_dir": "N",
 "street_name": "American",
 "street_post_type": "Ave",
 "street_post_dir": null,
 "street_full": "N American Ave",
 "unit": null,
 "building_floor": null,
 "postal_city": "Dover",
 "municipal_city": "Dover",
 "county_name": "Kent County",
 "county_fips": "10001",
 "state_abbr": "DE",
 "state_name": "Delaware",
 "state_fips": "10",
 "zip5": "19901",
 "plus4": null,
 "zip9": "19901",
 "latitude": 39.1622104,
 "longitude": -75.5244709,
 "addr_type": "Residential",
 "area_code": "302",
 "timezone": "America/New_York",
 "full_formatted_address": "1 N American Ave, Dover, DE 19901",
 "source_confidence": "S-Tier: NAD+OVERTURE+OA+TIGER[range]"
}
```

### 4.4 `116 26TH Street`（归一化键 `26TH|ST`）

**NAD 原始（非空字段全列）**
```json
{
 "OBJECTID": 98125586,
 "Add_Number": 116,
 "AddNo_Full": "116",
 "St_Name": "26TH",
 "St_PosTyp": "Street",
 "StNam_Full": "26TH Street",
 "County": "Kent",
 "Inc_Muni": "Dover",
 "Post_City": "Dover",
 "Nbrhd_Comm": "Dover",
 "State": "DE",
 "Zip_Code": "19902",
 "UUID": "601e6a91-fb4e-4dfd-9e95-83ea34025172",
 "AddAuth": "Kent County Delaware",
 "Longitude": -75.46892075282754,
 "Latitude": 39.11815707015073,
 "NatGrid": "18SVJ5946229993",
 "Placement": "Unknown",
 "AddrPoint": "-75.46892075282754 39.11815707015073",
 "AddrClass": "Numbered Thoroughfare Address",
 "DateUpdate": 1760659200000,
 "Addr_Type": "Unknown",
 "NAD_Source": "Kent County Delaware",
 "DataSet_ID": "{601e6a91-fb4e-4dfd-9e95-83ea34025172}",
 "_lon": -75.46892075262382,
 "_lat": 39.11815706975365
}
```
**Overture 原始**
```json
{
 "street": "26TH Street",
 "number": "116",
 "postcode": "19902",
 "postal_city": "Dover",
 "address_levels": [
  {
   "value": "DE"
  },
  {
   "value": "Dover"
  }
 ],
 "country": "US",
 "sources": [
  {
   "property": "",
   "dataset": "NAD",
   "license": "LicenseRef-Public-Domain-US",
   "record_id": "601E6A91-FB4E-4DFD-9E95-83EA34025172",
   "update_time": "2026-09-18T19:39:08.275Z",
   "confidence": null,
   "between": null,
   "provider": "nad",
   "resource": "nad",
   "version": "20250924"
  }
 ],
 "version": 1,
 "_lon": -75.46892075282754,
 "_lat": 39.11815707015073,
 "_id": "406061ec-89f1-4c6f-895a-0b1791463288",
 "_upstream": "NAD"
}
```
**OpenAddresses 原始**
```json
{
 "LON": "-75.4689189",
 "LAT": "39.1181492",
 "NUMBER": "116",
 "STREET": "26TH ST",
 "CITY": "Dover",
 "POSTCODE": "19902",
 "HASH": "94da87621dc8357f"
}
```
**TIGER 号段原始**
```json
[
 {
  "TLID": "68093527",
  "FULLNAME": "26th St",
  "LFROMHN": null,
  "LTOHN": null,
  "RFROMHN": "100",
  "RTOHN": "198",
  "PARITYL": null,
  "PARITYR": "E",
  "ZIPL": null,
  "ZIPR": "19902",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "26TH|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    100,
    198,
    "E"
   ]
  ]
 }
]
```
**合并后黄金记录（24 字段）**
```json
{
 "house_number": "116",
 "house_number_suffix": null,
 "street_pre_dir": null,
 "street_name": "26th",
 "street_post_type": "St",
 "street_post_dir": null,
 "street_full": "26th St",
 "unit": null,
 "building_floor": null,
 "postal_city": "Dover",
 "municipal_city": "Dover",
 "county_name": "Kent County",
 "county_fips": "10001",
 "state_abbr": "DE",
 "state_name": "Delaware",
 "state_fips": "10",
 "zip5": "19902",
 "plus4": null,
 "zip9": "19902",
 "latitude": 39.1181571,
 "longitude": -75.4689208,
 "addr_type": "Residential",
 "area_code": "302",
 "timezone": "America/New_York",
 "full_formatted_address": "116 26th St, Dover, DE 19902",
 "source_confidence": "S-Tier: NAD+OVERTURE+OA+TIGER[range]"
}
```

### 4.5 `403 9TH Street`（归一化键 `9TH|ST`）

**NAD 原始（非空字段全列）**
```json
{
 "OBJECTID": 98128873,
 "Add_Number": 403,
 "AddNo_Full": "403",
 "St_Name": "9TH",
 "St_PosTyp": "Street",
 "StNam_Full": "9TH Street",
 "County": "Kent",
 "Inc_Muni": "Dover",
 "Post_City": "Dover",
 "Nbrhd_Comm": "Dover",
 "State": "DE",
 "Zip_Code": "19902",
 "UUID": "6b73949f-1d31-45be-b4e5-c8d59ccae51f",
 "AddAuth": "Kent County Delaware",
 "Longitude": -75.48217778514383,
 "Latitude": 39.124980497727336,
 "NatGrid": "18SVJ5832030756",
 "Placement": "Unknown",
 "AddrPoint": "-75.48217778514383 39.124980497727336",
 "AddrClass": "Numbered Thoroughfare Address",
 "DateUpdate": 1552580673000,
 "Addr_Type": "Unknown",
 "NAD_Source": "Kent County Delaware",
 "DataSet_ID": "{6b73949f-1d31-45be-b4e5-c8d59ccae51f}",
 "_lon": -75.48217778505798,
 "_lat": 39.12498049805651
}
```
**Overture 原始**
```json
{
 "street": "9TH Street",
 "number": "403",
 "postcode": "19902",
 "postal_city": "Dover",
 "address_levels": [
  {
   "value": "DE"
  },
  {
   "value": "Dover"
  }
 ],
 "country": "US",
 "sources": [
  {
   "property": "",
   "dataset": "NAD",
   "license": "LicenseRef-Public-Domain-US",
   "record_id": "6B73949F-1D31-45BE-B4E5-C8D59CCAE51F",
   "update_time": "2026-09-18T19:39:08.275Z",
   "confidence": null,
   "between": null,
   "provider": "nad",
   "resource": "nad",
   "version": "20250924"
  }
 ],
 "version": 1,
 "_lon": -75.48217778514383,
 "_lat": 39.124980497727336,
 "_id": "58020404-2bcf-4843-8399-9b3542b824f1",
 "_upstream": "NAD"
}
```
**OpenAddresses 原始**
```json
{
 "LON": "-75.482176",
 "LAT": "39.1249726",
 "NUMBER": "403",
 "STREET": "9TH ST",
 "CITY": "Dover",
 "POSTCODE": "19902",
 "HASH": "ae311ea56a7a277c"
}
```
**TIGER 号段原始**
```json
[
 {
  "TLID": "68083455",
  "FULLNAME": "NE 9th St",
  "LFROMHN": "1",
  "LTOHN": "99",
  "RFROMHN": null,
  "RTOHN": null,
  "PARITYL": "O",
  "PARITYR": null,
  "ZIPL": "19963",
  "ZIPR": null,
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "9TH|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    1,
    99,
    "O"
   ]
  ]
 },
 {
  "TLID": "641695676",
  "FULLNAME": "9th St",
  "LFROMHN": "498",
  "LTOHN": "400",
  "RFROMHN": null,
  "RTOHN": null,
  "PARITYL": "E",
  "PARITYR": null,
  "ZIPL": "19902",
  "ZIPR": null,
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "9TH|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    400,
    498,
    "E"
   ]
  ]
 },
 {
  "TLID": "620131358",
  "FULLNAME": "9th St",
  "LFROMHN": null,
  "LTOHN": null,
  "RFROMHN": "499",
  "RTOHN": "401",
  "PARITYL": null,
  "PARITYR": "O",
  "ZIPL": null,
  "ZIPR": "19902",
  "PLUS4L": null,
  "PLUS4R": null,
  "ROAD_MTFCC": "S1400",
  "EDGE_MTFCC": "S1400",
  "matched_key": "9TH|ST",
  "normalized_ranges(min/max,不含方向)": [
   [
    401,
    499,
    "O"
   ]
  ]
 }
]
```
**合并后黄金记录（24 字段）**
```json
{
 "house_number": "403",
 "house_number_suffix": null,
 "street_pre_dir": null,
 "street_name": "9th",
 "street_post_type": "St",
 "street_post_dir": null,
 "street_full": "9th St",
 "unit": null,
 "building_floor": null,
 "postal_city": "Dover",
 "municipal_city": "Dover",
 "county_name": "Kent County",
 "county_fips": "10001",
 "state_abbr": "DE",
 "state_name": "Delaware",
 "state_fips": "10",
 "zip5": "19902",
 "plus4": null,
 "zip9": "19902",
 "latitude": 39.1249805,
 "longitude": -75.4821778,
 "addr_type": "Residential",
 "area_code": "302",
 "timezone": "America/New_York",
 "full_formatted_address": "403 9th St, Dover, DE 19902",
 "source_confidence": "S-Tier: NAD+OVERTURE+OA+TIGER[range]"
}
```

## 五、50 条完整黄金地址样本（19901 / 19904）

样本口径：全量黄金库 27,163 条中，19901/19904 共 23,196 条，按 (zip5, 街道, 门牌, 单元) 排序等距抽 50 条，并保证含多单元（APT/STE）样本；全库 zip5 分布见 3.2（另有 19902/19934/19936/19962/19961 等 Kent 县邮编）。

| # | full_formatted_address | street_full | unit | addr_type | zip5 | lat | lon | source_confidence |
|---|---|---|---|---|---|---|---|---|
| 1 | 10 Acacia Pl, Dover, DE 19901 | Acacia Pl |  | Residential | 19901 | 39.1679181 | -75.5006666 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 2 | 6926 Bayside Dr, Dover, DE 19901 | Bayside Dr |  | Residential | 19901 | 39.1952547 | -75.4724251 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 3 | 4009 Buttonwood Ct, Dover, DE 19901 | Buttonwood Ct |  | Residential | 19901 | 39.1218063 | -75.4901166 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 4 | 7009 Coconut Ct, Dover, DE 19901 | Coconut Ct |  | Residential | 19901 | 39.1154777 | -75.4817429 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 5 | 221 Dyke Branch Rd, Dover, DE 19901 | Dyke Branch Rd |  | Residential | 19901 | 39.2069918 | -75.5609621 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 6 | 61 Elm Ter, Dover, DE 19901 | Elm Ter |  | Residential | 19901 | 39.1541919 | -75.5206425 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 7 | 5005 Ginkgo Ct, Dover, DE 19901 | Ginkgo Ct |  | Residential | 19901 | 39.1227257 | -75.4914608 | A-Tier: NAD[no-tiger-street] |
| 8 | 353 Helena Dr, Dover, DE 19901 | Helena Dr |  | Residential | 19901 | 39.1996088 | -75.5478999 | A-Tier: NAD[no-tiger-street] |
| 9 | 5 Huntley Cir, Dover, DE 19901 | Huntley Cir |  | Residential | 19901 | 39.137012 | -75.5210601 | A-Tier: NAD[no-tiger-street] |
| 10 | 280 Kentwood Dr, Dover, DE 19901 | Kentwood Dr |  | Residential | 19901 | 39.2040479 | -75.5441955 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 11 | 2081 Leipsic Rd, Dover, DE 19901 | Leipsic Rd |  | Residential | 19901 | 39.198683 | -75.5311036 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 12 | 2004 Magnolia Ct, Dover, DE 19901 | Magnolia Ct |  | Residential | 19901 | 39.1189766 | -75.4886802 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 13 | 8 Millstone Ct, Dover, DE 19901 | Millstone Ct |  | Residential | 19901 | 39.1102955 | -75.520092 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 14 | 485 N East Ave, Dover, DE 19901 | N East Ave |  | Residential | 19901 | 39.1739564 | -75.5235518 | S-Tier: NAD+OVERTURE+OA+TIGER[street-only] |
| 15 | 4562 New Jersey Dr, Dover, DE 19901 | New Jersey Dr |  | Residential | 19901 | 39.106507 | -75.50375 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 16 | 194 Pennsylvania Ave, Dover, DE 19901 | Pennsylvania Ave |  | Residential | 19901 | 39.1650219 | -75.5249462 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 17 | 162 President Dr, Dover, DE 19901 | President Dr |  | Residential | 19901 | 39.1420446 | -75.5034952 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 18 | 19 Rockford Xing, Dover, DE 19901 | Rockford Xing |  | Residential | 19901 | 39.1719413 | -75.5083817 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 19 | 226 Royal Grant Way, Dover, DE 19901 | Royal Grant Way |  | Residential | 19901 | 39.1102381 | -75.5300248 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 20 | 968 S Little Creek Rd, Dover, DE 19901 | S Little Creek Rd |  | Residential | 19901 | 39.1567391 | -75.5004255 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 21 | 543 Schooner Way, Dover, DE 19901 | Schooner Way |  | Residential | 19901 | 39.1784374 | -75.5119666 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 22 | 71 St Jones Ave, Dover, DE 19901 | St Jones Ave |  | Residential | 19901 | 39.1380548 | -75.5102299 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 23 | 105 Teak Ct, Dover, DE 19901 | Teak Ct |  | Residential | 19901 | 39.1676127 | -75.4998085 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 24 | 55 W Lebanon Rd, Dover, DE 19901 | W Lebanon Rd |  | Residential | 19901 | 39.1179985 | -75.5181736 | S-Tier: NAD+OVERTURE+OA+TIGER[street-only] |
| 25 | 1840 Windswept Cir, Dover, DE 19901 | Windswept Cir |  | Residential | 19901 | 39.1243382 | -75.5036507 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 26 | 206 Artis Dr, Dover, DE 19904 | Artis Dr |  | Residential | 19904 | 39.144074 | -75.5838738 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 27 | 413 Beuvale Ln, Dover, DE 19904 | Beuvale Ln |  | Residential | 19904 | 39.1453509 | -75.5623572 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 28 | 61 Carnoustie Rd, Dover, DE 19904 | Carnoustie Rd |  | Residential | 19904 | 39.169124 | -75.5631926 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 29 | 307 Cold Spring Pl, Dover, DE 19904 | Cold Spring Pl |  | Residential | 19904 | 39.1621195 | -75.5556853 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 30 | 440 David Hall Rd, Dover, DE 19904 | David Hall Rd |  | Residential | 19904 | 39.1260795 | -75.5364305 | S-Tier: NAD+OVERTURE+TIGER[range] |
| 31 | 45 Forest Creek Dr, Dover, DE 19904 | Forest Creek Dr |  | Residential | 19904 | 39.1739604 | -75.551833 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 32 | 305 Gillibrook Ln, Dover, DE 19904 | Gillibrook Ln |  | Residential | 19904 | 39.1461831 | -75.5627378 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 33 | 32 Hardwood Dr, Dover, DE 19904 | Hardwood Dr |  | Residential | 19904 | 39.1830428 | -75.5941433 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 34 | 1601 John Clark Rd, Dover, DE 19904 | John Clark Rd |  | Residential | 19904 | 39.1264979 | -75.5367242 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 35 | 45 Lindale Dr, Dover, DE 19904 | Lindale Dr |  | Residential | 19904 | 39.1702148 | -75.5752836 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 36 | 211 Meadows Dr, Dover, DE 19904 | Meadows Dr |  | Residential | 19904 | 39.1842433 | -75.5650521 | A-Tier: NAD[no-tiger-street] |
| 37 | 416 N Bradford St, Dover, DE 19904 | N Bradford St |  | Residential | 19904 | 39.1677063 | -75.5298445 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 38 | 151 N Queen St, Dover, DE 19904 | N Queen St |  | Residential | 19904 | 39.162815 | -75.5313583 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 39 | 321 Norway Dr, Dover, DE 19904 | Norway Dr |  | Residential | 19904 | 39.2129979 | -75.5756254 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 40 | 230 Pebble Valley Dr, Dover, DE 19904 | Pebble Valley Dr |  | Residential | 19904 | 39.1623992 | -75.567629 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 41 | 124 Quail Hollow Dr, Dover, DE 19904 | Quail Hollow Dr |  | Residential | 19904 | 39.1723945 | -75.5496461 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 42 | 280 Rittenhouse Dr, Dover, DE 19904 | Rittenhouse Dr |  | Residential | 19904 | 39.2058865 | -75.5895268 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 43 | 133 S Governors Ave, Dover, DE 19904 | S Governors Ave |  | Residential | 19904 | 39.1584955 | -75.5269184 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 44 | 740 S State St, Dover, DE 19904 | S State St |  | Residential | 19904 | 39.1487323 | -75.522704 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 45 | 941 Silver Lake Blvd, Dover, DE 19904 | Silver Lake Blvd |  | Residential | 19904 | 39.1770889 | -75.5365498 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 46 | 83 Glenn St Apt A, Dover, DE 19901 | Glenn St | Apt A | Residential (Multi-Unit) | 19901 | 39.1277796 | -75.4908195 | S-Tier: NAD+OVERTURE+OA+TIGER[street-only] |
| 47 | 730 Horsepond Rd A, Dover, DE 19901 | Horsepond Rd | A | Residential (Multi-Unit) | 19901 | 39.153354 | -75.4872366 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 48 | 730 Horsepond Rd B, Dover, DE 19901 | Horsepond Rd | B | Residential (Multi-Unit) | 19901 | 39.1527442 | -75.4873358 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 49 | 268 Kentwood Dr Lot 268, Dover, DE 19901 | Kentwood Dr | Lot 268 | Residential (Multi-Unit) | 19901 | 39.2035423 | -75.5448846 | S-Tier: NAD+OVERTURE+OA+TIGER[range] |
| 50 | 150 Martin Luther King Jr Blvd S Apt RM09, Dover, DE 19901 | Martin Luther King Jr Blvd S | Apt RM09 | Residential (Multi-Unit) | 19901 | 39.1563924 | -75.5196922 | A-Tier: NAD[no-tiger-street] |

## 六、产物清单

| 产物 | 说明 |
|---|---|
| `data/dover/task003/dover_golden_addresses.jsonl` | 全量黄金库 27,163 条（28 字段） |
| `data/dover/task003/dover_golden_addresses.csv` | CSV 版（同字段） |
| `data/dover/task003/golden_sample_50.csv` | 50 条代表性样本 |
| `data/dover/task003/golden_fillrate_24fields.csv` | 24 字段非空率 |
| `data/dover/task003/dover_funnel.json` | 完整漏斗 + 分布 + 源统计（机器可读） |
| `data/dover/task003/five_address_4source_comparisons.json` | 5 条四源原始对照 |
| `docs/task003_report.md` | 本报告 |
| `scripts/dover_golden_coalesce.py` | 生产级 ETL 脚本（runner 上运行） |

## 七、决策与口径声明（不确定处的自行判定）

1. **plus4/zip9 不造数**：四源实测全空，按既定硬事实保持 `null`；`zip9` 降级为 `zip5`。唯一替代路径是等 USPS ZIP+4 商业数据源，不属本任务范围。
2. **addr_type 为启发式**：NAD `Addr_Type`/`Placement`/`AddrClass` 全库单值常量，无判别力。规则 = 有 unit → `Residential (Multi-Unit)`；`LandmkName`/`Building` 非空或街道属于 Dover 商业走廊（['COMMERCE', 'DUPONT', 'LOOCKERMAN']）→ `Commercial`；其余 → `Residential`。
3. **A-Tier 包含『仅街道命中』的 NAD 记录**：TIGER 号段覆盖不到的街名（新街/私路）若直接丢弃会误杀真实地址（多单元公寓、新建房），因此保留并以 `tiger_verify` 列显式标注可追溯。
4. **匹配采用三级键**：strict（前方向|核心|后缀|后方向）→ loose（核心|后缀）→ core（仅核心），逐级降级；跨源方向词与后缀全称/缩写差异由词表统一（West↔W、Road↔Rd…）。
5. **坐标口径**：TIGER 为 NAD83、其余 WGS84，且各源精度差 3 个数量级；空间判定统一按 WGS84 容差（K 县面 + Dover 市面 + ZCTA），`tiger_distance_m` 记录最近道路顶点距离供复核。
6. **OA `<Null>` 脏行按指令零容忍丢弃**：其中有门牌+街名、仅因 `UNIT/CITY` 标记为 `<Null>` 的行（112 / 111）本可视为有效地址，但指令明确列为脏数据 → 遵从指令丢弃，并在此声明。

## 八、复现命令

```bash
# 全部发生在 GitHub Actions runner（本地服务器零下载）
gh release download dover-raw-20261015-0450 -R ip9988001/world-map-data-test -D data/dover/task003/raw
python scripts/dover_golden_coalesce.py --input-dir data/dover/task003/raw \
  --out-dir data/dover/task003 --docs-dir docs
```

> 结论：四源全量 → 漏斗后 **27,163** 条黄金地址（S 25,018 / A 2,145），24 字段宽表已投产；`plus4` 按实测事实留空，无任何编造数据。
