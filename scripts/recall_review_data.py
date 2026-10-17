"""Explicit bounded shortlist and short inspected source excerpts, not discovery."""
SHORTLIST={
 'old_city_central':['太平桥公园','淮海公园','福州路','延中公园','复兴公园','中国社会主义青年团中央机关旧址','大韩民国临时政府旧址','徐光启故居(九间楼)','春广场','fudeli','上海人民广场','东海大楼'],
 'wukang_fuxing_xujiahui':['武康路历史文化名街','普希金雕像','衡山公园','天钥桥路口袋公园','优秀历史建筑乌鲁木齐南路176号','襄阳公园','徐家汇公园','聂耳铜像','中南新邨','盛宣怀住宅'],
 'hongkou_literary':['山阴路274弄','李白烈士故居','沈尹默故居','爱思儿童公园','四川北路文化中心图书馆','上海多伦路地区海派文化馆(多伦生活广场店)','上海子兮艺术社非遗文化馆','日本海军特别陆战队司令部旧址','世界文豪广场','尹奉吉纪念园(梅园)']}
# Only verbatim small subject excerpts are semantic evidence. Negative/unresolved
# checks remain judgments in review, not invented positive factual evidence.
SOURCES={
 '太平桥公园': [('https://www.shhuangpu.gov.cn/BigFileUpLoadStorage/temp/2025-12-26/d54221cd-e39c-4bd5-98a1-3690138dbdd5/%E9%BB%84%E5%BA%9C%E5%8A%9E%E5%8F%91202112.pdf','重点推进人民公园、广场公园、太平桥公园、古城公园等公园绿地“四化”示范点建设。','government')],
 '淮海公园':[('https://www.shanghai.gov.cn/nw17239/20250904/94d9f1c5fb954a3fbb9941bb5a0621f6.html','广场公园（黄浦段）L1地块草坪、淮海公园大草坪、丽园公园草坪、南园滨江绿地大草坪，开放期均为每年5月16日至10月9日，以及12月1日至次年4月14日。','government')],
 '福州路':[('https://www.shanghai.gov.cn/nw4411/20240919/8eba22ff0b934017abc1f962eae7c529.html?siteId=1','“外滩·新闻历史文化街区”北接南京路步行街，南临福州路文化一条街','government')],
 '延中公园':[('https://www.amap.com/place/B00155ILXP','延中公园是一家公园，地址为上海市黄浦区巨鹿路成都南路口。地理坐标：31.222443,121.467051。','amap')],
 '复兴公园':[('https://english.shanghai.gov.cn/en-Parks/20250220/636b3df5761e4055b731a92d2abddcb3.html','Fuxing Park','government')],
 '中国社会主义青年团中央机关旧址':[('https://www.shanghai.gov.cn/nw17239/20260924/6d8d89744aef4043b941cbf78fede58b.html','中国社会主义青年团中央机关旧址纪念馆\n地址：淮海中路567弄1-6号','government')],
 '大韩民国临时政府旧址':[('https://www.shanghai.gov.cn/gwk/search/content/f6c94ab732754740a06562bd7aeae40c','区级文物保护单位大韩民国临时政府旧址（马当路306弄4号）本体原址保留，不纳入征收实施范围。','government'),('https://www.shanghai.gov.cn/nw4411/20260108/8358d0e5029b45a981750e8696ba90c7.html','下午，总统夫妇一同访问大韩民国临时政府旧址。','government')],
 '徐光启故居(九间楼)':[('https://www.shanghai.gov.cn/shanghai/download/gongkai/hff1429.pdf','徐光启故居———九间楼','government')],
 '春广场':[('https://www.jfdaily.com/sgh/detail?id=1554679','公园内的沉床花坛、玫瑰园和春广场共同构成了园中的几何平面构图','official')],
 'fudeli':[('https://www.shanghai.gov.cn/jingan/index.html','辅德里公园原名广场公园（静安段），位于静安区大沽路379号','government')],
 '武康路历史文化名街':[('https://www.shanghai.gov.cn/citywalk/20260625/3492b1b945c146fc96c4585d7b04f00d.html','武康路-安福路街区位于徐汇区衡复历史文化风貌区内，南至武康路淮海中路，北至安福路、乌鲁木齐路。','government')],
 '普希金雕像':[('https://www.supdri.com/artmap/details.html?id=2&isPath=1&type=line','沿线经典建筑和雕塑有黄兴故居、巴金故居、湖南别墅、丁香花园、上方花园、黑石公寓、聂耳铜像和普希金铜像等。','official')],
 '衡山公园':[('https://www.shanghai.gov.cn/nw17239/20250519/57cb4173d2274749a8a9f8eca3d05412.html','徐家汇公园的月季倾泻如瀑，衡山公园的藤本月季攀檐绕廊','government')],
 '天钥桥路口袋公园':[('https://www.shhk.gov.cn/xwzx/002008/002008040/20240213/de1605dc-7013-4437-9aaa-c8da3d3fcdb5.html','天钥桥路口袋公园','government')],
 '优秀历史建筑乌鲁木齐南路176号':[('https://fgj.sh.gov.cn/yxlsjzjk/20240223/921ff8d978724856b21e8c38fc1d23ba.html','原则同意乌鲁木齐南路176号等优秀历史建筑保护性修缮项目设计方案','government')],
 '襄阳公园':[('https://www.shanghai.gov.cn/nw17239/20251203/572ffde1f42142a3ab088fc66ba847e5.html','这条线路从汾阳路音乐街区漫步至襄阳公园，沿途串联起多个融合音乐艺术与自然生态的公共空间。','government')],
 '徐家汇公园':[('https://www.shanghai.gov.cn/nw17239/20250324/147efed623f141bb95a509e62aefdd0f.html','徐家汇公园的樱花主要集中在悬铃木大道的南端和汇金湖河畔，粉白色的染井吉野樱和东京樱与湖光林色交相辉映','government')],
 '聂耳铜像':[('https://www.supdri.com/artmap/details.html?id=2&isPath=1&type=line','沿线经典建筑和雕塑有黄兴故居、巴金故居、湖南别墅、丁香花园、上方花园、黑石公寓、聂耳铜像和普希金铜像等。','official')],
 '山阴路274弄':[('https://www.shhk.gov.cn/xwzx/002006/20200525/f6009f16-7343-4748-9539-6410f382d221.html','听完越界筑路的故事，学员们漫步到了山阴路274弄，一条小而精致的弄堂。这是通往鲁迅公园和虹口足球场地铁站的一条交通便道','government')],
 '李白烈士故居':[('https://www.shhk.gov.cn/xwzx/002008/002008045/002008045002/20260907/a797bda7-753b-4a6f-b8a3-bdeda4d9c9ba.html','坐南朝北的三层砖木结构的老式洋房，曾是抗日战争和解放战争时期李白同志的住所，也是他最后居住、工作和被捕的地方。一、二楼李白烈士事迹陈列室，讲述了李白的成长经历以及与敌人斗争的光辉事迹。三楼为场景复原，再现了李白烈士生前战斗、生活的情景。','government')],
 '沈尹默故居':[('https://www.shhk.gov.cn/qyfwy/030002/030002002/030002002005/20181215/b300eab7-5cb1-43de-835b-b20d2b40308c.html','沈尹默故居是沿街三层两开间西式住宅','government'),('https://www.shhk.gov.cn/slh/038001/20251114/803f173f-6bd9-4bbc-aa6d-5aeff18bb1f7.html','统筹84处红色旧址遗址，推出“重走解放路”等研学线路，活化沈尹默故居、景云里名人故居群等历史建筑，让居民在城市更新中触摸文化根脉。','government')],
 '爱思儿童公园':[('https://www.shhk.gov.cn/xwzx/002003/20240428/ea83a215-53ff-4b16-8493-c5c4171a556d.html','在公园步道两侧沿途设置了多块书本样式的宣传版，并附以“民生无小事”“长风破浪会有时，直挂云帆济沧海”等名言警句，让游客在漫步小径中接受廉文化的熏陶。','government')],
 '世界文豪广场':[('https://english.shanghai.gov.cn/en-ScenicSpots/20250321/4c723d5d75064d0da60ae2be855ac702.html','It also houses the Shanghai Luxun Museum and the World Literary Giant Square, reflecting the park\'s rich cultural legacy.','government')],
 '尹奉吉纪念园(梅园)':[('https://english.shanghai.gov.cn/en-ScenicSpots/20250321/4c723d5d75064d0da60ae2be855ac702.html','Meiyuan Garden, which is dedicated to Korean independence activist Yun Bong-gil.','government')]}

