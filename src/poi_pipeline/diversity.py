"""Soft multi-label diagnostics; never alter RouteEngine scoring or POI tags."""
from collections import Counter
import re

TEXTURE={'street','lane','historic_building','public_square','civic_space','landmark','community_space','historic_district','religious_building','industrial_heritage','urban_renewal'}

def facets(p):
 category=p['category']['en'];zh=p['category']['zh'];name=p['name']['zh'];typ=p['poi_type'];tags=p['tags']
 if typ=='park' or category=='park':return {'park'}
 if p.get('urban_texture_audit'):return set(p['urban_texture_audit']['facets'])
 result=set()
 if typ=='street':result.add('street')
 if '石库门' in zh or ('里弄' in zh) or typ=='district' and re.search('邨|弄',name):result.add('lane')
 if re.search('历史住宅|历史公寓|名人故居|历史宗教',zh) or re.search('故居|大楼|会址|旧址',name):result.add('historic_building')
 if typ=='district' and re.search('历史|老城|石库门',zh):result.add('historic_district')
 if typ=='landmark':result.add('landmark')
 if '广场' in name:result.update(('public_square','civic_space'))
 if re.search('宗教|教堂|天主堂|庙',zh+name):result.add('religious_building')
 if 'industrial_heritage' in tags['interest_tags']:result.add('industrial_heritage')
 if 'urban_renewal' in tags['culture_tags']:result.add('urban_renewal')
 if re.search('文化|艺术|书院|美术|纪念馆|书局|博物|剧院',zh+name) or category in ('museum','cultural_venue','performance_venue'):result.add('cultural_space')
 return result

def distribution(pois):
 n=len(pois);counts=Counter(f for p in pois for f in facets(p))
 return dict(nodes=n,category_distribution=dict(Counter(p['category']['en'] for p in pois)),
  primary_role_distribution=dict(Counter(p['route_role']['primary'] for p in pois)),
  park_share=round(counts['park']/n,4) if n else 0,street_lane_share=round(sum(bool(facets(p)&{'street','lane'}) for p in pois)/n,4) if n else 0,
  historic_building_share=round(counts['historic_building']/n,4) if n else 0,
  public_square_civic_space_share=round(sum(bool(facets(p)&{'public_square','civic_space'}) for p in pois)/n,4) if n else 0,
  landmark_share=round(counts['landmark']/n,4) if n else 0,cultural_space_share=round(counts['cultural_space']/n,4) if n else 0,
  urban_texture_node_count=sum(bool(facets(p)&TEXTURE) for p in pois),facet_counts=dict(counts),
  definitions='Facets may overlap; legacy classification uses existing category/type/name/tags, new facets have explicit scope audit. Ordinary parks excluded from urban_texture count. Diagnostics never add tags or change roles.')

def route_diversity(row,raw_index):
 pois=[raw_index[s['poi_id']] for s in row['selected_stops']];f=[facets(p) for p in pois]
 return dict(poi_categories=[p['category']['en'] for p in pois],route_roles=[s['primary_role'] for s in row['selected_stops']],
  park_count=sum('park' in v for v in f),street_lane_count=sum(bool(v&{'street','lane'}) for v in f),
  landmark_building_count=sum(bool(v&{'landmark','historic_building'}) for v in f),urban_texture_count=sum(bool(v&TEXTURE) for v in f),
  route_category_diversity=len({p['category']['en'] for p in pois}),soft_diagnostic_only=True)
