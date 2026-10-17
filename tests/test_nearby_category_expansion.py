"""Phase 3B_3 addendum: seven types, grouped queries, independent category views."""
from dataclasses import replace
from pathlib import Path
import json
import unittest
from unittest.mock import Mock
from src import POIRepository
from src.amap_category_mapping import AmapCategoryMapping, classify_service_poi
from src.nearby_models import NearbyServiceCategory as C, DEFAULT_CATEGORIES, DISPLAY_GROUPS, NearbyCategoryResult
from src.providers.amap.nearby import AmapNearbyPoiProvider
from src.providers.base import ProviderTimeoutError
from src.services.location_service import LocationService
from src.services.ttl_cache import TTLCache
from src.services.nearby_service import NearbyService
from src.services.nearby_rest_stop_service import NearbyRestStopService
from src.services.world_context_service import WorldContextService
from tests.test_nearby_rest_stops import ORIGIN, AT, item, raw, client_for


def seven_rows():
    specs=[('B0RESTAURANT','050100','中餐厅','Lunch',{}),('B0CAFE00001','050500','咖啡厅','Coffee',{}),
           ('B0TEA000001','050600','茶艺馆','奶茶门店',dict(tag='奶茶;果茶')),
           ('B0DESSERT01','050700','冷饮店','Gelato',{}),('B0CONVEN001','060201','便利店','Water',{}),
           ('B0RESTROOM1','200300','公共厕所','Public restroom',{}),('B0MALL00001','060101','购物中心','Commercial complex',{})]
    rows=[]
    for pid,code,typ,name,business in specs:
        row=raw(business=business);row.update(id=pid,typecode=code,type=typ,name=name);rows.append(row)
    return rows


def grouped_client():
    client=client_for([])
    def query(path,params):
        assert path=='/v5/place/around'
        codes=params['types'].split('|')
        return {'pois':[row for row in seven_rows() if any(row['typecode']==c or row['typecode'].startswith(c[:4]) for c in codes)]}
    client.get.side_effect=query
    return client


