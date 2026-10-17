"""Bounded Amap geography observations for initial product boundaries."""
import json
from pathlib import Path
from src.poi_pipeline.sources.base import CachedHTTP
from src.poi_pipeline.sources.amap_source import AmapSource

ROOT = Path(__file__).resolve().parents[1]
TERMS = {
 'wukang_fuxing_xujiahui': ['华山路复兴西路','长乐路陕西南路','肇嘉浜路陕西南路','建国西路嘉善路','广元路华山路','南丹路漕溪北路','徐家汇天主堂','上海宋庆龄故居纪念馆','武康大楼','陕南邨'],
 'old_city_central': ['张园','思南公馆','新天地北里','南京西路石门一路','淮海中路重庆南路','复兴中路重庆南路','中华路河南南路','人民路河南南路','外滩陈毅广场','中山东二路东门路','北京东路西藏中路'],
 'hongkou_literary': ['鲁迅公园','1933老场坊','今潮8弄','四川北路海宁路','东江湾路大连西路','甜爱路山阴路','多伦路','溧阳路海伦路','山阴路四达路']}

def main():
    out=ROOT/'data/poi_pipeline/all_zones'
    http=CachedHTTP(out/'cache', retries=0, timeout=15, min_interval=.2)
    source=AmapSource(http)
    observations=[]
    for zone, terms in TERMS.items():
        for term in terms:
            try:
                result=source.request('place/text',dict(keywords=term,city='上海',citylimit='true',offset='3',page='1',extensions='base',output='JSON'))
                observations.append(dict(zone_id=zone,query=term,retrieved_at=result['retrieved_at'],results=result['response'].get('pois',[])))
            except Exception as exc:
                observations.append(dict(zone_id=zone,query=term,error=type(exc).__name__))
            (out/'boundary_map_observations.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([dict(zone=r['zone_id'],query=r['query'],results=[dict(id=p['id'],name=p['name'],location=p.get('location')) for p in r.get('results',[])],error=r.get('error')) for r in observations],ensure_ascii=True))

if __name__=='__main__': main()
