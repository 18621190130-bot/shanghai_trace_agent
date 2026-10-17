"""Explicit production route-node identity; not a physical-object equivalence claim."""
import re
from urllib.parse import urlsplit
from ...geo_utils import haversine_km
from ..normalization import match_key

KNOWN_IDENTITIES = {
    'p5': dict(aliases=['Long Museum (West Bund)','龙美术馆','龙美术馆（西岸馆）'], urls=['detail_aa8Ec.html']),
    'p28': dict(aliases=['West Bund Museum','西岸美术馆','西岸美术馆x蓬皮杜中心'], urls=['detail_695y4T.html']),
    'p29': dict(aliases=['TANK Shanghai','上海油罐艺术中心','油罐艺术中心'], urls=['detail_e9dD9.html']),
    'p30': dict(aliases=['Gate M West Bund Dream Center','Gate M西岸梦中心','西岸梦中心'], urls=[]),
    'p31': dict(aliases=['START Museum','START星美术馆','星美术馆'], urls=['detail_6f9E8.html','2022-1230.html']),
}


def names_for(candidate):
    return {match_key(n) for n in [candidate.get('name_zh',''),candidate.get('name_en',''),
            candidate.get('name',''),*candidate.get('aliases',[])] if n}


def address_key(value):
    return re.sub(r'^(上海市|上海|徐汇区)+','',match_key(value)).replace('号','')


class ProductionIdentityResolver:
    def __init__(self, repository, known_source_identities=None, zone_id='west_bund', identity_registry=None):
        self.repository=repository
        self.zone_id=zone_id
        self.registry=identity_registry if identity_registry is not None else (KNOWN_IDENTITIES if zone_id=='west_bund' else {})
        self.raw={p['id']:p for p in repository.get_raw_data()['pois'] if p['walk_zone']['id']==zone_id}
        self.known_source_identities=known_source_identities or {}

    def resolve(self,candidate):
        names=names_for(candidate)
        point=candidate.get('coordinates')
        address=address_key(candidate.get('address',''))
        records=candidate.get('merged_source_records',[])
        source_ids={r['source_type']+':'+r['source_candidate_id'] for r in records}
        sources=candidate.get('sources',[])
        scores=[]
        for pid,raw in self.raw.items():
            poi=self.repository.get_poi_by_id(pid)
            registry=self.registry.get(pid,dict(aliases=[],urls=[]))
            aliases={match_key(n) for n in [raw['name']['zh'],raw['name']['en'],*raw['name'].get('aliases',[]),*registry['aliases']]}
            exact=bool(names & aliases)
            distance=haversine_km(point,poi.coordinates)*1000 if point else None
            location=distance is not None and distance<=220
            production_address=address_key(raw['location'].get('address_zh',''))
            address_match=bool(address and production_address and (address in production_address or production_address in address))
            url_match=any(s.get('source_type') in ('official','government') and urlsplit(s.get('url','')).hostname in ('www.westbund.com','westbund.com')
                          and any(s.get('url','').endswith(u) for u in registry['urls']) for s in sources)
            source_match=any(self.known_source_identities.get(sid)==pid for sid in source_ids)
            explicit=candidate.get('production_id')==pid
            if source_match or explicit or (exact and (location or address_match or url_match)):
                # A known source cannot conceal a material geometry conflict.
                status='possible_duplicate' if distance is not None and distance>600 else 'existing_production'
                scores.append(dict(identity_status=status,production_match=pid,confidence='high' if status=='existing_production' else 'low',
                    evidence=dict(name_match=exact,distance_m=round(distance,1) if distance is not None else None,
                        address_match=address_match,known_official_url=url_match,known_source_identity=source_match,explicit_production_id=explicit),
                    mapping_scope='existing_route_node; internal source objects do not become separate stops'))
            elif exact:
                scores.append(dict(identity_status='possible_duplicate',production_match=pid,confidence='medium',
                    evidence=dict(name_match=True,distance_m=round(distance,1) if distance is not None else None),
                    mapping_scope='insufficient corroboration; not eligible as a new node'))
        if len(scores)==1:
            return scores[0]
        if len(scores)>1:
            return dict(identity_status='unresolved',production_match=None,confidence='low',alternatives=scores)
        # A same-brand differently named complex must not be silently imported.
        if self.zone_id=='west_bund' and any('gatem' in n or '西岸梦中心' in n for n in names):
            return dict(identity_status='possible_duplicate',production_match='p30',confidence='low',
                        evidence=dict(reason='shared brand or parent name, distinct entity/scope needs review'))
        return dict(identity_status='new_candidate' if point and names else 'unresolved',production_match=None,
                    confidence='medium' if point else 'low',evidence=dict(reason='no production identity match'))
