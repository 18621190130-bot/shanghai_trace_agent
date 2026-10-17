"""Phase 3B_2 contracts: synthetic provider responses, no real network."""
import copy
from dataclasses import replace
from datetime import datetime,timezone,timedelta
import io
import json
import math
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import Mock,patch

from src import POIRepository,Location
from src.providers.amap import AmapClient,AmapWalkingProvider
from src.providers.amap.world import AmapGeocodingProvider,AmapPoiProvider
from src.providers.base import ProviderResponseError,ProviderTimeoutError
from src.world_models import (ResolvedLocation,PoiLiveInfo,PoiCandidate,LiveDataStatus,SHANGHAI)
from src.poi_mapping import PoiMappingRepository,match_poi
from src.services.ttl_cache import TTLCache
from src.services.location_service import LocationService,current_location
from src.services.proximity_service import ProximityService,ProximityConfig
from src.services.poi_live_info_service import PoiLiveInfoService
from src.services.opening_hours import resolve_open_status
from src.services.world_context_service import WorldContextService
from src.trip_state import TripState
from tools.demos.trip_demo import load_fixture
from scripts.match_amap_poi_ids import audit

POINT = Location(31.167682,121.463841,'GCJ02')
AT = datetime(2026,10,5,12,tzinfo=SHANGHAI)
ID = 'B0TEST12345'


def geodata():
    return dict(status='1',regeocode=dict(formatted_address='上海市徐汇区龙腾大道',addressComponent=dict(
        province='上海市',city=[],district='徐汇区',township='龙华街道',adcode='310104',
        streetNumber=dict(street='龙腾大道',number='2600号'))))


def poidata():
    return dict(status='1',pois=[dict(id=ID,name='西岸美术馆',location='121.463841,31.167682',address='龙腾大道2600号',
        type='科教文化服务;美术馆',business=dict(tel='021-00000000',opentime_today='10:00-18:00',
        opentime_week='周一至周日 10:00-18:00',rating='4.5',cost='50',tag='艺术;文化'))])


def client_for(data):
    network = Mock(side_effect=lambda *a,**k:io.BytesIO(json.dumps(data).encode()))
    with patch.dict(os.environ,AMAP_WEB_SERVICE_KEY='unit-placeholder'):
        client = AmapClient(opener=network,min_interval_s=0)
    return client,network


def maps(status='MATCHED',pid=ID):
    return PoiMappingRepository(records={'p28':dict(identity_mapping_status=status,live_info_applicability='FULL',entity_type='museum',aliases=[],reviewed=False,match_method='AUTO_HIGH_CONFIDENCE' if status=='MATCHED' else None,matched_name='Museum' if status=='MATCHED' else None,notes='',amap_poi_id=pid if status=='MATCHED' else None,confidence=.99)})


def fixed_info(**changes):
    return PoiLiveInfo(provider_id=ID,name='West Bund',opentime_today='10:00-18:00',
                       opentime_week='Week schedule',live_data_status='PARTIAL',fetched_at='2026-10-05T02:00:00+00:00',**changes)


