# world-map-data-test

World Address Data Factory 的**公开测试仓库** —— 与生产仓库 `MAP-DATA` 完全隔离，用于试验「按城市切片取数」的机器人流程。

## 铁律

**所有数据下载都在 GitHub Actions 的 runner 上执行**，本地服务器只写代码、触发、看结果、看产物。任何 GB 级总包都不落到本地。

## 机器人 #1：`dover-fetch`

把 **Dover, DE** 从四个数据源「按邮编 / BBox / SQL / 州小包」切出来 —— 不下全美总包。

| 源 | 取数方式 | 现状 |
|---|---|---|
| Overture Maps (addresses) | `overturemaps download --bbox=...` 云端按框切 | 见 `data/dover/manifest.json` |
| USDOT NAD (ArcGIS REST) | `FeatureServer/0/query` + `resultOffset` 分页；官方图层拒绝匿名查询时自动回退镜像 | 同上 |
| OpenAddresses.io | `us/de` 州/县级成品小包（每次现查最新 run id） | 同上 |
| Census TIGERweb | ZCTA5 / Incorporated Places / Counties / States + TIGER/Line 小包 | 同上 |

### 锚定参数（四源统一口径）

| 项 | 值 |
|---|---|
| 州 | `DE` / FIPS `10` |
| 县 | `Kent County` / FIPS `10001` |
| 市 | `Dover` / Place FIPS `1021200` |
| 邮编 | `19901`（扩展 `19904`） |
| BBox | `[-75.60, 39.10, -75.45, 39.22]`（西经, 南纬, 东经, 北纬） |

### 产物

- `data/dover/raw/` — 各源原始产物（Overture geojson / NAD geojson / OA zip / TIGER json+zip）
- `data/dover/*.csv` — 各源 19901 抽样（≤500 条）
- `data/dover/align_19901_main_state.csv` — **三源并排对齐样本**（邮编 19901 且街道含 `MAIN` 或 `STATE`，排序后取前 300–500 条）
- `data/dover/manifest.json` — 每个源的状态 / 耗时 / 条数 / 字节 / 错误
- `docs/dover_report.md` — 自动生成的人类可读报告

### 手动触发

Actions → `dover-fetch` → Run workflow（可改 `state/city/zip/bbox`，默认就是 Dover）。

本地运行（同样要遵守铁律：别在服务器上下 GB 级包）：

```bash
pip install -r requirements.txt
python bots/dover_fetch.py
```
