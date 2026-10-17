"""Verify exact authorized data changes and frozen engine/Trip implementation."""
import copy
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from src import POIRepository
from src.spatial_profiles import SpatialProfileRepository
from src.poi_mapping import PoiMappingRepository

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/spatial_identity'


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    baseline=load(OUT/'baseline_manifest.json')
    changed=[p for p,h in baseline.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    allowed_src={'src/poi_repository.py','src/poi_mapping.py'}
    forbidden=[p for p in changed if p.startswith('src/') and p not in allowed_src]
    allowed_changes=allowed_src | {'tests/test_identity_calibration.py','tests/test_phase2_5_promotion.py',
        'tests/test_trip_agent.py','tests/test_trip_final_acceptance.py','tests/test_trip_interaction.py',
        'scripts/audit_location_delivery.py','scripts/match_amap_poi_ids.py',
        'data/pois.json','data/amap_poi_mappings.json','data/amap_manual_confirmations.json'}
    forbidden += [p for p in changed if p not in allowed_changes and p not in forbidden]
    new_src={p.relative_to(ROOT).as_posix() for p in (ROOT/'src').rglob('*.py')}-set(baseline)
    assert new_src=={'src/spatial_profiles.py','src/spatial_geometry.py'},new_src
    assert not forbidden,forbidden
    before=load(OUT/'pois_before.json'); expected=copy.deepcopy(before)
    evidence=load(OUT/'provider_evidence.json')['details']
    for row in expected['pois']:
        pid=row['id']
        if pid not in ('p10','p12','p34'):continue
        coord=evidence[pid]['normalized']['location']
        row['location']['representative_lat']=coord['lat'];row['location']['representative_lng']=coord['lng']
        if pid=='p34':row['location']['coordinate_system']='GCJ-02 / Amap formal identity coordinate (Phase 3B_2.2)'
    assert expected==load(ROOT/'data/pois.json'),'Unexpected Core change'
    repo=POIRepository();ids={p.id for p in repo.get_all_pois()}
    profiles=SpatialProfileRepository(core_ids=ids).all();mappings=load(ROOT/'data/amap_poi_mappings.json');PoiMappingRepository(records=mappings)
    assert len(ids)==58 and 'p40' not in ids and set(mappings)==ids
    assert mappings['p35']['identity_mapping_status']=='NOT_FOUND'
    regional=[r for r in profiles.values() if r['spatial_type']!='POINT']
    assert all(r['spatial_extent'] is not None for r in regional)
    active_paths=['data/pois.json','data/amap_poi_mappings.json','data/amap_manual_confirmations.json',
                  'data/core_spatial_profiles.json','tests/fixtures/trip_semantics_initial.json',
                  'examples/walking_routing/live_west_bund.json','examples/spatial_identity/live_acceptance.json',
                  'examples/location_awareness/calibration/new_generated_west_bund.json']
    active_refs=[p for p in active_paths if '"p40"' in (ROOT/p).read_text(encoding='utf-8')]
    assert not active_refs,active_refs
    exposures=[]
    values=[v.encode() for k,v in os.environ.items() if k in ('AMAP_WEB_SERVICE_KEY','AMAP_API_KEY','DEEPSEEK_API_KEY') and len(v)>=16]
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.py','.json','.md','.txt','.example') and '__pycache__' not in path.parts:
            if any(key in path.read_bytes() for key in values):exposures.append(path.relative_to(ROOT).as_posix())
    assert not exposures,exposures
    result=dict(phase='3B_2.2', changed_baseline_files=changed, unexpected_protected_changes=forbidden,
                frozen_route_trip_replan_walking_sources_unchanged=True,authorized_core_changes=['p10','p12','p34'],
                core_change_scope_verified=True,production_count=58,identity_counts={s:sum(r['identity_mapping_status']==s for r in mappings.values()) for s in ('MATCHED','AMBIGUOUS','NOT_FOUND')},
                spatial_counts=dict(Counter(r['spatial_type'] for r in profiles.values())),valid_regional_anchors=len(regional),
                valid_regional_extents=len(regional),active_p40_reference_count=len(active_refs),active_reference_inventory=active_paths,
                configured_secret_exposures=exposures,phase3b_3_started=False)
    (OUT/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':main()