class GeocodingTests(unittest.TestCase):
    def test_normalization_all_fields_and_municipality(self):
        client,network = client_for(geodata())
        result = AmapGeocodingProvider(client).reverse_geocode(POINT)
        self.assertEqual((result.city,result.district,result.adcode),('上海市','徐汇区','310104'))
        self.assertEqual((result.street,result.street_number),('龙腾大道','2600号'))
        self.assertEqual(result.live_data_status,'AVAILABLE')
        self.assertEqual(result.location,POINT)
        self.assertIn('extensions=base',network.call_args.args[0].full_url)

    def test_optional_fields_missing_not_fabricated(self):
        client,_ = client_for(dict(status='1',regeocode=dict(formatted_address='上海')))
        result = AmapGeocodingProvider(client).reverse_geocode(POINT)
        self.assertIsNone(result.city);self.assertIsNone(result.adcode)
        self.assertEqual(result.live_data_status,'PARTIAL')

    def test_missing_and_malformed_results(self):
        for raw in (None,[],{},dict(addressComponent='bad'),dict(addressComponent=dict(streetNumber='bad'))):
            with self.subTest(raw=raw),self.assertRaises(ProviderResponseError):
                AmapGeocodingProvider(client_for(dict(status='1',regeocode=raw))[0]).reverse_geocode(POINT)

    def test_gcj_cache_rounding_and_original_time(self):
        client,network = client_for(geodata())
        service = LocationService(AmapGeocodingProvider(client),AmapWalkingProvider(client).normalize_location_for_amap)
        first = service.reverse_geocode(POINT)
        second = service.reverse_geocode(Location(POINT.lat+.00000001,POINT.lng,'GCJ02'))
        self.assertEqual(network.call_count,1);self.assertTrue(second.cache_hit)
        self.assertEqual(first.fetched_at,second.fetched_at)

    def test_wgs_conversion_then_regeo_reuses_frozen_converter(self):
        client,network = client_for(geodata())
        network.side_effect = [io.BytesIO(b'{"status":"1","locations":"121.463841,31.167682"}'),
                               io.BytesIO(json.dumps(geodata()).encode())]
        service = LocationService(AmapGeocodingProvider(client),AmapWalkingProvider(client).normalize_location_for_amap)
        gps = dict(lat=31.16,lng=121.46,coordinate_system='WGS84')
        result = service.reverse_geocode(gps);again = service.reverse_geocode(gps)
        self.assertEqual(result.location,POINT);self.assertTrue(again.cache_hit)
        self.assertEqual(network.call_count,2)
        self.assertIn('coordinate/convert',network.call_args_list[0].args[0].full_url)
        self.assertIn('/geocode/regeo',network.call_args_list[1].args[0].full_url)

    def test_failure_returns_safe_unavailable_preserves_input_datum(self):
        client,network = client_for(geodata());network.side_effect = socket.timeout('unit-placeholder')
        service = LocationService(AmapGeocodingProvider(client),AmapWalkingProvider(client).normalize_location_for_amap)
        for point in (POINT,Location(31,121,'WGS84')):
            result = service.reverse_geocode(point)
            self.assertEqual(result.live_data_status,'UNAVAILABLE')
            self.assertEqual(result.location.coordinate_system,point.coordinate_system)
            self.assertEqual(result.error_code,'provider_timeout')
            self.assertNotIn('unit-placeholder',json.dumps(result.to_dict()))

    def test_invalid_location_input(self):
        examples = [dict(lat=91,lng=121,coordinate_system='GCJ02'),dict(lat=31,lng=181,coordinate_system='GCJ02'),
                    dict(lat=float('nan'),lng=121,coordinate_system='GCJ02'),dict(lat=31,lng=float('inf'),coordinate_system='WGS84'),
                    dict(lat=31,lng=121,coordinate_system='other'),dict(lat=31,lng=121),dict(lat=True,lng=121,coordinate_system='GCJ02')]
        for value in examples:
            with self.subTest(value=value),self.assertRaises(ValueError):current_location(value)

    def test_service_reverse_cache_expires_and_failure_is_not_cached(self):
        now=[0];client,network=client_for(geodata())
        service=LocationService(AmapGeocodingProvider(client),None,cache=TTLCache(10,clock=lambda:now[0]))
        service.reverse_geocode(POINT);now[0]=10
        network.side_effect=socket.timeout()
        self.assertEqual(service.reverse_geocode(POINT).live_data_status,'UNAVAILABLE')
        network.side_effect=lambda *a,**k:io.BytesIO(json.dumps(geodata()).encode())
        self.assertEqual(service.reverse_geocode(POINT).live_data_status,'AVAILABLE')
        self.assertEqual(network.call_count,3)


