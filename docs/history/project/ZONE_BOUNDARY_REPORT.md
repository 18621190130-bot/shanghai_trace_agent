# ShanghaiTrace 初始产品边界报告

这些边界用于 discovery 与产品路线范围，不是行政/法律边界。按用户授权通过检查后自动用于 Phase 2.5。

GCJ-02；顶点顺序为纬度、经度；审核带为边界内外 150 m，带内标记 needs_boundary_review，不自动 reject。

## 武康—复兴—徐家汇 (`wukang_fuxing_xujiahui`)

北侧以华山路—复兴西路至长乐路的衡复街区外缘为折线；东侧贴陕西南路走向，南侧由肇嘉浜路折向天钥桥路及南丹路；西侧沿华山路、徐家汇核心街坊回接。道路间顶点为产品近似包络，不声称逐段道路测绘。

西南徐家汇段是名称与既有 p32/p33/p35 所需的连续走廊，不纳入整个徐汇；p13旧代表点疑偏北，保留原点并记录后续坐标核验。

Seed 数量：8；全部覆盖：True；面积约 5.2657 km²；审核带 150 m；polygon 有效且无自交。

```json
[[31.2121, 121.4367], [31.216, 121.4458], [31.2208, 121.4577], [31.2145, 121.4596], [31.209, 121.4608], [31.203, 121.4623], [31.201, 121.4518], [31.1965, 121.4438], [31.189, 121.443], [31.1885, 121.4348], [31.1955, 121.4335], [31.2002, 121.4355], [31.205, 121.437]]
```

| Seed | 名称 | 覆盖 |
|---|---|---|
| p2 | 永康路与嘉善路口 | needs_review |
| p11 | 建业里 | inside_pilot |
| p12 | 陕南邨 | inside_pilot |
| p13 | 武康大楼 | inside_pilot |
| p21 | 上海宋庆龄故居纪念馆 | inside_pilot |
| p32 | 徐家汇天主堂 | inside_pilot |
| p33 | 徐家汇书院 | inside_pilot |
| p35 | 徐家汇商圈 | inside_pilot |

来源（道路与区域上下文用于产品判断，非来源官方划定本 polygon）：
- https://lhsr.sh.gov.cn/srgl/20220617/cf46474f-4259-4087-ada5-105e2ec94971.html
- https://www.shanghai.gov.cn/xuhui/index.html
- https://www.amap.com/detail/B0FFLKX9L6
- https://www.amap.com/detail/B0FFI8IG7M
- https://www.amap.com/detail/B0KR5HYRLD
- https://www.amap.com/detail/B0FFHPGFQZ
- https://www.amap.com/detail/B0LR7AID10
- https://www.amap.com/detail/B0FFHPHVYA
- https://www.amap.com/detail/B0M2MRNDAM
- https://www.amap.com/detail/B0H3TUK613
- https://www.amap.com/detail/B00154815D
- https://www.amap.com/detail/B0FFGJQOL3
- https://www.amap.com/detail/B00151EA79
- https://www.amap.com/detail/B0FFFZS38D
- https://www.amap.com/detail/B0H2A569FM

## 老城厢—新天地—外滩 (`old_city_central`)

北西侧沿南京西路—南京东路街坊串联张园和南京路；东北侧止于外白渡桥南侧，东侧顺外滩浦西岸线向南至老城厢东缘；南侧沿中华路及复兴路相关街坊，西南以思南公馆街坊回接重庆南路。滨江折线不包含浦东。

张园位于名称核心的西北侧，按既有 p9 和南京路连续街区保留，不把静安区纳入；新天地北里与张园旧代表坐标存在地图差异，旧点和主POI位置都在产品范围内，不通过改坐标凑边界。

Seed 数量：8；全部覆盖：True；面积约 7.6729 km²；审核带 150 m；polygon 有效且无自交。

```json
[[31.2288, 121.4585], [31.2317, 121.469], [31.2355, 121.4795], [31.2421, 121.4865], [31.2414, 121.4903], [31.2365, 121.4925], [31.23, 121.4965], [31.2232, 121.5], [31.216, 121.4965], [31.2151, 121.4925], [31.2171, 121.484], [31.2118, 121.4712], [31.2138, 121.4668], [31.22, 121.465], [31.2254, 121.4585]]
```

| Seed | 名称 | 覆盖 |
|---|---|---|
| p7 | 新天地北里（石库门街区） | inside_pilot |
| p9 | 张园 | inside_pilot |
| p14 | 外滩·陈毅广场 | needs_review |
| p15 | 豫园 | inside_pilot |
| p20 | 上海城隍庙 | inside_pilot |
| p23 | 思南公馆 | inside_pilot |
| p24 | 中共一大纪念馆 | inside_pilot |
| p34 | 南京路步行街 | inside_pilot |

