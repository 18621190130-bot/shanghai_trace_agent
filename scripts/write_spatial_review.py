"""Render the full regional spatial inventory for project owner acceptance."""
from pathlib import Path
from src import POIRepository


def main():
    repo=POIRepository();lines=['# Spatial Profile Review — Phase 3B_2.2','',
        '58 Core：26 POINT、27 AREA、5 LINEAR。下表覆盖全部 32 个 AREA/LINEAR。所有坐标为纬度、经度，GCJ02。', '',
        '范围是首版 City Walk 体验范围，非行政边界、精确地籍或开放许可；没有伪装为 PROVIDER 的边界。CORE_EXISTING anchor 保留现有访问点并记录同主体地图匹配的偏移，不由 extent 求几何中心。', '',
        'Reviewed=false 仅表示负责人尚未完成本次空间产品验收；不表示缺少必需字段。所有 32 项已通过模型校验。Identity 的授权确认状态独立。', '',
        '| Core | Spatial Type | Anchor lat, lng | Anchor Source / Confidence | Extent Type | Extent Source / Confidence | Reviewed |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    regional=[]
    for poi in repo.get_all_pois():
        row=repo.get_spatial_profile(poi.id)
        if row['spatial_type']=='POINT':continue
        regional.append((poi,row));a=row['route_anchor'];e=row['spatial_extent']
        desc=e['type']+(f" ({e['radius_m']}m)" if e['type']=='CENTER_RADIUS' else '')
        lines.append(f"| {poi.id} {poi.name_zh} | {row['spatial_type']} | {a['lat']:.6f}, {a['lng']:.6f} | {a['source']} / {a['confidence']} | {desc} | {e['extent_source']} / {e['extent_confidence']} | false |")
    lines.extend(['','## 重点验收项','',
        '徐家汇商圈的矩形 polygon 限定美罗城、港汇及相邻教堂前公共空间核心片区，不代表更广的徐家汇中央活动区。', '',
        '南京路西侧 anchor 是观光车位置旁的公共步行起点，不要求乘车或买票；多伦路使用文化街牌坊入口；甜爱路采用四川北路至甜爱支路首版体验段；武康路、福州路使用道路端点。secondary anchor 当前不增加路线内部步行用时。', '',
        '新天地北里、外滩陈毅广场及西岸主要开放空间使用现有访问点和明确的体验半径。半径只描述访问点附近的首版体验范围；例如跑道公园 350m 圆不声称覆盖整条跑道。产品若要求完整公园边界，需以后另取边界，当前没有自动 geofence。', '',
        '真正仍需负责人选择的是上述体验范围及入口是否符合产品希望的游览段；没有遗留 AMBIGUOUS 身份，也不需为徐家汇选择一个替代商场身份。其余字段与坐标规范化已自动完成。', ''])
    for poi,row in regional:
        a=row['route_anchor'];e=row['spatial_extent'];lines.extend([f'## {poi.id} {poi.name_zh}', '',
            f"Anchor：{a.get('name','')}；{a['notes']}", '', f"Extent：{e['notes']}", ''])
        if row.get('secondary_anchor'):
            b=row['secondary_anchor'];lines.extend([f"Secondary：{b['lat']}, {b['lng']}；{b.get('name','')}；{b['notes']}", ''])
    Path('SPATIAL_PROFILE_REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
