from typing import Protocol
from ..nearby_models import NearbyCategoryResult, ServicePoiCategory
from ..walking_models import Location


class NearbyPoiProvider(Protocol):
    provider: str
    def search_nearby(self, origin: Location, category: ServicePoiCategory, *, radius_m: int, limit: int) -> NearbyCategoryResult: ...


class BatchNearbyPoiProvider(NearbyPoiProvider, Protocol):
    def search_nearby_categories(self, origin: Location, categories: tuple[ServicePoiCategory, ...], *, radius_m: int, limit: int) -> dict[str, NearbyCategoryResult]: ...
