"""One-time factual entrance audit; no routing or spatial writes."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.web_sdk import load_local_environment
from src.providers.amap import AmapClient
from src.providers.amap.arrival import AmapArrivalProvider
from src.providers.base import ExternalProviderError
from src.poi_repository import POIRepository
load_local_environment()
if os.environ.get('AMAP_API_KEY'):os.environ['AMAP_WEB_SERVICE_KEY']=os.environ['AMAP_API_KEY']
m=json.loads((ROOT/'data/amap_poi_mappings.json').read_text(encoding='utf-8'));ids=list(dict.fromkeys(r['amap_poi_id'] for r in m.values() if r['identity_mapping_status']=='MATCHED'));provider=AmapArrivalProvider(AmapClient(timeout_s=15));raw={};batches=[]
for i in range(0,len(ids),10):
 batch=ids[i:i+10]
 try:raw.update(provider.fetch(batch));batches.append({'ids':batch,'status':'SUCCESS'})
 except ExternalProviderError as exc:batches.append({'ids':batch,'status':type(exc).__name__})
records={pid:{'provider_id':row['amap_poi_id'],'navi':raw.get(row['amap_poi_id'],{}).get('navi',{}),'retrieved_at':time.time()} for pid,row in m.items() if row.get('amap_poi_id') in raw}
(ROOT/'data/poi_arrival_locations.json').write_text(json.dumps({'schema_version':1,'records':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'examples/arrival/navi_batches.json').write_text(json.dumps({'batches':batches,'records':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'batches':len(batches),'records':len(records),'entr_location_present':sum(bool(r['navi'].get('entr_location')) for r in records.values())}))
