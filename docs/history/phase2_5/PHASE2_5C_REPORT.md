# PHASE2_5C_REPORT

## 1. Candidate KB summary

candidate POIs=35，West Bund=13；8个新节点、5个既有anchors。candidate_kb_status=ready_for_promotion。production pois.json 未覆盖。

route-role distribution={'anchor': 5, 'supporting_stop': 6, 'transition_stop': 2}。

**确定性验收检查通过不等于8条请求都成功**：7条完整路线成功，A纯art/no-museums正确返回composition_failure；不伪造anchor或添加低相关Gate M。

## 2. Final West Bund 13 nodes

| ID | 名称 | primary | eligible | interest / experience / culture |
| --- | --- | --- | --- | --- |
| p5 | 龙美术馆（西岸馆） | anchor | anchor, supporting_stop | architecture, art, industrial_heritage, waterfront / adaptive_reuse, museum_visit, photogenic, riverside_walk / industrial_transformation, modern_shanghai, urban_renewal |
| p28 | 西岸美术馆 | anchor | anchor, supporting_stop | architecture, art, waterfront / museum_visit, photogenic, riverside_walk / industrial_transformation, modern_shanghai, urban_renewal |
| p29 | 上海油罐艺术中心 | anchor | anchor, supporting_stop | architecture, art, industrial_heritage, waterfront / adaptive_reuse, museum_visit, photogenic, riverside_walk / industrial_transformation, modern_shanghai, urban_renewal |
| p30 | Gate M 西岸梦中心 | anchor | anchor, supporting_stop | industrial_heritage, modern_city, shopping_lifestyle, waterfront / adaptive_reuse, photogenic, riverside_walk, shopping_leisure / industrial_transformation, modern_shanghai, urban_renewal |
| p31 | 星美术馆 | anchor | anchor, supporting_stop | architecture, art, industrial_heritage / adaptive_reuse, architecture_detail, museum_visit / industrial_transformation, modern_shanghai, urban_renewal |
| p36 | 西岸艺术中心 | supporting_stop | supporting_stop | architecture, art, industrial_heritage / adaptive_reuse, architecture_detail / industrial_transformation |
| p37 | 西岸穹顶艺术中心（含北广场） | supporting_stop | supporting_stop | art / — / — |
| p38 | 滨江滑板公园 | supporting_stop | supporting_stop | parks, waterfront / riverside_walk, social_observation / public_life |
| p39 | 徐汇跑道公园 | supporting_stop | supporting_stop | history, parks / adaptive_reuse, street_scene / urban_renewal |
| p40 | 上海摄影艺术中心 | supporting_stop | supporting_stop | architecture, art / museum_visit / — |
| p42 | 徐汇滨江海事塔广场 | transition_stop | transition_stop | waterfront / riverside_walk / — |
| p43 | 北票码头塔吊 | transition_stop | transition_stop | industrial_heritage, waterfront / riverside_walk / — |
| p41 | 西岸大剧院 | supporting_stop | supporting_stop | art / — / — |

## 3. New stable IDs

| Staging identity | Candidate production ID |
| --- | --- |
| route:art_center | p36 |
| route:dome | p37 |
| route:skate | p38 |
| route:runway | p39 |
| route:photography | p40 |
| route:wb_7ca7f91efb488c29 | p41 |
| route:wb_72b583ec31ffce20 | p42 |
| route:wb_fd436a54b9d249a2 | p43 |

已有ID最高已为p35，因此显式分配p36–p43；ID映射常量按identity版本化，不按当前数组位置生成。重排staging不改变ID。

## 4. Route-role implementation

POIRepository验证route_role.primary/eligible；POI.effective_primary_role和RouteStop.effective_primary_role暴露审定角色。旧节点缺少角色时返回None，不隐式猜测anchor。访问模式不改变角色。

## 5. Composition rule

candidate defaults显式启用west_bund，仅plan_for_me/surprise_me执行：至少1 anchor、至少2 anchor/supporting；Minimum Viable City Walk仍为3站。几何、avoid、must-go优先。违规路线可在原质量/预算门槛内作一次独立节点插入或替换，找不到则composition_failure，保留所选相关节点和明确诊断。
超过2个连续transition仅为软偏好：只在等距离排序中优先选择较短连续串，不为了组成拉长路程或添加节点。
西岸局部质量修正沿用_relevant的核心兴趣OR语义：多兴趣命中用于排序，单个真实核心兴趣匹配不被最高分种子的多标签分母隐式否决。核心比较仍要求真实请求标签；距离增长、边际步行、预算及负面偏好门槛保留。不是修改标签或角色。

