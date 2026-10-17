"""Explicit per-node product judgments, never a role inference from ID or fame."""
import json
from pathlib import Path

DECISIONS={
'p2':('transition_stop','medium','街口的核心体验是街景与日常活动观察；现有访问范围仅短时公共空间观察，主要连接衡复街道节点，不足以独立承担目的地主题。'),
'p11':('supporting_stop','medium','门、弄堂和天井构成明确的住宅空间观察体验，值得主动绕入；现有短时外观范围不支持作为整条路线核心，避免把酒店内部当作可自由参观空间。'),
'p12':('transition_stop','medium','既有体验限定于入口与立面细节，短暂停留提供街道连续性；没有更大独立访问范围的证据，不承担核心目的地。'),
'p13':('supporting_stop','medium','船形转角立面与路口形态提供独立建筑观察价值；既有范围是短时外观观察，没有把知名度转换为主题承担能力，故不列anchor。'),
'p21':('anchor','high','既有来源支持人物长期生活及国务活动住所，完整参访可持续展开人物、近现代史与居住空间体验；适合作为明确目的地组织周边路线。'),
'p32':('anchor','medium','用户确认的教堂建筑外观及可选深入参访，提供完整宗教建筑与徐家汇文化主题观察；即使入内未知仍有明确目的地体验，但不保证当前开放。'),
'p33':('supporting_stop','medium','用户确认的短时入内与公共阅读空间观察有独立文化体验，可补充徐家汇建筑主题；当前证据不支持将其当作路线的主要目的地。'),
'p35':('supporting_stop','medium','既有范围明确是多栋商业空间及其间公共空间的区域观察，有整体城市生活体验；并非普通商铺，但默认短时商圈观察不承担文化路线核心。'),
'p7':('anchor','medium','石库门街巷肌理与商业再利用形成可独立持续探索的整体街区，可用完整访问范围承担城市更新主题；不是因购物或production身份判定。'),
'p9':('anchor','medium','既有完整历史建筑群保存与重新使用的观察体验具有独立目的地范围，能围绕保护和再利用组织主题；依赖街区公共范围，非入店购物。'),
'p14':('anchor','medium','既有外滩节点同时涵盖临江历史建筑界面、河流与对岸天际线的对照观察，可独立展开上海历史与现代城市主题；不再拆广场和雕像为新站。'),
'p15':('anchor','medium','用户确认的街区游览以及可选完整园林参访，分别具有持续探索范围；能承担老城商业与园林主题，明确walk_stop不含购票园林。'),
'p20':('anchor','high','官方支持的道教宫观及完整参访范围可以独立阐释城隍信仰与传统城市，具有专门宗教文化目的地价值；与周边商城观察区分。'),
'p23':('supporting_stop','high','历史住宅建筑群与保护再利用提供独立街区体验，值得主动加入；在此产品的默认短时外观范围内主要补充周边历史和更新主题。'),
'p24':('anchor','high','既有官方支持的纪念馆完整参访可以持续展开政治史与石库门城市空间关系，具备独立主目的地价值；外观模式不改变审定角色。'),
'p34':('anchor','medium','用户明确确认核心步行路段作为完整目的地，持续的商业建筑和街道观察能够承担城市商业史主题；不以普通商店数量增加路线站点。'),
'p4':('anchor','medium','故居作为文学人物具体生活空间，结合既有完整参访范围可承担鲁迅文学主题；周边街巷作为理解背景，不将每个内部居所再拆站。'),
'p10':('supporting_stop','medium','旧弄堂与新文化功能并置，提供独立再利用观察体验，可连接四川北路其他目的地；现有证据不足以将其设为全路线核心。'),
'p16':('anchor','medium','既有完整公园参访范围支持持续公共生活观察、步行与文学背景体验，能独立承担社区公园主题；内部纪念设施不重复计站。'),
'p25':('supporting_stop','high','旧址阅读和文化交流网络有具体独立体验，可有目的地补充鲁迅主题；与故居和街区相辅，不凭书店类别或历史名气升级anchor。'),
'p26':('supporting_stop','high','官方支持的文学组织旧址和完整短时参访能解释作家网络，适合文学路线重点补充；现有资料支持专题站而非一般路线核心。'),
'p27':('anchor','high','原工业建筑的坡道、廊桥与空间流线构成可持续独立探索的完整建筑体验，能承担工业空间再利用主题；内部商户和展厅不独立增站。')}

def main():
 rows={pid:dict(primary_role=role,eligible_roles=[role],role_confidence=confidence,role_reason=reason,
   independent_destination_value='high' if role=='anchor' else 'medium' if role=='supporting_stop' else 'low',
   citywalk_experiential_value='high' if role=='anchor' else 'medium') for pid,(role,confidence,reason) in DECISIONS.items()}
 path=Path(__file__).resolve().parents[1]/'data/poi_pipeline/existing_role_decisions.json'
 path.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
