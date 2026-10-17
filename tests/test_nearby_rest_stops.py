"""Offline service boundaries and adversarial provider normalization."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from src import POIRepository, Location
from src.amap_category_mapping import AmapCategoryMapping, classify_service_poi
from src.nearby_models import ServicePoi, NearbyCategoryResult, ServicePoiCategory as C, DEFAULT_CATEGORIES
from src.providers.amap.nearby import AmapNearbyPoiProvider
from src.providers.amap import AmapWalkingProvider
from src.providers.base import ProviderResponseError, ProviderTimeoutError, ProviderQuotaError
from src.services.location_service import LocationService
from src.services.nearby_rest_stop_service import NearbyRestStopService
from src.services.ttl_cache import TTLCache
from src.services.world_context_service import WorldContextService
from src.trip_state import TripState
from tools.demos.trip_demo import load_fixture
from src.world_models import SHANGHAI

ORIGIN = Location(31.167682,121.463841,'GCJ02')
AT = datetime(2026,10,5,12,tzinfo=SHANGHAI)
FETCHED = AT.astimezone(timezone.utc).isoformat()


def item(pid='B0TEST12345', cat=C.CAFE, *, distance=100, **kw):
    return ServicePoi('amap',pid,'Test facility',cat,(cat,),'test type',ORIGIN,distance,'PROVIDER',FETCHED,**kw)


def client_for(rows):
    client = Mock();client.redact_text.side_effect = lambda value:value.replace('secret-value','[REDACTED]')
    client.get.return_value = {'pois':rows}
    return client


def raw(**kw):
    return dict(id='B0TEST12345',name='Actual name',typecode='050500',type='餐饮服务;咖啡厅;咖啡厅',
                location=ORIGIN.amap_value(),distance='100',address='Real address',**kw)


class CategoryTests(unittest.TestCase):
    def test_four_categories_and_subtypes(self):
        for code,expected in [('050501',C.CAFE),('050101',C.RESTAURANT),('050200',C.RESTAURANT),('050301',C.RESTAURANT),('050400',C.RESTAURANT),('200301',C.RESTROOM),('060201',C.CONVENIENCE_STORE),('050000',C.RESTAURANT)]:
            with self.subTest(code=code): self.assertEqual(classify_service_poi(code),(expected,))
    def test_excluded_services_and_name_keywords_never_reclassify(self):
        for code in ('061200','080304','090100','100100','150500','050600'):
            self.assertEqual(classify_service_poi(code,'咖啡厅'),())
        r=raw();r.update(name='咖啡便利店',typecode='090100',type='医疗保健服务;综合医院')
        self.assertEqual(AmapNearbyPoiProvider(client_for([r])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results,())
    def test_provider_type_fallback_without_codes(self):
        self.assertEqual(classify_service_poi(None,'购物服务;便民商店/便利店;便利店'),(C.CONVENIENCE_STORE,))
        self.assertEqual(classify_service_poi(None,'体育休闲服务;酒吧'),())
    def test_multiple_categories_stable_priority(self):
        self.assertEqual(classify_service_poi('050301|050500'),(C.CAFE,C.RESTAURANT))
    def test_query_types_are_configured_and_convenience_is_not_franchise(self):
        mapping=AmapCategoryMapping();self.assertEqual(mapping.query_types(C.CONVENIENCE_STORE),'060200')
        self.assertNotIn('050500',mapping.query_types(C.RESTAURANT))


class ProviderTests(unittest.TestCase):
    def test_single_around_search_includes_business_no_detail(self):
        r=raw(business=dict(tel='12345',rating='4.5',cost='35',opentime_today='08:00-22:00',opentime_week='每天08:00-22:00'))
        client=client_for([r]);page=AmapNearbyPoiProvider(client).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5)
        client.get.assert_called_once();path,params=client.get.call_args.args
        self.assertEqual(path,'/v5/place/around');self.assertEqual(params['location'],ORIGIN.amap_value())
        self.assertEqual(params['show_fields'],'business');self.assertEqual(params['page_num'],1)
        self.assertEqual(page.results[0].rating,4.5);self.assertEqual(page.results[0].cost,35)
        self.assertEqual(page.results[0].data_status,'AVAILABLE')
    def test_missing_optional_fields_stay_null(self):
        row=AmapNearbyPoiProvider(client_for([raw()])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results[0]
        for name in ('rating','cost','tel','opentime_today','opentime_week'):self.assertIsNone(getattr(row,name))
        self.assertEqual(row.open_status,'UNKNOWN');self.assertEqual(row.data_status,'PARTIAL')
    def test_invalid_numbers_fall_back_or_remain_null(self):
        for value in ('-1','nan','inf',[],True,None):
            r=raw(business=dict(rating=value,cost=value));r['distance']=value
            row=AmapNearbyPoiProvider(client_for([r])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results[0]
            self.assertEqual(row.distance_type,'HAVERSINE');self.assertAlmostEqual(row.distance_m,0)
            self.assertIsNone(row.rating);self.assertIsNone(row.cost)
        r=raw(business=dict(rating='8',cost='0'));row=AmapNearbyPoiProvider(client_for([r])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results[0]
        self.assertIsNone(row.rating);self.assertEqual(row.cost,0)
    def test_provider_distance_is_preferred_and_not_claimed_as_walking(self):
        row=AmapNearbyPoiProvider(client_for([raw()])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results[0]
        self.assertEqual(row.distance_type,'PROVIDER');self.assertEqual(row.distance_m,100)
        self.assertNotIn('walking_distance',row.to_dict())
    def test_outside_radius_is_filtered_using_actual_position_too(self):
        a=raw();a['distance']='801';b=raw();b['location']='121.9,31.9';b['distance']='0'
        self.assertEqual(AmapNearbyPoiProvider(client_for([a,b])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results,())
    def test_invalid_id_name_location_and_business_are_not_fake_results(self):
        for field,value in [('id','p35'),('name',[]),('location','bad'),('location','121,91'),('business','bad')]:
            r=raw();r[field]=value
            with self.subTest(field=field),self.assertRaises(ProviderResponseError):AmapNearbyPoiProvider(client_for([r])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5)
    def test_mixed_malformed_records_preserve_real_results_with_partial(self):
        page=AmapNearbyPoiProvider(client_for([None,raw()])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5)
        self.assertEqual(len(page.results),1);self.assertEqual(page.status,'PARTIAL');self.assertEqual(page.errors,('malformed_service_poi',))
    def test_empty_is_success_but_malformed_container_is_failure(self):
        provider=AmapNearbyPoiProvider(client_for([]));self.assertEqual(provider.search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).status,'AVAILABLE')
        provider.client.get.return_value={'pois':None}
        with self.assertRaises(ProviderResponseError):provider.search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5)
    def test_external_errors_are_shared_abstraction(self):
        client=client_for([]);client.get.side_effect=ProviderQuotaError()
        with self.assertRaises(ProviderQuotaError):AmapNearbyPoiProvider(client).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5)
    def test_dynamic_text_is_redacted(self):
        r=raw(business=dict(tel='secret-value'));r['name']='secret-value'
        row=AmapNearbyPoiProvider(client_for([r])).search_nearby(ORIGIN,C.CAFE,radius_m=800,limit=5).results[0]
        self.assertNotIn('secret-value',json.dumps(row.to_dict()))
    def test_dto_namespace_and_validation(self):
        row=item();self.assertEqual(row.service_poi_id,'amap:B0TEST12345');self.assertNotIn('core_poi_id',row.to_dict())
        for kw in (dict(location=Location(31,121,'WGS84')),dict(distance_m=-1),dict(rating=6),dict(fetched_at='2026-10-05T12:00:00'),dict(categories=('HOTEL',)),dict(tel=[])):
            with self.subTest(kw=kw),self.assertRaises(ValueError):replace(row,**kw)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.repo=POIRepository();self.time=[AT];self.provider=Mock(spec=['provider','search_nearby','get_poi_detail']);self.provider.provider='amap'
        self.provider.search_nearby.side_effect=lambda origin,category,**kw:NearbyCategoryResult((item(cat=category),))
        self.locations=LocationService(None,None)
        self.service=NearbyRestStopService(self.provider,self.repo,self.locations,clock=lambda:self.time[0])
    def search(self,**kw):return self.service.search_nearby_rest_stops(location=ORIGIN,**kw)
    def test_gps_normalizes_via_existing_official_converter(self):
        client=client_for([]);client.get.return_value={'locations':ORIGIN.amap_value()}
        self.service.locations=LocationService(None,AmapWalkingProvider(client).normalize_location_for_amap)
        result=self.service.search_nearby_rest_stops(location=Location(31.16,121.46,'WGS84'),categories=[C.CAFE])
        self.assertEqual(result.origin,ORIGIN);self.assertEqual(result.origin_source,'CURRENT_LOCATION')
        client.get.assert_called_once_with('/v3/assistant/coordinate/convert',{'locations':'121.460000,31.160000','coordsys':'gps'})
        self.assertEqual(self.provider.search_nearby.call_args.args[0],ORIGIN)
    def test_gcj02_needs_no_conversion(self):
        self.locations.normalizer=Mock(side_effect=AssertionError('No conversion expected'))
        self.assertEqual(self.search(categories=[C.CAFE]).origin,ORIGIN);self.locations.normalizer.assert_not_called()
    def test_current_location_has_priority_even_over_unusable_core_id(self):
        result=self.search(core_poi_id='unknown',categories=[C.CAFE]);self.assertEqual(result.origin,ORIGIN);self.assertIsNone(result.core_poi_id)
        result=self.service.search_nearby_rest_stops(current_location=ORIGIN,core_poi_id='p35',categories=[C.CAFE]);self.assertEqual(result.origin_source,'CURRENT_LOCATION')
    def test_point_core_effective_coordinate(self):
        result=self.service.search_nearby_rest_stops(core_poi_id='p28',categories=[C.CAFE]);self.assertEqual(result.origin,ORIGIN);self.assertEqual(result.core_poi_id,'p28')
    def test_area_not_found_uses_anchor_not_identity_or_centroid(self):
        result=self.service.search_nearby_rest_stops(core_poi_id='p35',categories=[C.CAFE]);profile=self.repo.get_spatial_profile('p35');a=profile['route_anchor']
        self.assertEqual((result.origin.lat,result.origin.lng),(a['lat'],a['lng']))
        self.assertNotEqual((result.origin.lat,result.origin.lng),self.repo.get_poi_by_id('p35').original_coordinates)
        vertices=profile['spatial_extent']['vertices'][:-1];centroid=tuple(sum(v[key] for v in vertices)/len(vertices) for key in ('lat','lng'))
        self.assertNotEqual((result.origin.lat,result.origin.lng),centroid);self.assertEqual(result.status,'AVAILABLE')
    def test_linear_uses_recommended_entry_not_identity_or_exit(self):
        result=self.service.search_nearby_rest_stops(core_poi_id='p34',categories=[C.CAFE]);profile=self.repo.get_spatial_profile('p34')
        self.assertEqual((result.origin.lat,result.origin.lng),tuple(profile['route_anchor'][key] for key in ('lat','lng')))
        self.assertNotEqual((result.origin.lat,result.origin.lng),self.repo.get_poi_by_id('p34').original_coordinates)
        self.assertNotEqual((result.origin.lat,result.origin.lng),tuple(profile['secondary_anchor'][key] for key in ('lat','lng')))
    def test_default_categories_radius_limit_and_no_detail_n_plus_one(self):
        result=self.search();self.assertEqual(result.requested_categories,DEFAULT_CATEGORIES);self.assertEqual(result.radius_m,800);self.assertEqual(result.limit_per_category,5)
        self.assertEqual(self.provider.search_nearby.call_count,7);self.provider.get_poi_detail.assert_not_called()
    def test_invalid_input_is_rejected_before_requests(self):
        for kw in (dict(radius_m=0),dict(radius_m=3001),dict(radius_m=True),dict(limit_per_category=11),dict(limit_per_category=0),dict(categories=[]),dict(categories=['BAR']),dict(categories={C.CAFE})):
            with self.subTest(kw=kw),self.assertRaises(ValueError):self.search(**kw)
        for kw in ({},dict(core_poi_id='unknown'),dict(location={'lat':31,'lng':121}),dict(location=ORIGIN,current_location=ORIGIN)):
            with self.subTest(kw=kw),self.assertRaises(ValueError):self.service.search_nearby_rest_stops(**kw)
        self.provider.search_nearby.assert_not_called()
    def test_normalization_failure_is_unavailable_not_core_fallback(self):
        result=self.service.search_nearby_rest_stops(location=Location(31,121,'WGS84'),core_poi_id='p35')
        self.assertEqual(result.status,'UNAVAILABLE');self.assertIsNone(result.origin);self.assertEqual(result.results,());self.provider.search_nearby.assert_not_called()
    def test_dedup_across_and_within_categories_unions_classifications(self):
        self.provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult((item(cat=c),item(cat=c)))
        result=self.search(categories=[C.RESTAURANT,C.CAFE]);self.assertEqual(len(result.results),1)
        self.assertEqual(result.results[0].categories,(C.CAFE,C.RESTAURANT));self.assertEqual(result.results[0].primary_category,C.CAFE)
    def test_category_order_does_not_change_primary_or_sorting(self):
        a=self.search(categories=[C.RESTAURANT,C.CAFE]);b=self.search(categories=[C.CAFE,C.RESTAURANT])
        self.assertEqual([p.to_dict() for p in a.results],[p.to_dict() for p in b.results])
    def test_ranking_open_unknown_closed_then_distance_then_rating(self):
        rows=(item('B0CLOSED01',distance=1,opentime_today='01:00-02:00'),item('B0UNKNOWN1',distance=5),
              item('B0OPEN0001',distance=100,opentime_today='00:00-24:00',rating=3),item('B0OPEN0002',distance=100,opentime_today='00:00-24:00',rating=4),
              item('B0OPEN0003',distance=100,opentime_today='00:00-24:00'),item('B0OPEN0004',distance=200,opentime_today='00:00-24:00',rating=5))
        self.provider.search_nearby.return_value=NearbyCategoryResult(rows);self.provider.search_nearby.side_effect=None
        result=self.search(categories=[C.CAFE],limit_per_category=10)
        self.assertEqual([p.provider_poi_id for p in result.results],['B0OPEN0002','B0OPEN0001','B0OPEN0003','B0OPEN0004','B0UNKNOWN1','B0CLOSED01'])
    def test_zero_rating_is_actual_value_missing_stays_null(self):
        self.provider.search_nearby.side_effect=lambda *a,**kw:NearbyCategoryResult((item('B0ZERO0001',rating=0),item('B0NULL0001')))
        rows=self.search(categories=[C.CAFE]).results;self.assertEqual(rows[0].rating,0);self.assertIsNone(rows[1].rating)
    def test_restrooms_do_not_assume_all_day_or_guess_weekly(self):
        self.provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult((item(cat=c,opentime_week='每天全天开放'),))
        self.assertEqual(self.search(categories=[C.RESTROOM]).results[0].open_status,'UNKNOWN')
    def test_missing_opening_is_unknown_and_reliable_restroom_hours_parse(self):
        self.provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult((item(cat=c,opentime_today='08:00-22:00'),))
        self.assertEqual(self.search(categories=[C.RESTROOM]).results[0].open_status,'OPEN')
    def test_partial_and_total_provider_failure_do_not_invent_results(self):
        def query(origin,category,**kw):
            if category==C.RESTROOM:raise ProviderTimeoutError()
            return NearbyCategoryResult((item('B0'+category.value.replace('_',''),cat=category),))
        self.provider.search_nearby.side_effect=query;result=self.search()
        self.assertEqual(result.status,'PARTIAL');self.assertEqual(len(result.results),6);self.assertEqual(result.errors[0]['code'],'provider_timeout')
        self.service.cache=TTLCache(300);self.provider.search_nearby.side_effect=RuntimeError('https://x/?key=secret-value')
        result=self.search();self.assertEqual(result.status,'UNAVAILABLE');self.assertEqual(result.results,());self.assertNotIn('secret-value',json.dumps(result.to_dict()))
    def test_malformed_partial_page_status_propagates(self):
        self.provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult((item(cat=c),),'PARTIAL',('malformed_service_poi',))
        result=self.search(categories=[C.CAFE]);self.assertEqual(result.status,'PARTIAL');self.assertEqual(len(result.results),1)
    def test_successful_empty_is_available(self):
        self.provider.search_nearby.side_effect=lambda *a,**kw:NearbyCategoryResult()
        self.assertEqual(self.search().status,'AVAILABLE');self.assertEqual(self.search().results,())
    def test_invalid_provider_contract_is_safe_failure(self):
        for value in (None,NearbyCategoryResult((item(cat=C.RESTAURANT),)),NearbyCategoryResult((item(),),'UNAVAILABLE'),NearbyCategoryResult((item(),),'AVAILABLE',('unexpected_error',)),NearbyCategoryResult((item(),),'PARTIAL',None),NearbyCategoryResult((replace(item(),data_status='UNAVAILABLE'),))):
            self.service.cache=TTLCache(300);self.provider.search_nearby.side_effect=None;self.provider.search_nearby.return_value=value
            result=self.search(categories=[C.CAFE]);self.assertEqual(result.status,'UNAVAILABLE');self.assertEqual(result.results,())
    def test_failed_categories_are_not_cached(self):
        self.provider.search_nearby.side_effect=ProviderTimeoutError();self.search(categories=[C.CAFE]);self.search(categories=[C.CAFE])
        self.assertEqual(self.provider.search_nearby.call_count,2)
        self.service.provider=None;self.service.cache=TTLCache(300)
        result=self.search();self.assertEqual(result.status,'UNAVAILABLE');self.assertEqual(result.results,())
    def test_cache_ttl_capacity_keys_and_defensive_results(self):
        tick=[0];self.service.cache=TTLCache(300,clock=lambda:tick[0])
        a=self.search(categories=[C.CAFE]);a.to_dict()['results'][0]['name']='changed'
        b=self.search(categories=[C.CAFE]);self.assertEqual(self.provider.search_nearby.call_count,1);self.assertEqual(b.cache_hit_categories,(C.CAFE,));self.assertNotEqual(b.results[0].name,'changed')
        self.search(categories=[C.CAFE],radius_m=900);self.search(categories=[C.CAFE],limit_per_category=6);self.search(categories=[C.RESTAURANT])
        self.service.search_nearby_rest_stops(location=Location(ORIGIN.lat+.00001,ORIGIN.lng,'GCJ02'),categories=[C.CAFE])
        self.assertEqual(self.provider.search_nearby.call_count,5)
        tick[0]=300;self.search(categories=[C.CAFE]);self.assertEqual(self.provider.search_nearby.call_count,6)
    def test_cache_recomputes_open_status_and_does_not_reuse_today_across_midnight(self):
        self.provider.search_nearby.side_effect=lambda *a,**kw:NearbyCategoryResult((item(opentime_today='08:00-12:01'),))
        self.assertEqual(self.search(categories=[C.CAFE]).results[0].open_status,'OPEN')
        self.time[0]=AT+timedelta(minutes=2);self.assertEqual(self.search(categories=[C.CAFE]).results[0].open_status,'CLOSED')
        self.time[0]=AT+timedelta(days=1);self.assertEqual(self.search(categories=[C.CAFE]).results[0].open_status,'UNKNOWN')
        self.assertEqual(self.provider.search_nearby.call_count,1)
    def test_limit_is_strict_after_dedup_multi_category_and_sort(self):
        self.provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult(tuple(replace(item(f'B0LIMIT{i:03}',cat=c,distance=i),categories=(C.CAFE,C.RESTAURANT),primary_category=C.CAFE) for i in range(15)))
        result=self.search(categories=[C.CAFE,C.RESTAURANT],limit_per_category=3)
        self.assertEqual(len(result.results),3);self.assertEqual(result.to_dict()['category_counts'],{C.CAFE:3,C.RESTAURANT:3})
    def test_world_facade_query_does_not_mutate_trip_route_core_or_spatial_data(self):
        plan,intent=load_fixture();trip=TripState.create(plan,intent);trip.start_trip();before=trip.to_dict()
        files={p:Path(p).read_bytes() for p in ('data/pois.json','data/core_spatial_profiles.json','data/amap_poi_mappings.json')}
        raw_before=self.repo.get_raw_data();coords_before={p.id:p.coordinates for p in self.repo.get_all_pois()}
        info=Mock();world=WorldContextService(self.repo,self.locations,info,nearby=self.service)
        world.search_nearby_rest_stops(core_poi_id=trip.current_poi_id)
        self.assertEqual(trip.to_dict(),before);self.assertEqual(trip.route_versions,before['route_versions'])
        self.assertEqual(self.repo.get_raw_data(),raw_before);self.assertEqual({p.id:p.coordinates for p in self.repo.get_all_pois()},coords_before)
        for p,data in files.items():self.assertEqual(Path(p).read_bytes(),data)
        info.get_poi_live_info.assert_not_called();self.assertEqual(len(self.repo.get_all_pois()),58)
    def test_world_environment_shares_client_and_nearby_requires_no_mapping_detail(self):
        client=client_for([]);world=WorldContextService.from_environment(repository=self.repo,client=client)
        result=world.search_nearby_rest_stops(core_poi_id='p35',categories=[C.RESTROOM])
        self.assertEqual(result.status,'AVAILABLE');self.assertIs(world.nearby.provider.client,client)
        self.assertEqual([call.args[0] for call in client.get.call_args_list],['/v5/place/around'])


if __name__=='__main__':unittest.main()
