"""Bounded product review decisions; tags remain evidence-driven."""
from scripts.recall_review_data import SOURCES as F_SOURCES

# Each zone has six repair candidates. No successful node is re-enriched.
SELECTED={
 'old_city_central':['上海人民广场','福州路','中国社会主义青年团中央机关旧址','大韩民国临时政府旧址','徐光启故居(九间楼)','东海大楼'],
 'wukang_fuxing_xujiahui':['优秀历史建筑乌鲁木齐南路176号','中南新邨','盛宣怀住宅','张乐平','上海交响乐团音乐厅','徐家汇公园'],
 'hongkou_literary':['李白烈士故居','沈尹默故居','日本海军特别陆战队司令部旧址','四川北路文化中心图书馆','上海多伦路地区海派文化馆(多伦生活广场店)','上海多伦现代美术馆']}

# Short, inspected subject excerpts; dates/hours are not made evergreen facts.
SOURCES={
 '上海人民广场':[
 ('https://cgzf.sh.gov.cn/cmsres/93/93019f9cb5d44c08933f17508a226ea6/6db9509e42251bc6063c5b003b6e8ff2.pdf','东起西藏中路西侧人行道，西至黄陂北路东侧人行道，南起延安东路北侧人行道，北至上海大剧院和人民大道200号外墙沿线范围内的公共区域。','government'),
 ('https://www.shanghai.gov.cn/gwk/search/content/bd8ed5c6-4e7b-4197-91bf-10971f53b902','“西藏路复合功能发展轴”实现南北向交通与活力连接，串联人民广场、南京路、淮海路、新天地、世博地区浦西片区等功能地标点','government')],
 '福州路':[
 ('https://www.shanghai.gov.cn/gwk/search/content/cf46474f-4259-4087-ada5-105e2ec94971','福州路 | 中山东一路-西藏中路','government'),
 ('https://www.shanghai.gov.cn/nw4411/20200903/0001-4411_1362010.html','打造主题文化地标，依托福州路文化用品街、金陵东路音乐文化街等已具深厚文化底蕴的街区氛围，进一步提升街区开放度和商业品质','government')],
 '中国社会主义青年团中央机关旧址':F_SOURCES['中国社会主义青年团中央机关旧址'],
 '大韩民国临时政府旧址':F_SOURCES['大韩民国临时政府旧址'],
 '徐光启故居(九间楼)':[
 ('https://www.shanghai.gov.cn/shanghai/download/gongkai/hff1429.pdf','徐光启故居——九间楼 黄浦区乔家路234－244号','government'),
 ('https://m.thepaper.cn/newsDetail_forward_16433163','上海黄浦上海市黄浦区新闻中心官方澎湃号。在黄浦的街头巷尾，有许多像这样有故事的建筑。徐光启出生在上海县城南乔家浜南岸太卿坊，在此后相当一段岁月里，他都生活在乔家路234号至244号的这幢建筑里，这是徐光启故居，人们习惯称呼他的故居为“九间楼”，或者“九间头”。','official')],
 '优秀历史建筑乌鲁木齐南路176号':F_SOURCES['优秀历史建筑乌鲁木齐南路176号'],
 '中南新邨':[
 ('https://www.xuhui.gov.cn/zfjg_qzfbm_fgj_bmdt/20241104/546672.html','中南新邨 建筑类型 | 花园式里弄 建筑地址 | 淮海中路1670弄 建筑风格 | 现代主义风格。中南新邨建筑均为平缓的红瓦坡屋顶，形式简洁，横向窗间墙灰绿色面砖贴面，深绿色钢窗，整体强调水平线条。','government')],
 '盛宣怀住宅':[
 ('https://fgj.sh.gov.cn/yxlsjz/20200331/fe7b4d6f35774b708a2c5122849065bd.html','优秀历史建筑。1D004 | 盛宣怀住宅 | 日本领事馆 | 淮海中路1517号','government')],
 '张乐平':[
 ('https://www.xuhui.gov.cn/xwzx_zwxx/20260715/575182.html','离开武康大楼，一行人抵达五原路288弄张乐平故居，走近“三毛之父”，探寻经典漫画背后的温情与初心。在专业讲解员的带领下，大家参观故居展厅，了解张乐平先生的创作生涯。','government')],
 '上海交响乐团音乐厅':[
 ('https://www.shanghai.gov.cn/xuhui/index.html','上海交响乐团音乐厅位于上海复兴中路1380号。建筑外立面采用褐红色陶土砖，曲面屋顶形似摊开的乐谱，因外观被昵称为“馄饨皮”。','government')],
 '徐家汇公园':F_SOURCES['徐家汇公园'],
 '李白烈士故居':F_SOURCES['李白烈士故居'],
 '沈尹默故居':F_SOURCES['沈尹默故居'],
 '日本海军特别陆战队司令部旧址':[
 ('https://www.shhk.gov.cn/xwzx/002004/20190826/eb1c2f45-f642-4218-af30-3327b4777473.html','走读李白烈士故居、日本海军特别陆战队司令部旧址和周恩来在沪早期革命活动旧址。日本海军特别陆战司令部旧址位于黄渡路口，斑驳的围墙记录了这幢看似普通的建筑背后的历史。这里曾经是日军重要军事基地，如今已是解放军部队的重要军事基地。','government')],
 '四川北路文化中心图书馆':[
 ('https://www.shhk.gov.cn/shhk/8a8aec5f-a003-4c93-911d-88d2dcc2eaef/c5ab84a9-8af4-4579-8550-353a1ec06475/%E8%99%B9%E5%8F%A3%E5%B9%B4%E9%89%B42021.pdf','四川北路街道图书馆 | 海伦路505号','government'),
 ('https://www.shhk.gov.cn/hkjy_nas/07b6abda-39b8-4046-a72c-cd4dd334fb96/f127a8f8-8eb5-4d3e-a2a1-28e7043c3d80/2025%E5%B9%B4%E6%9A%91%E6%9C%9F%E6%B4%BB%E5%8A%A8%E9%A1%B9%E7%9B%AE%EF%BC%88%E6%AD%A3%E7%A8%BF%29.pdf','四川北路街道 海伦路505号。前往社区图书馆少儿阅览室，在书海遨游；体验图书馆“小小志愿者”活动，了解图书馆管理、收归整理等流程。','government')],
 '上海多伦现代美术馆':[
 ('https://www.shhk.gov.cn/bmff/004001/004001006/004001006002/20260428/fb47bcab-fc58-4d6d-9faf-5fe6b0892b92.html','上海多伦现代美术馆 地址：多伦路27号 开放时间：周二至周日 10:00-18:00（17:30停止入场）','government')],
}

