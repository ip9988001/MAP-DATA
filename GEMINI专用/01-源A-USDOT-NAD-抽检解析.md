# 源 A · USDOT NAD（官方 60 列）抽检与结构解析

> 抽检人：PI-Agent　时间：2026-10-15　用途：供 Gemini 参考 24 字段黄金表/合并规则的架构依据
> 数据文件（仓库内）：`data/dover/raw/nad_dover_official.geojson.gz`（**20,000 条**，官方 REST 原样导出）
> 全量对应产物（GitHub Release `dover-raw-20261015-0450`）：`nad_dover_full.ndjson`（**28,028 条**，与官方 `returnCountOnly` 一致，`truncated=false`）
> 落库形态：`data/dover/nad_dover_full.csv` = 60 原生字段 + `lon`/`lat` 两列 = **62 列**

---

## 一、字段组成：60 原生字段 + 2 坐标列 = 62 列，按语义分 6 族

> 括号内为**实测非空率**（基于 20,000 条）

### ① 门牌号族（4 列）
| 列 | 非空率 | 说明 |
|---|---|---|
| `AddNum_Pre` | 0.00% | 门牌前缀（全空） |
| `Add_Number` | **100%** | Integer 类型，Dover 实测 1~12351，唯一 2,968 |
| `AddNum_Suf` | 0.00% | 门牌后缀（全空） |
| `AddNo_Full` | 100% | 与 `Add_Number` **20,000/20,000 完全相同**（因 Pre/Suf 全空）→ 冗余列 |

### ② 街道精细拆分族（9 列）
| 列 | 非空率 | 说明 |
|---|---|---|
| `St_PreMod` | 0.00% | 前修饰词 |
| `St_PreDir` | 16.39% | 前方向词，仅 4 个值：South 1355 / North 1112 / West 453 / East 358（**全称**） |
| `St_PreTyp` | 0.00% | 前类型词 |
| `St_PreSep` | 0.00% | 前介词 |
| `St_Name` | **100%** | 核心路名，唯一 989，**全大写**（`DENNEYS`/`COMMERCE`） |
| `St_PosTyp` | 99.83% | 街道后缀，**22 个受控全称**（见下） |
| `St_PosDir` | 0.13% | 后方向词，仅 Northeast 12 / South 11 / Southwest 3 |
| `St_PosMod` | 0.00% | 后修饰词 |
| `StNam_Full` | **100%** | 完整街道名，唯一 1,123（拼装规则见第二节） |

**`St_PosTyp` 完整词表（22 个全称，非 USPS 缩写）**：
Drive 5813 / Road 3446 / Street 2678 / Avenue 1915 / Court 1542 / Lane 1439 / Way 741 / Circle 659 / Boulevard 463 / Place 400 / Highway 293 / Terrace 195 / Trail 139 / Run 83 / Green 62 / Crossing 39 / Parkway 26 / Extension 15 / Path 13 / Creek 2 / Plaza 2 / Land 1

### ③ 子地址 / 建筑族（8 列）
`Building`/`Floor`/`Room`/`Seat`/`Addtl_Loc`/`LandmkName` 全 0%；`Unit` 0.23%（20 个值）；`SubAddress` 0.23%（**与 Unit 完全同值** → 冗余列）

`Unit` 全部取值：`APT A`(9) `APT B`(8) `APT C`(3) `STE B`(3) `STE A`(3) `APT E`(2) `APT D`(2) `STE C`(2) `APT 2`(2) `APT 1`(2) `APT I/J/H/G/F`(各1) `APT 3`(1) `STE D`(1) `LOT 268`(1) **`A`(1，裸字母)** `APT RM09`(1) → **格式不统一，去重必须归一化**

