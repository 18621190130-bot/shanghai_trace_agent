"""Export the complete calibrated catalog and five actual route outputs for review."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.demos.demo import EXAMPLES, render_plan
from src import POIRepository, RouteEngine


def export():
    repo = POIRepository()
    raw = repo.get_raw_data()
    engine = RouteEngine(repo)
    plans = {name: engine.generate_route(request) for name, request in EXAMPLES.items()}
    output = ROOT / "examples"
    output.mkdir(exist_ok=True)
    payload = {"examples": {name: plan.to_dict() for name, plan in plans.items()},
               "missing_coordinate_poi_ids": repo.get_missing_coordinate_ids()}
    (output / "route_plans.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    catalog = {"metadata": raw["metadata"], "pois": [
        {key: poi[key] for key in ("id", "display_order", "name", "walk_zone", "poi_type", "visit_profile",
                                   "visit_profile_calibration", "visit_mode_details", "location")} for poi in raw["pois"]]}
    (output / "poi_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "manual_routes.txt").write_text("\n\n".join(render_plan(name, plan, repo) for name, plan in plans.items()) + "\n", encoding="utf-8")
    lines = ["# ShanghaiTrace Phase 1.5B — Final POI and Route Calibration V2", "",
             "交付日期：2026-10-03。27 个运行 POI、四区命名、全部访问模式与节奏已校准；全部 68 项测试通过。没有进入 Phase 2。", "",
             "时间为产品规划估计，不是游客平均停留统计。徐家汇书院采用用户实际体验确认的 15/30/40 分钟，也不推断为总体游客统计。新增第二模式的保守估计已得到用户授权，标记为待人工校准。", "",
             "## 1. 最终目录与全部 visit_profile", "",
             "编号为 display_order，内部 ID 单独列出用于开发核对，不作为游客端地点编号。W=walk_stop，F=full_visit。每组时间为 quick / standard / deep（分钟）；† 表示新增估计，待人工校准。", "",
             "| 显示编号 | 内部 ID | 中文名 | English Name | Zone | poi_type | 默认模式 | W 时间 | F 时间 |",
             "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |"]
    letters = {z["id"]: chr(65 + i) for i, z in enumerate(raw["metadata"]["walk_zones"])}
    for poi in raw["pois"]:
        profile = poi["visit_profile"]
        pending = poi["visit_profile_calibration"]["pending_manual_calibration_modes"]
        def times(mode):
            if mode not in profile["modes"]:
                return "—"
            values = profile["modes"][mode]
            return "/".join(str(values[p]) for p in ("quick", "standard", "deep")) + (" †" if mode in pending else "")
        lines.append(f"| {poi['display_order']} | {poi['id']} | {poi['name']['zh']} | {poi['name']['en']} | {letters[poi['walk_zone']['id']]} | {poi['poi_type']} | {profile['default_mode']} | {times('walk_stop')} | {times('full_visit')} |")
    lines.extend(["", "所有 Supported Modes 就是表中有时间的模式；完整逐项 JSON 见 [poi_catalog.json](examples/poi_catalog.json)，运行数据见 [pois.json](data/pois.json)。没有 flexible 或 recommended_stay。", "",
                  "默认时间保持 Phase 1.5A 建议或本次明确覆盖值。第二模式待校准项：龙美术馆外观、新天地深入、今潮8弄深入、思南公馆深入、一大纪念馆外观、纪念书局深入、1933老场坊深入、西岸美术馆外观、西岸梦中心深入、星美术馆外观。其可达范围也需要人工核验。", "",
                  "## 2. 每个 Walk Zone 的 POI", ""])
    for zone in raw["metadata"]["walk_zones"]:
        names = "、".join(f"#{p.display_order} {p.name_zh}" for p in repo.get_pois_by_zone(zone["id"]))
        lines.extend([f"- **Zone {letters[zone['id']]}：{zone['name_zh']} / {zone['name_en']}**（{zone['poi_count']} 个）；内部区域 ID：`{zone['id']}`。", "", "  " + names, ""])
    lines.extend(["## 3. 访问范围与模式选择", "",
                  "- walk_stop 表示沿途或重点短停；full_visit 表示主要游览目的地，允许 park、street、district，并不隐含建筑入内或购票。", "- 明确的 visit_mode_overrides 优先，否则使用 POI 默认模式；travel_pace 默认为 standard。", "- 因请求明确提供的不可完整参访状态、拒绝已知门票、或时间不足而不可用时，支持 walk_stop 且允许降级的地点可以保留并降级。每个节点保留 requested_visit_mode、selected_visit_mode、downgrade_reason 和具体 scope。", "- 可通过 allow_mode_downgrade=false 坚持完整参访；此时不可行就返回失败，不偷换模式。", "- 豫园 W：商城及周边街区，不购园林票；F：购票入园并包含周边游览。该范围覆盖旧 Phase 1 的园林本体定义。", "- 油罐 W：外观、工业遗产与滨江；F：入场看展。", "- 徐家汇商圈 W：公共空间、短暂商场停留与补给；F：购物、用餐和深入商圈探索。不是单栋商场。", "",
                  "## 4. 坐标与缺失清单", "",
                  "street/district 使用 representative_lat / representative_lng；venue/landmark/park 使用 lat / lng。内部统一近似转换为 GCJ-02。代表点只用于估算接近和站间距离，不代表区域唯一位置、入口、出口或内部完整轨迹。", "",
                  "| 显示编号 | 地点 | 缺项 |", "| ---: | --- | --- |"])
    for pid in repo.get_missing_coordinate_ids():
        poi = repo.get_poi_by_id(pid)
        missing = "纬度" if poi.original_coordinates[1] is not None else "纬度、经度"
        lines.append(f"| {poi.display_order} | {poi.name_zh} | {missing} |")
    if not repo.get_missing_coordinate_ids():
        lines.append("| — | 无：27 个 POI 均有可用坐标 | 无 |")
    lines.extend(["", "本次已补齐此前缺失的五个地点。缺坐标保护逻辑保留，并用人工构造缺失数据的测试验证。", "",
                  "| 补齐地点 | 纬度 | 经度 | 存储坐标体系 | 来源 |", "| --- | ---: | ---: | --- | --- |"])
    for poi in raw["pois"]:
        loc = poi["location"]
        if "coordinate_previous_record" in loc:
            lat = loc.get("representative_lat", loc.get("lat"))
            lng = loc.get("representative_lng", loc.get("lng"))
            lines.append(f"| {poi['name']['zh']} | {lat:.6f} | {lng:.6f} | {loc['coordinate_system']} | [公开地图]({loc['coordinate_source']}) |")
    lines.extend(["", "城隍庙与思南公馆采用高德 POI 锚点；思南公馆是街区代表点，来源地址为复兴中路509号，目录保留523号。中共一大采用历史会址的完整 WGS84 点，原不完整经纬度另存于 coordinate_previous_record，没有拼接不同坐标系；这个锚点不代表新展馆入口。", "",
                  "左联会址取自虹口档案馆公开地图 WM00377，匹配多伦路201弄2号。精确点数据的坐标系尚未获得明确声明，暂按 WGS84 解释并标注 Needs manual coordinate review。星美术馆取自西岸官网 BMap 目的地（BD09：31.193849, 121.476902），近似转为 GCJ-02；原始值随数据保存。全部为地图锚点，未经游客入口实地核验。", "",
                  "新增坐标来源与状态：", "",
                  "- 徐家汇天主堂：采用 [OSM 节点 11224212192 的 Mapcarta 展示位置](https://mapcarta.com/N11224212192)，WGS84 近似锚点，尚未核实游客入口。", "- 徐家汇书院：采用 [OSM 节点 10610507005 的 Mapcarta 展示位置](https://mapcarta.com/N10610507005)，与历史徐家汇藏书楼区分，尚未核实入口。", "- 南京路：采用[公开位置参考](https://opentravelguide.com/china/shanghai/shanghai/attractions/nanjing-road-pedestrian-street/)作为暂定代表点。来源坐标系未核实，暂按 WGS84 解释并明确提示人工复核；不宣称为准确中点。", "- 徐家汇商圈：参考[美罗城 OSM 展示位置](https://mapcarta.com/W225521733)，向港汇方向选取近似公共空间锚点，是产品选择点，未经入口或地理中心核验。", "",
                  "运行代码无联网或地图导航调用；以上只用于本次静态数据校准。旧坐标沿用既有资料及其近似性质。", "",
                  "## 5. 全部测试结果", "",
                  "```text", "python -m unittest discover -s tests -t . -q", "Ran 68 tests in 5.727s", "OK", "```", "",
                  "实际运行环境：Python 3.14.6。原 39 项测试按新区域和模式语义更新保留；新增 29 项校准与边界测试。", "",
                  "| 测试文件 | 测试数 | 结果 |", "| --- | ---: | --- |", "| test_cli.py | 4 | 全通过 |", "| test_geo_utils.py | 2 | 全通过 |", "| test_recommendation.py | 5 | 全通过 |", "| test_repository.py | 6 | 全通过 |", "| test_route_engine.py | 22 | 全通过 |", "| test_visit_calibration.py | 29 | 全通过 |", "",
                  "A–H：书院 F=30；南京路 F=60；徐家汇商圈 W=30/F=90；豫园 W=45/F=90；油罐 W=25/F=75，均通过。还覆盖三档节奏、模式校验、闭馆/门票/预算降级、必去完整性、降级关闭、代表坐标、软站数目标、五次完整输出一致性，以及独立重算预算。", "",
                  "旧豫园 90 分钟不可行测试现明确指定 full_visit 并禁止降级，继续验证最低 105 分钟；默认 walk_stop 的 90 分钟请求则可以成功。这是本次确认后的预期变化。", "",
                  "## 6. 五条人工路线测试输出", "",
                  "以下为用户指定的五组请求的实际程序输出，供人工复核；不是已完成实地体验审核的声明。未提供起点，首站到达前移动不计入预算。全部 standard。完整 JSON 见 [route_plans.json](examples/route_plans.json)，含每站模式、时间、距离、分数、匹配标签、解释与警告；游客可读全文见 [manual_routes.txt](examples/manual_routes.txt)。", "",
                  "| 路线 | 顺序 | 估算 km | 步行 min | 停留 min | 缓冲 min | 总计 / 预算 min | 软站数目标 |", "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |"])
    for index, plan in enumerate(plans.values(), 1):
        stops = " → ".join(f"#{n.display_order} {n.name_zh}（{'W' if n.selected_visit_mode == 'walk_stop' else 'F'}，{n.estimated_stay_minutes:g}）" for n in plan.ordered_pois)
        target = plan.richness_target
        goal = f"{target['min_stops']}–{target['max_stops']}；{'达到' if plan.richness_target_met else '未达到'}"
        lines.append(f"| {index} | {stops} | {plan.total_estimated_distance_km:.3f} | {plan.total_estimated_walking_minutes:.2f} | {plan.total_stay_minutes:g} | {plan.buffer_minutes:g} | {plan.total_estimated_minutes:.2f} / {plan.request['available_minutes']} | {goal} |")
    lines.extend(["", "静态结果检查：", "",
                  "- Route 1：陕南邨 → 永康路 → 建业里 → 徐家汇天主堂 → 徐家汇书院。从原武康—复兴片区进入徐家汇后没有再返回，片区转换一次；在当前坐标估算模型下通过顺序检查。实际入口与道路连通仍待核验。", "- Route 2：鲁迅公园与故居两站。50+30 分钟停留加移动和缓冲后为 101.43 分钟，剩余 18.57 分钟不足以加入现有相关候选。未达到 3–4 站软目标，保留警告。", "- Route 3：油罐外观 → 西岸美术馆外观 → 龙美术馆完整参访。西岸美术馆因剩余时间不足从默认 full_visit 降为 walk_stop，已记录；该外观时间为待校准估计，不宣称实际看过两座美术馆展览。未达到 4–5 站软目标。", "- Route 4：外滩 → 南京路 → 新天地。南京路合理纳入且为 full_visit 60 分钟；总计 177.28 分钟，预算余量较小。其他符合当前兴趣的候选无法在预算内插入，未硬凑四站。", "- Route 5：永康路 → 徐家汇商圈。商圈以默认 walk_stop 30 分钟进入；其他可规划候选没有请求的购物/现代城市兴趣匹配，不用建筑文化点凑站数。完整购物目的地体验应显式指定商圈 full_visit=90。", "",
                  "## 7. Route Engine 当前行为和限制", "",
                  "- 时间来自 selected mode × travel_pace，不再取旧停留区间中值；默认模式与用户覆盖均有可追溯记录。", "- 必去点先安排；小规模访问顺序可穷举优化，插入候选时重新核算总预算，最多五个节点的候选集合按最短估算开放路径排序，减少片区来回跳跃。", "- 相关性先过滤：给定 interest_tags 时可选点至少匹配一个兴趣；没有兴趣标签时至少匹配一个已给体验或文化标签；全空请求才不做标签过滤。必去不受此软相关性限制。", "- 站数目标为 ≤90 分钟 2–3 站、91–150 分钟 3–4 站、151–240 分钟 4–5 站。选择优先趋向目标上沿，不能突破预算或删除必去；必去数量可超过目标上沿。未达到就提示。", "- 联合模式/点集/区域选择仍是启发式：不会为了提高站数主动降级已经可行的完整参访，也不全局替换已选点；软目标未达到不等于证明不存在更多站方案。", "- 直线距离乘固定绕行因子不识别街道、围墙、过街、入口或交通。区域型 POI 内部移动包含在参访体验中，但未单独计入估算移动里程；无法保证真实累计步行上限。", "- 闭馆依赖 full_visit_unavailable_poi_ids 的明确输入，不解析日期/开放时间文字，不检查实时状态；外部 walk_stop 可达性也未实时验证。", "- 门票与预约未知仍提示；willing_to_buy_tickets=false 只处理已知需要门票的模式，不把 full_visit 一律当作收费。", "- 跨区仅由必去触发，全程按步行估计；既有符号跨区惩罚未随意赋值。超过八个必去点的搜索失败不冒充不可行证明。", "- 临时代表坐标与十项第二模式时间需要后续人工核验。自动测试不能证明现实游客体验已经合格。", "",
                  "## 8. 文件变更", "",
                  "修改：data/pois.json；src/models.py、poi_repository.py、route_engine.py、__init__.py；tools/demos/demo.py；examples/request.json、route_plans.json；tests/helpers.py、test_repository.py、test_recommendation.py、test_route_engine.py、test_cli.py；README.md、CONTEXT.md 与历史记录提示。", "",
                  "新增：src/visit_planner.py；tests/test_visit_calibration.py；scripts/calibrate_phase15b.py、export_phase15b_audit.py；本报告；examples/poi_catalog.json、manual_routes.txt；data/archive/pois_phase1.json、examples/phase1/route_plans_phase1.json。旧原始 v1/v2/v3 文件保留作为历史来源，不参与当前运行；当前核心集合完全移除两个旧 POI。", "",
                  "本阶段完成并停止，不接入 LLM、OpenAI API、Agent Framework、RAG、数据库服务器或前端重构。"])
    (ROOT / "docs/history/phase1/PHASE15B_CALIBRATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Exported 27 POI profiles, four zone lists, five complete route plans and calibration report.")


if __name__ == "__main__":
    export()
