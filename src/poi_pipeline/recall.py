"""Bounded recall understanding gate; final semantic validator is unchanged."""
import json,re,hashlib
from pathlib import Path
from .normalization import match_key
from .semantic.schema import semantic_schema
from .semantic.validation import validate_semantic_enrichment,TAG_GATES
from .semantic.repair_policy import compact_evidence
from .zone_semantic import PROMPT
from .role_audit import validate_role
from ..llm_client import parse_provider_json,LLMClientError
from ..models import RequestValidationError

REASONS=('generic_service','generic_retail','generic_food_drink','temporary_event','duplicate','production_duplicate','internal_entity','child_entity','outside_boundary','low_citywalk_value','insufficient_evidence','weak_identity','weak_location','weak_semantic_signal','category_not_allowed','unstable_place','possible_duplicate','other')

def recall_prefilter(c):
 if c.get('internal_parent') or c.get('recall_parent'):return 'internal_entity'
 if c.get('entity_stability')=='temporary' or c.get('entity_no_longer_exists'):return 'unstable_place'
 status=c.get('identity',{}).get('identity_status')
 if status=='existing_production':return 'production_duplicate'
 if status!='new_candidate':return 'possible_duplicate' if status=='possible_duplicate' else 'weak_identity'
 if not c.get('coordinates'):return 'weak_location'
 if c['boundary_status']=='outside_pilot':return 'outside_boundary'
 if c['boundary_status']=='needs_review':return 'boundary_review_defer'
 name=c['name_zh'] or c['name_en']
 categories=';'.join(r['source_category'] for r in c['merged_source_records'])
 if re.search('永久关闭|永久停业|已拆除|已撤除|活动已结束',name):return 'unstable_place'
 if re.search('餐饮服务|amenity=(?:cafe|restaurant|fast_food)',categories):return 'generic_food_drink'
 if re.search('停车|厕所|卫生间|出入口|公交站|地铁站|充电|打卡点|培训|篮球|网球|体育场|健身房|leisure=(?:pitch|sports_centre)',name+';'+categories):return 'generic_service'
 if re.search('公司|集团|小学|中学|办公|物业',name):return 'generic_service'
 if re.search('购物服务',categories) and not re.search('历史|文化名街|特色商业街',name):return 'generic_retail'
 signal=re.search('故居|旧址|历史|建筑|公园|花园|雕像|铜像|纪念|广场|文化馆|图书馆|新邨|街$|路$|弄$|弄堂|住宅|音乐厅|剧场|美术馆|fudeli',name,re.I)
 mapped=any(r['source_type'] in ('amap','osm') for r in c['merged_source_records'])
 if not mapped:return 'weak_identity'
 if not signal:return 'weak_semantic_signal'
 # This permits understanding, not admission. Authority/location/access repairs
 # are separately required before accepting any semantic output.
 return None

def identity(c):
 return next((r['source_type']+':'+r['source_candidate_id'] for r in c['merged_source_records'] if r['source_type']=='amap'),c['candidate_id'])

class RecallBudget:
 def __init__(self,path):
  self.path=Path(path);self.rows=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
 def reserve(self,zone,node,retry=False,reason=None):
  prior=[r for r in self.rows if r['node']==node and r['zone']==zone]
  if len(prior)>=2:raise ValueError('node call budget exhausted')
  if retry:
   if not prior or reason not in ('schema_syntax_repair','material_new_evidence'):raise ValueError('retry not justified')
   if sum(r['retry'] for r in self.rows)>=6:raise ValueError('retry budget exhausted')
  elif prior or sum(not r['retry'] and r['zone']==zone for r in self.rows)>=8:raise ValueError('zone first-call budget exhausted')
  if len(self.rows)>=30:raise ValueError('total call budget exhausted')
  row=dict(zone=zone,node=node,retry=retry,reason=reason,status='reserved')
  self.rows.append(row);self.save();return row
 def save(self):
  self.path.parent.mkdir(parents=True,exist_ok=True)
  self.path.write_text(json.dumps(self.rows,ensure_ascii=False,indent=2),encoding='utf-8')

