# 2026-10-08 人工审核发布结果

已应用用户提供的 poi_image_review.json，并按用户指定将图 1 原文件保存为 p35.png（徐家汇商圈）、图 2 保存为 p2.png（永康路与嘉善路口）。图片未裁剪、未重绘。来源记为用户提供，原始网站与许可未知，不虚构授权。

真实图片：36/36 个非 anchor；AMAP=34，MANUAL_WEB=2，CURATED=0。22 个 anchor 按要求继续留白。所有 58 个 slot 保持不变。

剩余非 anchor 待处理：无。

验证：审核摘要及所选 URL 校验通过；两张本地图片与附件逐字节一致；58 个 ID 顺序和 22 个 anchor 留白状态不变；746 个冻结文件哈希不变。本次仅提交图片与元数据，不重复运行历史回归，不重新调用高德 detail API。原始审核文件、合并后的审核文件和提交前 manifest 均已保留。

以下为首次采集时的历史记录，其待审统计不代表当前状态。

---

# TraceMate Phase 4B_1 — POI Image Coverage

## 当前状态：实现与候选采集完成，等待人工图片审核；尚未最终 PASS

遵循本次最新要求：22 个 anchor 保持图片留白。当前 frontend/content.json 没有已配置精选图，不虚构“22 张 curated 已完成”。已有或以后加入的 CURATED 图始终优先，enrichment 不会覆盖 anchor。没有开始 Phase 4B_2 Arrival Card。

## 覆盖统计

- core_total: 58
- anchor_count: 22
- non_anchor_count: 36
- identity_matched_total: 57
- identity_matched_non_anchor: 35
- amap_candidates: 34
- photo_candidates: 99
- metadata_rejected_photos: 0
- pending_human_review: 34
- needs_manual_images: 2
- published_real_images: 0
- curated_reserved: 22
- rendered_fallback: 58
- provider_request_batches: 4
- permanent_provider_downloads: 0

正式可展示真实图片按来源统计：CURATED = 0、AMAP = 0、MANUAL_WEB = 0；有效 FALLBACK 展示 = 58。manifest 中 22 条 CURATED/MISSING 是人为预留，而不是实际有图；其余 36 条为 FALLBACK。候选 AMAP = 34 / 36（94.4%），全部 reviewed=false，等待人工确认；不得将候选覆盖率当成上线覆盖率。

| Route role | Core 数 | AMAP 候选 | 已发布真实图 |
| --- | ---: | ---: | ---: |
| anchor | 22 | 0 | 0 |
| supporting_stop | 29 | 28 | 0 |
| transition_stop | 7 | 6 | 0 |

## 需要人工补图（目前确定无候选）

- `p2` 永康路与嘉善路口 — NO_PROVIDER_PHOTOS
- `p35` 徐家汇商圈 — IDENTITY_NOT_FOUND

## 完整待审核图片清单

下列地点均已找到高德候选，但尚未经过真人视觉审核。POINT 同样需要核对地点与照片质量；AREA/LINEAR 必须确认其能代表整个 Core 概念。审核拒绝的地点会加入人工补图队列。

