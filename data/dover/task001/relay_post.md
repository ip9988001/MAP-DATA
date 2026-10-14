TASK-001 交付：Dover DE 19901 四源样本对照 + 全字段非空填充率
作战室（免登录直接打开）: https://gempi.gtop.dev
仓库: https://github.com/ip9988001/world-map-data-test
产物: data/dover/task001/task001_records.jsonl | task001_records.csv | fillrate_4sources.csv | docs/task001_report.md

【一、四源规模与已抽样】
· USDOT NAD（官方正牌通道 A，字段 60 列）: 全量 28028 行 / 已抽 20
· Overture Maps（字段 11 列）: 全量 28027 行 / 已抽 20
· OpenAddresses us/de（字段 11 列）: 全量 92455 行 / 已抽 20
· Census TIGER addrfeat（字段 25 列）: 全量 11072 行 / 已抽 15 + 边界 5 条

【二、全字段非空填充率（关键字段；全量见 fillrate_4sources.csv）】
--- USDOT NAD (official, 60 cols) ---
  Add_Number         100.00%   (28028/28028)
  St_Name            100.00%   (28028/28028)
  StNam_Full         100.00%   (28028/28028)
  County             100.00%   (28028/28028)
  Inc_Muni           100.00%   (28028/28028)
  Post_City          100.00%   (28028/28028)
  Zip_Code           100.00%   (28028/28028)
  Plus_4               0.00%   (0/28028)
  UUID               100.00%   (28028/28028)
  AddAuth            100.00%   (28028/28028)
  Longitude          100.00%   (28028/28028)
  Latitude           100.00%   (28028/28028)
  Placement          100.00%   (28028/28028)
  Addr_Type          100.00%   (28028/28028)
  NAD_Source         100.00%   (28028/28028)
  [该源 60 个字段整体平均非空率 40.61%]

--- Overture Maps (bbox 全量) ---
  address_levels     100.00%   (28027/28027)
  country            100.00%   (28027/28027)
  lat                100.00%   (28027/28027)
  lon                100.00%   (28027/28027)
  number             100.00%   (28027/28027)
  postcode           100.00%   (28027/28027)
  sources            100.00%   (28027/28027)
  street             100.00%   (28027/28027)
  unit                 0.19%   (52/28027)
  [该源 11 个字段整体平均非空率 90.93%]

--- OpenAddresses us/de (全量) ---
  LON                100.00%   (92455/92455)
  LAT                100.00%   (92455/92455)
  NUMBER              99.30%   (91808/92455)
  STREET              99.96%   (92421/92455)
  UNIT                 0.62%   (577/92455)
  CITY                80.19%   (74141/92455)
  DISTRICT             0.00%   (0/92455)
  REGION               0.00%   (0/92455)
  POSTCODE            86.00%   (79512/92455)
  ID                   0.00%   (0/92455)
  HASH               100.00%   (92455/92455)
  [该源 11 个字段整体平均非空率 60.55%]

--- Census TIGER addrfeat (Kent 全量) ---
  TLID               100.00%   (11072/11072)
  FULLNAME           100.00%   (11072/11072)
  [该源 25 个字段整体平均非空率 70.84%]

