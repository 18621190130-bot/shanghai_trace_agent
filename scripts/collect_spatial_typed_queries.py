import os
if os.environ.get("RUN_LIVE_AMAP_TESTS") != "1" or not os.environ.get("AMAP_WEB_SERVICE_KEY"):
    raise RuntimeError("Live opt-in and key required")
import json
from pathlib import Path
from src.providers.amap import AmapClient
from src.providers.amap.world import AmapPoiProvider
from src import Location
p=Path('examples/spatial_identity/provider_evidence.json');d=json.loads(p.read_text(encoding='utf-8'));client=AmapClient();provider=AmapPoiProvider(client)
for q in ['南京东路 西藏中路','南京路步行街西入口','徐家汇 肇嘉浜路 虹桥路']:
 data=client.get('/v5/place/text',dict(keywords=q,region='上海',city_limit='true',types='190000|110000',page_size=25,page_num=1));rows=provider._mapping_candidates(data);d['queries'][q]=[r.to_dict() for r in rows];print(q,[(r.name,r.location) for r in rows])
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
