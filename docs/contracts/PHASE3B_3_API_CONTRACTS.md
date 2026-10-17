# Phase 3B_3 — Nearby Services API

## 只读入口

```python
from src.services.world_context_service import WorldContextService
from src.nearby_models import NearbyServiceCategory
from src import Location

world = WorldContextService.from_environment()
result = world.search_nearby_services(
    location=Location(31.16, 121.46, 'WGS84'),
    core_poi_id='p35',  # GPS存在时，此fallback不参与origin选择
    categories=[NearbyServiceCategory.CAFE, NearbyServiceCategory.RESTROOM],
    radius_m=800,
    limit_per_category=5,
)
payload = result.to_dict()
```

签名：`search_nearby_services(location=None, core_poi_id=None, categories=None, radius_m=800, limit_per_category=5, *, current_location=None)`。`current_location` 是 `location` 的别名；两者不能同时传。Location 可为已有DTO或严格的 `lat/lng/coordinate_system` dict。调用者从当前路线取Core ID后用 `core_poi_id` 传入，facade不读取或写入TripStore。

GPS优先于Core，WGS84复用已有LocationService/AmapWalkingProvider官方转换；失败返回UNAVAILABLE且origin=null，不悄悄跳到Core。没有GPS时，POINT使用有效routing coordinate，AREA/LINEAR通过冻结的repository overlay使用route_anchor。p35的Identity NOT_FOUND不影响查询。没有origin、未知Core、空/未知类别、非法radius/limit均抛ValueError，不发请求。半径1–3000m，limit1–10，均为int、不接受bool。categories=None默认七类：RESTAURANT、CAFE、TEA_DRINK、DESSERT_ICE_CREAM、CONVENIENCE_STORE、RESTROOM、MALL；支持单个category字符串或非空list/tuple，去重并固定顺序。

## 响应

NearbySearchResult：origin、origin_source（CURRENT_LOCATION/CORE_POI）、core_poi_id（仅Core来源）、radius_m、limit_per_category、requested_categories、results、status、provider、fetched_at、errors、category_statuses、cache_hit_categories、category_result_ids。to_dict另有category_counts及display_groups。category_result_ids是每类按自身排序的Service ID列表，指向全局去重results；前端按此显示，不能把results整体顺序解释为跨品类推荐。fetched_at为本次查询时间；每个ServicePoi自己的fetched_at为provider观察时间。

status=AVAILABLE表示各类别查询成功，允许真实空列表；PARTIAL表示部分失败或provider部分记录损坏；UNAVAILABLE表示全类别失败或坐标规范化失败。ServicePoi.data_status则表达单店动态字段完整性；它为PARTIAL不自动把成功的查询标为PARTIAL。errors只含category、stage及固定safe code，不保留API URL、body、异常文本或key。

ServicePoi：provider、provider_poi_id、service_poi_id（如amap:B0…）、name、primary_category、categories、category（primary别名）、provider_type、provider_typecode、location、coordinate_system、distance_m、distance_type、address、tel、rating、cost、opentime_today、opentime_week、open_status、data_status、fetched_at、status_evaluated_at、classification_source。rating/cost/tel/opening缺失保留null，不补评分或费用。所有结果location=GCJ02。Service ID独立于Core stable ID，不插入Core、候选池、Trip、RouteVersion或must-go/visited。

## Provider / 分类

`BatchNearbyPoiProvider.search_nearby_categories(origin, categories, *, radius_m, limit)` 返回各类NearbyCategoryResult(results tuple, status, errors)，单组失败只影响其成员类别。原 `NearbyPoiProvider.search_nearby(origin, category, *, radius_m, limit)` 仍兼容，非batch provider可走旧适配路径。可注入mock/provider；WorldContextService constructor支持 `nearby=` 注入。默认 `AmapNearbyPoiProvider` 与其他世界服务共享AmapClient，不改现有HTTP/错误/转换实现。

每个配置查询组仅发一次 `/v5/place/around`，types来自 `data/amap_service_categories.json`，`show_fields=business`，`sortrule=distance`，`page_num=1`，`page_size=min(25,limit*3*本组请求类别数)`。默认七类四组around：MEALS、DRINKS_AND_DESSERT、ESSENTIALS、MALLS。类别组合可减少请求；缓存仅请求缺失类别对应的组，无text查询，无逐店detail。查询候选池有限，非全量搜索，不跨页扩大API调用。

