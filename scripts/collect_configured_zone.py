import argparse,json
from dataclasses import asdict
from pathlib import Path
from src.poi_repository import POIRepository
from src.poi_pipeline.zone_config import ZonePipelineConfig
from src.poi_pipeline.zone_collection import collect_zone,consolidate_zone
from src.poi_pipeline.sources.base import CachedHTTP
from src.poi_pipeline.models import RawCandidate
from src.poi_pipeline.normalization import normalize_candidate
from src.poi_pipeline.deduplication import deduplicate_candidates
import hashlib

ROOT=Path(__file__).resolve().parents[1]
def run(zone,live=False):
 config=ZonePipelineConfig.load(zone)
 if zone=='west_bund': raise ValueError('Approved West Bund is frozen; discovery forbidden for this phase')
 out=ROOT/'data/poi_pipeline/all_zones'; repo=POIRepository(ROOT/'data/pois_phase2_5_candidate.json')
 http=CachedHTTP(out/'cache',offline=not live,retries=0,min_interval=1.1,timeout=15,max_response_bytes=12_000_000,retry_failed=live)
 raw,canonical,rejected,errors=collect_zone(config,http,repo)
 fallbacks=json.loads((ROOT/'data/poi_pipeline/authority_excerpt_fallbacks.json').read_text(encoding='utf-8'))
 for f in fallbacks:
  if f['zone_id']!=zone: continue
  record=RawCandidate(hashlib.sha256((f['url']+f['name']).encode()).hexdigest()[:20],
    'government','Official indexed excerpt via web search',f['url'],f['retrieved_at'],name_zh=f['name'],
    source_category='official_place_mention',entity_kind=f['entity_kind'],
    snippets=[dict(text=f['text'],supports=['identity','history'],extraction=f['retrieval_method'])])
  raw.append(record)
  canonical.extend(asdict(c) for c in deduplicate_candidates([normalize_candidate(record,config)],zone))
 nodes,registry=consolidate_zone(canonical,repo,config)
 for suffix,value in [('raw_candidates',[asdict(r) for r in raw]),('collection_report',dict(errors=errors,deterministic_rejected=rejected,raw_count=len(raw))),('prepared_nodes',nodes),('internal_entities',registry)]:
  (out/f'{zone}_{suffix}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(zone=zone,raw=len(raw),mapped_nodes=len(nodes),errors=errors),ensure_ascii=True),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--zone',required=True);p.add_argument('--live',action='store_true');a=p.parse_args();run(a.zone,a.live)