【三、80 条样本（每条一行；完整键值对见 task001_records.jsonl）】
  1. [NAD] #5921 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT I Type=Unknown (-75.55852402540219,39.20332040984156)
  2. [NAD] #5921 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT D Type=Unknown (-75.55852402540219,39.20332040984156)
  3. [NAD] #5921 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT C Type=Unknown (-75.55852402540219,39.20332040984156)
  4. [NAD] #5921 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT B Type=Unknown (-75.55852402540219,39.20332040984156)
  5. [NAD] #5931 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT J Type=Unknown (-75.55833318048569,39.20311975816247)
  6. [NAD] #5931 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT H Type=Unknown (-75.55833318048569,39.20311975816247)
  7. [NAD] #5931 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT G Type=Unknown (-75.55833318048569,39.20311975816247)
  8. [NAD] #5931 West DENNEYS Road | Dover/Kent/DE 19901 | Unit=APT F Type=Unknown (-75.55833318048569,39.20311975816247)
  9. [NAD] #1991 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51531368210591,39.11962309843974)
 10. [NAD] #2275 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.5144082247538,39.112577987799995)
 11. [NAD] #2297 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51426231719084,39.110047005397675)
 12. [NAD] #2293 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51449123037135,39.110459935698486)
 13. [NAD] #2291 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51445387000932,39.11072314193764)
 14. [NAD] #2289 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.5145118769953,39.110944474572285)
 15. [NAD] #2287 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51450594503827,39.111171429361036)
 16. [NAD] #2285 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51456261860476,39.11138629739942)
 17. [NAD] #2281 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51459066814942,39.11160188483775)
 18. [NAD] #2279 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51454817575488,39.11177860956841)
 19. [NAD] #2284 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.51517907046718,39.110955443351635)
 20. [NAD] #2282 South STATE Street | Dover/Kent/DE 19901 | Unit=None Type=Unknown (-75.5152922166716,39.111486117458846)
 21. [OVERTURE] 1870 South STATE Street |  19901 | (-75.51687328799936,39.12353619110574)
 22. [OVERTURE] 1860 South STATE Street |  19901 | (-75.5169535710106,39.123815801899454)
 23. [OVERTURE] 1840 South STATE Street |  19901 | (-75.51708452773308,39.12407934085116)
 24. [OVERTURE] 1820 South STATE Street |  19901 | (-75.51739414736281,39.12470290524546)
 25. [OVERTURE] 1830 South STATE Street |  19901 | (-75.51725737280141,39.12440690828663)
 26. [OVERTURE] 1810 South STATE Street |  19901 | (-75.51752492703682,39.124978651818246)
 27. [OVERTURE] 1740 South STATE Street |  19901 | (-75.51799843507256,39.12678608123444)
 28. [OVERTURE] 1694 South STATE Street |  19901 | (-75.51840204079741,39.12760651567034)
 29. [OVERTURE] 1695 South STATE Street |  19901 | (-75.51767664421669,39.12758494638719)
 30. [OVERTURE] 1685 South STATE Street |  19901 | (-75.51778286742613,39.12791688609328)
 31. [OVERTURE] 1675 South STATE Street |  19901 | (-75.51738339362115,39.12846404358506)
 32. [OVERTURE] 1622 South STATE Street |  19901 | (-75.51942681082595,39.12967836941234)
 33. [OVERTURE] 1630 South STATE Street |  19901 | (-75.51931933856163,39.129440388843605)
 34. [OVERTURE] 1671 South STATE Street |  19901 | (-75.51808385939194,39.12882092977983)
 35. [OVERTURE] 1673 South STATE Street |  19901 | (-75.51741857334497,39.12899131973113)
 36. [OVERTURE] 1679 South STATE Street |  19901 | (-75.51734346746412,39.1295876163482)
 37. [OVERTURE] 1679 South STATE Street |  19901 | (-75.51719969051172,39.12961634045743)
 38. [OVERTURE] 1679 South STATE Street |  19901 | (-75.51686017657919,39.12971434898367)
 39. [OVERTURE] 1679 South STATE Street |  19901 | (-75.51748558124777,39.129835487942806)
 40. [OVERTURE] 1679 South STATE Street |  19901 | (-75.51760856386275,39.12981679073135)
 41. [OA]  HAZLETTVILLE RD |   | (-75.5597279,39.1492736)
 42. [OA] 835 BAY RD |   | (-75.5004951,39.1477108)
 43. [OA] 15 PIN OAK DR |   | (-75.5571213,39.1745631)
 44. [OA] 213 N BRADFORD ST |   | (-75.5278239,39.1642163)
 45. [OA] 54 S KIRKWOOD ST |   | (-75.5317355,39.1587209)
 46. [OA]  WESTVIEW TER |   | (-75.5294789,39.1423933)
 47. [OA] 647 WYOMING AVE |   | (-75.5332478,39.1448257)
 48. [OA] 1207 E DIVISION ST |   | (-75.5070399,39.1671497)
 49. [OA] 124 E WATER ST |   | (-75.5193113,39.1543697)
 50. [OA] 117 HOLMES ST |   | (-75.4989172,39.1580082)
 51. [OA] 375 S NEW ST |   | (-75.5272291,39.1560136)
 52. [OA]  GREENS OF DOVER |   | (-75.5575901,39.1631479)
 53. [OA]  OAKMONT DR |   | (-75.5626097,39.1748134)
 54. [OA] 945 FOREST ST |   | (-75.5407959,39.1593863)
 55. [OA] 222 W REED ST |   | (-75.5283887,39.1591371)
 56. [OA]  THE GREEN |   | (-75.5240687,39.1561707)
 57. [OA] 211 DELAWARE AVE |   | (-75.522465,39.165026)
 58. [OA]  TOPAZ CIR |   | (-75.5592185,39.1801202)
 59. [OA]  S FARMVIEW DR |   | (-75.5516171,39.155691)
 60. [OA] 18 N GOVERNORS AVE |   | (-75.528803,39.1615329)
 61. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=641078146
 62. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68087633
 63. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68113338
 64. [TIGER-range] None-None N State St | ZIP=None PLUS4=None SIDE=None TLID=636203731
 65. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68087652
 66. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68087655
 67. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68102266
 68. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68102265
 69. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68103178
 70. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=636203727
 71. [TIGER-range] None-None W Denneys Rd | ZIP=None PLUS4=None SIDE=None TLID=68114041
 72. [TIGER-range] None-None State College Rd | ZIP=None PLUS4=None SIDE=None TLID=68101092
 73. [TIGER-range] None-None N State St | ZIP=None PLUS4=None SIDE=None TLID=649807798
 74. [TIGER-range] None-None N State St | ZIP=None PLUS4=None SIDE=None TLID=68087888
 75. [TIGER-range] None-None N State St | ZIP=None PLUS4=None SIDE=None TLID=639568257
 76. [TIGER-boundary] ZCTA5 19901 count=1 where=ZCTA5='19901' GEOID=19901
 77. [TIGER-boundary] ZCTA5 19904 count=1 where=ZCTA5='19904' GEOID=19904
 78. [TIGER-boundary] Dover Place count=1 where=STATE='10' AND BASENAME='Dover' GEOID=1021200
 79. [TIGER-boundary] Kent County count=1 where=STATE='10' AND COUNTY='001' GEOID=10001
 80. [TIGER-boundary] DE State count=1 where=STATE='10' GEOID=10

【四、方法与边界（如实披露）】
· NAD 走交通部官方正牌通道 A（xOi1kZaI0eWDREZv），字段 60 列由元数据动态解析；第三方阉割镜像 Do88DoK2xjTUCXd1 已在代码层拉黑。
· 抽取偏好：ZIP=19901 命中者优先，且 DENNEYS / State St / Loockerman St 置前（TASK-001 点名）。
· TIGER 边界命中：ZCTA5 19901, ZCTA5 19904, Dover Place, Kent County, DE State（未命中候选 [{'label': 'DE State', 'where': "STUSPS='DE'", 'count': 0, 'fields': []}, {'label': 'DE State', 'where': "STATEFP='10'", 'count': 0, 'fields': []}]）
· TIGER addrfeat 是**道路门牌区间表**（FROMHN-TOHN/TLID），与前三源的「点地址」不同性质，不可直接合并。
· Overture 的 address_levels / sources 是嵌套结构，在宽表里按 JSON 字符串落库。