# Each product role is evaluated independently of category count or target 60.
# Walk durations are explicit estimates for the bounded scope, not official times.
PROFILES={
 '上海人民广场':('public_space','anchor','high','high',18,'城市中心公共广场的独立城市空间体验，可承载上海城市中心主题；不含博物馆、人民公园或地铁内部。',['public_square','civic_space','landmark']),
 '福州路':('public_space','supporting_stop','medium','high',15,'有明确文化街身份与连接价值；只观察代表点附近公共街段，不包含沿线书店或场馆内部，不把全路反复计数。',['street']),
 '中国社会主义青年团中央机关旧址':('heritage','supporting_stop','medium','medium',18,'可主动参访的独立旧址与纪念馆体验，补充老城历史路线；不因红色旧址类别自动认定核心目的地。',['historic_building','cultural_space']),
 '大韩民国临时政府旧址':('heritage','supporting_stop','medium','medium',12,'官方确认原址保留及近期访问；限定街面旧址观察，内部开放安排未知，不默认为入馆。',['historic_building']),
 '徐光启故居(九间楼)':('heritage','transition_stop','low','medium',7,'临街旧址标识与建筑外观的短观察；不承诺进入住宅或施工区域，不把历史关联当作完整场馆体验。',['historic_building']),
 '东海大楼':('architecture','supporting_stop','medium','medium',10,'独立历史建筑立面的观察节点；与南京路总体步行体验区分，不包含商场内部购物。',['historic_building','landmark']),
 '优秀历史建筑乌鲁木齐南路176号':('architecture','transition_stop','low','medium',7,'具体门牌的优秀历史建筑外观短观察；不进入居民住宅，不以建筑名气认定anchor。',['historic_building']),
 '中南新邨':('heritage','supporting_stop','medium','medium',12,'里弄入口、临街建筑与门上铁艺提供独立建筑阅读；住宅内部及院落均不纳入访问承诺。',['lane','historic_building','community_space']),
 '盛宣怀住宅':('heritage','transition_stop','low','medium',6,'仅公共道路侧的历史住宅门牌与街面观察，领事住宅内部完全排除；隐私围墙导致核心建筑不可见时跳过。',['historic_building']),
 '张乐平':('cultural_venue','supporting_stop','medium','medium',20,'已有近期公众展厅参访证据的故居与漫画创作观察，补充街区文化主题。',['historic_building','cultural_space']),
 '上海交响乐团音乐厅':('architecture','supporting_stop','medium','medium',12,'有直接官方建筑描述的音乐厅外观观察；不包含购票音乐会或未经证明的内部参观。',['landmark','cultural_space']),
 '徐家汇公园':('park','supporting_stop','medium','medium',15,'工业及唱片厂址再利用的公共空间观察，补充徐家汇城市文化路线；内部设施不另拆stop。',[]),
 '李白烈士故居':('heritage','supporting_stop','medium','medium',20,'独立旧址展陈与电台体验证据充分，作为历史路线的参访补充；不以革命人物知名度直接判anchor。',['historic_building','cultural_space']),
 '沈尹默故居':('heritage','supporting_stop','medium','medium',18,'独立故居陈列与书法体验，补充文学历史街区；不因标签多少提高角色。',['historic_building','cultural_space']),
 '日本海军特别陆战队司令部旧址':('heritage','transition_stop','low','medium',6,'官方走读证据支持道路侧旧址观察；军事设施内部完全排除，不提供进入承诺或内部观察位置。',['historic_building']),
 '四川北路文化中心图书馆':('cultural_venue','supporting_stop','medium','medium',15,'地址对齐的社区图书馆阅读空间提供主动休憩与文化体验；不把活动临时安排当作常设节目。',['cultural_space','community_space']),
 '上海多伦现代美术馆':('cultural_venue','supporting_stop','medium','medium',20,'公立美术馆的独立看展体验；与多伦路公共街段不重复计算，不单拆馆内书房。',['cultural_space'])}

