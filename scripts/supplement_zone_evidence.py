"""Persist material evidence improvements and migrate the first-run attempt ledger."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/poi_pipeline/all_zones'

def main():
 nodes={c['candidate_id']:c for f in OUT.glob('*_prepared_nodes.json') for c in json.loads(f.read_text(encoding='utf-8'))}
 for f in (OUT/'semantic_cache').glob('*.json'):
  row=json.loads(f.read_text(encoding='utf-8'));c=nodes.get(row['candidate_id'])
  if c and 'node_identity' not in row:
   row['node_identity']=next((r['source_type']+':'+r['source_candidate_id'] for r in c['merged_source_records'] if r['source_type']=='amap'),c['candidate_id'])
   row['evidence_hash']=hashlib.sha256(json.dumps(c['evidence_catalog'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
   f.write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
 path=ROOT/'data/poi_pipeline/zone_configs.json';rows=json.loads(path.read_text(encoding='utf-8'))
 additions={
 'wukang_fuxing_xujiahui':[
  ('https://www.xuhui.gov.cn/xwzx_tpxw/20240423/535878.html',['徐家汇公园'],'public_space'),
  ('https://www.shanghai.gov.cn/nw17239/20250423/404016f40ea2426ab8c7e6e7c6de9d46.html',['襄阳公园'],'public_space')],
 'old_city_central':[
  ('https://www.shanghai.gov.cn/nw17239/20250904/94d9f1c5fb954a3fbb9941bb5a0621f6.html',['古城公园'],'public_space'),
  ('https://lhsr.sh.gov.cn/ywdt/20241206/9b079c2d-7ea5-4c55-a0cd-2052074593cc.html',['古城公园'],'public_space'),
  ('https://www.shanghai.gov.cn/nw4411/20260806/8eb10d2a4b4a449593276dcb877fe7c2.html',['复兴公园'],'public_space')],
 'hongkou_literary':[]}
 for row in rows:
  for u,n,k in additions.get(row['zone_id'],[]):
   if u not in [t['url'] for t in row['official_source_targets']]:row['official_source_targets'].append(dict(url=u,names=n,entity_kind=k))
 path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