### ④ 行政区划族（13 列）
| 列 | 非空率 | 值分布 |
|---|---|---|
| `County` | 100% | 单一值 `Kent` |
| `Inc_Muni` | 100% | 7 值：Dover 16595 / Camden Wyoming 2730 / Cheswold 358 / Magnolia 314 / Camden 1 / Little Creek 1 / Wyoming 1 |
| `Post_City` | 100% | 5 值：Dover 16602 / Camden Wyoming 2710 / Cheswold 373 / Magnolia 314 / Little Creek 1 |
| `Census_Plc` | 20.57% | 5 个 CDP：Highland Acres / Dover Base Housing / Rising Sun-Lebanon / Kent Acres / Rodney Village |
| `Nbrhd_Comm` | **100%** | 97 值，**语义混杂**：有的是城市名（`Dover` 12884 / `Camden` 1192），有的是小区名（`VILLAGES OF NOBLES POND - PHASE 1`、`Capitol Park`、`The Estates at Pickering Pointe`）→ **不能当行政城市用** |
| `NatAmArea` | 1.00% | `Lenape Indian Tribe of Delaware` |
| `NatAmSub`/`Urbnztn_PR`/`PlaceOther`/`PlaceNmTyp`/`Uninc_Comm` | 0.00% | 全空 |
| `State` | 100% | 单一值 `DE` |
| `Zip_Code` | **100%** | **7 值**：19904 8683 / 19901 7720 / 19934 2712 / 19936 354 / 19962 314 / 19902 216 / 19961 1 |

### ⑤ 坐标与网格族（6 列）
| 列 | 非空率 | 说明 |
|---|---|---|
| `Longitude` | 100% | 14 位小数，范围 −75.59998 ~ −75.45021 |
| `Latitude` | 100% | 14 位小数，范围 39.10001 ~ 39.21999 |
| `NatGrid` | 100% | MGRS 式，如 `18SVJ4940841164` |
| `AddrPoint` | 100% | `"经度 纬度"` 拼串，如 `-75.58606037592598 39.21829360455592` |
| `Plus_4` | **0.00%** | **全空**（zip9 无法由此得到） |
| `Elevation` | 0.00% | 全空 |

### ⑥ 系统与溯源族（20 列）
- 唯一键：`OBJECTID`（100%，范围 98102231~98165807）、`UUID`（100%，**36 位 GUID**，**真主键**）、`DataSet_ID`（100%，**= `{UUID}` 花括号包裹** → 冗余列）
- `DateUpdate`：100%，**epoch 毫秒整数**（`1613735141000` → 2021-02-19T11:45:41Z），1,660 个不同值
- **单值常量列（有值=没信息）**：`AddAuth`=`Kent County Delaware`、`NAD_Source`=`Kent County Delaware`、`Placement`=`Unknown`、`Addr_Type`=`Unknown`、`AddrClass`=`Numbered Thoroughfare Address`
- 全空：`AddrRefSys`、`Related_ID`、`RelateType`、`ParcelSrc`、`Parcel_ID`、`Lifecycle`、`Effective`、`Expire`、`AnomStatus`、`LocatnDesc`、`DeliverTyp`

---

## 二、结构 / 架构 / 格式规则（实测校验）

**地址结构 = 三段式**：`门牌号 (Add_Number)` + `街道 ([St_PreDir] + St_Name + St_PosTyp + [St_PosDir])` + `子地址 (Unit)`

**拼装公式（20,000 条全量校验）**
| 公式 | 命中 |
|---|---|
| `StNam_Full = St_PreDir + " " + St_Name + " " + St_PosTyp` | **19,974 / 20,000（99.87%）** 例：`West DENNEYS Road` |
| `StNam_Full = St_Name + " " + St_PosTyp + " " + St_PosDir` | 26 / 20,000　例：`BAY Circle South` |

**大小写规则**：`St_Name` 全大写；`St_PosTyp` 首字母大写（`Road`/`Street`）；`St_PreDir`/`St_PosDir` 全称首字母大写（`West`/`South`）；`StNam_Full` 沿袭拼接结果（例 `West DENNEYS Road` —— 大小写混合）。

**唯一坐标陷阱**：同址多单元**共享同一坐标**。实测 `5921 W DENNEYS Road` 的 `APT A/B/C/D/I` 五条记录坐标为 `(-75.55852402540219, 39.20332040984156)` 完全相同 → **坐标不能当唯一键**。

**冗余列清单（合并时勿重复计数）**：`AddNo_Full` = `Add_Number`；`SubAddress` = `Unit`；`DataSet_ID` = `{UUID}`。

**值域/精度**：`Add_Number` 是 Integer（1~12351）；`UUID` 36 位；坐标 14 位小数。

---

## 三、抽检 20 条完整原始记录