class PoiProviderTests(unittest.TestCase):
    def test_detail_normalized_fields(self):
        client,network = client_for(poidata())
        result = AmapPoiProvider(client).get_poi_detail(ID)
        self.assertEqual(result.provider_id,ID);self.assertEqual(result.rating,4.5);self.assertEqual(result.cost,50)
        self.assertEqual(result.tags,('艺术','文化'));self.assertEqual(result.location,POINT)
        self.assertEqual(result.live_data_status,'AVAILABLE')
        self.assertEqual(result.opentime_today,'10:00-18:00');self.assertEqual(result.open_status,'UNKNOWN')
        self.assertIn('/v5/place/detail?',network.call_args.args[0].full_url)

    def test_missing_optional_fields_and_invalid_numbers(self):
        data = poidata();data['pois'][0].pop('business');data['pois'][0].pop('location')
        result = AmapPoiProvider(client_for(data)[0]).get_poi_detail(ID)
        for field in ('location','tel','opentime_today','rating','cost','tags'):
            self.assertIsNone(getattr(result,field))
        for rating,cost in (('nan','inf'),('-1','-1'),('7',{}),(True,False)):
            data = poidata();data['pois'][0]['business'].update(rating=rating,cost=cost)
            result = AmapPoiProvider(client_for(data)[0]).get_poi_detail(ID)
            self.assertIsNone(result.rating);self.assertIsNone(result.cost)

    def test_missing_wrong_id_and_invalid_id_fail_safely(self):
        for data in (dict(status='1'),dict(status='1',pois=[]),dict(status='1',pois=[dict(id='OTHER')]),dict(status='1',pois='bad')):
            with self.subTest(data=data),self.assertRaises(ProviderResponseError):AmapPoiProvider(client_for(data)[0]).get_poi_detail(ID)
        provider = AmapPoiProvider(client_for(poidata())[0])
        for pid in ('',None,'bad?id=',123):
            with self.subTest(pid=pid),self.assertRaises(ProviderResponseError):provider.get_poi_detail(pid)

    def test_redaction_and_provider_tags_remain_external(self):
        data = poidata();data['pois'][0]['business']['opentime_week'] = 'unit-placeholder'
        result = AmapPoiProvider(client_for(data)[0]).get_poi_detail(ID)
        self.assertNotIn('unit-placeholder',json.dumps(result.to_dict()))

    def test_search_candidates_normalized_and_bad_rows_skipped(self):
        data = poidata();data['pois'] += [None,dict(id='BAD01',name='bad',location='nan,31')]
        client,network = client_for(data)
        result = AmapPoiProvider(client).search_mapping_candidates('西岸美术馆')
        self.assertEqual(len(result),1);self.assertEqual(result[0].provider_id,ID)
        self.assertIn('/v5/place/text?',network.call_args.args[0].full_url)


class OpeningTests(unittest.TestCase):
    def test_standard_hours_boundaries(self):
        for hour,minute,status in ((9,59,'CLOSED'),(10,0,'OPEN'),(12,0,'OPEN'),(18,0,'CLOSED'),(19,0,'CLOSED')):
            self.assertEqual(resolve_open_status('10:00-18:00',AT.replace(hour=hour,minute=minute)),status)

    def test_cross_midnight_boundaries(self):
        for hour,status in ((18,'OPEN'),(23,'OPEN'),(0,'OPEN'),(1,'OPEN'),(2,'CLOSED'),(12,'CLOSED')):
            self.assertEqual(resolve_open_status('18:00-02:00',AT.replace(hour=hour)),status)

    def test_multiple_intervals_and_explicit_all_day(self):
        self.assertEqual(resolve_open_status('10:00–12:00;14:00至18:00',AT),'CLOSED')
        self.assertEqual(resolve_open_status('10:00–12:00;14:00至18:00',AT.replace(hour=15)),'OPEN')
        self.assertEqual(resolve_open_status('00:00-24:00',AT),'OPEN')

    def test_unknown_not_guessed(self):
        for value in (None,'','全天','节假日调整','以现场公告为准','部分区域开放','周一闭馆','10:00-18:00（节假日调整）',
                      '25:00-26:00','10:60-18:00','00:00-00:00','10:00-24:01','10:00-18:00;notice'):
            with self.subTest(value=value):self.assertEqual(resolve_open_status(value,AT),'UNKNOWN')

    def test_timezone_explicit_utc_converted(self):
        self.assertEqual(resolve_open_status('10:00-18:00',datetime(2026,10,5,4,tzinfo=timezone.utc)),'OPEN')
        with self.assertRaises(ValueError):resolve_open_status('10:00-18:00',datetime(2026,10,5,12))


