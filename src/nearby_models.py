"""Ephemeral observations. Never share the Core stable-ID namespace."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
import math
import re
from .walking_models import Location
from .world_models import LiveDataStatus, OpenStatus


class NearbyServiceCategory(StrEnum):
    CAFE = 'CAFE'
    TEA_DRINK = 'TEA_DRINK'
    DESSERT_ICE_CREAM = 'DESSERT_ICE_CREAM'
    RESTAURANT = 'RESTAURANT'
    CONVENIENCE_STORE = 'CONVENIENCE_STORE'
    RESTROOM = 'RESTROOM'
    MALL = 'MALL'


# Compatibility names; category primary priority is stable independently of query order.
ServicePoiCategory = NearbyServiceCategory
DEFAULT_CATEGORIES = (ServicePoiCategory.RESTAURANT, ServicePoiCategory.CAFE, ServicePoiCategory.TEA_DRINK,
                      ServicePoiCategory.DESSERT_ICE_CREAM, ServicePoiCategory.CONVENIENCE_STORE,
                      ServicePoiCategory.RESTROOM, ServicePoiCategory.MALL)
DISPLAY_GROUPS = {'FOOD_AND_DRINK': DEFAULT_CATEGORIES[:4], 'ESSENTIALS': DEFAULT_CATEGORIES[4:6],
                  'REST_AND_SHELTER': (ServicePoiCategory.MALL,)}


class NearbySearchOrigin(StrEnum):
    CURRENT_LOCATION = 'CURRENT_LOCATION'
    CORE_POI = 'CORE_POI'


class DistanceType(StrEnum):
    PROVIDER = 'PROVIDER'
    HAVERSINE = 'HAVERSINE'


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Timezone-aware fetched_at required') from None


@dataclass(frozen=True)
class ServicePoi:
    provider: str
    provider_poi_id: str
    name: str
    primary_category: str
    categories: tuple[str, ...]
    provider_type: str | None
    location: Location
    distance_m: float
    distance_type: str
    fetched_at: str
    provider_typecode: str | None = None
    address: str | None = None
    tel: str | None = None
    rating: float | None = None
    cost: float | None = None
    opentime_today: str | None = None
    opentime_week: str | None = None
    open_status: str = OpenStatus.UNKNOWN
    data_status: str = LiveDataStatus.PARTIAL
    status_evaluated_at: str | None = None
    classification_source: str = 'PROVIDER_TYPECODE'

    def __post_init__(self):
        if not isinstance(self.provider, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', self.provider): raise ValueError('Invalid service provider')
        if not isinstance(self.provider_poi_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{5,64}', self.provider_poi_id): raise ValueError('Invalid service ID')
        if not isinstance(self.name, str) or not self.name.strip(): raise ValueError('Service name required')
        if not isinstance(self.location, Location) or self.location.coordinate_system != 'GCJ02': raise ValueError('Service location must be GCJ02')
        if not isinstance(self.categories, tuple) or not self.categories or len(set(self.categories)) != len(self.categories): raise ValueError('Invalid service categories')
        for category in self.categories: ServicePoiCategory(category)
        if self.primary_category not in self.categories: raise ValueError('Primary category must belong to categories')
        if self.classification_source not in ('PROVIDER_TYPECODE','PROVIDER_TYPE','STRUCTURED_CATEGORY','NAME_FALLBACK'): raise ValueError('Invalid classification source')
        DistanceType(self.distance_type); OpenStatus(self.open_status); LiveDataStatus(self.data_status)
        for field, maximum in (('distance_m', None), ('rating', 5), ('cost', None)):
            value = getattr(self, field)
            if value is None:
                if field == 'distance_m': raise ValueError('Service distance required')
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or maximum is not None and value > maximum: raise ValueError('Invalid service numeric field')
        for field in ('provider_type','provider_typecode','address','tel','opentime_today','opentime_week'):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip()): raise ValueError('Invalid service text field')
        timestamp(self.fetched_at)
        if self.status_evaluated_at is not None: timestamp(self.status_evaluated_at)

    @property
    def service_poi_id(self): return f'{self.provider}:{self.provider_poi_id}'

    @property
    def category(self): return self.primary_category

    @property
    def coordinate_system(self): return self.location.coordinate_system

    def to_dict(self):
        return dict(asdict(self), service_poi_id=self.service_poi_id, category=self.category, coordinate_system=self.coordinate_system)


@dataclass(frozen=True)
class NearbyCategoryResult:
    results: tuple[ServicePoi, ...] = ()
    status: str = LiveDataStatus.AVAILABLE
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class NearbySearchResult:
    origin: Location | None
    origin_source: str
    radius_m: int
    requested_categories: tuple[str, ...]
    results: tuple[ServicePoi, ...]
    status: str
    provider: str
    fetched_at: str
    errors: tuple[dict, ...] = ()
    core_poi_id: str | None = None
    limit_per_category: int = 5
    cache_hit_categories: tuple[str, ...] = ()
    category_statuses: tuple[dict, ...] = ()
    category_result_ids: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self):
        result = asdict(self)
        result['results'] = [row.to_dict() for row in self.results]
        result['category_counts'] = {category: len(self.category_result_ids.get(category, ())) for category in self.requested_categories}
        result['display_groups'] = dict(DISPLAY_GROUPS)
        return result


NearbyServicePoi = ServicePoi
