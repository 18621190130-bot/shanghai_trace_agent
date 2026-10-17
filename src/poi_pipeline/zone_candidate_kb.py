"""Candidate-only merge with stable semantic identity IDs and protected baseline."""
import copy,hashlib
from collections import Counter

def stable_poi_id(zone_id,source_identity):
    return 'pz_'+hashlib.sha256((zone_id+'|'+source_identity).encode()).hexdigest()[:12]

def merge_zone(base,config,audits,accepted):
 kb=copy.deepcopy(base);by_id={p['id']:p for p in kb['pois']}
 for a in audits:
  p=by_id[a['poi_id']]
  p.update(route_role=dict(primary=a['primary_role'],eligible=a['eligible_roles']),
   role_confidence=a['role_confidence'],route_role_audit=copy.deepcopy(a),
   route_selectable=a['route_selectable'],counts_as_route_stop=a['counts_as_route_stop'])
 zone=next(z for z in kb['metadata']['walk_zones'] if z['id']==config.zone_id)
 for row in accepted:
  c,s=row['candidate'],row['semantic']
  # Prefer the persisted provider parent ID; array order and evidence additions do not renumber nodes.
  identity=next((r['source_type']+':'+r['source_candidate_id'] for r in c['merged_source_records'] if r['source_type']=='amap'),c['candidate_id'])
  pid=stable_poi_id(config.zone_id,identity)
  profile=s['visit_profile_proposal'];modes={k:v for k,v in profile.items() if k in ('walk_stop','full_visit') and v}
  street=c['entity_kind']=='street' or any('道路名' in r['source_category'] or r['raw_provider_tags'].get('highway')=='pedestrian' for r in c['merged_source_records'])
  typ='park' if s['category']=='park' else 'street' if street else 'venue'
  environment='outdoor' if typ in ('park','street') or s['category']=='public_space' else 'mixed'
  location=dict(address_zh=c['address'],coordinate_system='GCJ-02',coordinate_note='Provider representative anchor, not verified entrance or a routed access point.')
  location.update(dict(zip(('representative_lat','representative_lng') if typ=='street' else ('lat','lng'),c['coordinates'])))
  p=dict(id=pid,display_order=len(kb['pois'])+1,name=dict(zh=c['name_zh'] or c['name_en'],en=c['name_en'] or c['name_zh'],aliases=c['aliases']),
   location=location,walk_zone=dict(id=config.zone_id,name_zh=zone['name_zh'],name_en=zone['name_en']),
   category=dict(zh=s['category'],en=s['category']),tags={g:s[g] for g in ('interest_tags','experience_tags','culture_tags')},
   poi_type=typ,planning=dict(environment=environment,crowd_level_default=None,ticket_required=None,reservation_required=None,opening_hours=None,last_verified=None),
   content=dict(summary_zh=s['summary_draft']['text']),culture_bridge=dict(explanation_zh=s['culture_bridge_draft']['text'] if s['culture_bridge_draft'] else '',content_status='literal evidence excerpt; no unverified English translation'),
   verification=dict(status='automatically_validated_candidate',source_confidence=row['source_confidence'],semantic_confidence=s['semantic_confidence'],source='Phase 2.5D/E configured pipeline; candidate only'),
   visit_profile=dict(default_mode='walk_stop',supported_modes=list(modes),modes=modes),
   visit_profile_calibration=dict(time_basis='product_planning_estimate',pending_manual_calibration_modes=list(modes)),
   visit_mode_details={m:dict(environment=environment,ticket_required=None,scope=(profile['scope']+'；仅该街道公共步行观察，不含沿街现有POI场馆内部参访，不重复计入同一体验。' if street else profile['scope'])) for m in modes},
   route_role=dict(primary=s['route_role']['primary'],eligible=s['route_role']['eligible']),role_confidence=s['route_role']['confidence'],
   route_role_audit=s['route_role'],route_selectable=True,counts_as_route_stop=True,
   source_provenance=dict(staging_node_id=c['candidate_id'],stable_identity=identity,sources=c['sources'],evidence_catalog=c['evidence_catalog'],tag_evidence=s['tag_evidence'],boundary_status=c['boundary_status'],stability_audit=row.get('stability_audit'),subject_scope_validation=s.get('subject_scope_validation')))
  if pid in by_id: raise ValueError('Stable ID collision: '+pid)
  by_id[pid]=p;kb['pois'].append(p);row['poi_id']=pid
 counts=Counter(p['walk_zone']['id'] for p in kb['pois'])
 kb['metadata'].update(poi_count=len(kb['pois']),version='phase2.5de-all-zones-candidate',production_imported=False,candidate_kb_status='pending_regression')
 for z in kb['metadata']['walk_zones']:z['poi_count']=counts[z['id']]
 return kb
