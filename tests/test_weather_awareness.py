"""Deterministic weather contracts; no real network or today's weather assertions."""
import copy
from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock
from src import POIRepository, Location
from src.providers.amap.weather import AmapWeatherProvider
from src.providers.base import ProviderResponseError, ProviderTimeoutError
from src.weather_models import CurrentWeather, WeatherForecast, WeatherForecastDay, SHANGHAI, local_time
from src.world_models import ResolvedLocation
from src.services.location_service import LocationService
from src.services.weather_service import WeatherService
from src.services.weather_risk import WeatherRiskClassifier
from src.services.ttl_cache import TTLCache
from src.services.world_context_service import WorldContextService

POINT = Location(31.167682, 121.463841, 'GCJ02')


def raw_current():
    return dict(province='上海市', city='徐汇区', adcode='310104', weather='晴', temperature='23',
                humidity='60', winddirection='东', windpower='3', reporttime='2026-10-06 12:00:00')


def client_for(data):
    client = Mock()
    client.get.return_value = data
    client.redact_text.side_effect = lambda text: text.replace('SECRET', '[REDACTED]')
    return client


def resolved(point=POINT, **kw):
    return ResolvedLocation(point, province='上海市', city='上海市', district='徐汇区', adcode='310104',
                            live_data_status='AVAILABLE', **kw)


class WeatherProviderTests(unittest.TestCase):
    def test_complete_current(self):
        client = client_for({'lives': [raw_current()]})
        value = AmapWeatherProvider(client).get_current_weather('310104')
        self.assertEqual(value.data_status, 'AVAILABLE')
        self.assertEqual(value.temperature_c, 23)
        self.assertEqual(value.humidity_pct, 60)
        self.assertIsNone(value.district)  # Native provider does not supply district.
        self.assertEqual(value.report_time, '2026-10-06T12:00:00+08:00')
        self.assertIsNotNone(datetime.fromisoformat(value.fetched_at).tzinfo)
        client.get.assert_called_once_with('/v3/weather/weatherInfo', {'city':'310104','extensions':'base'})

    def test_missing_fields_are_null(self):
        value = AmapWeatherProvider(client_for({'lives':[{'weather':'晴'}]})).get_current_weather('310104')
        self.assertEqual(value.data_status, 'PARTIAL')
        for key in ('province','city','district','adcode','temperature_c','humidity_pct','wind_power','report_time'):
            self.assertIsNone(value.to_dict()[key])

    def test_negative_temperature_and_float_fields(self):
        raw = dict(raw_current(), temperature_float='-2.7', humidity_float='65.5')
        value = AmapWeatherProvider(client_for({'lives':[raw]})).get_current_weather('310104')
        self.assertEqual(value.temperature_c, -2.7)
        self.assertEqual(value.humidity_pct, 65.5)

    def test_invalid_numbers_are_null(self):
        for v in ('NaN', 'Infinity', [], True, '999', None):
            with self.subTest(v=v):
                value = AmapWeatherProvider(client_for({'lives':[dict(raw_current(),temperature=v,humidity=v)]})).get_current_weather('310104')
                self.assertIsNone(value.temperature_c)
                self.assertIsNone(value.humidity_pct)

    def test_invalid_timestamp_and_code(self):
        value = AmapWeatherProvider(client_for({'lives':[dict(raw_current(),reporttime='unknown',adcode='bad')]})).get_current_weather('310104')
        self.assertIsNone(value.report_time)
        self.assertIsNone(value.adcode)

    def test_invalid_envelopes(self):
        for payload in ({}, {'lives':[]}, {'lives':{}}, {'lives':[None]}, {'lives':[{}]}, {'lives':[raw_current(),raw_current()]}):
            with self.subTest(payload=payload), self.assertRaises(ProviderResponseError):
                AmapWeatherProvider(client_for(payload)).get_current_weather('310104')

    def test_invalid_request_adcode(self):
        for v in ('Shanghai','310104&key=SECRET',310104,None):
            with self.subTest(v=v), self.assertRaises(ProviderResponseError):
                AmapWeatherProvider(client_for({})).get_current_weather(v)

    def test_forecast_daily_schema(self):
        day = dict(date='2026-10-07',dayweather='小雨',nightweather='晴',daytemp='25',nighttemp='18',
                   daywind='东',nightwind='西',daypower='3',nightpower='4')
        client = client_for({'forecasts':[dict(raw_current(),casts=[day])]})
        value = AmapWeatherProvider(client).get_weather_forecast('310104')
        self.assertEqual(value.precision, 'DAILY')
        self.assertEqual(value.data_status, 'AVAILABLE')
        self.assertEqual(value.days[0].night_temperature_c, 18)
        client.get.assert_called_once_with('/v3/weather/weatherInfo', {'city':'310104','extensions':'all'})

    def test_forecast_missing_fields(self):
        value = AmapWeatherProvider(client_for({'forecasts':[{'casts':[{'date':'invalid'}]}]})).get_weather_forecast('310104')
        self.assertEqual(value.data_status, 'PARTIAL')
        self.assertTrue(all(v is None for v in value.days[0].to_dict().values()))

    def test_forecast_invalid_casts(self):
        for casts in ({}, [None]):
            with self.subTest(casts=casts), self.assertRaises(ProviderResponseError):
                AmapWeatherProvider(client_for({'forecasts':[{'casts':casts}]})).get_weather_forecast('310104')

    def test_redaction(self):
        value = AmapWeatherProvider(client_for({'lives':[dict(raw_current(),weather='SECRET')]})).get_current_weather('310104')
        self.assertEqual(value.weather_text, '[REDACTED]')


class WeatherServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo = POIRepository()
        self.geo = Mock()
        self.geo.reverse_geocode.side_effect = lambda point: resolved(point)
        self.normalize = Mock(return_value=POINT)
        self.locations = LocationService(self.geo, self.normalize)
        self.provider = Mock()
        self.provider.get_current_weather.return_value = CurrentWeather(adcode='310104',weather_text='晴',data_status='AVAILABLE')
        self.provider.get_weather_forecast.return_value = WeatherForecast(adcode='310104',data_status='AVAILABLE')
        self.service = WeatherService(self.provider,self.repo,self.locations)

    def test_gps_normalize_regeo_adcode_priority(self):
        gps = Location(31.16,121.46,'WGS84')
        result = self.service.get_current_weather(gps,current_core_poi_id='p35')
        self.normalize.assert_called_once_with(gps)
        self.geo.reverse_geocode.assert_called_once_with(POINT)
        self.provider.get_current_weather.assert_called_once_with('310104')
        self.assertEqual(result.origin_source,'CURRENT_LOCATION')
        self.assertEqual(result.resolved_location['district'],'徐汇区')
        self.assertIsNone(result.district)

    def test_core_point_area_linear_effective_coordinates(self):
        for pid in ('p28','p35','p34'):
            with self.subTest(pid=pid):
                result = self.service.get_current_weather(current_core_poi_id=pid)
                actual = self.geo.reverse_geocode.call_args.args[0]
                self.assertEqual((actual.lat,actual.lng),self.repo.get_poi_by_id(pid).coordinates)
                self.assertEqual(result.origin_source,'CURRENT_CORE')
                self.assertEqual(result.origin_core_poi_id,pid)

    def test_next_unvisited_and_skipped(self):
        trip = dict(visited_poi_ids=['p28'],skipped_poi_ids=['p34'])
        version = dict(route_snapshot=dict(ordered_pois=[dict(poi_id=pid) for pid in ['p28','p34','p35']]))
        result = self.service.get_current_weather(trip_state=trip,route_version=version)
        self.assertEqual(result.origin_core_poi_id,'p35')
        self.assertEqual(result.origin_source,'NEXT_UNVISITED_CORE')

    def test_trip_current_before_next(self):
        result = self.service.get_current_weather(trip_state=dict(current_poi_id='p28',active_route=dict(ordered_pois=[dict(poi_id='p35')])))
        self.assertEqual(result.origin_core_poi_id,'p28')

    def test_cache_types_separate_and_context_refreshed(self):
        self.service.get_current_weather(POINT)
        result = self.service.get_current_weather(current_core_poi_id='p35')
        self.assertTrue(result.cache_hit)
        self.assertEqual(result.origin_core_poi_id,'p35')
        self.service.get_weather_forecast(POINT)
        self.assertTrue(self.service.get_weather_forecast(POINT).cache_hit)
        self.assertEqual(self.provider.get_current_weather.call_count,1)
        self.assertEqual(self.provider.get_weather_forecast.call_count,1)

    def test_ttl_expiry(self):
        clock = [0]
        service = WeatherService(self.provider,self.repo,self.locations,current_cache=TTLCache(600,clock=lambda:clock[0]),
                                 forecast_cache=TTLCache(1800,clock=lambda:clock[0]))
        service.get_current_weather(POINT); service.get_weather_forecast(POINT)
        clock[0] = 600
        self.assertFalse(service.get_current_weather(POINT).cache_hit)
        self.assertTrue(service.get_weather_forecast(POINT).cache_hit)
        clock[0] = 1800
        self.assertFalse(service.get_weather_forecast(POINT).cache_hit)

    def test_provider_failure_not_cached_and_recovery(self):
        self.provider.get_current_weather.side_effect=[ProviderTimeoutError(),self.provider.get_current_weather.return_value]
        result = self.service.get_current_weather(POINT)
        self.assertEqual(result.data_status,'UNAVAILABLE')
        self.assertEqual(result.error_code,'provider_timeout')
        self.assertFalse(self.service.get_current_weather(POINT).cache_hit)

    def test_forecast_failure_not_cached(self):
        self.provider.get_weather_forecast.side_effect=ProviderTimeoutError()
        for _ in range(2):self.assertEqual(self.service.get_weather_forecast(POINT).data_status,'UNAVAILABLE')
        self.assertEqual(self.provider.get_weather_forecast.call_count,2)

    def test_regeo_failure_prevents_weather(self):
        self.geo.reverse_geocode.side_effect=ProviderTimeoutError()
        result = self.service.get_current_weather(POINT)
        self.assertEqual(result.error_code,'provider_timeout')
        self.provider.get_current_weather.assert_not_called()

    def test_missing_or_invalid_origin(self):
        for args in ({}, {'current_core_poi_id':'bad'}, {'current_location':{'lat':31}}):
            with self.subTest(args=args):self.assertEqual(self.service.get_current_weather(**args).data_status,'UNAVAILABLE')

    def test_bad_dto(self):
        self.provider.get_current_weather.return_value={}
        self.assertEqual(self.service.get_current_weather(POINT).error_code,'provider_response_invalid')

    def test_defensive_cache_and_inputs(self):
        trip=dict(current_poi_id='p35');before=copy.deepcopy(trip)
        result=self.service.get_current_weather(trip_state=trip)
        result.resolved_location['district']='mutated'
        self.assertEqual(self.service.get_current_weather(trip_state=trip).resolved_location['district'],'徐汇区')
        self.assertEqual(trip,before)

    def test_cache_adcodes_separate(self):
        self.geo.reverse_geocode.side_effect=lambda point:replace(resolved(point),adcode='310104' if point==POINT else '310101')
        self.service.get_current_weather(POINT)
        self.service.get_current_weather(Location(31.2,121.5,'GCJ02'))
        self.assertEqual([c.args[0] for c in self.provider.get_current_weather.call_args_list],['310104','310101'])

    def test_provider_namespace_separates_shared_cache(self):
        cache=TTLCache(600)
        self.provider.provider='amap'
        other=Mock();other.provider='other';other.get_current_weather.return_value=CurrentWeather(provider='other',data_status='AVAILABLE')
        first=WeatherService(self.provider,self.repo,self.locations,current_cache=cache)
        second=WeatherService(other,self.repo,self.locations,current_cache=cache)
        first.get_current_weather(POINT)
        self.assertEqual(second.get_current_weather(POINT).provider,'other')
        other.get_current_weather.assert_called_once()

    def test_missing_adcode_regeo_blocks_weather(self):
        self.geo.reverse_geocode.side_effect=lambda point:replace(resolved(point),adcode=None,live_data_status='PARTIAL')
        self.assertEqual(self.service.get_current_weather(POINT).error_code,'provider_response_invalid')
        self.provider.get_current_weather.assert_not_called()

    def test_converter_failure_isolated(self):
        self.normalize.side_effect=ProviderTimeoutError()
        result=self.service.get_current_weather(Location(31.16,121.46,'WGS84'))
        self.assertEqual(result.error_code,'provider_timeout')
        self.geo.reverse_geocode.assert_not_called()
        self.provider.get_current_weather.assert_not_called()

    def test_facade_shared_client(self):
        client=client_for({})
        world=WorldContextService.from_environment(repository=self.repo,client=client)
        self.assertIs(world.weather.provider.client,client)
        self.assertIs(world.locations.provider.client,client)
        self.assertIs(world.poi_info.provider.client,client)
        self.assertIs(world.reality.weather,world.weather)