# Five materially improved evidence bundles; second calls are phase-budgeted.
SOURCES['襄阳公园'].append(('https://www.shanghai.gov.cn/nw15343/20250106/403da6dee9324dc08ab9194adf9199b3.html','区林长办开展丰富多样的“公园+”活动，依托“绿知汇”生态科普联盟中心，用好襄阳公园等4个葩科小屋和16个市民园艺中心阵地，积极开展面向儿童的科普、观鸟、文化和体育等活动。','government'))
SOURCES['徐家汇公园'].append(('https://www.shanghai.gov.cn/nw15343/20250625/89c5c3f7be2a4dfbaae717e8bb74de36.html','在徐家汇公园，曹立强沿着人行步道察看景观绿化养护、儿童空间打造以及公厕布局等情况。','government'))
SOURCES['李白烈士故居'].append(('https://www.shhk.gov.cn/xwzx/002008/002008047/002008047002/20251222/17639b35-93cb-4d17-87de-e06467604e62.html','故居还保留了发报互动体验区，并在发报设备上进行了提升优化，同时设置了一定难度，让观众可以学习摩斯电码小知识，体验更真实的发送电码过程，寓教于乐。','government'))
SOURCES['沈尹默故居'][0]=(SOURCES['沈尹默故居'][0][0],'沈尹默故居是沿街三层两开间西式住宅，居门首挂有赵朴初题写的“沈尹默先生故居”匾额。底楼是陈列室、有沈尹默的半身塑像，橱里陈列着沈尹默先生生前眼镜、笔筒等遗物和书法集、诗词集、书法理论等。二楼是书房兼画室，陈列着沈尹默的书法精品。','government')
SOURCES['中国社会主义青年团中央机关旧址'][0]=(SOURCES['中国社会主义青年团中央机关旧址'][0][0],'中国社会主义青年团中央机关旧址纪念馆\n地址：淮海中路567弄1-6号\n该7处场馆均向公众（含未成年人）免费开放，无需预约。','government')