def enrich_once(c,taxonomy,client,budget,cache_dir,live=False):
 catalog=c['evidence_catalog'];node=identity(c);zone=c['walk_zone']
 path=Path(cache_dir)/(hashlib.sha256((zone+'|'+node).encode()).hexdigest()+'.json')
 # Added provider identity must never trigger another call for an understood
 # route node. Prefer its original successful attempt, keeping provenance.
 existing=[(p,json.loads(p.read_text(encoding='utf-8'))) for p in Path(cache_dir).glob('*.json')]
 matches=[(p,s) for p,s in existing if s.get('candidate_id')==c['candidate_id']]
 if matches:
  path,saved=next(((p,s) for p,s in matches if s.get('semantic')),matches[0])
  node=saved['node_identity']
 evidence_hash=hashlib.sha256(json.dumps(catalog,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 retry=False;old_attempt=None
 if path.exists():
  saved=json.loads(path.read_text(encoding='utf-8'))
  if saved.get('output') and saved.get('semantic'):
   saved['semantic']=validate_semantic_enrichment(saved['output'],c,catalog,taxonomy);validate_role(saved['semantic']['route_role'])
   return dict(saved,cache_hit=True,api_calls_this_run=0)
  if (live and c.get('recall_material_repair') and saved.get('evidence_hash')!=evidence_hash
      and sum(r['node']==node and r['zone']==zone for r in budget.rows)<2):
   retry=True;old_attempt=saved
  else:return dict(saved,cache_hit=True,api_calls_this_run=0)
 if not live:return dict(semantic=None,reason='not_enriched_offline',cache_hit=False,api_calls_this_run=0)
 if not retry and any(r['node']==node and r['zone']==zone for r in budget.rows):return dict(semantic=None,reason='reserved_or_failed_attempt_already_recorded',cache_hit=False,api_calls_this_run=0)
 payload=dict(candidate={k:c[k] for k in ('candidate_id','name_zh','name_en','entity_kind','boundary_status')},evidence=compact_evidence(catalog))
 supported={tag:[ref for ref,atom in payload['evidence'].items() if re.search(pattern,atom['field']+': '+json.dumps(atom['value'],ensure_ascii=False),re.I)] for tag,pattern in TAG_GATES.items()}
 payload['lexically_eligible_tag_refs']={t:refs for t,refs in supported.items() if refs}
 schema=semantic_schema(taxonomy)
 for group,tags in taxonomy.items():schema['properties'][group]['items']['enum']=[t for t in tags if supported.get(t)]
 prompt=PROMPT+'\nThis is recall review. Short exterior observation can be transition_stop only when a distinct stable public node is evidenced; never invent accessibility. Supporting is not a target quota. Summary MUST be one exact short substring of one evidence value. factual_fields all null is preferred. No dates needed. Keep at most two tags per group. Select only directly supported tags. Reasons are judgments, not new facts. Planning durations are estimates, not official visit times.'
 reservation=budget.reserve(zone,node,retry=retry,reason='material_new_evidence' if retry else None)
 saved=dict(candidate_id=c['candidate_id'],node_identity=node,output=None,semantic=None,cache_hit=False,api_calls_this_run=1,evidence_hash=evidence_hash,
  prior_attempt=old_attempt,material_repair=c.get('recall_material_repair'))
 try:
  output=parse_provider_json(client.structured_parse(system_prompt=prompt,user_text=json.dumps(payload,ensure_ascii=False),schema=schema))
  saved['output']=output
  saved['semantic']=validate_semantic_enrichment(output,c,catalog,taxonomy);validate_role(saved['semantic']['route_role'])
  reservation['status']='success'
 except (LLMClientError,RequestValidationError,ValueError) as exc:
  saved['semantic']=None;saved['reason']=str(exc);reservation['status']='failed';reservation['error_type']=type(exc).__name__
 saved['provider']=client.last_response_metadata;budget.save()
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
 return saved