来源（道路与区域上下文用于产品判断，非来源官方划定本 polygon）：
- https://lhsr.sh.gov.cn/srgl/20220617/cf46474f-4259-4087-ada5-105e2ec94971.html
- https://www.shanghai.gov.cn/gwk/search/content/bd8ed5c6-4e7b-4197-91bf-10971f53b902
- https://ghzyj.sh.gov.cn/tpxw/20231121/623eca025e1c4b1fa0e64ee992e06477.html
- https://www.amap.com/detail/B00155QIPB
- https://www.amap.com/detail/B0J0Y7JX9Z
- https://www.amap.com/detail/B0MUF7HNR3
- https://www.amap.com/detail/B001574I9I
- https://www.amap.com/detail/B0FFHFDQ1C
- https://www.amap.com/detail/B0M2ZU2ZC3
- https://www.amap.com/detail/B00156YMMX
- https://www.amap.com/detail/B0FFK0XU84
- https://www.amap.com/detail/B0FFF6XN5S
- https://www.amap.com/detail/BZAFR000SK
- https://www.amap.com/detail/B0FFHPFZ6R
- https://www.amap.com/detail/B0M2MRN1AB
- https://www.amap.com/detail/B0FFHPO4RO
- https://www.amap.com/detail/B0L0BSU5AW
- https://www.amap.com/detail/B0I6RUVKAZ
- https://www.amap.com/detail/B0FFHPGMRE
- https://www.amap.com/detail/B0M2MRMWUP
- https://www.amap.com/detail/B0FFHD418I
- https://www.amap.com/detail/BZAFR002ID
- https://www.amap.com/detail/B0IA3DU6GU
- https://www.amap.com/detail/B0IA3DULUO

## 鲁迅公园—四川北路 (`hongkou_literary`)

北侧取鲁迅公园北缘，西侧沿东江湾路—四川北路西侧街坊；东侧覆盖山阴路、溧阳路相关街坊，向海伦路—沙泾路1933既有节点收束；南侧在海宁路以北回接四川北路。以连续文学街区和步行连接空间限定范围。

1933老场坊为既有东南端文化建筑节点，与文学核心存在主题差别，但经溧阳路—海伦路连接，不扩至北外滩；鲁迅公园内部纪念馆与雕塑不重复计站。

Seed 数量：6；全部覆盖：True；面积约 2.5803 km²；审核带 150 m；polygon 有效且无自交。

```json
[[31.2745, 121.479], [31.2745, 121.4857], [31.27, 121.4868], [31.2655, 121.487], [31.261, 121.4875], [31.2567, 121.4935], [31.2525, 121.493], [31.2519, 121.487], [31.253, 121.48], [31.257, 121.477], [31.2635, 121.4768], [31.2695, 121.478]]
```

| Seed | 名称 | 覆盖 |
|---|---|---|
| p4 | 鲁迅故居 | inside_pilot |
| p10 | 今潮8弄 | needs_review |
| p16 | 鲁迅公园 | inside_pilot |
| p25 | 1927·鲁迅与内山纪念书局 | inside_pilot |
| p26 | 中国左翼作家联盟会址纪念馆 | inside_pilot |
| p27 | 1933老场坊 | needs_review |

来源（道路与区域上下文用于产品判断，非来源官方划定本 polygon）：
- https://lhsr.sh.gov.cn/srgl/20220617/cf46474f-4259-4087-ada5-105e2ec94971.html
- https://www.shhk.gov.cn/xwzx/002008/002008040/20230505/c99546c4-c705-4670-8ff9-d703233d444e.html
- https://www.shhk.gov.cn/xwzx/002008/002008040/20240812/88aa3935-4aec-4b22-bf63-33915fd9c319.html
- https://www.amap.com/detail/B00155KZKW
- https://www.amap.com/detail/B0FFILLF0X
- https://www.amap.com/detail/B00155LPBC
- https://www.amap.com/detail/B0FFH56QSK
- https://www.amap.com/detail/B0FFHPLT57
- https://www.amap.com/detail/B0M2MRMYNJ
- https://www.amap.com/detail/B0FFH02DM0
- https://www.amap.com/detail/B00155P1VL
- https://www.amap.com/detail/B0FFH165MQ
- https://www.amap.com/detail/B0LD1PJRN1
- https://www.amap.com/detail/B00155FLFD
- https://www.amap.com/detail/BZAGR0033N
- https://www.amap.com/detail/B00155L3AW

## 徐汇西岸滨江 (`west_bund`)

沿用已验收西岸边界；不重新采集或 enrichment。

原审批150米审核带决定保持。

Seed 数量：5；全部覆盖：True；面积约 2.758 km²；审核带 150 m；polygon 有效且无自交。

```json
[[31.157, 121.458], [31.157, 121.467], [31.17, 121.467], [31.1775, 121.4648], [31.182, 121.4665], [31.1895, 121.473], [31.1895, 121.466], [31.18, 121.458]]
```

| Seed | 名称 | 覆盖 |
|---|---|---|
| p5 | 龙美术馆（西岸馆） | inside_pilot |
| p28 | 西岸美术馆 | inside_pilot |
| p29 | 上海油罐艺术中心 | inside_pilot |
| p30 | Gate M 西岸梦中心 | needs_review |
| p31 | 星美术馆 | needs_review |

来源（道路与区域上下文用于产品判断，非来源官方划定本 polygon）：
- https://www.westbund.com/cn/index/NEWS-CENTER/2022-0930.html