| Core ID | 地点 | 空间类型 | 候选数 |
| --- | --- | --- | ---: |
| p10 | 今潮8弄 | AREA | 3 |
| p11 | 建业里 | AREA | 3 |
| p12 | 陕南邨 | AREA | 3 |
| p13 | 武康大楼 | POINT | 3 |
| p23 | 思南公馆 | AREA | 3 |
| p25 | 1927·鲁迅与内山纪念书局 | POINT | 3 |
| p26 | 中国左翼作家联盟会址纪念馆 | POINT | 3 |
| p33 | 徐家汇书院 | POINT | 3 |
| p36 | 西岸艺术中心 | POINT | 3 |
| p37 | 西岸穹顶艺术中心（含北广场） | AREA | 3 |
| p38 | 滨江滑板公园 | AREA | 3 |
| p39 | 徐汇跑道公园 | AREA | 3 |
| p42 | 徐汇滨江海事塔广场 | AREA | 3 |
| p43 | 北票码头塔吊 | POINT | 3 |
| p41 | 西岸大剧院 | POINT | 3 |
| pz_a74f9e58195a | 古城公园 | AREA | 3 |
| pz_0b545bb1cf2a | 四川北路公园 | AREA | 3 |
| pz_b4acff8f32fc | 甜爱路 | LINEAR | 3 |
| pz_68957332b418 | 太平桥公园 | AREA | 3 |
| pz_8919938b21f2 | 淮海公园 | AREA | 3 |
| pz_553cfd36707c | 衡山公园 | AREA | 3 |
| pz_a27dbbc6cab8 | 襄阳公园 | AREA | 3 |
| pz_a446052910a0 | 山阴路274弄 | AREA | 2 |
| pz_cc5300aee299 | 福州路 | LINEAR | 3 |
| pz_66452d5db8a1 | 大韩民国临时政府旧址 | POINT | 3 |
| pz_54f53d30c0dc | 安康公寓（乌鲁木齐南路176号） | POINT | 1 |
| pz_de47b0cf3e98 | 中南新邨 | AREA | 3 |
| pz_437ddd34f2c1 | 张乐平故居 | POINT | 3 |
| pz_7e40d824dbee | 上海交响乐团音乐厅 | POINT | 3 |
| pz_09b5938601ee | 徐家汇公园 | AREA | 3 |
| pz_8b1bb0928e7e | 李白烈士故居 | POINT | 3 |
| pz_c862ec0d6ddd | 沈尹默故居 | POINT | 3 |
| pz_c4f63095cb01 | 日本海军特别陆战队司令部旧址 | POINT | 3 |
| pz_f8277d15786a | 上海多伦现代美术馆 | POINT | 3 |

## 获取与选择策略

只读取现有 data/amap_poi_mappings.json 的 MATCHED ID，共 35 个非 anchor identity；没有模糊名称搜索，没有调用 LLM 或图像识别。复用现有 AmapClient，通过 `/v5/place/detail`、`id=A|B|...`、`show_fields=photos` 分 4 批获取，最多 10 ID/批，使用 AMAP_API_KEY Web Service Key。JS Key 不参与采集。

