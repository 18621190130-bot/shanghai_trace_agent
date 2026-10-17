"""Read-only seven-category nearby service observations; depends on neither TripStore nor route mutations."""
from dataclasses import replace
from datetime import datetime
from ..geo_utils import haversine_km
from ..nearby_models import (ServicePoi, ServicePoiCategory, DEFAULT_CATEGORIES, NearbySearchOrigin, NearbyCategoryResult,
                            NearbySearchResult)
from ..walking_models import Location
from ..world_models import LiveDataStatus, OpenStatus, SHANGHAI
from ..providers.base import ExternalProviderError, ProviderResponseError, ProviderUnavailableError
from .location_service import current_location as coerce_location
from .opening_hours import shanghai_time, resolve_open_status
from .ttl_cache import TTLCache

SAFE_ERRORS = {'provider_error', 'provider_response_invalid', 'provider_unavailable', 'provider_timeout', 'provider_quota_exceeded'}


def safe_error(exc):
    return exc.code if isinstance(exc, ExternalProviderError) and exc.code in SAFE_ERRORS else 'provider_response_invalid'


def normalize_categories(value):
    if value is None: return DEFAULT_CATEGORIES
    if isinstance(value, str): value = [value]
    if not isinstance(value, (list, tuple)) or not value: raise ValueError('At least one service category required')
    selected = {ServicePoiCategory(v) for v in value}
    return tuple(c for c in DEFAULT_CATEGORIES if c in selected)


def rank(row):
    status = {OpenStatus.OPEN: 0, OpenStatus.UNKNOWN: 1, OpenStatus.NOT_APPLICABLE: 1, OpenStatus.CLOSED: 2}
    return (status[row.open_status], row.distance_m, row.rating is None, -(row.rating or 0), row.service_poi_id)


def merge(rows):
    by_id = {}
    for row in rows:
        previous = by_id.get(row.service_poi_id)
        if previous is None:
            by_id[row.service_poi_id] = row
            continue
        # Keep an actual provider observation, union classification only; no invented fields.
        completeness = lambda p: sum(getattr(p, f) is not None for f in ('address','tel','rating','cost','opentime_today','opentime_week'))
        preferred = min((previous, row), key=lambda p: (-completeness(p), -datetime.fromisoformat(p.fetched_at).timestamp(), p.distance_m))
        combined = tuple(c for c in ServicePoiCategory if c in set(previous.categories) | set(row.categories))
        by_id[row.service_poi_id] = replace(preferred, categories=combined, primary_category=combined[0])
    return list(by_id.values())


