"""Amap world DTO normalization; one shared 3B_1 client and converter."""
import math
import re
from ..base import ProviderResponseError
from .walking import parse_polyline
from ...walking_models import Location
from ...world_models import ResolvedLocation, PoiLiveInfo, PoiCandidate, LiveDataStatus, utc_now


def optional_text(value, client):
    return client.redact_text(value.strip()) if isinstance(value, str) and value.strip() else None


def optional_number(value, maximum=None):
    try:
        if isinstance(value, bool):return None
        n = float(value)
        return n if math.isfinite(n) and n >= 0 and (maximum is None or n <= maximum) else None
    except (ValueError, TypeError, OverflowError):return None


def optional_location(value):
    if value is None or value == '' or value == []:return None
    points = parse_polyline(value)
    if len(points) != 1:raise ProviderResponseError()
    return Location(points[0][1], points[0][0], 'GCJ02')


class AmapGeocodingProvider:
    def __init__(self, client):self.client = client

    def reverse_geocode(self, location):
        if location.coordinate_system != 'GCJ02':raise ProviderResponseError()
        data = self.client.get('/v3/geocode/regeo', {'location': location.amap_value(), 'extensions': 'base'})
        raw = data.get('regeocode')
        if not isinstance(raw, dict) or not raw:raise ProviderResponseError()
        component = raw.get('addressComponent') or {}
        if not isinstance(component, dict):raise ProviderResponseError()
        street = component.get('streetNumber') or {}
        if not isinstance(street, dict):raise ProviderResponseError()
        get = lambda value: optional_text(value, self.client)
        fields = dict(formatted_address=get(raw.get('formatted_address')),
                      province=get(component.get('province')), city=get(component.get('city')),
                      district=get(component.get('district')), township=get(component.get('township')),
                      adcode=get(component.get('adcode')), street=get(street.get('street')),
                      street_number=get(street.get('number')))
        # Amap returns an empty city list for municipalities; province is its documented city identity.
        if fields['city'] is None and fields['province'] in ('上海市', '北京市', '天津市', '重庆市'):
            fields['city'] = fields['province']
        if not any(fields.values()):raise ProviderResponseError()
        status = LiveDataStatus.AVAILABLE if all(fields[k] for k in ('formatted_address','city','district','adcode')) else LiveDataStatus.PARTIAL
        return ResolvedLocation(location, **fields, fetched_at=utc_now(), live_data_status=status)


class AmapPoiProvider:
    def __init__(self, client):self.client = client

    def get_poi_detail(self, provider_id):
        if not isinstance(provider_id, str) or not re.fullmatch(r'[A-Za-z0-9]{5,32}', provider_id):
            raise ProviderResponseError()
        data = self.client.get('/v5/place/detail', {'id': provider_id, 'show_fields': 'business'})
        pois = data.get('pois')
        if not isinstance(pois, list):raise ProviderResponseError()
        raw = next((p for p in pois if isinstance(p, dict) and p.get('id') == provider_id), None)
        if raw is None:raise ProviderResponseError()
        business = raw.get('business') or {}
        if not isinstance(business, dict):raise ProviderResponseError()
        text = lambda value: optional_text(value, self.client)
        tags = text(business.get('tag') or business.get('keytag') or business.get('rectag') or raw.get('tag') or raw.get('atag'))
        fields = dict(name=text(raw.get('name')), address=text(raw.get('address')),
                      location=optional_location(raw.get('location')),
                      tel=text(business.get('tel', raw.get('tel'))),
                      opentime_today=text(business.get('opentime_today', raw.get('opentime_today'))),
                      opentime_week=text(business.get('opentime_week', raw.get('opentime_week'))),
                      rating=optional_number(business.get('rating'), 5), cost=optional_number(business.get('cost')),
                      tags=tuple(x.strip() for x in re.split('[;；,，]', tags) if x.strip()) if tags else None,
                      poi_type=text(raw.get('type')))
        if fields['name'] is None:raise ProviderResponseError()
        status = LiveDataStatus.AVAILABLE if all(v is not None for v in fields.values()) else LiveDataStatus.PARTIAL
        return PoiLiveInfo(provider_id=provider_id, **fields, fetched_at=utc_now(), live_data_status=status)

    def search_mapping_candidates(self, name):
        data = self.client.get('/v5/place/text', {'keywords': name, 'region': '上海', 'city_limit': 'true',
                                              'page_size': 10, 'page_num': 1})
        return self._mapping_candidates(data)

    def search_identity_near_coordinate(self, name, location, *, types='', radius=1000):
        """Calibration-only identity lookup; not a runtime nearby recommendation service."""
        if location.coordinate_system != 'GCJ02':raise ProviderResponseError()
        params = {'keywords':name,'location':location.amap_value(),'radius':radius,'page_size':25,'page_num':1}
        if types:params['types'] = types
        return self._mapping_candidates(self.client.get('/v5/place/around',params))

    def _mapping_candidates(self, data):
        pois = data.get('pois')
        if not isinstance(pois, list):raise ProviderResponseError()
        output = []
        for raw in pois:
            if not isinstance(raw, dict):continue
            pid = optional_text(raw.get('id'), self.client);label = optional_text(raw.get('name'), self.client)
            try:location = optional_location(raw.get('location'))
            except ProviderResponseError:continue
            if not pid or not label or not location:continue
            output.append(PoiCandidate(pid, label, location, optional_text(raw.get('adname'), self.client),
                                       optional_text(raw.get('address'), self.client), optional_text(raw.get('type'), self.client)))
        return output
