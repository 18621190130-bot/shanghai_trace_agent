# 图片与 Cultural Bridge 填写指南

所有预留内容集中在 `frontend/content.json`。修改后刷新网页即可，不需要打包。

## 图片

1. 将你选好的照片放入 `frontend/assets/`，例如 `frontend/assets/wukang.jpg`。
2. 将对应位置的 `src: null` 改为 `"src": "/assets/wukang.jpg"`。路径以 `/assets/` 开头，不能写电脑绝对路径或外部网址。
3. 可添加 `"alt": "照片描述"`。建议使用压缩后的 WebP/JPEG，单张约 200–500 KB。

| 配置位置 | 页面用途 |
| --- | --- |
| `hero[0]` 至 `hero[7]` | 封面环绕标题的八张图片，保留现有 id/label |
| `features.walk` | 首页路线介绍、路线设置页 |
| `features.culture` | 首页文化介绍 |
| `pois.p28` 等真实 POI id | 地点图库、路线缩略图和详情图复用 |

封面为竖向卡片，建议约 4:5；正文图片建议 4:3 或横向构图。页面会用 `object-fit: cover` 裁切，尽量把重点放在中间。色块中的十字和文字是预留位，添加照片后自动消失。

地点图片示例（合并进现有 `pois`，不要覆盖其它顶层字段）：

```json
"pois": {
  "p28": {"src": "/assets/west-bund.jpg", "alt": "西岸美术馆", "theme": "blue"}
}
```

## Cultural Bridge

已按用户提供的《地点内容.docx》填入全部 22 个 anchor 的英文文化正文，并补充中文精简转述。缺少内容时仍显示预留状态。

- `cultural_bridge.landing.en/zh`：首页文化区域的短介绍，值为字符串。
- `cultural_bridge.places.<POI id>.en/zh`：该地点的文化详情；当前使用 `paragraphs: ["段落一", "段落二"]`，保留阅读分段，也兼容以下旧字段。

```json
"cultural_bridge": {
  "landing": {"en": null, "zh": null},
  "places": {
    "p28": {
      "zh": {
        "why_matters": "在此填写：为什么值得关注",
        "bridge": "在此填写：帮助理解的跨文化联系",
        "look_for": "在此填写：现场值得观察的细节",
        "local_context": "在此填写：上海本地背景"
      },
      "en": null
    }
  }
}
```

示例只是字段说明，不会自动写入网页。某种语言为 `null` 时，该语言仍显示预留状态；不会自动翻译或拼凑内容。字段接受纯文本，不执行 HTML。Core POI id 可查看本地 `/api/bootstrap` 返回的 `pois` 列表；不修改 `data/pois.json` 来添加网页图片或文化文案。

## 四个街区介绍和图片

`zones` 的真实 id 为 `wukang_fuxing_xujiahui`、`old_city_central`、`hongkou_literary`、`west_bund`。

- `zones.<id>.src`：Places in mind 街区卡片图片，例如 `/assets/west-bund-zone.jpg`。
- `zones.<id>.introduction.en`：Explore the city 的英文介绍。
- `zones.<id>.introduction.zh`：中文介绍，可留空。

这些内容默认留空，由你填写。Plan a walk 的右侧介绍栏已删除，`features.walk` 现在只用于首页正文。

## 2026-10-08 内容导入

- 封面：8 张照片位于 `frontend/assets/hero/`。
- Anchor：22 张用户照片位于 `frontend/assets/poi-images/`，在 `data/poi_images.json` 中记为 CURATED。
- Cultural Bridge：`frontend/content.json` 的 `cultural_bridge.places`；英文保留用户正文，中文为精简转述。
- What to notice：`data/poi_arrival_content.json` 的 `records.<id>.what_to_notice.en/zh`，覆盖全部 58 个 Core POI。
- `scripts/import_editorial_content.py` 可重现本次导入；重复运行会按本次源文件及 editorial.json 重写相应内容，后续手工修改应同步维护输入。
- 对照清单：`examples/content_fill/import_audit.json`，记录原文件名、地点 ID、静态路径、文件哈希和文字校正。
- 两处照片编号按用户确认修正：外滩照片 p4 → p14；星美术馆照片 p41 → p31。原文件未改名。