DEFER_NOTES={
 '春广场':('internal_entity','官方说明属于复兴公园内部景观；不拆成独立 stop。','independent visit scope'),
 'fudeli':('weak_identity','缓存英文名位置与大沽路379号的辅德里公园未对齐，不能凭译名合并。','provider identity/address reconciliation'),
 '延中公园':('weak_location','OSM 代表点与高德巨鹿路成都南路口约200m差异，可能是不同分区，补证没有解决。','sub-park identity and representative anchor'),
 '徐光启故居(九间楼)':('insufficient_evidence','保护名单支持稳定身份；缺的是独立街面观察/展陈体验证据，不是此刻是否开门。','independent public observation or exhibition scope'),
 '世界文豪广场':('internal_entity','官方明确位于已有鲁迅公园文化纪念区。','distinct experience outside existing park scope'),
 '尹奉吉纪念园(梅园)':('internal_entity','已有鲁迅公园内的梅园，不增加内部停靠数。','independent non-overlapping visit scope'),
 '四川北路文化中心图书馆':('insufficient_evidence','两次定向查找未形成该地址的权威独立文化体验证据。','current identity/public access'),
 '上海多伦路地区海派文化馆(多伦生活广场店)':('insufficient_evidence','未找到能区分同名机构与商场内部文化设施的直接证据。','venue identity and independent visitor scope'),
 '上海子兮艺术社非遗文化馆':('insufficient_evidence','有工作坊索引线索，但未证明稳定开放的独立常设参访空间。','stable venue/address/public access'),
 '日本海军特别陆战队司令部旧址':('insufficient_evidence','历史旧址 map 记录不证明现时公众可参访范围。','public exterior scope/access'),
 '中南新邨':('insufficient_evidence','社区型对象不等于游客可进入的独立文化节点。','heritage identity and public walk scope'),
 '盛宣怀住宅':('insufficient_evidence','历史名称和 map 点尚不足以证明独立可观察参访范围。','current exterior access and heritage match'),
 '上海人民广场':('weak_location','多个面/点代表对象，范围宽且与周边节点独立访问范围未分清。','bounded visitor scope'),
 '东海大楼':('insufficient_evidence','历史建筑线索保留，未以名气推断值得独立停靠。','facade public observation scope and architectural evidence')}