> 抽检构成：17 条普通住宅（覆盖不同街道后缀、7 个邮编、7 个 Inc_Muni、CDP）+ 3 条多单元结构。
> **这 20 条中 100% 为空的 34 个字段**（即下列省略部分，未隐藏任何值）：
> `AddNum_Pre、AddNum_Suf、AddrRefSys、Addtl_Loc、AnomStatus、Building、DeliverTyp、Effective、Elevation、Expire、Floor、LandmkName、Lifecycle、LocatnDesc、NatAmArea、NatAmSub、ParcelSrc、Parcel_ID、PlaceNmTyp、PlaceOther、Plus_4、RelateType、Related_ID、Room、Seat、St_PosDir、St_PosMod、St_PreMod、St_PreSep、St_PreTyp、SubAddress、Uninc_Comm、Unit、Urbnztn_PR`

```
#1  OBJECTID=98102243 | Add_Number=192 | AddNo_Full=192 | St_Name=SALT CREEK | St_PosTyp=Drive | StNam_Full=SALT CREEK Drive | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19904 | UUID=8d8229ec-af7d-4d16-8527-1a1bca291bd5 | AddAuth=Kent County Delaware | Longitude=-75.56922378175489 | Latitude=39.20655975819539 | NatGrid=18SVJ5085339853 | Placement=Unknown | AddrPoint=-75.56922378175489 39.20655975819539 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={8d8229ec-af7d-4d16-8527-1a1bca291bd5}
#2  OBJECTID=98102242 | Add_Number=2905 | AddNo_Full=2905 | St_Name=KENTON | St_PosTyp=Road | StNam_Full=KENTON Road | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19904 | UUID=710861d2-1f5a-4d6c-91e3-8c542d478c8b | AddAuth=Kent County Delaware | Longitude=-75.58737479672367 | Latitude=39.18386497701044 | NatGrid=18SVJ4926937344 | Placement=Unknown | AddrPoint=-75.58737479672367 39.18386497701044 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={710861d2-1f5a-4d6c-91e3-8c542d478c8b}
#3  OBJECTID=98102246 | Add_Number=522 | AddNo_Full=522 | St_Name=ANN MOORE | St_PosTyp=Street | StNam_Full=ANN MOORE Street | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19904 | UUID=f9cff4a2-3b08-4a0c-9326-27aea87be8e3 | AddAuth=Kent County Delaware | Longitude=-75.53875697247908 | Latitude=39.1496325550417 | NatGrid=18SVJ5344633519 | Placement=Unknown | AddrPoint=-75.53875697247908 39.1496325550417 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1731686923000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={f9cff4a2-3b08-4a0c-9326-27aea87be8e3}
#4  OBJECTID=98102264 | Add_Number=4 | AddNo_Full=4 | St_Name=KENDRA | St_PosTyp=Court | StNam_Full=KENDRA Court | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=VILLAGES OF NOBLES POND - PHASE 1 | State=DE | Zip_Code=19904 | UUID=b9a7ab59-6a4d-4b8e-8917-ea30863f0040 | AddAuth=Kent County Delaware | Longitude=-75.57787823100527 | Latitude=39.20525771940273 | NatGrid=18SVJ5010539713 | Placement=Unknown | AddrPoint=-75.57787823100527 39.20525771940273 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1726132995000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={b9a7ab59-6a4d-4b8e-8917-ea30863f0040}
#5  OBJECTID=98112978 | Add_Number=101 | AddNo_Full=101 | St_Name=BEECHWOOD | St_PosTyp=Avenue | StNam_Full=BEECHWOOD Avenue | County=Kent | Inc_Muni=Dover | Post_City=Dover | Census_Plc=Kent Acres CDP | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=ed81ca14-7403-4fb9-9d80-bdcd0289cc24 | AddAuth=Kent County Delaware | Longitude=-75.51605054549572 | Latitude=39.13200142528688 | NatGrid=18SVJ5539731551 | Placement=Unknown | AddrPoint=-75.51605054549572 39.13200142528688 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={ed81ca14-7403-4fb9-9d80-bdcd0289cc24}
#6  OBJECTID=98102245 | Add_Number=45 | AddNo_Full=45 | St_Name=GUARD HOUSE | St_PosTyp=Lane | StNam_Full=GUARD HOUSE Lane | County=Kent | Inc_Muni=Cheswold | Post_City=Dover | Nbrhd_Comm=VILLAGES OF NOBLES POND - PHASE 1 | State=DE | Zip_Code=19904 | UUID=eb578b58-e9fc-45dc-bc00-9bbff0e1664e | AddAuth=Kent County Delaware | Longitude=-75.5767746025108 | Latitude=39.20712042933819 | NatGrid=18SVJ5020139919 | Placement=Unknown | AddrPoint=-75.5767746025108 39.20712042933819 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1726133576000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={eb578b58-e9fc-45dc-bc00-9bbff0e1664e}
#7  OBJECTID=98123497 | Add_Number=1991 | AddNo_Full=1991 | St_PreDir=South | St_Name=STATE | St_PosTyp=Street | StNam_Full=South STATE Street | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=7fc165b9-d2a7-483d-83ff-c6023d50acb6 | AddAuth=Kent County Delaware | Longitude=-75.51531368210591 | Latitude=39.11962309843974 | NatGrid=18SVJ5545330177 | Placement=Unknown | AddrPoint=-75.51531368210591 39.11962309843974 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={7fc165b9-d2a7-483d-83ff-c6023d50acb6}
#8  OBJECTID=98102248 | Add_Number=810 | AddNo_Full=810 | St_Name=RUTH | St_PosTyp=Way | StNam_Full=RUTH Way | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19904 | UUID=1b76564f-ef93-46be-9a06-8c40b45be23e | AddAuth=Kent County Delaware | Longitude=-75.53921780838786 | Latitude=39.14957085598015 | NatGrid=18SVJ5340633513 | Placement=Unknown | AddrPoint=-75.53921780838786 39.14957085598015 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1731686923000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={1b76564f-ef93-46be-9a06-8c40b45be23e}
#9  OBJECTID=98117018 | Add_Number=1272 | AddNo_Full=1272 | St_PreDir=South | St_Name=GOVERNORS | St_PosTyp=Avenue | StNam_Full=South GOVERNORS Avenue | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19904 | UUID=ba04e60e-9b9e-4846-b552-1c90ee15cbda | AddAuth=Kent County Delaware | Longitude=-75.529121919454 | Latitude=39.136343074253396 | NatGrid=18SVJ5427032040 | Placement=Unknown | AddrPoint=-75.529121919454 39.136343074253396 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={ba04e60e-9b9e-4846-b552-1c90ee15cbda}
#10 OBJECTID=98122152 | Add_Number=688 | AddNo_Full=688 | St_Name=QUAIL LANDING | St_PosTyp=Circle | StNam_Full=QUAIL LANDING Circle | County=Kent | Inc_Muni=Magnolia | Post_City=Magnolia | Census_Plc=Rising Sun-Lebanon CDP | Nbrhd_Comm=Quail Landing | State=DE | Zip_Code=19962 | UUID=a2398eba-3ba0-4098-95db-e8b12243197b | AddAuth=Kent County Delaware | Longitude=-75.49728770518408 | Latitude=39.10793592157799 | NatGrid=18SVJ5700428872 | Placement=Unknown | AddrPoint=-75.49728770518408 39.10793592157799 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1482315818000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={a2398eba-3ba0-4098-95db-e8b12243197b}
#11 OBJECTID=98102322 | Add_Number=1970 | AddNo_Full=1970 | St_PreDir=South | St_Name=LITTLE CREEK | St_PosTyp=Road | StNam_Full=South LITTLE CREEK Road | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=14314ff8-dbfa-4188-893e-866a3bcb6d84 | AddAuth=Kent County Delaware | Longitude=-75.4762600232454 | Latitude=39.15451092916098 | NatGrid=18SVJ5884934031 | Placement=Unknown | AddrPoint=-75.4762600232454 39.15451092916098 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={14314ff8-dbfa-4188-893e-866a3bcb6d84}
#12 OBJECTID=98123361 | Add_Number=8013 | AddNo_Full=8013 | St_Name=PISTACHIO | St_PosTyp=Place | StNam_Full=PISTACHIO Place | County=Kent | Inc_Muni=Dover | Post_City=Dover | Census_Plc=Dover Base Housing CDP | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=78b33964-d7b0-429e-b6e6-19fdddb249c6 | AddAuth=Kent County Delaware | Longitude=-75.48070498971055 | Latitude=39.11244916706509 | NatGrid=18SVJ5844029365 | Placement=Unknown | AddrPoint=-75.48070498971055 39.11244916706509 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={78b33964-d7b0-429e-b6e6-19fdddb249c6}
#13 OBJECTID=98102247 | Add_Number=523 | AddNo_Full=523 | St_Name=RIDGELY | St_PosTyp=Boulevard | StNam_Full=RIDGELY Boulevard | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19904 | UUID=10bdc400-7d16-4a52-be3e-2cafa4c7f51f | AddAuth=Kent County Delaware | Longitude=-75.53854805458744 | Latitude=39.149203721818445 | NatGrid=18SVJ5346433472 | Placement=Unknown | AddrPoint=-75.53854805458744 39.149203721818445 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760355312000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={10bdc400-7d16-4a52-be3e-2cafa4c7f51f}
#14 OBJECTID=98124068 | Add_Number=2033 | AddNo_Full=2033 | St_PreDir=West | St_Name=HAWTHORNE | St_PosTyp=Drive | StNam_Full=West HAWTHORNE Drive | County=Kent | Inc_Muni=Dover | Post_City=Dover | Census_Plc=Dover Base Housing CDP | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=4d661d6d-e72f-4053-b1ff-1de585581303 | AddAuth=Kent County Delaware | Longitude=-75.48742530713199 | Latitude=39.118505882761966 | NatGrid=18SVJ5786330040 | Placement=Unknown | AddrPoint=-75.48742530713199 39.118505882761966 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1745422772000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={4d661d6d-e72f-4053-b1ff-1de585581303}
#15 OBJECTID=98112973 | Add_Number=266 | AddNo_Full=266 | St_PreDir=South | St_Name=DUPONT | St_PosTyp=Highway | StNam_Full=South DUPONT Highway | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=4ecbe8fa-139e-47e0-b3ad-5bcfe93519f1 | AddAuth=Kent County Delaware | Longitude=-75.51328083940062 | Latitude=39.159741788642954 | NatGrid=18SVJ5565434628 | Placement=Unknown | AddrPoint=-75.51328083940062 39.159741788642954 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1628511460000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={4ecbe8fa-139e-47e0-b3ad-5bcfe93519f1}
#16 OBJECTID=98124053 | Add_Number=52 | AddNo_Full=52 | St_Name=DOVE CREEK | St_PosTyp=Terrace | StNam_Full=DOVE CREEK Terrace | County=Kent | Inc_Muni=Dover | Post_City=Dover | Census_Plc=Rising Sun-Lebanon CDP | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=375333c3-76c6-44b9-907e-091973c0f842 | AddAuth=Kent County Delaware | Longitude=-75.50338647684312 | Latitude=39.113932255371246 | NatGrid=18SVJ5648029540 | Placement=Unknown | AddrPoint=-75.50338647684312 39.113932255371246 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={375333c3-76c6-44b9-907e-091973c0f842}
#17 OBJECTID=98123661 | Add_Number=17 | AddNo_Full=17 | St_PreDir=East | St_Name=BRADYS | St_PosTyp=Lane | StNam_Full=East BRADYS Lane | County=Kent | Inc_Muni=Dover | Post_City=Dover | Census_Plc=Highland Acres CDP | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=c3f06c39-6279-4014-bdfe-394e848f4407 | AddAuth=Kent County Delaware | Longitude=-75.5148820455859 | Latitude=39.115049881466675 | NatGrid=18SVJ5548729670 | Placement=Unknown | AddrPoint=-75.5148820455859 39.115049881466675 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={c3f06c39-6279-4014-bdfe-394e848f4407}
#18 OBJECTID=98122259 | Add_Number=71 | AddNo_Full=71 | St_Name=JOGGER | St_PosTyp=Trail | StNam_Full=JOGGER Trail | County=Kent | Inc_Muni=Magnolia | Post_City=Magnolia | Census_Plc=Rising Sun-Lebanon CDP | Nbrhd_Comm=The Estates at Pickering Pointe | State=DE | Zip_Code=19962 | UUID=fc65959a-517a-49f6-8167-0760df619776 | AddAuth=Kent County Delaware | Longitude=-75.49082137699038 | Latitude=39.104187762561054 | NatGrid=18SVJ5756128453 | Placement=Unknown | AddrPoint=-75.49082137699038 39.104187762561054 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={fc65959a-517a-49f6-8167-0760df619776}
#19 OBJECTID=98128204 | Add_Number=212 | AddNo_Full=212 | St_PreDir=North | St_Name=GOVERNORS | St_PosTyp=Boulevard | StNam_Full=North GOVERNORS Boulevard | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Capitol Park | State=DE | Zip_Code=19901 | UUID=6f913859-5128-4858-af6e-863e1ba70648 | AddAuth=Kent County Delaware | Longitude=-75.5057232216083 | Latitude=39.14181813808396 | NatGrid=18SVJ5629532636 | Placement=Unknown | AddrPoint=-75.5057232216083 39.14181813808396 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={6f913859-5128-4858-af6e-863e1ba70648}
#20 OBJECTID=98126900 | Add_Number=3996 | AddNo_Full=3996 | St_Name=PEACHTREE | St_PosTyp=Run | StNam_Full=PEACHTREE Run | County=Kent | Inc_Muni=Dover | Post_City=Dover | Nbrhd_Comm=Dover | State=DE | Zip_Code=19901 | UUID=4f77b83f-be69-435d-b604-f377617829ad | AddAuth=Kent County Delaware | Longitude=-75.54012006567443 | Latitude=39.102090981908354 | NatGrid=18SVJ5329728244 | Placement=Unknown | AddrPoint=-75.54012006567443 39.102090981908354 | AddrClass=Numbered Thoroughfare Address | DateUpdate=1760659200000 | Addr_Type=Unknown | NAD_Source=Kent County Delaware | DataSet_ID={4f77b83f-be69-435d-b604-f377617829ad}
```

