import os
if os.environ.get("RUN_LIVE_AMAP_TESTS") != "1" or not os.environ.get("AMAP_WEB_SERVICE_KEY"):
    raise RuntimeError("Live opt-in and key required")
import json
from pathlib import Path
from src.providers.amap import AmapClient
from src.providers.amap.world import AmapPoiProvider
p=Path('examples/spatial_identity/provider_evidence.json');d=json.loads(p.read_text(encoding='utf-8'));provider=AmapPoiProvider(AmapClient())
for q in ['西藏中路与南京东路交叉口','肇嘉浜路与漕溪北路交叉口','多伦路牌坊','多伦路与四川北路交叉口','甜爱路351弄']:
 rows=provider.search_mapping_candidates(q);d['queries'][q]=[r.to_dict() for r in rows];print(q,[(r.name,r.location,r.poi_type) for r in rows])
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
