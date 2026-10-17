"""Enrich accepted Phase 2.5A staging artifacts; never promote production data."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.llm_client import DeepSeekLLMClient, LLMClientError, redact_diagnostic
from src.poi_repository import POIRepository
from src.poi_pipeline.coverage import WestBundCoverageAnalyzer
from src.poi_pipeline.sources.base import utc_now
from src.poi_pipeline.semantic.preparation import prepare_candidates, evidence_catalog, geographic_context, duplicate_context
from src.poi_pipeline.semantic.enricher import POISemanticEnricher
from src.poi_pipeline.semantic.admission import evaluate_citywalk_candidate, marginal_coverage_gain, coverage_preview
from src.poi_pipeline.semantic.reporting import render_report


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(redact_diagnostic(value),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def fallback_role():
    return dict(primary='supporting_stop', eligible=['supporting_stop'], confidence='low',
                reason='语义失败后的审核占位，尚未形成可靠角色结论。', independent_destination_value='low',
                route_connector_value='low', alternatives_reason={r:'证据解释未通过，暂不能判断。' for r in ('anchor','supporting_stop','transition_stop')},
                provisional_only=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--max-attempts',type=int,default=4,help='Maximum total attempts per candidate, including cached failed attempts')
    parser.add_argument('--test-result',default='not recorded')
    args=parser.parse_args()
    # Prevent verbose provider content logging in this batch task.
    os.environ['DEEPSEEK_DEBUG']='0'
    if args.live and not os.environ.get('DEEPSEEK_API_KEY'):
        parser.error('DEEPSEEK_API_KEY is not available in process environment')
    root=ROOT/'data/poi_pipeline'
    output=root/'semantic'
    repo=POIRepository()
    before=hashlib.sha256(repo.path.read_bytes()).hexdigest()
    raw=json.loads((root/'canonical/west_bund_canonical_candidates.json').read_text(encoding='utf-8'))
    original_bundles=json.loads((root/'canonical/west_bund_evidence_bundles.json').read_text(encoding='utf-8'))
    candidates,bundles,lineage=prepare_candidates(raw,original_bundles)
    baseline=WestBundCoverageAnalyzer(repo).analyze()
    production=repo.get_pois_by_zone('west_bund')
    write(output/'west_bund_prepared_candidates.json',candidates)
    write(output/'west_bund_prepared_evidence.json',bundles)
    write(output/'west_bund_merge_manifest.json',lineage)

    def process(candidate):
        catalog=evidence_catalog(bundles[candidate['candidate_id']])
        geography=geographic_context(candidate,candidates,production)
        client=DeepSeekLLMClient(timeout=90,max_tokens=3600)
        enricher=POISemanticEnricher(client,repo.taxonomy,output/'cache',live=args.live,max_attempts=args.max_attempts)
        try:
            semantic,run=enricher.enrich(candidate,catalog,geography)
        except LLMClientError as exc:
            semantic,run=None,dict(failed=True,attempts=[],api_calls_this_run=0,cache_hit=False,error=exc.kind)
        duplicates=duplicate_context(candidate,candidates,production)
        admission=evaluate_citywalk_candidate(candidate,semantic,geography,duplicates)
        gain=marginal_coverage_gain(semantic,baseline)
        row=dict(candidate_id=candidate['candidate_id'], name=candidate['name_zh'] or candidate['name_en'],
            category=semantic['category'] if semantic else 'unknown',coordinates=candidate['coordinates'],coordinate_system='GCJ-02',
            route_role=semantic['route_role'] if semantic else fallback_role(),
            **{g:semantic[g] if semantic else [] for g in repo.taxonomy},
            citywalk_value=semantic['citywalk_value'] if semantic else None,
            source_confidence=admission['factors']['source_confidence'],semantic_confidence=semantic['semantic_confidence'] if semantic else 'low',
            coverage_gain=gain,sources=candidate['sources'],decision=admission['decision'],reason=admission['reasons'],
            admission=admission,geographic_value=geography,semantic=semantic,evidence_catalog=catalog,
            component_candidates=candidate.get('component_candidates',[]),
            selection_priority=round(gain['score']+(1 if geography['fills_spatial_gap'] else 0),4),run=run)
        return row

    rows=[]
    with ThreadPoolExecutor(max_workers=max(1,min(3,args.workers))) as executor:
        pending={executor.submit(process,c):c for c in candidates}
        for future in as_completed(pending):
            row=future.result()
            rows.append(row)
            write(output/'checkpoint'/f"{row['candidate_id']}.json",row)
            print(json.dumps(dict(done=len(rows),total=len(candidates),candidate_id=row['candidate_id'],
                                 enriched=row['semantic'] is not None,decision=row['decision']),ensure_ascii=True),flush=True)
    rows.sort(key=lambda r:r['candidate_id'])
    attempts=[a for r in rows for a in r['run'].get('attempts',[])]
    usage=Counter()
    for attempt in attempts:
        for key,value in ((attempt.get('provider') or {}).get('usage') or {}).items():
            if isinstance(value,int): usage[key]+=value
    metadata=dict(created_at=utc_now(),raw_canonical_count=len(raw),prepared_count=len(candidates),
        successfully_enriched=sum(r['semantic'] is not None for r in rows),number_failed=sum(r['semantic'] is None for r in rows),
        supported_subset_recovered=sum(bool(r['semantic'] and r['semantic'].get('rejected_tag_proposals')) for r in rows),
        failed_candidates=[dict(candidate_id=r['candidate_id'],name=r['name'],reason=r['run'].get('final_validation_error',r['run'].get('error'))) for r in rows if r['semantic'] is None],
        number_retried=sum(len(r['run'].get('attempts',[]))>1 for r in rows),
        api_calls_this_run=sum(r['run'].get('api_calls_this_run',0) for r in rows),cache_hits=sum(r['run'].get('cache_hit',False) for r in rows),
        total_recorded_attempts=len(attempts),error_counts=dict(Counter(a['kind'] for a in attempts if a['status']=='failed')),
        token_usage=dict(usage),decisions=dict(Counter(r['decision'] for r in rows)),test_result=args.test_result,
        production_sha256=before,production_unchanged=hashlib.sha256(repo.path.read_bytes()).hexdigest()==before)
    preview=coverage_preview(rows,baseline)
    write(output/'west_bund_enriched_candidates.json',[dict(candidate_id=r['candidate_id'],semantic=r['semantic'],run=r['run']) for r in rows])
    write(output/'west_bund_review.json',rows)
    write(output/'west_bund_coverage_preview.json',preview)
    write(output/'west_bund_enrichment_run.json',metadata)
    (ROOT/'docs/history/phase2_5/PHASE2_5B_REPORT.md').write_text(render_report(rows,preview,metadata,lineage),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