class WeatherRiskTests(unittest.TestCase):
    def test_text_rules(self):
        expected={'晴':[],'多云':[],'小雨':['RAIN'],'暴雨':['HEAVY_RAIN'],'大雨':['HEAVY_RAIN'],
                  '雷阵雨':['THUNDERSTORM'],'雨夹雪':['RAIN','SNOW'],'小雪':['SNOW']}
        for text,codes in expected.items():
            with self.subTest(text=text):self.assertEqual(WeatherRiskClassifier().classify(CurrentWeather(weather_text=text,data_status='AVAILABLE')),codes)

    def test_temperature_boundaries(self):
        for temperature,codes in ((34.9,[]),(35,['EXTREME_HEAT']),(0,['EXTREME_COLD']),(-3,['EXTREME_COLD']),(0.1,[]),(None,[])):
            with self.subTest(temperature=temperature):self.assertEqual(WeatherRiskClassifier().classify(CurrentWeather(temperature_c=temperature,data_status='AVAILABLE')),codes)

    def test_wind_conservative(self):
        for value,codes in (('6',['STRONG_WIND']),('6-7级',['STRONG_WIND']),('5-6',[]),('≤3',[]),('微风',[]),('18',[]),('7-6',[]),(None,[])):
            with self.subTest(value=value):self.assertEqual(WeatherRiskClassifier().classify(CurrentWeather(wind_power=value,data_status='AVAILABLE')),codes)

    def test_forecast_rules_daily_only(self):
        forecast=WeatherForecast(days=(WeatherForecastDay(day_weather='雷阵雨',night_temperature_c=-1),),data_status='AVAILABLE')
        self.assertEqual(WeatherRiskClassifier().classify(forecast),['EXTREME_COLD','THUNDERSTORM'])

    def test_unavailable_no_risk(self):
        self.assertEqual(WeatherRiskClassifier().classify(CurrentWeather(weather_text='暴雨')),[])
        self.assertEqual(WeatherRiskClassifier().classify(WeatherForecast(days=(WeatherForecastDay(day_weather='暴雨'),))),[])

    def test_shanghai_time_awareness(self):
        utc=datetime(2026,10,5,18,tzinfo=timezone.utc)
        self.assertEqual(local_time(utc).date().isoformat(),'2026-10-06')
        self.assertEqual(local_time(utc).tzinfo.key,'Asia/Shanghai')
        with self.assertRaises(ValueError):local_time(datetime(2026,10,6))