## 6. Backward compatibility

production配置未开启composition，因此原数据及其路线行为保留。其他三个zone的POI JSON逐字段保持一致；固定显式zone请求与Phase 2 production基线的状态、所选ID/模式、总时间一致。Places in mind西岸保留显式选择集合，不暗加anchor；两座transition也可生成明确选择的轻量路线，composition.enabled=false。

## 7. Tag coverage before → after

### interest_tags

| tag | Phase 2 | Candidate |
| --- | ---: | ---: |
| history | 0 | 1 |
| architecture | 4 | 6 |
| local_life | 0 | 0 |
| literature | 0 | 0 |
| art | 4 | 8 |
| industrial_heritage | 4 | 6 |
| waterfront | 4 | 7 |
| religion | 0 | 0 |
| parks | 0 | 2 |
| modern_city | 1 | 1 |
| modern_china_history | 0 | 0 |
| music | 0 | 0 |
| gardens | 0 | 0 |
| shopping_lifestyle | 1 | 1 |

### experience_tags

| tag | Phase 2 | Candidate |
| --- | ---: | ---: |
| iconic_landmark | 0 | 0 |
| neighborhood_walk | 0 | 0 |
| street_scene | 0 | 1 |
| local_atmosphere | 0 | 0 |
| museum_visit | 4 | 5 |
| photogenic | 4 | 4 |
| quiet_walk | 0 | 0 |
| adaptive_reuse | 4 | 6 |
| riverside_walk | 4 | 7 |
| bookish | 0 | 0 |
| social_observation | 0 | 1 |
| architecture_detail | 1 | 2 |
| shopping_leisure | 1 | 1 |

### culture_tags

| tag | Phase 2 | Candidate |
| --- | ---: | ---: |
| old_city | 0 | 0 |
| shikumen | 0 | 0 |
| lane_life | 0 | 0 |
| modern_shanghai | 5 | 5 |
| literary_shanghai | 0 | 0 |
| religious_culture | 0 | 0 |
| sino_foreign_exchange | 0 | 0 |
| political_history | 0 | 0 |
| industrial_transformation | 5 | 6 |
| urban_renewal | 5 | 6 |
| garden_culture | 0 | 0 |
| public_life | 0 | 1 |
| music_culture | 0 | 0 |

non-museum art nodes：0 → 3；无尽影院没有计入。

## 8. Eight deterministic route regression cases

| Case | Status | Pool before / eligible / relevant | Stops | Minimum | Composition | Avoid | Total min | Utilization | Failure cause |
| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | --- |
| A | composition_failure | 13/8/3 | 3 | True | False | True | 121.3 | 67.4% | route_role_composition |
| B | success | 13/13/8 | 4 | True | True | True | 144.2 | 96.1% | — |
| C | success | 13/13/9 | 5 | True | True | True | 169.1 | 94.0% | — |
| D | success | 13/13/8 | 5 | True | True | True | 176.6 | 98.1% | — |
| E | success | 13/13/7 | 4 | True | True | True | 130.8 | 87.2% | — |
| F | success | 13/13/12 | 4 | True | True | True | 179.1 | 99.5% | — |
| G | success | 13/8/5 | 5 | True | True | True | 154.4 | 85.8% | — |
| H | success | 13/8/8 | 5 | True | True | True | 137.4 | 76.3% | — |

### Case A: art; no museums

