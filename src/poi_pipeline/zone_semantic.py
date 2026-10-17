"""Compact, cached, at most two attempts per candidate; no broad retry loops."""
import hashlib,json,re
from pathlib import Path
from .semantic.enricher import SYSTEM_PROMPT
from .semantic.repair_policy import compact_evidence, failure_category, TargetedRetryPolicy
from .semantic.schema import semantic_schema
from .semantic.validation import validate_semantic_enrichment, TAG_GATES
from ..llm_client import parse_provider_json,LLMClientError
from ..models import RequestValidationError
from .role_audit import validate_role,ROLE_STANDARD

PROMPT=SYSTEM_PROMPT+'\nPrefer at most two directly evidenced interest/experience tags each; culture may be empty. No facts are required. All factual_fields may be null. A list of park names supports parks, not neighborhood, quiet, social or industrial claims. Only a venue with evidenced independent experience can be anchor; low information never implies anchor. Existing and new nodes use exactly this role standard: '+json.dumps(ROLE_STANDARD)

class ZoneSemanticEnricher:
 def __init__(self,client,taxonomy,cache_dir,live=False):
  self.client,self.taxonomy,self.cache_dir,self.live=client,taxonomy,Path(cache_dir),live
  self.cache_dir.mkdir(parents=True,exist_ok=True)

 def enrich(self,candidate):
  catalog=candidate['evidence_catalog']
  node_identity=next((r['source_type']+':'+r['source_candidate_id'] for r in candidate['merged_source_records'] if r['source_type']=='amap'),candidate['candidate_id'])
  payload=dict(candidate={k:candidate[k] for k in ('candidate_id','name_zh','name_en','entity_kind','boundary_status')},
   evidence=compact_evidence(catalog),evidence_tag_gates=TAG_GATES)
  digest=hashlib.sha256(json.dumps(dict(prompt=PROMPT,payload=payload,taxonomy=self.taxonomy),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  path=self.cache_dir/(digest+'.json')
  if path.exists():
   saved=json.loads(path.read_text(encoding='utf-8'))
   if saved['output']:
    saved['semantic']=validate_semantic_enrichment(saved['output'],candidate,catalog,self.taxonomy)
    validate_role(saved['semantic']['route_role'])
   return dict(saved,cache_hit=True,api_calls_this_run=0)
  history=[json.loads(p.read_text(encoding='utf-8')) for p in self.cache_dir.glob('*.json')]
  prior=[r for r in history if r.get('candidate_id')==candidate['candidate_id'] or r.get('node_identity')==node_identity]
  prior_count=sum(len(r['attempts']) for r in prior)
  evidence_hash=hashlib.sha256(json.dumps(catalog,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  if prior_count>=2 or (prior_count and any(r.get('evidence_hash')==evidence_hash for r in prior)):
   return dict(candidate_id=candidate['candidate_id'],semantic=None,output=None,attempts=[],cache_hit=False,api_calls_this_run=0,reason='candidate_attempt_budget_exhausted_or_no_material_change')
  if not self.live: raise LLMClientError('Semantic cache miss; use --live',kind='cache_miss')
  attempts=[]; output=None; semantic=None; feedback=None
  for number in range(2-prior_count):
   try:
    # Narrow only what a candidate may propose, using evidence rather than
    # coverage. This does not assert that every lexically eligible tag is true.
    supported={tag:[ref for ref,atom in payload['evidence'].items() if re.search(pattern,atom['field']+': '+json.dumps(atom['value'],ensure_ascii=False),re.I)] for tag,pattern in TAG_GATES.items()}
    payload['lexically_eligible_tag_refs']={t:refs for t,refs in supported.items() if refs}
    schema=semantic_schema(self.taxonomy)
    for group,tags in self.taxonomy.items():
     schema['properties'][group]['items']['enum']=[t for t in tags if supported.get(t)]
    output=parse_provider_json(self.client.structured_parse(system_prompt=PROMPT,user_text=json.dumps(payload,ensure_ascii=False),schema=schema,validation_feedback=feedback))
    semantic=validate_semantic_enrichment(output,candidate,catalog,self.taxonomy)
    validate_role(semantic['route_role'])
    attempts.append(dict(status='success',provider=self.client.last_response_metadata)); break
   except LLMClientError as exc:
    attempts.append(dict(status='provider_error',kind=exc.kind));output=None;break
   except (RequestValidationError,ValueError) as exc:
    feedback=str(exc);kind=failure_category(feedback)
    attempts.append(dict(status='validation_failure',kind=kind,feedback=feedback,provider=self.client.last_response_metadata));output=None
    allowed=TargetedRetryPolicy().permits(reasons=['failed'],attempts=prior_count+number+1,error_kind=kind,
      insufficient_evidence='insufficient evidence' in feedback.lower(),omittable_field=feedback.startswith('unsupported factual field ') and ';' not in feedback)
    if not allowed: break
  saved=dict(candidate_id=candidate['candidate_id'],node_identity=node_identity,semantic=semantic,output=output,attempts=attempts,cache_hit=False,api_calls_this_run=len(attempts),request_hash=digest,evidence_hash=evidence_hash,retry_reason='evidence_materially_improved' if prior_count else None)
  path.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
  return saved
