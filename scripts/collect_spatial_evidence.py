"""Collect sanitized provider evidence for spatial identity finalization."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from src.providers.amap import AmapClient
from src.providers.amap.world import AmapPoiProvider
from src import POIRepository,Location

IDS={'p10':'B0HDACXK1W','p12':'B00156COKX','p34':'B0IA369WVI','p25':'B0I2KZFZRY','pz_b72e3b8998b3':'B00155FLFD'}
QUERIES=['南京东路与西藏中路交叉口','南京东路与中山东一路交叉口','甜爱路与四川北路交叉口','甜爱路与甜爱支路交叉口','多伦路与四川北路交叉口','武康路与华山路交叉口','武康路与淮海中路交叉口','福州路与西藏中路交叉口','福州路与中山东一路交叉口','美罗城','港汇恒隆广场','徐家汇商圈','山阴路274弄小区','中南新邨','新天地北里']
def main():
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1':raise RuntimeError('Opt-in required')
    client=AmapClient();provider=AmapPoiProvider(client);repo=POIRepository();evidence={'details':{},'surroundings':{},'queries':{}}
    for pid,aid in IDS.items():
        raw=client.get('/v5/place/detail',{'id':aid,'show_fields':'business,children'})['pois']
        info=provider.get_poi_detail(aid)
        evidence['details'][pid]=dict(normalized=info.to_dict(),raw=[{k:r.get(k) for k in ('id','name','location','address','adname','adcode','type','typecode','children')} for r in raw])
        evidence['surroundings'][pid]=[p.to_dict() for p in provider.search_identity_near_coordinate('',info.location,types='110000|140000|190000',radius=200)]
    for q in QUERIES:evidence['queries'][q]=[c.to_dict() for c in provider.search_mapping_candidates(q)]
    Path('examples/spatial_identity/provider_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({pid:r['raw'] for pid,r in evidence['details'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