分类先使用typecode，再看provider类型层级及structured category。咖啡0505；餐厅0501/0502/0503/0504（精确050000普通餐饮也支持）；冰淇淋/甜品/烘焙0507/0508/0509统一DESSERT_ICE_CREAM；厕所精确200300/200301/200302/200303（不含200304母婴室）；便利店0602；MALL精确060101购物中心。060100仅在结构化类型明确购物中心/综合体时接受，060102普通商场/单家百货、060103免税店、商业街/写字楼/超市均不作为MALL。即使粗provider code为060101，明确含百货/商厦/department store等单体百货语义也保守排除；此规则可能遗漏名字带这类词的真实综合体，是首版有意限制。061200是专营店，不当便利店。

TEA_DRINK没有被伪造为某个唯一正式高德typecode。0506/0507/0508/0509或精确050000是可能被粗分类的饮品候选；先要求provider结构化字段明确奶茶、茶饮、果茶等，缺失时才使用配置内现代饮品名称/品牌关键词fallback，且classification_source显式NAME_FALLBACK。传统茶馆/茶艺馆没有现代饮品证据时不分类为TEA_DRINK；不使用泛“茶”关键词。明显医院、餐厅、写字楼等typecode不能被名字改成茶饮。咖啡不等于所有饮品。咖啡同时有甜品typecode或structured tag时支持双类，primary仍为CAFE。

primary优先CAFE→TEA_DRINK→DESSERT_ICE_CREAM→RESTAURANT→CONVENIENCE_STORE→RESTROOM→MALL；这只用于同店身份的稳定主类，不是不同品类质量排序。

官方参数及business字段依据[高德搜索POI 2.0文档](https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch)。分类码依据[官方分类下载](https://lbs.amap.com/api/webservice/download)，核验摘录见 `examples/nearby_rest_stops/category_reference.json`。本配置应随provider分类变化单独维护。

## 去重、排序、开放状态

按provider+provider_poi_id全局去重；同ID合并categories，保留一个真实观察，不拼造缺失字段。每个category内稳定排序：OPEN→UNKNOWN/NOT_APPLICABLE→CLOSED；distance升序；同距离rating有值在前、降序；最后service_poi_id。零评分仍是真实值，null没有变为0。CLOSED不按开放状态过滤，仅受半径及结果数量上限限制。

每个类别独立取top limit，将其ID写入category_result_ids，再合并成全局唯一results。category_counts按各类ID列表统计，最大limit；多类门店只在inventory出现一次。不要通过遍历inventory的categories自行截断或重排分类视图。limit是上限，非保证数量。

优先有效非负provider distance，否则Haversine；distance_type显式PROVIDER/HAVERSINE，均不声明为walking距离。为避免不在附近的异常返回，provider距离与实际坐标直线距离均须在请求半径内。

只复用已有today opening parser，周营业描述不猜，厕所无时间时UNKNOWN，不默认24小时开放。Cache保存原观察，每次查询重算open_status；观察日期与上海当前日期不同则不用today hours。

## 缓存 / 边界

复用TTLCache，TTL=300s、LRU容量512、防御性复制；key含provider、完整规范化origin、category、radius、limit。当前不做GPS量化，确保缓存不会改变实际origin距离语义。成功/部分有效页可缓存，失败不缓存；没有坐标/假店名/估计设施fallback。缓存命中不会调用detail。

本阶段不修改TripCommand NLU，不实现带我去、detour、公交/地铁、Weather、Route Reality Check、图片、评论或UI。前端可直接调用本只读能力并展示返回字段。

## Compatibility

推荐类为 `NearbyService`，推荐方法为 `search_nearby_services`。`NearbyRestStopService` 是同类的兼容别名；服务与WorldContextService均保留 `search_nearby_rest_stops(*args, **kwargs)`，统一转发新接口。模型保留ServicePoi/ServicePoiCategory，同时提供NearbyServicePoi/NearbyServiceCategory别名。默认新旧入口均为七类，明确只传旧四类时仍能正常查询。

后续展示分组：FOOD_AND_DRINK（正餐/咖啡/茶饮/甜品），ESSENTIALS（便利店/厕所），REST_AND_SHELTER（商场）。本轮不实现UI，不增加药店、医院、ATM、超市、酒店或其他类别。
