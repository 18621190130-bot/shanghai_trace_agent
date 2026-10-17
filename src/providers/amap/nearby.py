"""Bounded grouped around searches, inline business fields; no detail fan-out."""
import re
from ...amap_category_mapping import AmapCategoryMapping
from ...geo_utils import haversine_km
from ...nearby_models import ServicePoi, NearbyCategoryResult, ServicePoiCategory, DistanceType
from ...world_models import LiveDataStatus, utc_now
from ..base import (ProviderResponseError, ExternalProviderError, ProviderUnavailableError,
                    ProviderTimeoutError, ProviderQuotaError)
from .world import optional_text, optional_number, optional_location


class AmapNearbyPoiProvider:
    provider = 'amap'

    def __init__(self, client, *, mapping=None):
        self.client = client
        self.mapping = mapping if mapping is not None else AmapCategoryMapping()

    def search_nearby(self, origin, category, *, radius_m, limit):
        result = self.search_nearby_categories(origin,(ServicePoiCategory(category),),radius_m=radius_m,limit=limit)[ServicePoiCategory(category)]
        if result.status == LiveDataStatus.UNAVAILABLE:
            error = {'provider_timeout':ProviderTimeoutError,'provider_quota_exceeded':ProviderQuotaError,
                     'provider_unavailable':ProviderUnavailableError}.get(result.errors[0],ProviderResponseError)
            raise error()
        return result

    def search_nearby_categories(self, origin, categories, *, radius_m, limit):
        requested = tuple(ServicePoiCategory(c) for c in categories)
        if not requested or origin.coordinate_system != 'GCJ02' or type(radius_m) is not int or not 1 <= radius_m <= 3000 or type(limit) is not int or not 1 <= limit <= 10: raise ValueError('Invalid nearby request')
        output = {}
        for members,types in self.mapping.query_groups(requested):
            try:
                data = self.client.get('/v5/place/around',dict(location=origin.amap_value(),types=types,radius=radius_m,
                    sortrule='distance',show_fields='business',page_size=min(25,limit*3*len(members)),page_num=1))
                rows,malformed = self._normalize(data,origin,radius_m)
                if malformed and not rows: raise ProviderResponseError()
                for category in members:
                    output[category] = NearbyCategoryResult(tuple(row for row in rows if category in row.categories),
                        LiveDataStatus.PARTIAL if malformed else LiveDataStatus.AVAILABLE,('malformed_service_poi',) if malformed else ())
            except Exception as exc:
                code = exc.code if isinstance(exc,ExternalProviderError) and exc.code in {'provider_error','provider_response_invalid','provider_unavailable','provider_timeout','provider_quota_exceeded'} else 'provider_response_invalid'
                for category in members:output[category] = NearbyCategoryResult((),LiveDataStatus.UNAVAILABLE,(code,))
        return output

    def _normalize(self,data,origin,radius_m):
        raw_rows = data.get('pois')
        if not isinstance(raw_rows,list):raise ProviderResponseError()
        rows = []; malformed = 0; fetched_at = utc_now()
        text = lambda value:optional_text(value,self.client)
        for raw in raw_rows:
            try:
                if not isinstance(raw,dict):raise ProviderResponseError()
                pid = text(raw.get('id')); name = text(raw.get('name')); location = optional_location(raw.get('location'))
                if not pid or not re.fullmatch(r'[A-Za-z0-9]{5,32}',pid) or not name or location is None:raise ProviderResponseError()
                business = raw.get('business') or {}
                if not isinstance(business,dict):raise ProviderResponseError()
                provider_type = text(raw.get('type')); typecode = text(raw.get('typecode'))
                structured = text(business.get('tag') or business.get('keytag') or business.get('rectag') or raw.get('category'))
                categories,classification_source = self.mapping.classify_with_source(typecode,provider_type,structured_category=structured,name=name)
                if not categories:continue
                geometric_distance = haversine_km((origin.lat,origin.lng),(location.lat,location.lng))*1000
                distance = optional_number(raw.get('distance')); distance_type = DistanceType.PROVIDER
                if distance is None:distance = geometric_distance;distance_type = DistanceType.HAVERSINE
                if distance > radius_m or geometric_distance > radius_m:continue
                fields = dict(address=text(raw.get('address')),tel=text(business.get('tel',raw.get('tel'))),
                    rating=optional_number(business.get('rating'),5),cost=optional_number(business.get('cost')),
                    opentime_today=text(business.get('opentime_today',raw.get('opentime_today'))),
                    opentime_week=text(business.get('opentime_week',raw.get('opentime_week'))))
                status = LiveDataStatus.AVAILABLE if all(v is not None for v in fields.values()) else LiveDataStatus.PARTIAL
                rows.append(ServicePoi(self.provider,pid,name,categories[0],categories,provider_type,location,
                    distance,distance_type,fetched_at,provider_typecode=typecode,data_status=status,
                    classification_source=classification_source,**fields))
            except (ProviderResponseError,ValueError,TypeError):malformed += 1
        return rows,malformed
