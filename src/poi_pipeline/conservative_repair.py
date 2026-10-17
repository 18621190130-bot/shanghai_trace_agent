"""Build a fresh minimal evidence-cited skeleton; never trim a failed proposal."""
import copy,json,re
from .semantic.schema import FACTS
from .semantic.validation import TAG_GATES,tag_support_errors,validate_semantic_enrichment
from .role_audit import validate_role
from .subject_validation import validate_subject_scope

class ConservativeSemanticRepair:
 def build(self,candidate,taxonomy,*,profile,tags,summary_ref):
  category,primary,independent,connector,minutes,scope,facets=profile
  catalog=candidate['evidence_catalog'];tag_evidence=[]
  groups=('interest_tags','experience_tags','culture_tags')
  if any(len(ts)>limit for ts,limit in zip(tags,(2,2,1))):raise ValueError('Skeleton tag caps exceeded')
  if not tags[0]:raise ValueError('Skeleton requires an evidenced interest tag')
  for group,proposals in zip(groups,tags):
   for tag in proposals:
    if tag not in taxonomy[group]:raise ValueError('Unknown taxonomy proposal')
    options=[]
    for ref,atom in catalog.items():
     item=dict(group=group,tag=tag,evidence_refs=[ref])
     # Prefer direct subject authority excerpts over names/provider categories.
     if atom['source_type'] not in ('government','official'):continue
     if atom['field'] in ('name_zh','name_en','category','coordinates','address'):continue
     if not tag_support_errors(item,catalog):options.append(item)
    if not options:raise ValueError('No direct subject authority citation for '+tag)
    tag_evidence.append(options[0])
  role=dict(primary=primary,eligible=[primary],confidence='medium',reason=scope,
   independent_destination_value=independent,route_connector_value=connector,
   alternatives_reason={r:('本节点的独立体验与受证据限制的访问范围支持当前角色；不能为配比改变角色。') for r in ('anchor','supporting_stop','transition_stop')})
  validate_role(role)
  atom=catalog[summary_ref]
  if not isinstance(atom['value'],str):raise ValueError('Summary must quote one exact evidence value')
  output=dict(category=category,**{g:list(t) for g,t in zip(groups,tags)},tag_evidence=tag_evidence,
   category_evidence_refs=[summary_ref],route_role=role,citywalk_value=dict(level='high' if primary=='anchor' else 'medium',reason=scope,evidence_refs=[summary_ref]),
   summary_draft=dict(text=atom['value'],evidence_refs=[summary_ref]),culture_bridge_draft=None,
   visit_profile_proposal=dict(walk_stop=dict(quick=max(3,minutes//2),standard=minutes,deep=minutes+8),full_visit=None,
    time_basis='product_planning_estimate',scope=scope),semantic_confidence='medium',stability='stable',
   missing_information=['实时开放、预约与票务需未来实时层核实；代表点不等于入口。'],
   factual_fields={f:None for f in FACTS},taxonomy_extension_candidate=[])
  # Same validator, facts, coordinate inheritance, subject gate and role contract.
  semantic=validate_semantic_enrichment(output,candidate,catalog,taxonomy)
  semantic=validate_subject_scope(semantic,candidate)
  if semantic['subject_scope_validation']['removed_tags']:raise ValueError('Subject-scope validation removed a skeleton tag; defer rather than hard rescue')
  validate_role(semantic['route_role'])
  return dict(output=output,semantic=semantic,method='fresh_minimum_evidence_skeleton',api_calls=0,facets=facets,
   role_judgment_basis='explicit product assessment of independent destination / experience / connector value; category and target count are not role evidence')
