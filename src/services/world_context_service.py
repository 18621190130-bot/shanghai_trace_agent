"""Read-only tool facade. Deliberately has no TripStore or command mutations."""
from ..poi_mapping import PoiMappingRepository
from ..poi_repository import POIRepository
from .location_service import LocationService
from .poi_live_info_service import PoiLiveInfoService
from .proximity_service import ProximityService
from .nearby_service import NearbyService
from .weather_service import WeatherService
from .route_reality_check_service import RouteRealityCheckService


class WorldContextService:
    def __init__(self, repository, locations, poi_info, proximity=None, *, nearby=None, weather=None, reality=None):
        self.repository,self.locations,self.poi_info = repository,locations,poi_info
        self.proximity = proximity if proximity is not None else ProximityService(locations)
        self.nearby = nearby if nearby is not None else NearbyService(None,repository,locations)
        self.weather = weather if weather is not None else WeatherService(None,repository,locations)
        self.reality = reality if reality is not None else RouteRealityCheckService(self.weather,poi_info,repository=repository)

    @classmethod
    def from_environment(cls, *, repository=None, mappings=None, client=None, proximity_config=None):
        from ..providers.amap import AmapClient,AmapWalkingProvider
        from ..providers.amap.world import AmapGeocodingProvider,AmapPoiProvider
        from ..providers.amap.nearby import AmapNearbyPoiProvider
        from ..providers.amap.weather import AmapWeatherProvider
        repository = repository if repository is not None else POIRepository()
        client = client if client is not None else AmapClient()
        locations = LocationService(AmapGeocodingProvider(client),AmapWalkingProvider(client).normalize_location_for_amap)
        info = PoiLiveInfoService(AmapPoiProvider(client),mappings if mappings is not None else PoiMappingRepository(),repository=repository)
        nearby = NearbyService(AmapNearbyPoiProvider(client),repository,locations)
        weather = WeatherService(AmapWeatherProvider(client),repository,locations)
        return cls(repository,locations,info,ProximityService(locations,proximity_config),nearby=nearby,weather=weather)

    def get_current_weather(self,*args,**kwargs):return self.weather.get_current_weather(*args,**kwargs)

    def get_weather_forecast(self,*args,**kwargs):return self.weather.get_weather_forecast(*args,**kwargs)

    def check_route_reality(self,*args,**kwargs):return self.reality.check_route_reality(*args,**kwargs)

    def reverse_geocode(self,location):return self.locations.reverse_geocode(location)

    def get_poi_live_info(self,core_poi_id,**kwargs):return self.poi_info.get_poi_live_info(core_poi_id,**kwargs)

    def search_nearby_services(self,location=None,core_poi_id=None,categories=None,radius_m=800,limit_per_category=5,*,current_location=None):
        return self.nearby.search_nearby_services(location,core_poi_id,categories,radius_m,limit_per_category,current_location=current_location)

    def search_nearby_rest_stops(self,*args,**kwargs):
        return self.search_nearby_services(*args,**kwargs)

    def check_arrival(self,current_location,target_poi_id):
        poi = self.repository.get_poi_by_id(target_poi_id)
        if poi is None:raise ValueError('Unknown target Core POI')
        return self.proximity.check_arrival(current_location,poi)
