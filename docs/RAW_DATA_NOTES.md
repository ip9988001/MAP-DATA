# 原始数据特征备忘录（只用来看坑，不含任何清洗规则）

> 本仓库定位：**只做采集与归档（EL）**，产物是"真实世界的数据镜像"。
> 本文件只客观记录在实测中发现的数据特征，**不给处理方案**——怎么清洗、去重、
> 合并、裁剪，全部由下游 Transform 仓库自行决定。
> 实测样本：`raw-US-RI-v1`（NAD 头 12MB / 8,495 行完整解析）+ 四源全量产物。

## 1. 范围口径：BBox 是矩形，必然含邻州

`scope.bbox` 是州的外接矩形，下载层**不做空间裁剪**（保持上游原样）。
以 RI 为例，BBox 内 NAD 的 `State` 实测分布：

| State | 行数 | 占比 |
|---|---|---|
| RI | 391,461 | 68.8% |
| MA | 151,213 | 26.6% |
| CT | 26,548 | 4.7% |
| 合计 | 569,222 | 100% |

同一 BBox 下 Overture 也含邻州点（抽样首条即 CT `Stonington 06378`）。

精确数字以每次运行写进 `MANIFEST.json` 的 `quality.state_distribution` 为准
（该块由流式扫描产出，与落盘文件逐行对齐，只读、不改数据）。

## 2. NAD 字段特征

- **邮编在 `Zip_Code`**（抽样 8,495 行 100% 有值，格式如 `06351`）；
  `Post_Code` 同批 **0% 有值（全空）**，`Plus_4` 亦空。
- **`Post_City` 实测 100% 为字符串 `"Not stated"`**。
- 真正有填充的是 `County`、`Inc_Muni`（均 100%）。
- `NAD_Source` 直接标明数据提供方（如 `State of Rhode Island` /
  `State of Connecticut`），可作为州归属的第二佐证。
- `Addr_Type` 取值示例：`Single Family Home` / `Seasonal Home` /
  `Multi-Family Home` / `Commercial` / `Unknown`（邻州段多为 `Unknown`）。
- 字段总表：`nad_full_columns.json`（60 字段）与 `nad_native_metadata.json`
  （服务端原始图层元数据，含别名/类型/长度）。
- 落盘额外字段：`_lon` / `_lat`（由 geometry 的 x/y 拆出，便于直接建点）。

## 3. 各源规模关系（不要拿它们互相对账）

| 源 | 计数含义 | RI 实测 |
|---|---|---|
| NAD | 门牌点 | 569,222 |
| Overture | 门牌 feature | 569,372 |
| OpenAddresses | 各源原始行（未合并） | 488,709 |
| TIGER addrfeat | **地址范围线段**，非门牌点 | 62,103 |

TIGER `addrfeat` 是拓扑号段（每段覆盖一个地址区间），量级比门牌点小一个数量级，
两者不可比。

## 4. OpenAddresses 包特征

- 每个 zip 内是 `us/<st>/<src>.csv`，表头 11 列：
  `LON,LAT,NUMBER,STREET,UNIT,CITY,DISTRICT,REGION,POSTCODE,ID,HASH`（实际顺序以文件为准）。
- 不同源之间**可能重叠**：RI 的 `statewide` 与 `city_of_cranston` / `providence`
  实测无交集，但 `statewide` 自身含 2,896 行重复（488,709 → 去重 485,813）。
- 上游不发布逐源行数声明（`/runs/{run}/us/{st}/{src}.json` 实测 404），
  因此 `MANIFEST.completeness.openaddresses` 记录的是 run id + 包内实标行数。

## 5. 已知的上游限制（影响完整性的部分）

- **Esri `returnIdsOnly` 有 400,000 条静默上限**：整表 count 97,928,946，
  ids 恒返回 400,000 且不报错。因此主键清单必须与同 BBox 的 `returnCountOnly`
  对账；不足即四象限递归切分（RI 实测 1 层、4 个叶子）。
- `returnCountOnly` / `returnIdsOnly` 的 GET 请求在参数过大时会 414/400，
  `objectIds` 批取必须走 POST 表单。
- Overture CLI 的 `-f` 只接受 `geojson` / `geojsonseq` / `geoparquet`
  （写 `parquet` 会 rc=2）。

## 6. 产物一致性怎么自查

`MANIFEST.json` 里每个资产同时给了两个摘要：

- `sha256`：**整个文件**的 sha256（字节级校验用）
- `sha256_head`：前 1MB 的 sha256 前 16 位（只取一小段做快检用）

另有 `row_counts`（每个数据产物可数则记）与 `completeness`（四源"上游声明 vs
本地实得"对照，含对账方法）。
