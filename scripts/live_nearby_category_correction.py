"""Only requery the two mappings directly changed after real provider observations."""
import copy
import json
import os
from pathlib import Path
from scripts.live_nearby_acceptance import AuditedClient,OUTPUT
from src import POIRepository,Location
from src.nearby_models import ServicePoiCategory as C
from src.services.world_context_service import WorldContextService


def main():
    if os.environ.get('RUN_LIVE_AMAP_TESTS')!='1' or not os.environ.get('AMAP_WEB_SERVICE_KEY','').strip():raise RuntimeError('Live opt-in and key required')
    initial=json.loads(OUTPUT.with_name('live_acceptance_initial.json').read_text(encoding='utf-8'))
    combined=copy.deepcopy(initial);repo=POIRepository();client=AuditedClient();world=WorldContextService.from_environment(repository=repo,client=client)
    corrected=(C.RESTROOM,C.MALL);changes=[]
    for case in combined['cases']:
        old=case['result'];origin=Location(**old['origin'])
        args=dict(location=origin) if old['origin_source']=='CURRENT_LOCATION' else dict(core_poi_id=old['core_poi_id'])
        result=world.search_nearby_services(**args,categories=corrected)
        assert result.status=='AVAILABLE' and result.origin==origin,result.errors
        assert all(p.provider_typecode!='200304' for p in result.results)
        assert all(not any(word in p.name.casefold() for word in ('百货','商厦','department store')) for p in result.results if C.MALL in p.categories)
        lookup={p['service_poi_id']:p for p in old['results']}
        lookup.update({p.service_poi_id:p.to_dict() for p in result.results})
        for category in corrected:
            old['category_result_ids'][category]=list(result.category_result_ids[category]);old['category_counts'][category]=len(result.category_result_ids[category])
        ids=list(dict.fromkeys(i for category in old['requested_categories'] for i in old['category_result_ids'][category]))
        old['results']=[lookup[i] for i in ids];old['fetched_at']=result.fetched_at
        old['category_statuses']=[s for s in old['category_statuses'] if s['category'] not in corrected]+list(result.category_statuses)
        changes.append(dict(case=case['case'],result=result.to_dict()))
        assert len(ids)==len(set(ids)) and all(n<=5 for n in old['category_counts'].values())
    assert len(client.calls)==6 and all(c['path']=='/v5/place/around' for c in client.calls)
    combined['category_correction']=dict(categories=list(corrected),cases=changes,provider_calls=client.calls,
        provider_observations=client.observations,around_request_count=6,detail_request_count=0,
        rationale='Real sample revealed 200304 mother/infant rooms and department stores inside coarse mall taxonomy. Only directly affected provider categories were requeried; other five categories retain original live observations.')
    combined['acceptance_passes']=dict(initial_full_live='PASS',targeted_mapping_correction_live='PASS',total_around_requests=18,total_detail_requests=0,official_conversion_requests=1)
    OUTPUT.write_text(json.dumps(combined,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(case=c['case'],counts=c['result']['category_counts']) for c in combined['cases']],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
