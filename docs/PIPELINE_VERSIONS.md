# 流水线版本与回滚

## v0（当前稳定版 · 已存档）

- **tag**：`v0-pipeline`　**branch**：`pipeline-v0`
- **commit**：`921da87`（2026-10-17）
- **回滚**：`git checkout v0-pipeline`，或 `git reset --hard v0-pipeline && git push -f origin main`
- **能力**：
  - NAD 主路径 `returnIdsOnly + objectIds(POST 批量)`，400k 静默上限用**四象限递归**破
  - 四源自证完整（`MANIFEST.completeness`）+ 只读质量统计（`quality.state_distribution`）
  - 发布门禁四把锁：缺源/空壳、NAD 覆盖不全、TIGER 双头对账、ISO 州码校验
  - 全球行政编码注册表（`rules/geo/`，249 国 + 5,046 区划）
- **产物形态**：一州一 tag，资产按源分文件（`nad_us_ri_full.ndjson` 等），**单 job 串行**
- **已发 Release**：`raw-US-DE-v1`（751,212 行）、`raw-US-RI-v1`（569,222 行 / 100% 覆盖）

## v1（规划中 · 按县切片 + 压缩 + 矩阵）

改造目标与已验证事实：

1. **按县真实边界（多边形）切片**，每片自证 `ids == count`
   - 实测：Providence 县多边形 = 204,087 行，ids 也是 204,087；`County='Providence'` 属性过滤同样 204,087（三者一致）
   - 州界多边形 = 391,461，与 `State='RI'` 完全一致
   - 溢出（不属于本州）= 州 bbox 569,222 − 州界 391,461 = **177,761** = MA 151,213 + CT 26,548（双源咬合）
2. **溢出单独打一个包**（不按县、不按州切），用于后续交叉核验
3. **全部分片 gzip**（无损），同时记录「压缩后 sha256」+「解压后 sha256」+ 解压后行数
4. **命名**：`{源}-US-{州}-{县FIPS5}-{县短名}`，如 `NAD-US-RI-44007-providence.ndjson.gz`；
   溢出包 `NAD-US-RI-OUTOFSTATE.ndjson.gz`；州级 `OVERTURE-US-RI.parquet`
5. **一州一 tag 不变**，只是资产数变多

### v1 已识别的两个硬问题（决定实现方式）

- **问题 A：大县的主键清单同样会撞 400k 上限**
  LA 县约 270 万条 → `returnIdsOnly` 照样被静默截断。
- **问题 B：多边形没法像 bbox 那样四象限切**
  县界是多边形，切矩形没有意义。

→ **统一解法：按 OBJECTID 区间二分**（纯属性切分，与几何/属性过滤正交，天然不重不漏）。
先 `outStatistics` 取 `min/max/count`，再对 `[lo,hi)` 二分，直到每段 ids < 400,000。
这条路对「州 bbox」「县多边形」「任意 where 过滤」全部通用，可替代现有四象限逻辑。

### v1 落地顺序（一次只动一个变量）

1. `--nad-ids-slicing oid`（OID 区间二分）→ 先与四象限并行存在，默认仍是 quadrant
2. `--pack-mode county_shards`（按县切片 + gzip + 新命名）→ 默认仍是 single
3. 用一个县数少的州（DE，3 个县）验证
4. 切默认值，重建 `raw-US-DE-v1` / `raw-US-RI-v1`（同名 tag 重发，保持"一州一 tag"）
5. 最后加矩阵工作流（一县一 job，`max-parallel: 2`）

### 回滚纪律

- v1 改造期间，**默认路径永远保持 v0 行为**；新逻辑全部走开关，验不过就关掉，main 始终可跑。
- 每个里程碑打 tag：`v1a-oid-slicing`、`v1b-county-shards`、`v1c-matrix`。