class MappingTests(unittest.TestCase):
    def setUp(self):self.poi = POIRepository().get_poi_by_id('p28')

    def candidate(self,name='西岸美术馆',pid=ID,point=POINT,district='徐汇区'):
        return PoiCandidate(pid,name,point,district,'龙腾大道2600号','美术馆')

    def test_high_confidence_match_not_first_result(self):
        row = match_poi(self.poi,[self.candidate('西岸美术馆地下停车场','BAD12345'),self.candidate()],expected_district='徐汇区')
        self.assertEqual(row['identity_mapping_status'],'MATCHED');self.assertEqual(row['amap_poi_id'],ID)
        self.assertFalse(row['reviewed'])

    def test_ambiguity_does_not_assign_id(self):
        row = match_poi(self.poi,[self.candidate(),self.candidate(pid='B0TEST67890')])
        self.assertEqual(row['identity_mapping_status'],'AMBIGUOUS');self.assertIsNone(row['amap_poi_id'])

    def test_far_or_district_mismatch_does_not_bind(self):
        for candidate in (self.candidate(point=Location(31.2,121.5,'GCJ02')),self.candidate(district='浦东新区')):
            row = match_poi(self.poi,[candidate],expected_district='徐汇区')
            self.assertEqual(row['identity_mapping_status'],'NOT_FOUND');self.assertIsNone(row['amap_poi_id'])

    def test_not_found_and_not_applicable(self):
        self.assertEqual(match_poi(self.poi,[])['identity_mapping_status'],'NOT_FOUND')
        for pid in ('p2','p34','p42','pz_0db17d82e9ec'):
            row = match_poi(POIRepository().get_poi_by_id(pid),[self.candidate()])
            self.assertEqual(row['identity_mapping_status'],'NOT_FOUND');self.assertIsNone(row['amap_poi_id']);self.assertEqual(row['live_info_applicability'],'NOT_APPLICABLE')

    def test_mapping_repository_is_defensive_and_validated(self):
        repository = maps();value = repository.get('p28');value['amap_poi_id'] = 'bad'
        self.assertEqual(repository.get('p28')['amap_poi_id'],ID)
        valid = repository.get('p28')
        for changes in (dict(identity_mapping_status='bad'),dict(identity_mapping_status='NOT_APPLICABLE'),
                        dict(live_info_applicability='bad'),dict(amap_poi_id=None),
                        dict(identity_mapping_status='AMBIGUOUS',amap_poi_id=ID),
                        dict(confidence=float('nan')),dict(confidence=.5,reviewed=False),
                        dict(reviewed=True,match_method='AUTO_HIGH_CONFIDENCE')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                PoiMappingRepository(records={'p28':dict(valid,**changes)})

    def test_full_58_audit_and_search_failure_controlled(self):
        provider = Mock();provider.search_mapping_candidates.side_effect = ProviderTimeoutError()
        repo = POIRepository();before = repo.get_raw_data()
        mappings,summary = audit(repo,provider)
        self.assertEqual(len(mappings),58);self.assertEqual(sum(summary['identity_counts'].values()),58)
        self.assertEqual(before,repo.get_raw_data());self.assertTrue(summary['search_failures'])


class PoiServiceTests(unittest.TestCase):
    def test_missing_and_ambiguous_mapping_never_request(self):
        provider = Mock()
        for status in ('AMBIGUOUS','NOT_FOUND'):
            result = PoiLiveInfoService(provider,maps(status),clock=lambda:AT).get_poi_live_info('p28')
            self.assertEqual(result.live_data_status,'UNAVAILABLE');self.assertEqual(result.open_status,'UNKNOWN')
        result = PoiLiveInfoService(provider,PoiMappingRepository(records={})).get_poi_live_info('p28')
        self.assertEqual(result.error_code,'mapping_missing');provider.get_poi_detail.assert_not_called()

    def test_cached_hours_status_recalculated_and_today_not_carried_next_day(self):
        provider = Mock();provider.get_poi_detail.return_value = fixed_info()
        service = PoiLiveInfoService(provider,maps(),clock=lambda:AT)
        noon = service.get_poi_live_info('p28')
        evening = service.get_poi_live_info('p28',current_local_time=AT.replace(hour=19))
        tomorrow = service.get_poi_live_info('p28',current_local_time=AT+timedelta(days=1))
        self.assertEqual(noon.open_status,'OPEN');self.assertEqual(evening.open_status,'CLOSED')
        self.assertEqual(tomorrow.open_status,'UNKNOWN');self.assertTrue(evening.cache_hit)
        self.assertEqual(noon.fetched_at,evening.fetched_at);self.assertEqual(provider.get_poi_detail.call_count,1)

    def test_timeout_no_data_invention_and_no_failure_cache(self):
        provider = Mock();provider.get_poi_detail.side_effect = ProviderTimeoutError()
        service = PoiLiveInfoService(provider,maps(),clock=lambda:AT)
        result = service.get_poi_live_info('p28')
        self.assertEqual(result.live_data_status,'UNAVAILABLE');self.assertEqual(result.error_code,'provider_timeout')
        self.assertIsNone(result.opentime_today);self.assertIsNone(result.rating)
        provider.get_poi_detail.side_effect = None;provider.get_poi_detail.return_value = fixed_info()
        self.assertEqual(service.get_poi_live_info('p28').live_data_status,'PARTIAL')
        self.assertEqual(provider.get_poi_detail.call_count,2)

    def test_weekly_prose_does_not_substitute_today(self):
        provider = Mock();provider.get_poi_detail.return_value = replace(fixed_info(),opentime_today=None)
        result = PoiLiveInfoService(provider,maps(),clock=lambda:AT).get_poi_live_info('p28')
        self.assertEqual(result.open_status,'UNKNOWN');self.assertEqual(result.opentime_week,'Week schedule')

    def test_cache_ttl_capacity_and_defensive_copies(self):
        now = [0];cache = TTLCache(10,max_entries=1,clock=lambda:now[0])
        cache.set('a',{'value':1});cache.get('a')['value']=9;self.assertEqual(cache.get('a'),{'value':1})
        now[0]=10;self.assertIsNone(cache.get('a'))
        cache.set('a',1);cache.set('b',2);self.assertIsNone(cache.get('a'))

    def test_service_detail_cache_expires(self):
        now=[0];provider=Mock();provider.get_poi_detail.return_value=fixed_info()
        service=PoiLiveInfoService(provider,maps(),clock=lambda:AT,cache=TTLCache(10,clock=lambda:now[0]))
        service.get_poi_live_info('p28');service.get_poi_live_info('p28')
        self.assertEqual(provider.get_poi_detail.call_count,1)
        now[0]=10;service.get_poi_live_info('p28')
        self.assertEqual(provider.get_poi_detail.call_count,2)

    def test_invalid_time_rejected_and_faulty_provider_safe(self):
        provider=Mock();provider.get_poi_detail.side_effect=RuntimeError('sensitive raw details')
        service=PoiLiveInfoService(provider,maps(),clock=lambda:AT)
        with self.assertRaises(ValueError):service.get_poi_live_info('p28',current_local_time=AT.replace(tzinfo=None))
        result=service.get_poi_live_info('p28')
        self.assertEqual(result.error_code,'provider_response_invalid')
        self.assertNotIn('sensitive raw details',json.dumps(result.to_dict()))


class ProximityTests(unittest.TestCase):
    def setUp(self):
        self.poi = POIRepository().get_poi_by_id('p28')
        self.locations = LocationService(None,None)
        self.service = ProximityService(self.locations)

    def point(self,meters):return Location(POINT.lat+meters/111195.0802335,POINT.lng,'GCJ02')

    def test_30_120_1000m_and_zero(self):
        for meters,status in ((0,'ARRIVED'),(30,'ARRIVED'),(120,'NEAR'),(1000,'FAR')):
            result = self.service.check_arrival(self.point(meters),self.poi)
            self.assertEqual(result.status,status);self.assertAlmostEqual(result.distance_m,meters,places=2)

    def test_configurable_thresholds(self):
        service = ProximityService(self.locations,ProximityConfig(20,100))
        self.assertEqual(service.check_arrival(self.point(30),self.poi).status,'NEAR')
        self.assertEqual(service.check_arrival(self.point(120),self.poi).status,'FAR')
        for values in ((-1,200),(200,100),(100,100),(float('nan'),200),(60,float('inf'))):
            with self.assertRaises(ValueError):ProximityConfig(*values)

    def test_wgs_conversion_only_and_no_walking_or_regeo_request(self):
        normalizer = Mock(return_value=POINT)
        locations = LocationService(None,normalizer)
        service = ProximityService(locations)
        result = service.check_arrival(Location(31.16,121.46,'WGS84'),self.poi)
        self.assertEqual(result.status,'ARRIVED');normalizer.assert_called_once()

    def test_all_world_queries_leave_trip_and_kb_unchanged(self):
        repo = POIRepository();kb = Path('data/pois.json').read_bytes()
        plan,intent = load_fixture();trip = TripState.create(plan,intent);before = trip.to_dict()
        client,network = client_for(geodata())
        location = LocationService(AmapGeocodingProvider(client),AmapWalkingProvider(client).normalize_location_for_amap)
        provider = Mock();provider.get_poi_detail.side_effect = ProviderTimeoutError()
        world = WorldContextService(repo,location,PoiLiveInfoService(provider,maps(),repository=repo))
        world.reverse_geocode(POINT);world.check_arrival(POINT,'p28');world.get_poi_live_info('p28')
        self.assertEqual(before,trip.to_dict());self.assertEqual(kb,Path('data/pois.json').read_bytes())
        TripState.from_dict(trip.to_dict())
