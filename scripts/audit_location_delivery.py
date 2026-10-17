"""Current calibration delivery audit; historical phase evidence remains unchanged."""
import copy
import hashlib
import json
import os
from pathlib import Path
from src import POIRepository
from src.poi_mapping import PoiMappingRepository

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/location_awareness'
AUTHORIZED_PROTECTED_CHANGES={'src/providers/amap/client.py','data/pois.json','tests/test_phase2_5_promotion.py','tests/test_trip_agent.py','tests/test_trip_final_acceptance.py','tests/test_trip_interaction.py'}

def main():
    if (ROOT/'data/core_spatial_profiles.json').exists():
        from scripts.audit_spatial_delivery import main as spatial_audit
        return spatial_audit()
    baseline=json.loads((OUT/'phase3b_1_baseline_manifest.json').read_text(encoding='utf-8'))
    changed=[p for p,h in baseline.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    forbidden=[p for p in changed if p not in AUTHORIZED_PROTECTED_CHANGES]
    records=json.loads((ROOT/'data/amap_poi_mappings.json').read_text(encoding='utf-8'));PoiMappingRepository(records=records)
    repo=POIRepository();current=repo.get_raw_data()
    before=json.loads((OUT/'calibration/pois_before.json').read_text(encoding='utf-8'));expected=copy.deepcopy(before)
    expected['pois']=[p for p in expected['pois'] if p['id']!='p40']
    corrections=json.loads((OUT/'coordinate_corrections.json').read_text(encoding='utf-8'))['corrections']
    details=json.loads((OUT/'calibration/coordinate_provider_details.json').read_text(encoding='utf-8'))
    for i,p in enumerate(expected['pois'],1):
        p['display_order']=i
        for c in corrections:
            if c['core_id']==p['id']:
                assert details[p['id']]['provider_id']==c['amap_poi_id'] and details[p['id']]['location']==c['new_coordinate']
                lat,lng=('representative_lat','representative_lng') if p['poi_type']=='district' else ('lat','lng')
                p['location'][lat]=c['new_coordinate']['lat'];p['location'][lng]=c['new_coordinate']['lng']
    expected['metadata']['poi_count']=58
    for z in expected['metadata']['walk_zones']:z['poi_count']=sum(p['walk_zone']['id']==z['id'] for p in expected['pois'])
    assert expected==current,'Unauthorized Core knowledge change'
    assert set(records)=={p.id for p in repo.get_all_pois()} and len(records)==58
    assert '"p40"' not in json.dumps(current)
    active_paths=['data/pois.json','data/amap_poi_mappings.json','data/amap_manual_confirmations.json',
                  'data/poi_pipeline/promotion/production_cli_4.txt','tests/fixtures/trip_semantics_initial.json',
                  'examples/walking_routing/live_west_bund.json','examples/location_awareness/live_acceptance.json',
                  'examples/location_awareness/calibration/live_acceptance.json',
                  'examples/location_awareness/calibration/new_generated_west_bund.json']
    active_refs=[p for p in active_paths if '"p40"' in (ROOT/p).read_text(encoding='utf-8')]
    assert not active_refs,active_refs
    deletion=json.loads((ROOT/'data/deleted_core_pois.json').read_text(encoding='utf-8'))['deleted'][0]
    for route in deletion['affected_routes']:
        assert route['after']==[pid for pid in route['before'] if pid!='p40'] and not route['replacement_ids']
    keyvalues=[v.encode() for k,v in os.environ.items() if k in ('AMAP_WEB_SERVICE_KEY','AMAP_API_KEY','DEEPSEEK_API_KEY') and len(v)>=16]
    exposures=[]
    for p in ROOT.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.json','.md','.txt','.example') and '__pycache__' not in p.parts:
            if any(key in p.read_bytes() for key in keyvalues):exposures.append(p.relative_to(ROOT).as_posix())
    result=dict(phase='3B_2.1',changed_baseline_files=changed,unexpected_protected_changes=forbidden,core_change_scope_verified=True,frozen_route_trip_replan_sources_unchanged=not any(p.startswith('src/') and p!='src/providers/amap/client.py' for p in changed),production_count=58,mapping_count=58,configured_secret_exposures=exposures,coordinate_detail_provenance_verified=True,active_p40_reference_count=len(active_refs),active_reference_inventory=active_paths,remaining_route_order_preserved=True,historical_p40_evidence='Retained in archived candidates/reports and calibration baseline only; not a current Core identity.',phase3b_3_started=False)
    (OUT/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Phase 3B_2.1 Remaining Identity Review','', '身份与 Live Info 适用性独立；NOT_FOUND 不表示现实地点不存在。已人工确认项不重复请求确认。','', '## 真正仍有身份范围歧义','']
    for pid,row in records.items():
        if row['identity_mapping_status']!='AMBIGUOUS':continue
        lines.extend([f"### {pid} {row['core_name']}",'','| Provider ID | Candidate | Type | Offset m |','| --- | --- | --- | ---: |'])
        for c in row['candidates']:
            if c['name_similarity']>=.9 and c['distance_m']<=300 and c['district_consistent'] and c['entity_type_compatible']:
                lines.append(f"| {c['provider_id']} | {c['name']} | {c['poi_type']} | {c['distance_m']:.1f} |")
        lines.append('')
    lines.extend(['## NOT_FOUND：当前未取得可信 provider identity','', '| Core ID | Name | Evidence / limitation |','| --- | --- | --- |'])
    for pid,row in records.items():
        if row['identity_mapping_status']!='NOT_FOUND':continue
        first=row['candidates'][0] if row['candidates'] else None
        reason=(f"首候选 {first['name']} / {first['provider_id']}，偏移 {first['distance_m']:.1f}m；名称/距离/范围未满足保守匹配条件。" if first else '名称与附近检索未返回主体。')
        lines.append(f"| {pid} | {row['core_name']} | {reason} Core 的现实存在不被否定；未擅自修正坐标。 |")
    (OUT/'MAPPING_MANUAL_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if forbidden or exposures:raise SystemExit(1)

if __name__=='__main__':main()
