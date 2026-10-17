"""One role contract for existing and new nodes; no production-status fallback."""
from .semantic.schema import ROLES, LEVELS

ROLE_STANDARD = dict(
 anchor='High independent destination value, deliberate standalone visit, can carry a route theme.',
 supporting_stop='Independent worthwhile City Walk experience complementing a route destination.',
 transition_stop='Short street/public-space observation whose main value is connecting stronger stops.')

def validate_role(role):
    if role['primary'] not in ROLES or not role['eligible'] or any(r not in ROLES for r in role['eligible']) or role['primary'] not in role['eligible']:
        raise ValueError('Invalid route-role taxonomy')
    if role['confidence'] not in LEVELS or not role.get('reason'):
        raise ValueError('Role requires confidence and reason')
    if 'anchor' in role['eligible'] and role['independent_destination_value']!='high':
        raise ValueError('Anchor requires evidenced high independent destination value')
    return role

def audit_existing(repository,config,decisions):
    rows=[]
    raw=repository.get_raw_data()['pois']
    for pid in config.seed_production_pois:
        p=next(p for p in raw if p['id']==pid)
        if pid not in decisions: raise ValueError('Existing POI lacks explicit role audit: '+pid)
        d=decisions[pid]
        role=validate_role(dict(primary=d['primary_role'],eligible=d['eligible_roles'],confidence=d['role_confidence'],reason=d['role_reason'],independent_destination_value=d['independent_destination_value']))
        rows.append(dict(poi_id=pid,name=p['name']['zh'],**d,
            role_standard=ROLE_STANDARD,available_evidence=dict(source='preserved_existing_KB; product visit scope is not fresh external verification',
                summary=p['content'],visit_profile=p['visit_profile'],visit_scope=p.get('visit_mode_details'),verification=p['verification']),
            decision='defer' if role['confidence']=='low' else 'audited_existing',
            route_selectable=role['confidence']!='low',counts_as_route_stop=role['confidence']!='low',
            audit_method='explicit evidence-grounded product assessment; no default anchor; no tag-count/fame/category rule'))
    return rows
