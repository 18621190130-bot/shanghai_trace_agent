"""Versioned initial boundary decision, backed by saved map observations and official context."""
import json
from pathlib import Path
from src.poi_repository import POIRepository
from src.poi_pipeline.boundary import POLYGON
from src.poi_pipeline.geometry import validate_polygon
from src.poi_pipeline.sources.base import utc_now
from src.poi_pipeline.sources.official_source import SEEDS
from src.poi_pipeline.sources.amap_source import AmapSource

ROOT=Path(__file__).resolve().parents[1]
ROADS='https://lhsr.sh.gov.cn/srgl/20220617/cf46474f-4259-4087-ada5-105e2ec94971.html'
XUHUI='https://www.shanghai.gov.cn/xuhui/index.html'
PARKS='https://www.shanghai.gov.cn/gwk/search/content/cfa0770c-00d3-4733-ae5a-93ec852c1541'
HONGKOU='https://www.shhk.gov.cn/xwzx/002008/002008040/20230505/c99546c4-c705-4670-8ff9-d703233d444e.html'
TIANAI='https://www.shhk.gov.cn/xwzx/002008/002008040/20240812/88aa3935-4aec-4b22-bf63-33915fd9c319.html'
SICHUAN='https://www.shhk.gov.cn/xwzx/002006/20210303/1af66a88-d678-4800-9550-b9dc471ca58d.html'
OLD='https://www.shanghai.gov.cn/gwk/search/content/bd8ed5c6-4e7b-4197-91bf-10971f53b902'
FUXING='https://www.shanghai.gov.cn/nw4411/20260622/98dbfc7640924743b9b8c477426dbbca.html'

SPECS={
'wukang_fuxing_xujiahui': dict(
 polygon=[(31.2121,121.4367),(31.2160,121.4458),(31.2208,121.4577),(31.2145,121.4596),(31.2090,121.4608),(31.2030,121.4623),(31.2010,121.4518),(31.1965,121.4438),(31.1890,121.4430),(31.1885,121.4348),(31.1955,121.4335),(31.2002,121.4355),(31.2050,121.4370)],
 basis='北侧以华山路—复兴西路至长乐路的衡复街区外缘为折线；东侧贴陕西南路走向，南侧由肇嘉浜路折向天钥桥路及南丹路；西侧沿华山路、徐家汇核心街坊回接。道路间顶点为产品近似包络，不声称逐段道路测绘。',
 disputes='西南徐家汇段是名称与既有 p32/p33/p35 所需的连续走廊，不纳入整个徐汇；p13旧代表点疑偏北，保留原点并记录后续坐标核验。',
 terms=['徐家汇公园','上海工艺美术博物馆','襄阳公园','上海话剧艺术中心','衡复 历史建筑','武康路 文化'],
 targets=[(XUHUI,['徐家汇公园','上海工艺美术博物馆','上海话剧艺术中心','上海宋庆龄故居'],'venue'),(PARKS,['襄阳公园'],'public_space')],
 source_urls=[ROADS,XUHUI]),
'old_city_central': dict(
 polygon=[(31.2288,121.4585),(31.2317,121.4690),(31.2355,121.4795),(31.2421,121.4865),(31.2414,121.4903),(31.2365,121.4925),(31.2300,121.4965),(31.2232,121.5000),(31.2160,121.4965),(31.2151,121.4925),(31.2171,121.4840),(31.2118,121.4712),(31.2138,121.4668),(31.2200,121.4650),(31.2254,121.4585)],
 basis='北西侧沿南京西路—南京东路街坊串联张园和南京路；东北侧止于外白渡桥南侧，东侧顺外滩浦西岸线向南至老城厢东缘；南侧沿中华路及复兴路相关街坊，西南以思南公馆街坊回接重庆南路。滨江折线不包含浦东。',
 disputes='张园位于名称核心的西北侧，按既有 p9 和南京路连续街区保留，不把静安区纳入；新天地北里与张园旧代表坐标存在地图差异，旧点和主POI位置都在产品范围内，不通过改坐标凑边界。',
 terms=['复兴公园','古城公园','人民公园 上海','上海书城 福州路','老城厢 历史建筑','新天地 文化'],
 targets=[(FUXING,['复兴公园'],'public_space'),(PARKS,['古城公园','人民公园'],'public_space'),(OLD,['新天地','老城厢','外滩'],'street')],
 source_urls=[ROADS,OLD,'https://ghzyj.sh.gov.cn/tpxw/20231121/623eca025e1c4b1fa0e64ee992e06477.html']),
'hongkou_literary': dict(
 polygon=[(31.2745,121.4790),(31.2745,121.4857),(31.2700,121.4868),(31.2655,121.4870),(31.2610,121.4875),(31.2567,121.4935),(31.2525,121.4930),(31.2519,121.4870),(31.2530,121.4800),(31.2570,121.4770),(31.2635,121.4768),(31.2695,121.4780)],
 basis='北侧取鲁迅公园北缘，西侧沿东江湾路—四川北路西侧街坊；东侧覆盖山阴路、溧阳路相关街坊，向海伦路—沙泾路1933既有节点收束；南侧在海宁路以北回接四川北路。以连续文学街区和步行连接空间限定范围。',
 disputes='1933老场坊为既有东南端文化建筑节点，与文学核心存在主题差别，但经溧阳路—海伦路连接，不扩至北外滩；鲁迅公园内部纪念馆与雕塑不重复计站。',
 terms=['多伦路文化名人街','甜爱路','四川北路公园','李白烈士故居','四川北路 历史建筑','山阴路 文化'],
 targets=[(HONGKOU,['多伦路','鲁迅故居','左联会址纪念馆','内山书店'],'street'),(TIANAI,['甜爱路'],'street'),(SICHUAN,['四川北路公园'],'public_space')],
   source_urls=[ROADS,HONGKOU,TIANAI])}