依据：[高德官方 POI 2.0 ID 搜索文档](https://developer.amap.com/api/webservice/guide/api-advanced/newpoisearch)。

过滤非高德图片域名、无效 URL、重复 URL、菜单/二维码/广告/海报/商品/停车收费等标题，优先外观/街景等元数据明确的场景，稳定保留 provider 顺序。元数据只能给出候选，不能证明图片准确；本次没有把机器人判断写成“人工已审核”。只保存 URL/来源引用，没有永久下载 provider 图片。运行时图鉴读取一份本地 manifest，不触发 POI detail API。

## 人工审核与发布

1. 启动 `python web_server.py --port 8773`，打开 `http://127.0.0.1:8773/image-review/`。已启动的审核地址也可直接使用。
2. 每个地点选择候选图，勾选已核对，再通过；不合适则拒绝。AREA/LINEAR 在卡片中有醒目标记。浏览器本地保存进度；没有“一键全过”。图片加载失败时不能通过。
3. 点击“导出审核结果 JSON”。将文件放在项目内，如 `examples/poi_images/poi_image_review.json`。
4. 执行：`python scripts/enrich_poi_images.py --commit --review-file examples/poi_images/poi_image_review.json`。提交不调用 API；审核摘要必须匹配候选 audit，接受的 URL 必须属于该 POI。旧 manifest 与审核决定会留下证据。
5. 刷新网页。正式界面只显示通过的图片。未通过/缺图继续统一 fallback，位置和排序不变。

也可直接向开发者提供审核通过/拒绝的 Core ID 与候选序号，由开发者根据你的明确决定提交。未确认的条目保留待审状态。

重建候选：`python scripts/enrich_poi_images.py --dry-run`（调用高德，只更新候选与审计，不改正式 manifest）。已有候选复用：`python scripts/enrich_poi_images.py --from-audit examples/poi_images/image_audit.json --dry-run`（不调用 API）。新采集会产生新的候选摘要；先前审核不会被错误套用。

## 人工本地图片

使用 `frontend/assets/poi-images/{core_poi_id}.webp`，原始 ID 必须保留，包括 pz_ 开头的 ID。不直接热链其他网站。优先场馆官网、政府文旅、机构公开页面或有明确许可的 Commons 素材；保留授权/使用说明，不把“公开可访问”等同于“已获授权”。

在审核 JSON 的 decisions 中填写对应项，例如：

```json
{
  "p35": {
    "decision": "manual",
    "image_url": "/assets/poi-images/p35.webp",
    "source_url": "原始来源页面 URL",
    "source_name": "来源机构名称",
    "retrieved_at": "采集日期",
    "usage_note": "许可或使用说明"
  }
}
```

保留 review_template.json 中的 candidate_digest，填写 reviewed_at，然后用相同 commit 命令提交。手工选择是显式覆盖决定；普通 resolver 顺序为 CURATED → 已审核 AMAP → 已审核 MANUAL_WEB → FALLBACK。已有 CURATED 始终保留。Anchor 不从高德或手工网络队列自动填充，需要通过原有人工精选 content 槽位配置。

## 前端集成

frontend/poi-images.js 提供共享 resolvePoiImage(poiId, context)，返回 src/source/status/alt/theme。Atlas、人工选点缩略图、路线缩略图和 POI detail 共用它；后续 Arrival Card 可复用，但本阶段未实现。

图片统一 object-fit: cover，Atlas 固定 4:3；各使用场景保留原本固定图片容器。图片加载失败删除 img 并显示同尺寸占位，语言切换取 Core 的中/英文名称作为 alt，不将高德 title 当作英文文案。manifest 不可用也能使用 fallback。图片状态不参与任何排序、选点或路线评分。

## 验证

- Python 图片定向测试：8 项通过。
- JS 图片 resolver/安全域名/双语/占位测试：5 项通过。
- Edge 浏览器：58 slots、统一尺寸、破图回退、顺序不变、双语 alt、手机无横向溢出、34 个需手动勾选的审核入口、2 个缺图卡片通过。
- 不跑全部 Phase 3 历史回归；本次一次性 enrichment 共 4 条批量 API 请求，没有为了测试重复采集。
- 真实浏览器加载技术检查：34 张默认候选全部加载成功，失败 0；证据 examples/poi_images/photo_load_audit.json。此检查不判断地点或构图正确性。
- 未进行图片内容的 LLM 审核；人工审核是剩余验收条件。

## Frozen Backend Audit

采集前后 SHA-256 对比 746 个已有 data JSON 和 src Python 文件，变化 0 个。证据 examples/poi_images/frozen_before.json 与 frozen_audit.json。

Core POI content、route_role、spatial data、AMap identity mapping、TripState、Route Engine 均未修改。Phase 3A/3B 源码和数据保持原样；本次没有重跑全部历史用例，因此此处是文件不变证明，而不是新的全量行为回归结论。web_server.py 只增加只读 manifest 与受限审核静态文件入口，不改变规划/行程 API。

## Deliverables

- data/poi_images.json — 58 个稳定状态；22 个 anchor 预留。
- scripts/enrich_poi_images.py — 批量 ID 获取、dry-run、审核后 commit。
- examples/poi_images/image_audit.json / image_audit.html — 58 条审计、36 个非 anchor 审核卡片。
- examples/poi_images/provider_photo_response.json — 已脱离请求密钥的原始照片元数据和批次证据。
- examples/poi_images/missing_manual_review.json — 完整 36 项人工工作队列（含 34 待审）。
- examples/poi_images/needs_manual_images.json — 目前确定需补图的 2 项。
- examples/poi_images/review_template.json — 审核摘要与决定模板。
- frontend/poi-images.js — 共享 resolver 与错误回退。

停在 Phase 4B_1 人工审核；不宣称真实图已上线，不开始 Phase 4B_2。
