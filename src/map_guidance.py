"""Read-only, bounded in-app guidance using the shared AMap transport/walking service."""
import copy
import time
from collections import OrderedDict
from dataclasses import asdict
from threading import RLock

from .walking_models import Location
from .providers.amap.walking import number, parse_polyline
from .providers.base import ExternalProviderError, ProviderResponseError


class MapGuidance:
    MODES = ('walking', 'transit', 'taxi', 'bicycle')

    def __init__(self, client, walking, labels=None):
        self.client, self.walking, self.labels = client, walking, labels
        self.cache = OrderedDict()
        self.lock = RLock()

    def location(self, value):
        if not isinstance(value, dict):raise ValueError('invalid_location')
        point = Location(value.get('lat'), value.get('lng'), value.get('coordinate_system', 'GCJ02'))
        # This product supports Shanghai, including arrival from its airports.
        if not (30 <= point.lat <= 32 and 120 <= point.lng <= 123):raise ValueError('location_outside')
        return self.walking.normalize_location_for_amap(point)

    def search(self, body):
        query = body.get('query')
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100:raise ValueError('invalid_input')
        data = self.client.get('/v3/place/text', dict(keywords=query.strip(), city='310000', citylimit='true', offset=8, extensions='base'))
        results = []
        for p in data.get('pois', [])[:8]:
            try:
                lng, lat = map(float, p['location'].split(','))
                location = self.location(dict(lat=lat, lng=lng))
                text=lambda key:self.client.redact_text(p[key]) if isinstance(p.get(key),str) else ''
                address=' '.join(dict.fromkeys(filter(None,[text('cityname'),text('adname'),text('address')])))
                results.append(dict(id=p['id'],service_poi_id=p['id'],name=text('name'),address=address,category=text('type'),location=asdict(location)))
            except (ValueError, KeyError, TypeError):continue
        result=dict(results=results)
        return self.labels.apply(result) if self.labels and body.get('lang')=='en' else result

    def describe(self, body):
        point=self.location(body.get('location'))
        data=self.client.get('/v3/geocode/regeo',dict(location=point.amap_value(),extensions='base'))
        address=data.get('regeocode',{}).get('formatted_address')
        if not isinstance(address,str) or not address:raise ProviderResponseError()
        row=dict(service_poi_id='point:'+point.amap_value(),name=self.client.redact_text(address),address='',location=asdict(point))
        result=dict(results=[row])
        if self.labels and body.get('lang')=='en':result=self.labels.apply(result)
        return result['results'][0]

    def route(self, body):
        mode = body.get('mode', 'walking')
        if mode not in self.MODES:raise ValueError('invalid_mode')
        origin, destination = self.location(body.get('origin')), self.location(body.get('destination'))
        key = (mode, origin.amap_value(), destination.amap_value())
        # Serialize cache misses too: rapid clicks must not spend duplicate quota.
        with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() < cached[0]:return copy.deepcopy(cached[1])
            try:result = self._route(mode, origin, destination)
            except ExternalProviderError as exc:
                result = dict(mode=mode, availability='UNAVAILABLE', error_code=exc.code, segments=[], distance_m=None, duration_s=None)
            result.update(origin=asdict(origin), destination=asdict(destination))
            self.cache[key] = (time.monotonic() + (180 if result['availability']=='AVAILABLE' else 15), result)
            self.cache.move_to_end(key)
            while len(self.cache)>128:self.cache.popitem(last=False)
            return copy.deepcopy(result)

    def _route(self, mode, origin, destination):
        params = dict(origin=origin.amap_value(), destination=destination.amap_value())
        if mode == 'walking':
            r = self.walking.get_walking_route(origin, destination)
            return dict(mode=mode, availability='AVAILABLE', distance_m=r.distance_m, duration_s=r.duration_s,
                        segments=[dict(kind='walking', polyline=r.polyline)], steps=[asdict(s) for s in r.steps])
        endpoint = {'taxi':'/v3/direction/driving', 'transit':'/v3/direction/transit/integrated', 'bicycle':'/v5/direction/bicycling'}[mode]
        if mode=='transit':params.update(city='310000', cityd='310000', strategy=0, extensions='all')
        if mode=='bicycle':params.update(show_fields='cost,polyline')
        data = self.client.get(endpoint, params)
        try:
            paths=data['route']['transits' if mode=='transit' else 'paths']
            available=[]
            for path in paths:
                try:available.append(self._normalize_path(mode,path))
                except ProviderResponseError:continue
            if not available:raise ProviderResponseError()
            return min(available,key=lambda r:r['duration_s'])
        except (KeyError, IndexError, TypeError, AttributeError):raise ProviderResponseError() from None

    def _normalize_path(self, mode, path):
        try:
            distance = number(path.get('distance'), optional=True)
            duration = number(path.get('duration', path.get('cost', {}).get('duration')) if mode=='bicycle' else path.get('duration'))
            parts, steps = [], []
            def segment(item, kind):
                geometry = parse_polyline(item.get('polyline'))
                if len(geometry)<2:
                    if kind=='walking' and number(item.get('distance', 0))<=1:return
                    raise ProviderResponseError()
                parts.append(dict(kind=kind, polyline=geometry))
                label = item.get('name') or item.get('instruction') or ''
                steps.append(dict(kind=kind, instruction=self.client.redact_text(label) if isinstance(label,str) else ''))
            if mode=='transit':
                for s in path['segments']:
                    for w in (s.get('walking') or {}).get('steps', []):segment(w, 'walking')
                    lines = (s.get('bus') or {}).get('buslines', [])
                    if lines:segment(lines[0], 'transit')
                    # Rail/taxi portions without actual line geometry cannot be substituted by straight lines.
                    if any((s.get('railway') or {}).values()) or s.get('taxi'):raise ProviderResponseError()
            else:
                for s in path['steps']:segment(s, mode)
            if not parts:raise ProviderResponseError()
            return dict(mode=mode, availability='AVAILABLE', distance_m=distance, duration_s=duration, segments=parts, steps=steps)
        except (KeyError, IndexError, TypeError, AttributeError):raise ProviderResponseError() from None


def direction_lock(route):
    request = route.get('request', {})
    if request.get('route_mode') not in ('surprise_me','places_in_mind') and (request.get('start_poi_id') or request.get('start_lat') is not None):return 'fixed_start'
    for obj in [route, request, route.get('composition_diagnostics', {}), *route.get('ordered_pois', [])]:
        if any(obj.get(k) for k in ('direction_locked', 'fixed_order', 'time_windows', 'time_window', 'narrative_constraints', 'reservation_required')):
            return 'constrained_order'
    return None