def main():
 repo=POIRepository(); rows=[]; checks={}; now=utc_now()
 out=ROOT/'data/poi_pipeline/all_zones'; out.mkdir(parents=True,exist_ok=True)
 observations=json.loads((out/'boundary_map_observations.json').read_text(encoding='utf-8'))
 lines=['# ShanghaiTrace 初始产品边界报告','', '这些边界用于 discovery 与产品路线范围，不是行政/法律边界。按用户授权通过检查后自动用于 Phase 2.5。','', 'GCJ-02；顶点顺序为纬度、经度；审核带为边界内外 150 m，带内标记 needs_boundary_review，不自动 reject。','']
 for z in repo.get_raw_data()['metadata']['walk_zones']:
  zid=z['id']; pois=repo.get_pois_by_zone(zid)
  if zid=='west_bund':
   s=dict(polygon=POLYGON,basis='沿用已验收西岸边界；不重新采集或 enrichment。',disputes='原审批150米审核带决定保持。',terms=AmapSource.keywords,targets=SEEDS,source_urls=['https://www.westbund.com/cn/index/NEWS-CENTER/2022-0930.html'])
  else: s=SPECS[zid]
  seeds=[dict(poi_id=p.id,name=p.name_zh,coordinates=p.coordinates) for p in pois]
  diagnostic=validate_polygon(s['polygon'],seeds)
  map_urls=list(dict.fromkeys('https://www.amap.com/detail/'+p['id'] for obs in observations if obs['zone_id']==zid for p in obs.get('results',[]) if not any(t in p['name'] for t in ['公交','停车'])))
  row=dict(zone_id=zid,display_name=z['name_zh'],polygon=s['polygon'],coordinate_system='GCJ-02',boundary_review_margin_m=150,boundary_basis=s['basis'],seed_pois=seeds,seed_production_pois=[p.id for p in pois],source_urls=s['source_urls']+map_urls,retrieved_at=now,
   initial_product_boundary='approved_for_phase2_5_pipeline' if zid!='west_bund' else 'existing_approved_unchanged',
   discovery_terms=s['terms'],official_source_targets=[dict(url=u,names=n,entity_kind=k) for u,n,k in s['targets']],
   allowed_candidate_categories=['museum','cultural_venue','performance_venue','public_art','public_space','park','architecture','heritage','commercial_complex'],
   excluded_generic_categories=['generic_cafe','generic_restaurant','ordinary_shop','temporary_event','ordinary_sports_facility'],disputed_edges=s['disputes'])
  row['route_node_alias_groups']=[['多伦路','多伦路文化名人街']] if zid=='hongkou_literary' else []
  rows.append(row); checks[zid]=diagnostic
  lines+=['## '+z['name_zh']+' (`'+zid+'`)','',s['basis'],'',s['disputes'],'',f"Seed 数量：{len(seeds)}；全部覆盖：{diagnostic['all_production_seeds_covered']}；面积约 {diagnostic['area_km2']} km²；审核带 150 m；polygon 有效且无自交。",'', '```json',json.dumps(s['polygon']), '```','', '| Seed | 名称 | 覆盖 |','|---|---|---|']
  lines += [f"| {p['poi_id']} | {p['name']} | {p['status']} |" for p in diagnostic['seed_coverage']]
  lines+=['','来源（道路与区域上下文用于产品判断，非来源官方划定本 polygon）：']+[f'- {u}' for u in row['source_urls']]+['']
 (ROOT/'data/poi_pipeline/zone_configs.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'boundary_validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 # GCJ coordinates cannot be mislabeled as RFC7946 WGS84 GeoJSON.
 (out/'boundaries_gcj02.json').write_text(json.dumps(dict(type='FeatureCollection',coordinate_system='GCJ-02',warning='Non-RFC7946 coordinate system; convert before use with WGS84 basemaps.',features=[dict(type='Feature',properties=dict(zone_id=r['zone_id']),geometry=dict(type='Polygon',coordinates=[[[p[1],p[0]] for p in list(r['polygon'])+[r['polygon'][0]]]])) for r in rows]),ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'docs/history/project/ZONE_BOUNDARY_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
 print(json.dumps(checks,ensure_ascii=True))

if __name__=='__main__': main()
