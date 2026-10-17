"""Configured collection, normalization, identity and route-node consolidation."""
from collections import Counter
from dataclasses import asdict
from .sources.amap_source import AmapSource
from .sources.osm_source import OSMSource
from .sources.official_source import OfficialSource
from .normalization import normalize_candidate, match_key
from .deduplication import deduplicate_candidates
from .evidence import build_evidence_bundle
from .prefilter import prefilter_raw, normalized_name
from .semantic.preparation import evidence_catalog, unique
from .semantic.identity import ProductionIdentityResolver
from ..geo_utils import haversine_km

def collect_zone(config,http,repository):
    sources=[AmapSource(http,config),OSMSource(http,config),OfficialSource(http,config)]
    raw=[]; errors=[]
    for source in sources:
        try: raw.extend(source.collect())
        except Exception as exc: source.error('collection',exc)
        errors+=source.errors
    rejected=[]; retained=[]
    for r in raw:
        reason=prefilter_raw(r,config)
        if reason: rejected.append(dict(record_id=r.source_type+':'+r.source_candidate_id,name=r.name_zh or r.name_en,decision='reject',reason=reason))
        else: retained.append(r)
    normalized=[]
    for r in retained:
        try: normalized.append(normalize_candidate(r,config))
        except (ValueError,TypeError) as exc: errors.append(dict(source=r.source_type,error=type(exc).__name__,status='normalization_failure'))
    canonical=[asdict(c) for c in deduplicate_candidates(normalized,config.zone_id)]
    resolver=ProductionIdentityResolver(repository,zone_id=config.zone_id)
    return raw, canonical, rejected, errors

def consolidate_zone(candidates,repository,config):
    """Only exact unambiguous names link geometry-free authority mentions.

    Parent containment uses explicit provider parent identity, or corroborated
    name/address plus nearby geometry. Ambiguous overlap remains deferred.
    """
    from .models import RawCandidate,CanonicalCandidate
    resolver=ProductionIdentityResolver(repository,zone_id=config.zone_id)
    mapped=[c for c in candidates if c['coordinates']]
    registry=[]
    # Provider line/area/point representations of the same named street are one
    # tourist experience. Config aliases describe identity, never semantic truth.
    aliases=config.settings.get('route_node_alias_groups',[])
    def equivalent_names(a,b):
        an,bn=normalized_name(a['name_zh']),normalized_name(b['name_zh'])
        return an==bn or any(an in group and bn in group for group in aliases)
    groups=[]
    for c in mapped:
        g=next((g for g in groups if all(equivalent_names(c,m) and haversine_km(c['coordinates'],m['coordinates'])<=.18 for m in g)),None)
        if g is None:groups.append([c])
        else:g.append(c)
    mapped=[]
    for group in groups:
        group.sort(key=lambda c:(not any(s['source_type']=='amap' for s in c['sources']),-len(c['name_zh']),c['candidate_id']))
        leader=group[0]
        for member in group[1:]:
            leader['aliases']=sorted(set(leader['aliases']+[member['name_zh'],member['name_en']]+member['aliases'])-{''})
            leader['merged_source_records']=unique(leader['merged_source_records']+member['merged_source_records'])
            leader['sources']=unique(leader['sources']+member['sources'])
            registry.append(dict(entity_id=member['candidate_id'],parent_node=leader['candidate_id'],route_selectable=False,counts_as_route_stop=False,relationship='same_named_route_experience'))
        mapped.append(leader)
    for mention in [c for c in candidates if not c['coordinates']]:
        key=normalized_name(mention['name_zh'])
        matches=[c for c in mapped if c['boundary_status']!='outside_pilot' and key and key in {normalized_name(n) for n in [c['name_zh'],c['name_en'],*c['aliases']]}]
        if len(matches)==1:
            target=matches[0]
            target['merged_source_records']=unique(target['merged_source_records']+mention['merged_source_records'])
            target['sources']=unique(target['sources']+mention['sources'])
            registry.append(dict(entity_id=mention['candidate_id'],parent_node=target['candidate_id'],route_selectable=False,counts_as_route_stop=False,relationship='same_name_authority_evidence_link'))
        else:
            registry.append(dict(entity_id=mention['candidate_id'],name=mention['name_zh'],decision='defer',route_selectable=False,counts_as_route_stop=False,reason='authority_mention_geometry_ambiguous'))
    # Whole-production resolver catches cross-zone identities as well.
    resolvers=[ProductionIdentityResolver(repository,zone_id=z) for z in repository.zone_order]
    for c in mapped:
        identities=[r.resolve(c) for r in resolvers]
        matches=[i for i in identities if i['identity_status']!='new_candidate' and i['production_match']]
        c['identity']=matches[0] if matches else resolver.resolve(c)
        # Legacy parent display names include scope suffixes; recognize those
        # explicitly with name containment + nearby location, without merging
        # unrelated co-located objects by distance alone.
        if c['identity']['identity_status']=='new_candidate':
            cn=normalized_name(c['name_zh'])
            for p in repository.get_raw_data()['pois']:
                pn=normalized_name(p['name']['zh'])
                if len(cn)>=3 and len(pn)>=3 and (cn in pn or pn in cn) and haversine_km(c['coordinates'],repository.get_poi_by_id(p['id']).coordinates)<.8:
                    c['identity']=dict(identity_status='possible_duplicate',production_match=p['id'],confidence='medium',evidence=dict(reason='scope-name containment; legacy representative geometry requires reconciliation'))
                    break
        # Separate provider objects inside a source parent are not extra stops.
        for parent in mapped:
            if c is parent: continue
            cn,pn=normalized_name(c['name_zh']),normalized_name(parent['name_zh'])
            if len(pn)>=3 and pn in cn and cn!=pn and haversine_km(c['coordinates'],parent['coordinates'])<.25:
                c['internal_parent']=parent['candidate_id']; break
        raw=[RawCandidate(**r) for r in c['merged_source_records']]
        obj=CanonicalCandidate(**{**{k:v for k,v in c.items() if k in CanonicalCandidate.__dataclass_fields__},'merged_source_records':raw})
        c['evidence_catalog']=evidence_catalog(asdict(build_evidence_bundle(obj)))
    return mapped,registry
