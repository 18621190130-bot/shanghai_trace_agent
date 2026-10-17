"""One bounded map check per selected ambiguous identity, never zone discovery."""
import json,os,urllib.request,urllib.parse
from datetime import datetime,timezone
from scripts.run_poi_pipeline import ROOT,write,load
from scripts.diversity_review_data import SELECTED

OUT=ROOT/'data/poi_pipeline/diversity'
def run():
 OUT.mkdir(exist_ok=True);path=OUT/'map_checks.json';rows=load(path) if path.exists() else []
 for zone,names in SELECTED.items():
  for name in names:
   if any(r['zone']==zone and r['candidate_name']==name for r in rows):continue
   # F already verified these two mapped park/street identities; no repeated calls.
   if name in ('福州路','徐家汇公园'):continue
   query={'张乐平':'张乐平故居','优秀历史建筑乌鲁木齐南路176号':'乌鲁木齐南路176号','徐光启故居(九间楼)':'徐光启故居 九间楼','上海交响乐团音乐厅':'上海交响音乐厅','四川北路文化中心图书馆':'四川北路街道图书馆'}.get(name,name)
   row=dict(zone=zone,candidate_name=name,query=query,retrieved_at=datetime.now(timezone.utc).isoformat(),status='reserved',results=[])
   rows.append(row);write(path,rows)
   parameters=dict(key=os.environ['AMAP_API_KEY'],keywords=query,city='上海',citylimit='true',offset='3',page='1',extensions='base',output='JSON')
   try:
    with urllib.request.urlopen('https://restapi.amap.com/v3/place/text?'+urllib.parse.urlencode(parameters),timeout=20) as response:data=json.load(response)
    row.update(status='success' if data.get('status')=='1' else 'provider_error',results=[{k:p.get(k) for k in ('id','name','location','address','type','typecode','pname','cityname','adname')} for p in data.get('pois',[])])
   except Exception as exc:row.update(status='failed',error_type=type(exc).__name__)
   write(path,rows);print(json.dumps(dict(name=name,status=row['status'],results=row['results']),ensure_ascii=True),flush=True)
 return rows
if __name__=='__main__':run()
