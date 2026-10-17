from typing import Protocol
from ..walking_models import Location
from ..world_models import ResolvedLocation, PoiLiveInfo, PoiCandidate


class GeocodingProvider(Protocol):
    def reverse_geocode(self, location: Location) -> ResolvedLocation: ...


class PoiProvider(Protocol):
    def get_poi_detail(self, provider_id: str) -> PoiLiveInfo: ...


class PoiMappingSearchProvider(Protocol):
    def search_mapping_candidates(self, name: str) -> list[PoiCandidate]: ...
    def search_identity_near_coordinate(self, name: str, location: Location,
                                        *, types: str = '', radius: int = 1000) -> list[PoiCandidate]: ...

