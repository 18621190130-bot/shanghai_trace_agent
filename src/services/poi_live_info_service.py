from dataclasses import replace
from datetime import datetime
from ..world_models import PoiLiveInfo, MappingStatus, LiveDataStatus, SHANGHAI, OpenStatus, LiveInfoApplicability
from ..providers.base import ExternalProviderError, ProviderUnavailableError, ProviderResponseError
from .opening_hours import resolve_open_status, shanghai_time
from .ttl_cache import TTLCache


class PoiLiveInfoService:
    def __init__(self, provider, mappings, *, repository=None, ttl_s=1800, cache=None, clock=None):
        self.provider,self.mappings,self.repository = provider,mappings,repository
        self.cache = cache if cache is not None else TTLCache(ttl_s)
        self.clock = clock if clock is not None else lambda:datetime.now(SHANGHAI)

    def get_poi_live_info(self, core_poi_id, *, current_local_time=None):
        if not isinstance(core_poi_id,str) or not core_poi_id.strip():raise ValueError('Core POI ID is required')
        now = shanghai_time(current_local_time if current_local_time is not None else self.clock())
        mapping = self.mappings.get(core_poi_id)
        if self.repository is not None and self.repository.get_poi_by_id(core_poi_id) is None:
            return PoiLiveInfo(core_poi_id=core_poi_id,error_code='unknown_core_poi')
        if not mapping:return PoiLiveInfo(core_poi_id=core_poi_id,error_code='mapping_missing')
        status = mapping['identity_mapping_status'];provider_id = mapping.get('amap_poi_id')
        applicability = mapping['live_info_applicability']
        fallback_open = OpenStatus.NOT_APPLICABLE if applicability == LiveInfoApplicability.NOT_APPLICABLE else OpenStatus.UNKNOWN
        context = dict(core_poi_id=core_poi_id,mapping_status=status,identity_mapping_status=status,
                       live_info_applicability=applicability)
        if status != MappingStatus.MATCHED:
            return PoiLiveInfo(**context,open_status=fallback_open,error_code='mapping_'+status.lower())
        try:
            key = ('amap',provider_id)
            result = self.cache.get(key);hit = result is not None
            if result is None:
                if self.provider is None:raise ProviderUnavailableError()
                result = self.provider.get_poi_detail(provider_id)
                if not isinstance(result,PoiLiveInfo) or result.provider_id != provider_id or result.live_data_status == LiveDataStatus.UNAVAILABLE:
                    raise ProviderResponseError()
                self.cache.set(key,result)
            # Cache data, not OPEN: evaluate the time again on every query.
            # 'Today' hours cannot be reused across a Shanghai calendar-date boundary.
            fetched = datetime.fromisoformat(result.fetched_at) if result.fetched_at else None
            if fetched is not None and (fetched.tzinfo is None or fetched.utcoffset() is None):raise ProviderResponseError()
            fetched = fetched.astimezone(SHANGHAI) if fetched else None
            hours = result.opentime_today if fetched is not None and fetched.date() == now.date() else None
            return replace(result,**context,cache_hit=hit,
                           open_status=fallback_open if applicability == LiveInfoApplicability.NOT_APPLICABLE else resolve_open_status(hours,now),status_evaluated_at=now.isoformat())
        except Exception as exc:
            return PoiLiveInfo(**context,provider_id=provider_id,open_status=fallback_open,
                               error_code=exc.code if isinstance(exc,ExternalProviderError) else 'provider_response_invalid')