request=`{"available_minutes": 180, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["art"], "experience_tags": [], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": ["museum_visit"], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['art'], 'experience_tags': [], 'culture_tags': []}；avoid=['museum_visit']；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p30', 'p36', 'p37', 'p38', 'p39', 'p42', 'p43', 'p41']；relevant=['p36', 'p37', 'p41']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p36 | 西岸艺术中心 | supporting_stop | {'interest_tags': ['art'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |
| p37 | 西岸穹顶艺术中心（含北广场） | supporting_stop | {'interest_tags': ['art'], 'experience_tags': [], 'culture_tags': []} | full_visit | 60.0 |
| p41 | 西岸大剧院 | supporting_stop | {'interest_tags': ['art'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |

failure reason=['requires an anchor and at least two anchor/supporting stops']；max estimated leg km=0.7053766410975693。

### Case B: parks + waterfront + public life

request=`{"available_minutes": 150, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["parks", "waterfront"], "experience_tags": [], "culture_tags": ["public_life"], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": [], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['parks', 'waterfront'], 'experience_tags': [], 'culture_tags': ['public_life']}；avoid=[]；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；relevant=['p5', 'p28', 'p29', 'p30', 'p38', 'p39', 'p42', 'p43']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p38 | 滨江滑板公园 | supporting_stop | {'interest_tags': ['parks', 'waterfront'], 'experience_tags': [], 'culture_tags': ['public_life']} | walk_stop | 15.0 |
| p5 | 龙美术馆（西岸馆） | anchor | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | full_visit | 75.0 |
| p43 | 北票码头塔吊 | transition_stop | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |
| p42 | 徐汇滨江海事塔广场 | transition_stop | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |

failure reason=[]；max estimated leg km=0.6672344794431618。

### Case C: industrial heritage + waterfront

request=`{"available_minutes": 180, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["industrial_heritage", "waterfront"], "experience_tags": [], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": [], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []}；avoid=[]；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；relevant=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p38', 'p42', 'p43']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p30 | Gate M 西岸梦中心 | anchor | {'interest_tags': ['industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 30.0 |
| p29 | 上海油罐艺术中心 | anchor | {'interest_tags': ['industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 25.0 |
| p28 | 西岸美术馆 | anchor | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |
| p43 | 北票码头塔吊 | transition_stop | {'interest_tags': ['industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |
| p5 | 龙美术馆（西岸馆） | anchor | {'interest_tags': ['industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 25.0 |

failure reason=[]；max estimated leg km=1.979253968673333。

### Case D: architecture + art + photography-related viewing

request=`{"available_minutes": 180, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["architecture", "art"], "experience_tags": ["photogenic"], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": [], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['architecture', 'art'], 'experience_tags': ['photogenic'], 'culture_tags': []}；avoid=[]；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；relevant=['p5', 'p28', 'p29', 'p31', 'p36', 'p37', 'p40', 'p41']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p36 | 西岸艺术中心 | supporting_stop | {'interest_tags': ['architecture', 'art'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |
| p40 | 上海摄影艺术中心 | supporting_stop | {'interest_tags': ['architecture', 'art'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |
| p28 | 西岸美术馆 | anchor | {'interest_tags': ['architecture', 'art'], 'experience_tags': ['photogenic'], 'culture_tags': []} | full_visit | 75.0 |
| p29 | 上海油罐艺术中心 | anchor | {'interest_tags': ['architecture', 'art'], 'experience_tags': ['photogenic'], 'culture_tags': []} | walk_stop | 25.0 |
| p37 | 西岸穹顶艺术中心（含北广场） | supporting_stop | {'interest_tags': ['art'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |

failure reason=[]；max estimated leg km=0.44332853829981694。

### Case E: modern city + waterfront

request=`{"available_minutes": 150, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["modern_city", "waterfront"], "experience_tags": [], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": [], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['modern_city', 'waterfront'], 'experience_tags': [], 'culture_tags': []}；avoid=[]；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；relevant=['p5', 'p28', 'p29', 'p30', 'p38', 'p42', 'p43']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p30 | Gate M 西岸梦中心 | anchor | {'interest_tags': ['modern_city', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 30.0 |
| p29 | 上海油罐艺术中心 | anchor | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 25.0 |
| p28 | 西岸美术馆 | anchor | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |
| p42 | 徐汇滨江海事塔广场 | transition_stop | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |

failure reason=[]；max estimated leg km=1.3817039421059352。

### Case F: art + waterfront + industrial heritage

request=`{"available_minutes": 180, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["art", "waterfront", "industrial_heritage"], "experience_tags": [], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": [], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['art', 'industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []}；avoid=[]；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；relevant=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p40', 'p42', 'p43', 'p41']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p29 | 上海油罐艺术中心 | anchor | {'interest_tags': ['art', 'industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 25.0 |
| p36 | 西岸艺术中心 | supporting_stop | {'interest_tags': ['art', 'industrial_heritage'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |
| p43 | 北票码头塔吊 | transition_stop | {'interest_tags': ['industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |
| p5 | 龙美术馆（西岸馆） | anchor | {'interest_tags': ['art', 'industrial_heritage', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | full_visit | 75.0 |

failure reason=[]；max estimated leg km=1.9994773497669245。

### Case G: waterfront + parks; no museums

request=`{"available_minutes": 180, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": ["waterfront", "parks"], "experience_tags": [], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": ["museum_visit"], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': ['parks', 'waterfront'], 'experience_tags': [], 'culture_tags': []}；avoid=['museum_visit']；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p30', 'p36', 'p37', 'p38', 'p39', 'p42', 'p43', 'p41']；relevant=['p30', 'p38', 'p39', 'p42', 'p43']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p30 | Gate M 西岸梦中心 | anchor | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 30.0 |
| p39 | 徐汇跑道公园 | supporting_stop | {'interest_tags': ['parks'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |
| p42 | 徐汇滨江海事塔广场 | transition_stop | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |
| p43 | 北票码头塔吊 | transition_stop | {'interest_tags': ['waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 10.0 |
| p38 | 滨江滑板公园 | supporting_stop | {'interest_tags': ['parks', 'waterfront'], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |

failure reason=[]；max estimated leg km=1.3801518857310233。

### Case H: three-hour West Bund; no theme; no museums

request=`{"available_minutes": 180, "start_lat": null, "start_lng": null, "start_coordinate_system": "GCJ-02", "interest_tags": [], "experience_tags": [], "culture_tags": [], "must_go_poi_ids": [], "preferred_zone": "west_bund", "max_walking_km": null, "avoid_crowds": false, "environment_preference": null, "travel_pace": "standard", "visit_mode_overrides": {}, "full_visit_unavailable_poi_ids": [], "willing_to_buy_tickets": true, "allow_mode_downgrade": true, "avoid_tags": ["museum_visit"], "avoid_poi_ids": [], "route_mode": "plan_for_me"}`

matched={'interest_tags': [], 'experience_tags': [], 'culture_tags': []}；avoid=['museum_visit']；before=['p5', 'p28', 'p29', 'p30', 'p31', 'p36', 'p37', 'p38', 'p39', 'p40', 'p42', 'p43', 'p41']；eligible=['p30', 'p36', 'p37', 'p38', 'p39', 'p42', 'p43', 'p41']；relevant=['p30', 'p36', 'p37', 'p38', 'p39', 'p42', 'p43', 'p41']

| ID | Stop | Primary role | Matched tags | Visit mode | Product visit estimate min |
| --- | --- | --- | --- | --- | ---: |
| p30 | Gate M 西岸梦中心 | anchor | {'interest_tags': [], 'experience_tags': [], 'culture_tags': []} | walk_stop | 30.0 |
| p41 | 西岸大剧院 | supporting_stop | {'interest_tags': [], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |
| p37 | 西岸穹顶艺术中心（含北广场） | supporting_stop | {'interest_tags': [], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |
| p36 | 西岸艺术中心 | supporting_stop | {'interest_tags': [], 'experience_tags': [], 'culture_tags': []} | walk_stop | 15.0 |
| p39 | 徐汇跑道公园 | supporting_stop | {'interest_tags': [], 'experience_tags': [], 'culture_tags': []} | walk_stop | 20.0 |

failure reason=[]；max estimated leg km=0.7053766410975693。

A有3个真实non-museum art supporting stops，minimum_stop_count_passed=true、route_composition_passed=false。当前唯一non-museum anchor Gate M没有art标签，因此不能用于纯art补位。该问题来自审定角色组成约束，不是缺少三站，也不是当前边界空间空洞。

### Strong-theme baseline comparison

| Case | Phase 2 status / stops / max leg | Candidate status / stops / max leg |
| --- | --- | --- |
| C | success / 3 / 2.820090553579782 | success / 5 / 1.979253968673333 |
| F | success / 3 / 2.383285469796842 | success / 4 / 1.9994773497669245 |

## 9. Three-mode regression

| Mode | Status | Stop IDs | Composition enabled |
| --- | --- | --- | --- |
| plan_for_me | success | ['p30', 'p39', 'p42', 'p43', 'p38'] | True |
| places_in_mind | success | ['p42', 'p43'] | False |
| surprise_me | success | ['p41', 'p30', 'p37', 'p36', 'p43'] | True |

## 10. Optional real DeepSeek smoke tests

status=completed；calls=3。
- I have three hours to explore art in the West Bund but I do not want to visit museums.：contract=contract_passed；route status=composition_failure；provider metadata={'model': 'deepseek-flash', 'finish_reason': 'stop', 'usage': {'prompt_tokens': 2541, 'completion_tokens': 114, 'total_tokens': 2655, 'prompt_tokens_details': {'cached_tokens': 896}, 'prompt_cache_hit_tokens': 896, 'prompt_cache_miss_tokens': 1645}}；error=None。
- Give me a three-hour outdoor West Bund walk with river views and public spaces. No museums.：contract=contract_passed；route status=success；provider metadata={'model': 'deepseek-flash', 'finish_reason': 'stop', 'usage': {'prompt_tokens': 2540, 'completion_tokens': 180, 'total_tokens': 2720, 'prompt_tokens_details': {'cached_tokens': 2304}, 'prompt_cache_hit_tokens': 2304, 'prompt_cache_miss_tokens': 236}}；error=None。
- I have three hours in the West Bund and want to understand Shanghai industrial past while walking along the river.：contract=contract_passed；route status=success；provider metadata={'model': 'deepseek-flash', 'finish_reason': 'stop', 'usage': {'prompt_tokens': 2542, 'completion_tokens': 222, 'total_tokens': 2764, 'prompt_tokens_details': {'cached_tokens': 2304}, 'prompt_cache_hit_tokens': 2304, 'prompt_cache_miss_tokens': 238}}；error=None。

真实smoke只验证provider→RouteIntent→Engine契约，仍保留真实澄清/组成失败，不能将其误报为完整路线成功。最多3条、每条1次、无retry，未进行enrichment。

## 11. Geographic distribution

{
  "bands": {
    "north": [
      "p5",
      "p31",
      "p38",
      "p43"
    ],
    "central": [
      "p42"
    ],
    "south": [
      "p28",
      "p29",
      "p30",
      "p36",
      "p37",
      "p39",
      "p40",
      "p41"
    ]
  },
  "largest_latitude_gap_km": 0.9956847999999155,
  "basis": "approximate representative points; not actual pedestrian connectivity; no geographic failure inferred from distribution alone"
}

north纬度>=31.18，central 31.17–31.18，south<31.17；仅表示13个代表点的分布。没有依据从较多south点推导断路/不可达。跑道与大剧院点仍如实保留既有审核缓冲身份，未移动坐标凑polygon。

## 12. zone_expansion_diagnostic

```json
{
  "status": "evaluated",
  "zone_expansion_recommended": false,
  "theme_failure_count": 1,
  "insufficient_route_count": 0,
  "composition_failure_count": 1,
  "candidate_pool_sizes": {
    "A": {
      "before": 13,
      "after": 8,
      "relevant": 3
    },
    "B": {
      "before": 13,
      "after": 13,
      "relevant": 8
    },
    "C": {
      "before": 13,
      "after": 13,
      "relevant": 9
    },
    "D": {
      "before": 13,
      "after": 13,
      "relevant": 8
    },
    "E": {
      "before": 13,
      "after": 13,
      "relevant": 7
    },
    "F": {
      "before": 13,
      "after": 13,
      "relevant": 12
    },
    "G": {
      "before": 13,
      "after": 8,
      "relevant": 5
    },
    "H": {
      "before": 13,
      "after": 8,
      "relevant": 8
    }
  },
  "non_museum_route_success": {
    "A": false,
    "G": true,
    "H": true
  },
  "parks_public_space_route_success": {
    "B": true,
    "G": true,
    "H": true
  },
  "geographic_gap_indicators": {
    "bands": {
      "north": [
        "p5",
        "p31",
        "p38",
        "p43"
      ],
      "central": [
        "p42"
      ],
      "south": [
        "p28",
        "p29",
        "p30",
        "p36",
        "p37",
        "p39",
        "p40",
        "p41"
      ]
    },
    "largest_latitude_gap_km": 0.9956847999999155,
    "basis": "approximate representative points; not actual pedestrian connectivity; no geographic failure inferred from distribution alone"
  },
  "basis": "Majority of failures explicitly attributed to quality node shortage/geographic gaps; unknown and algorithm causes count against expansion.",
  "candidate_pool_size_per_case": {
    "A": {
      "before": 13,
      "after": 8,
      "relevant": 3
    },
    "B": {
      "before": 13,
      "after": 13,
      "relevant": 8
    },
    "C": {
      "before": 13,
      "after": 13,
      "relevant": 9
    },
    "D": {
      "before": 13,
      "after": 13,
      "relevant": 8
    },
    "E": {
      "before": 13,
      "after": 13,
      "relevant": 7
    },
    "F": {
      "before": 13,
      "after": 13,
      "relevant": 12
    },
    "G": {
      "before": 13,
      "after": 8,
      "relevant": 5
    },
    "H": {
      "before": 13,
      "after": 8,
      "relevant": 8
    }
  },
  "failure_causes": {
    "route_role_composition": 1,
    "quality_node_shortage": 0,
    "scoring_or_budget_constraint": 0
  },
  "missing_themes": [
    "art-only non-museum anchor eligibility"
  ],
  "actual_blocker": "pure art/no museums has sufficient supporting nodes but no relevant audited anchor",
  "recommended_expansion_direction": null,
  "missing_geographic_segment": null,
  "recommendation": "Do not expand zone to solve an audited-role composition conflict; independently review policy/theme semantics first."
}
```

多个请求的数据供给/空间缺口失败才可建议扩zone。本轮唯一失败为route_role_composition，所以推荐false；无新增collection、无扩边界。

## 13. Full test results

{
  "command": "python -m unittest discover -s tests -t . -q",
  "status": "passed",
  "exit_code": 0,
  "tests_run": 317,
  "elapsed_seconds": 10.645,
  "input_digest": "934dad51c101246d5138e89177527f76513d52af02be6bc12d2be71f08be8211"
}

protected unchanged=True；production SHA256=6585b3baf653ae89cc6a1e3c5fc10140bdd801fb298d92c392381d0b5fc17513。

## 14. Known limitations

- A纯art/no-museums没有审定anchor；应独立讨论组成政策或主题拓宽，不为了过测试修改role。
- 停留时间为product estimate；真实演出、开放、票务、预约与内部访问范围未实时核实。full_visit不保证可入内。
- 距离为Haversine×配置绕行系数；没有真实街道routing。
- 少数路线时间利用率高于95%，仍在硬预算内；70–95%为软偏好，没有为填时间加入低相关点。
- 没有把defer/internal对象加回。无尽影院reject_current_pilot保留历史证据，active conditional列表为空；旧Phase 2.5B报告保留为历史记录。
- 单步composition修复是轻量启发式，不承诺搜索所有合法路线；失败不自动断言数据不足。

## 15. Files modified

- src/models.py、poi_repository.py、intent_adapter.py、route_engine.py：兼容角色与显式zone/mode gating。
- 新增src/route_composition.py、src/west_bund_regression.py、src/poi_pipeline/candidate_kb.py。
- 新增scripts/export_phase2_5c.py、tests/test_phase2_5c.py。
- 新增data/pois_phase2_5_candidate.json及data/poi_pipeline/phase2_5c/验收、映射/归档、测试和smoke证据。
- 新增本报告；README增加候选运行说明。

## 16. Exact commands to reproduce

```powershell
python scripts/export_phase2_5c.py --run-tests
python -m unittest discover -s tests -t . -q
# Optional paid provider smoke (up to three calls; requires process DEEPSEEK_API_KEY)
python scripts/export_phase2_5c.py --live-smoke
```

默认POIRepository仍使用production；候选使用POIRepository("data/pois_phase2_5_candidate.json")，再交给现有RouteEntryService/RouteEngine。导出不覆盖production。

PHASE 2.5C STATUS: PASS

STOP：等待人工验收；不promotion，不扩zone，不开始Phase 3。
