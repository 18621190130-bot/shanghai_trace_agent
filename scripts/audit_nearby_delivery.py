"""Phase-specific freeze and non-mutation audit, independent of live API calls."""
import hashlib
import json
import os
from pathlib import Path
from src import POIRepository

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/nearby_rest_stops'
NEW_SRC={'src/nearby_models.py','src/amap_category_mapping.py','src/providers/nearby.py',
         'src/providers/amap/nearby.py','src/services/nearby_rest_stop_service.py','src/services/nearby_service.py'}


def main():
    baseline=json.loads((OUT/'phase3b_2_baseline_manifest.json').read_text(encoding='utf-8'))
    changed=[p for p,h in baseline.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert changed==['src/services/world_context_service.py'],changed
    new_src={p.relative_to(ROOT).as_posix() for p in (ROOT/'src').rglob('*.py')}-set(baseline)
    assert new_src==NEW_SRC,new_src
    repo=POIRepository();assert len(repo.get_all_pois())==58 and repo.get_poi_by_id('p40') is None
    sensitive=[v.encode() for k,v in os.environ.items() if k in ('AMAP_WEB_SERVICE_KEY','AMAP_API_KEY','DEEPSEEK_API_KEY') and len(v)>=16]
    exposures=[]
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.py','.json','.md','.txt','.example') and '__pycache__' not in path.parts:
            if any(secret in path.read_bytes() for secret in sensitive):exposures.append(path.relative_to(ROOT).as_posix())
    assert not exposures,exposures
    result=dict(phase='3B_3',production_core_count=58,changed_existing_files=changed,new_source_files=sorted(new_src),
        frozen_core_spatial_identity_data_unchanged=True,core_route_engine_candidates_unchanged=True,
        trip_nlu_route_version_replan_walking_sources_unchanged=True,shared_amap_client_converter_cache_opening_sources_unchanged=True,
        configured_secret_exposures=exposures,phase3b_4_started=False)
    (OUT/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':main()
