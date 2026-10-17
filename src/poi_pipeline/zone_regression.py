"""Zone-derived fixed classes of requests; failure cannot relabel an anchor."""
from collections import Counter
from ..models import RouteRequest
from ..route_engine import RouteEngine
from ..west_bund_regression import describe

def regression_cases(repository,zone,added_ids):
 pois=repository.get_pois_by_zone(zone)
 tags=Counter(t for p in pois for t in p.interest_tags)
 themes=[t for t,n in tags.most_common()]
 added=[p for p in pois if p.id in added_ids]
 new_tags=Counter(t for p in added for t in p.interest_tags)
 broad=themes[:2]
 return [
  ('core_1','strongest core theme',RouteRequest(180,preferred_zone=zone,interest_tags=themes[:1])),
  ('core_2','second core theme',RouteRequest(180,preferred_zone=zone,interest_tags=themes[1:2])),
  ('non_museum','outdoor/public-space walk; no museums',RouteRequest(150,preferred_zone=zone,interest_tags=list(dict.fromkeys(['parks']+broad)),avoid_tags=['museum_visit'])),
  ('new_coverage','new nodes thematic coverage',RouteRequest(180,preferred_zone=zone,interest_tags=list(dict.fromkeys([t for t,n in new_tags.most_common(2)]+broad)))),
  ('general_180','general three-hour walk',RouteRequest(180,preferred_zone=zone)),
  ('negative','no shopping',RouteRequest(180,preferred_zone=zone,avoid_tags=['shopping_lifestyle','shopping_leisure']))]

def run_zone_regression(repository,zone,added_ids):
 engine=RouteEngine(repository)
 rows=[describe(engine,req,name,label) for name,label,req in regression_cases(repository,zone,added_ids)]
 for r in rows:
  ids=[s['poi_id'] for s in r['selected_stops']]
  r['zone_isolation_passed']=all(repository.get_poi_by_id(pid).zone_id==zone for pid in ids)
  r['new_nodes_selected']=[pid for pid in ids if pid in added_ids]
  r['geographic_continuity_passed']=(r['estimated_max_single_leg_km'] or 0)<=3.5
  r['relevance_passed']=all(bool(s['matched_tags']['interest_tags'] or s['matched_tags']['experience_tags'] or s['matched_tags']['culture_tags']) or not any(r['request'][g] for g in ('interest_tags','experience_tags','culture_tags')) for s in r['selected_stops'])
  r['passed']=r['route_status']=='success' and r['minimum_viable_passed'] and r['composition_passed'] and r['negative_preference_passed'] and r['zone_isolation_passed'] and r['geographic_continuity_passed'] and r['relevance_passed']
 passed=sum(bool(r['passed']) for r in rows)
 shortage=sum(r['failure_attribution']=='insufficient_high_quality_poi_supply' for r in rows)
 return dict(zone_id=zone,cases=rows,passed_count=passed,total=len(rows),acceptable=passed>=4,
  zone_expansion_recommended=shortage>=2,expansion_passes=0,
  geographic_diagnostic='Approximate straight-line-derived walking distances; not real map routing. 3.5 km maximum leg is a diagnostic threshold.',
  anchor_coverage_gap=not any(p.route_role_primary=='anchor' for p in repository.get_pois_by_zone(zone)))