# These are new evidence-based skeleton choices, not edits of rejected outputs.
TAGS={
 '上海人民广场':(['modern_city'],['iconic_landmark'],[]),
 '福州路':([],['street_scene','neighborhood_walk'],[]),
 '中国社会主义青年团中央机关旧址':(['history'],[],[]),
 '大韩民国临时政府旧址':(['history'],[],['political_history']),
 '徐光启故居(九间楼)':(['history','architecture'],['architecture_detail'],[]),
 '东海大楼':(['history','architecture'],['architecture_detail'],[]),
 '优秀历史建筑乌鲁木齐南路176号':(['history','architecture'],['architecture_detail'],[]),
 '中南新邨':(['architecture'],['architecture_detail','neighborhood_walk'],['lane_life']),
 '盛宣怀住宅':(['history','architecture'],[],[]),
 '张乐平':(['history'],[],[]),
 '上海交响乐团音乐厅':(['architecture'],['architecture_detail'],[]),
 '徐家汇公园':(['parks','industrial_heritage'],['adaptive_reuse'],['industrial_transformation']),
 '李白烈士故居':(['history'],[],[]),
 '沈尹默故居':(['history','architecture'],['architecture_detail'],[]),
 '日本海军特别陆战队司令部旧址':(['history','architecture'],[],[]),
 '四川北路文化中心图书馆':(['local_life'],['bookish'],[]),
 '上海多伦现代美术馆':(['art'],['museum_visit'],[])}