class NearbyService:
    def __init__(self, provider, repository, locations, *, ttl_s=300, cache=None, clock=None):
        self.provider, self.repository, self.locations = provider, repository, locations
        self.cache = cache if cache is not None else TTLCache(ttl_s)
        self.clock = clock if clock is not None else lambda: datetime.now(SHANGHAI)

    def search_nearby_services(self, location=None, core_poi_id=None, categories=None, radius_m=800, limit_per_category=5,
                               *, current_location=None):
        requested = normalize_categories(categories)
        if type(radius_m) is not int or not 1 <= radius_m <= 3000: raise ValueError('Radius must be 1..3000 metres')
        if type(limit_per_category) is not int or not 1 <= limit_per_category <= 10: raise ValueError('Limit must be 1..10 per category')
        if location is not None and current_location is not None: raise ValueError('Supply one current location')
        supplied = current_location if current_location is not None else location
        now = shanghai_time(self.clock()); provider_name = getattr(self.provider, 'provider', 'amap')
        common = dict(radius_m=radius_m, requested_categories=requested, provider=provider_name,
                      fetched_at=now.isoformat(), limit_per_category=limit_per_category)
        if supplied is not None:
            supplied = coerce_location(supplied)  # Invalid caller data must not silently degrade.
            source = NearbySearchOrigin.CURRENT_LOCATION; core_id = None
            try:
                origin = self.locations.normalize_location_for_amap(supplied)
            except Exception as exc:
                return NearbySearchResult(None, source, results=(), status=LiveDataStatus.UNAVAILABLE,
                    errors=({'category': None, 'stage': 'origin_normalization', 'code': safe_error(exc)},), **common)
        else:
            if not isinstance(core_poi_id, str) or not core_poi_id.strip(): raise ValueError('Current location or Core POI required')
            poi = self.repository.get_poi_by_id(core_poi_id)
            if poi is None: raise ValueError('Unknown Core POI')
            # Repository's frozen spatial overlay already supplies AREA/LINEAR anchor coordinates.
            origin = Location(*poi.coordinates, 'GCJ02'); source = NearbySearchOrigin.CORE_POI; core_id = core_poi_id
        rows = []; errors = []; hits = []; statuses = []; pages = {}; missing = []
        keys = {c:(provider_name,origin.lat,origin.lng,c,radius_m,limit_per_category) for c in requested}
        for category in requested:
            pages[category] = self.cache.get(keys[category])
            if pages[category] is None:missing.append(category)
            else:hits.append(category)
        batch = getattr(self.provider,'search_nearby_categories',None)
        if missing and callable(batch):
            try:
                fresh = batch(origin,tuple(missing),radius_m=radius_m,limit=limit_per_category)
                if not isinstance(fresh,dict):raise ProviderResponseError()
                for category in missing:pages[category] = fresh.get(category)
            except Exception as exc:
                for category in missing:pages[category] = NearbyCategoryResult((),LiveDataStatus.UNAVAILABLE,(safe_error(exc),))
        else:
            # Compatibility for existing single-category providers; Amap always uses grouped requests.
            for category in missing:
                try:
                    if self.provider is None:raise ProviderUnavailableError()
                    pages[category] = self.provider.search_nearby(origin,category,radius_m=radius_m,limit=limit_per_category)
                except Exception as exc:pages[category] = NearbyCategoryResult((),LiveDataStatus.UNAVAILABLE,(safe_error(exc),))
        for category in requested:
            try:
                page = pages[category]
                if not isinstance(page,NearbyCategoryResult) or not isinstance(page.results,tuple) or page.status not in (LiveDataStatus.AVAILABLE,LiveDataStatus.PARTIAL,LiveDataStatus.UNAVAILABLE):raise ProviderResponseError()
                if not isinstance(page.errors,tuple) or any(not isinstance(code,str) for code in page.errors):raise ProviderResponseError()
                if page.status == LiveDataStatus.UNAVAILABLE:
                    if page.results or not page.errors:raise ProviderResponseError()
                    statuses.append({'category':category,'status':page.status})
                    errors.extend({'category':category,'stage':'nearby_search','code':code if code in SAFE_ERRORS else 'provider_response_invalid'} for code in page.errors)
                    continue
                if bool(page.errors) != (page.status == LiveDataStatus.PARTIAL):raise ProviderResponseError()
                for row in page.results:
                    if not isinstance(row,ServicePoi) or row.provider != provider_name or category not in row.categories or row.data_status == LiveDataStatus.UNAVAILABLE:raise ProviderResponseError()
                observed = []
                for row in page.results:
                    geometric_distance = haversine_km((origin.lat,origin.lng),(row.location.lat,row.location.lng))*1000
                    if row.distance_m > radius_m or geometric_distance > radius_m:continue
                    fetched = datetime.fromisoformat(row.fetched_at).astimezone(SHANGHAI)
                    hours = row.opentime_today if fetched.date() == now.date() else None
                    observed.append(replace(row,open_status=resolve_open_status(hours,now),status_evaluated_at=now.isoformat()))
                rows.extend(observed);statuses.append({'category':category,'status':page.status})
                for code in page.errors:
                    errors.append({'category':category,'stage':'nearby_search','code':'malformed_service_poi' if code == 'malformed_service_poi' else 'provider_response_invalid'})
                if category in missing:self.cache.set(keys[category],page)
            except Exception as exc:
                statuses.append({'category':category,'status':LiveDataStatus.UNAVAILABLE})
                errors.append({'category':category,'stage':'nearby_search','code':safe_error(exc)})
        # Rank within each category, then expose references into one deduplicated result inventory.
        inventory = merge(rows);selected = {};category_ids = {}
        for category in requested:
            top = sorted((row for row in inventory if category in row.categories),key=rank)[:limit_per_category]
            category_ids[category] = tuple(row.service_poi_id for row in top)
            for row in top:selected.setdefault(row.service_poi_id,row)
        if all(s['status'] == LiveDataStatus.AVAILABLE for s in statuses):status = LiveDataStatus.AVAILABLE
        elif all(s['status'] == LiveDataStatus.UNAVAILABLE for s in statuses):status = LiveDataStatus.UNAVAILABLE
        else:status = LiveDataStatus.PARTIAL
        return NearbySearchResult(origin,source,results=tuple(selected.values()),status=status,errors=tuple(errors),
            core_poi_id=core_id,cache_hit_categories=tuple(hits),category_statuses=tuple(statuses),category_result_ids=category_ids,**common)

    def search_nearby_rest_stops(self,*args,**kwargs):
        return self.search_nearby_services(*args,**kwargs)