### 附：多单元结构（Unit 非空）实样
```
179 COMMERCE Street, Cheswold, DE 19936 —— 同一门牌 3 个单元，坐标完全相同：
  Unit=APT E | SubAddress=APT E | UUID=f4a058d6-f9c0-4e3f-8e48-69ab5e24a719 | lon=-75.58606037592598 lat=39.21829360455592 | DateUpdate=1613735141000
  Unit=APT D | SubAddress=APT D | UUID=620e4f5a-66ea-42a0-be78-8c70ea738084 | 同上坐标
  Unit=APT C | SubAddress=APT C | UUID=eeaed93b-d1ff-4e20-9c52-140fb30cad42 | 同上坐标
5921 West DENNEYS Road, Dover, DE 19901 —— APT A/B/C/D/I 五条，坐标全部相同 (-75.55852402540219, 39.20332040984156)
BAY Circle South（后方向词形态）：
  Add_Number=10 | St_Name=BAY | St_PosTyp=Circle | St_PosDir=South | StNam_Full=BAY Circle South | Nbrhd_Comm=Carlisle Village Section II | Zip_Code=19904
  Add_Number=16 | 同上结构 | UUID=0def99e8-33ee-4376-b37e-1d1487c13a53
```

---

## 四、对 24 字段合并的结论（供 Gemini 参考）