SOURCES['上海人民广场'][1]=('https://www.shanghai.gov.cn/nw18454/20260602/40dbded48d5747bdb76023efebc0cc60.html','人民广场是上海的城市核心地标，更是见证百年城市变迁、镌刻红色发展记忆的重要载体。人民广场从旧时风貌蝶变为现代化城市客厅的百年历程。','government')
SOURCES['福州路'][1]=('https://www.shanghai.gov.cn/nw12344/20260228/2bd94b73f5d74b28bf38d392cebd8ab6.html','建设福州路文化街等“阅读+”街区，构建“城市书房”体系，形成建筑可阅读、街区可漫步、书店可品味的书香氛围。','government')
SOURCES['东海大楼']=[('https://fgj.sh.gov.cn/yxlsjz/20210922/8f72fa07617c4828a25ef948cd1c5da7.html','优秀历史建筑。2A027 | 慈淑大楼 | 东海商都 | 南京东路353号','government')]
SOURCES['优秀历史建筑乌鲁木齐南路176号'].append(('https://fgj.sh.gov.cn/yxlsjz1/20200331/e3b99cf457ae48cab87ad5c02aa0fee3.html','优秀历史建筑。4D033 | 巨福公寓/安康公寓 | 安康公寓/乌鲁木齐公寓 | 乌鲁木齐南路176号','government'))
TAGS['福州路']=(['architecture'],['street_scene','bookish'],[])
TAGS['中南新邨']=(['architecture'],['architecture_detail'],['lane_life'])
SOURCES['福州路'][0]=(SOURCES['福州路'][0][0],'上海市主要道路（河道）和景观区域范围界定。福州路 | 中山东一路-西藏中路','government')
SOURCES['张乐平'].append(('https://www.xuhui.gov.cn/xwzx_zwxx/20260702/574867.html','完成武康大楼、周璇旧居门头、张乐平故居三毛艺术弄等12个点位电影主题微更新','government'))
TAGS['张乐平']=(['art'],[],[])
SOURCES['李白烈士故居']=list(SOURCES['李白烈士故居'])+[('https://www.shhk.gov.cn/qyfwy/030002/030002002/030002002002/20190111/b53c6837-8bb2-4cc0-85b6-773559cc68ec.html','李白烈士故居位于黄渡路107弄亚西亚里15号。故居建筑为欧式联排花园里弄住宅，建于1935年。坐北朝南，砖木结构三层。1987年，故居对外开放。一、二楼为展厅，展出李白生平事迹；三楼为场景复原，再现李白生前战斗、生活的情景。','government')]
TAGS['李白烈士故居']=(['architecture'],['architecture_detail'],[])
TAGS['徐家汇公园']=(['parks','history'],[],['modern_shanghai'])

# Direct subject rows in the official museum register. This is a conservative
# avoidance tag even for an exterior-only visit, not a promise of access now.
MUSEUM_REGISTER='https://whlyj.sh.gov.cn/bwg/20250227/c238000e1dc5486e8027e2c4e1774ac4.html'
for _name,_row in {
 '中国社会主义青年团中央机关旧址':'中国社会主义青年团中央机关旧址纪念馆 | 淮海中路567弄1-6号',
 '大韩民国临时政府旧址':'大韩民国临时政府旧址管理处 | 马当路306弄4号',
 '张乐平':'衡复风貌博物馆群 | 张乐平故居（五原路288弄3号）',
 '李白烈士故居':'李白烈士故居 | 黄渡路107弄15号',
 '沈尹默故居':'沈尹默故居 | 海伦路504号',
}.items():
 SOURCES[_name].append((MUSEUM_REGISTER,'上海市博物馆名单（2024年度）。'+_row,'government'))
 _interest,_experience,_culture=TAGS[_name]
 TAGS[_name]=(_interest,_experience+['museum_visit'],_culture)