class CategoryExpansionTests(unittest.TestCase):
    def test_seven_categories_have_configured_queries_and_display_groups(self):
        mapping=AmapCategoryMapping();self.assertEqual(len(C),7)
        for category in DEFAULT_CATEGORIES:self.assertTrue(mapping.query_types(category))
        self.assertEqual(set(c for group in DISPLAY_GROUPS.values() for c in group),set(C))
    def test_modern_tea_structured_category_before_name_fallback(self):
        mapping=AmapCategoryMapping()
        for code in ('050600','050700','050900','050000'):
            cats,source=mapping.classify_with_source(code,'茶艺馆',structured_category='奶茶;果茶',name='No clue')
            self.assertIn(C.TEA_DRINK,cats);self.assertNotIn(C.CAFE,cats);self.assertEqual(source,'STRUCTURED_CATEGORY')
    def test_modern_tea_brand_name_is_gated_fallback_and_marked(self):
        mapping=AmapCategoryMapping();cats,source=mapping.classify_with_source('050600','茶艺馆',name='喜茶(店)')
        self.assertEqual(cats,(C.TEA_DRINK,));self.assertEqual(source,'NAME_FALLBACK')
        self.assertEqual(mapping.classify('090100','综合医院',name='奶茶果茶医院'),())
        self.assertEqual(mapping.classify('050100','中餐厅',name='奶茶餐馆'),(C.RESTAURANT,))
    def test_traditional_tea_and_generic_tea_word_not_modern_bubble_tea(self):
        for name in ('老上海茶馆','传统茶艺馆','普洱茶茶室','茶文化展示'):
            self.assertEqual(classify_service_poi('050600','茶艺馆',name=name),())
        self.assertEqual(classify_service_poi(None,'饮品店',name='Generic juice'),())
    def test_dessert_ice_cream_and_bakery_share_one_category(self):
        for code in ('050700','050800','050900'):
            self.assertEqual(classify_service_poi(code),(C.DESSERT_ICE_CREAM,))
    def test_cafe_plus_dessert_has_stable_primary_and_structured_evidence(self):
        self.assertEqual(classify_service_poi('050500|050900'),(C.CAFE,C.DESSERT_ICE_CREAM))
        cats,source=AmapCategoryMapping().classify_with_source('050500','咖啡厅',structured_category='咖啡;甜品')
        self.assertEqual(cats,(C.CAFE,C.DESSERT_ICE_CREAM));self.assertEqual(source,'STRUCTURED_CATEGORY')
    def test_mall_only_actual_shopping_center_not_department_store_office_street(self):
        self.assertEqual(classify_service_poi('060101','购物中心'),(C.MALL,))
        self.assertEqual(classify_service_poi('060100','商场;购物中心'),(C.MALL,))
        for code,typ in (('060102','普通商场'),('060103','免税品店'),('060100','商场'),('120201','商务写字楼'),('190301','道路名'),('100100','酒店'),('110000','景点'),('060400','超市')):
            self.assertEqual(classify_service_poi(code,typ,name='奶茶冰淇淋购物中心'),())
        for name in ('东方商厦','某百货店','Example Department Store'):
            self.assertEqual(classify_service_poi('060101','购物中心',name=name),())
        self.assertEqual(classify_service_poi('200304','公共设施;公共厕所;婴儿换洗间/哺乳室/母婴室'),())
        self.assertEqual(classify_service_poi(None,'公共设施;公共厕所;母婴室'),())
        self.assertEqual(classify_service_poi('200303','公共设施;公共厕所;残障洗手间/无障碍洗手间'),(C.RESTROOM,))
    def test_group_configuration_covers_default_with_four_requests(self):
        groups=AmapCategoryMapping().query_groups(DEFAULT_CATEGORIES)
        self.assertEqual(len(groups),4);self.assertEqual(set(c for members,_ in groups for c in members),set(C))
        self.assertEqual(len(AmapCategoryMapping().query_groups((C.CAFE,C.TEA_DRINK,C.DESSERT_ICE_CREAM))),1)
    def test_grouped_api_normalizes_seven_categories_without_detail(self):
        client=grouped_client();pages=AmapNearbyPoiProvider(client).search_nearby_categories(ORIGIN,DEFAULT_CATEGORIES,radius_m=800,limit=5)
        self.assertEqual(client.get.call_count,4);self.assertEqual(set(pages),set(C))
        self.assertTrue(all(len(page.results)==1 and page.status=='AVAILABLE' for page in pages.values()))
        self.assertEqual(pages[C.TEA_DRINK].results[0].classification_source,'STRUCTURED_CATEGORY')
        self.assertEqual({call.args[0] for call in client.get.call_args_list},{'/v5/place/around'})
        self.assertTrue(all(call.args[1]['show_fields']=='business' and call.args[1]['page_size']<=25 for call in client.get.call_args_list))
    def test_shared_group_failure_only_marks_its_member_categories_unavailable(self):
        client=grouped_client();original=client.get.side_effect
        def query(path,params):
            if '050500' in params['types']:raise ProviderTimeoutError()
            return original(path,params)
        client.get.side_effect=query;repo=POIRepository()
        service=NearbyService(AmapNearbyPoiProvider(client),repo,LocationService(None,None))
        result=service.search_nearby_services(location=ORIGIN)
        self.assertEqual(result.status,'PARTIAL');self.assertEqual(client.get.call_count,4)
        failed={s['category'] for s in result.category_statuses if s['status']=='UNAVAILABLE'}
        self.assertEqual(failed,{C.CAFE,C.TEA_DRINK,C.DESSERT_ICE_CREAM})
        self.assertTrue(all(e['code']=='provider_timeout' for e in result.errors));self.assertEqual(len(result.results),4)
    def test_service_default_and_compatibility_alias_share_cache_and_implementation(self):
        client=grouped_client();repo=POIRepository();service=NearbyService(AmapNearbyPoiProvider(client),repo,LocationService(None,None),clock=lambda:AT)
        world=WorldContextService(repo,service.locations,Mock(),nearby=service)
        a=world.search_nearby_services(location=ORIGIN);b=world.search_nearby_rest_stops(location=ORIGIN)
        self.assertIs(NearbyRestStopService,NearbyService);self.assertEqual(a.requested_categories,DEFAULT_CATEGORIES)
        self.assertEqual(client.get.call_count,4);self.assertEqual(len(a.results),7);self.assertEqual(b.cache_hit_categories,DEFAULT_CATEGORIES)
        self.assertEqual([r.to_dict() for r in a.results],[r.to_dict() for r in b.results])
    def test_cafe_dessert_duplicate_is_one_inventory_row_with_two_views(self):
        row=replace(item(),categories=(C.CAFE,C.DESSERT_ICE_CREAM))
        provider=Mock(spec=['provider','search_nearby']);provider.provider='amap'
        provider.search_nearby.side_effect=lambda *args,**kw:NearbyCategoryResult((row,row))
        result=NearbyService(provider,POIRepository(),LocationService(None,None),clock=lambda:AT).search_nearby_services(location=ORIGIN,categories=[C.CAFE,C.DESSERT_ICE_CREAM])
        self.assertEqual(len(result.results),1);self.assertEqual(result.results[0].primary_category,C.CAFE)
        self.assertEqual(result.category_result_ids[C.CAFE],result.category_result_ids[C.DESSERT_ICE_CREAM])
    def test_per_category_sort_does_not_compare_different_categories_quality(self):
        cafe=item('B0CAFEOPEN1',distance=500,opentime_today='00:00-24:00')
        mall=item('B0MALL00001',cat=C.MALL,distance=1,opentime_today='01:00-02:00')
        provider=Mock(spec=['provider','search_nearby']);provider.provider='amap'
        provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult((cafe if c==C.CAFE else mall,))
        result=NearbyService(provider,POIRepository(),LocationService(None,None),clock=lambda:AT).search_nearby_services(location=ORIGIN,categories=[C.CAFE,C.MALL])
        self.assertEqual(result.category_result_ids[C.CAFE],(cafe.service_poi_id,));self.assertEqual(result.category_result_ids[C.MALL],(mall.service_poi_id,))
        self.assertEqual(result.results[1].open_status,'CLOSED')
    def test_multi_category_inventory_union_does_not_starve_other_category_limits(self):
        shared=replace(item('B0SHARED001',distance=50),categories=(C.CAFE,C.DESSERT_ICE_CREAM))
        cafe=item('B0CAFEBEST1',distance=1);dessert=item('B0DESSBEST1',cat=C.DESSERT_ICE_CREAM,distance=2)
        provider=Mock(spec=['provider','search_nearby']);provider.provider='amap'
        provider.search_nearby.side_effect=lambda o,c,**kw:NearbyCategoryResult((shared,cafe) if c==C.CAFE else (shared,dessert))
        result=NearbyService(provider,POIRepository(),LocationService(None,None),clock=lambda:AT).search_nearby_services(location=ORIGIN,categories=[C.CAFE,C.DESSERT_ICE_CREAM],limit_per_category=1)
        self.assertEqual(set(r.service_poi_id for r in result.results),{cafe.service_poi_id,dessert.service_poi_id})
        self.assertEqual(result.to_dict()['category_counts'],{C.CAFE:1,C.DESSERT_ICE_CREAM:1})
    def test_all_services_remain_ephemeral_even_mall_shares_core_neighborhood(self):
        repo=POIRepository();before=repo.get_raw_data();client=grouped_client();world=WorldContextService.from_environment(repository=repo,client=client)
        result=world.search_nearby_services(core_poi_id='p35')
        self.assertEqual(result.origin_source,'CORE_POI');self.assertEqual(repo.get_raw_data(),before)
        self.assertIsNone(repo.get_poi_by_id('amap:B0MALL00001'));self.assertEqual(len(repo.get_all_pois()),58)
    def test_cache_queries_only_missing_groups_and_failed_groups_are_retried(self):
        client=grouped_client();service=NearbyService(AmapNearbyPoiProvider(client),POIRepository(),LocationService(None,None))
        service.search_nearby_services(location=ORIGIN,categories=[C.CAFE]);self.assertEqual(client.get.call_count,1)
        service.search_nearby_services(location=ORIGIN);self.assertEqual(client.get.call_count,5)
        result=service.search_nearby_services(location=ORIGIN);self.assertEqual(client.get.call_count,5);self.assertEqual(result.cache_hit_categories,DEFAULT_CATEGORIES)
    def test_invalid_batch_contract_and_raw_failure_are_safe(self):
        provider=Mock(spec=['provider','search_nearby_categories']);provider.provider='amap'
        service=NearbyService(provider,POIRepository(),LocationService(None,None),clock=lambda:AT)
        provider.search_nearby_categories.return_value={C.CAFE:NearbyCategoryResult((item(),))}
        result=service.search_nearby_services(location=ORIGIN,categories=[C.CAFE,C.MALL])
        self.assertEqual(result.status,'PARTIAL');self.assertEqual(len(result.results),1)
        self.assertEqual(result.category_statuses[1]['status'],'UNAVAILABLE')
        service.cache=TTLCache(300)
        provider.search_nearby_categories.side_effect=RuntimeError('key=secret-value')
        result=service.search_nearby_services(location=ORIGIN)
        self.assertEqual(result.status,'UNAVAILABLE');self.assertEqual(result.results,());self.assertNotIn('secret-value',json.dumps(result.to_dict()))


if __name__=='__main__':unittest.main()