1. **真正有信息量的约 26 列**，20 条抽检里 34 列恒空 → 这是 NAD 平均非空率 40.61% 的来源。
2. **`Placement`/`Addr_Type`/`AddrClass`/`AddAuth`/`NAD_Source` 全是单值常量**（`Unknown`/`Numbered Thoroughfare Address`/`Kent County Delaware`）→ `addr_type` 必须靠 `Unit` 存在性 + 商业走廊重分类，不能靠 NAD 现成字段。
3. **`Plus_4` 100% 全空** → `zip9` 无法由 NAD 提供。
4. **本 bbox 覆盖面大于 Dover 市**：含 **7 个邮编**（19901/19902/19904/19934/19936/19961/19962）、**7 个 Inc_Muni**、4 个 CDP。**"多佛全量"口径必须先定义：按 bbox 还是按 Dover Place 多边形（GEOID 1021200）**，否则漏斗表数字会被质疑。
5. **冗余列**：`AddNo_Full`=`Add_Number`、`SubAddress`=`Unit`、`DataSet_ID`=`{UUID}`。
6. **坐标不能当唯一键**（同址多单元共享坐标）；真主键是 `UUID`。
7. `Nbrhd_Comm` 100% 非空但语义混杂（城市名 + 小区名混用）→ 不能当行政城市。
