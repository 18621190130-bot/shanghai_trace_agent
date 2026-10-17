# 原始素材

这里保存用户提供的原文件，仅保留在本机，不纳入版本控制（本说明文件除外）；网站读取的是 `frontend/` 和 `data/` 中已导入的内容。

| 原位置 | 当前位置 | 用途 |
| --- | --- | --- |
| `照片-封面/` | `photos/cover/` | 封面原图 |
| `照片 封面以外/` | `photos/anchors/` | Anchor POI 原图 |
| `地点内容.docx` | [content/地点内容.docx](content/地点内容.docx) | Cultural Bridge 原始文案 |
| `lightspark-reference.png` | [design/lightspark-reference.png](design/lightspark-reference.png) | 设计参考 |

原图和文档按原字节迁移。生产图片仍在 `frontend/assets/`，文化文案在 `frontend/content.json`，到达观察提示在 `data/poi_arrival_content.json`，图片来源清单在 `data/poi_images.json`。

生产清单和历史审核中的旧素材文件名保留为来源记录，可用上表定位到新位置。导入工具 `scripts/import_editorial_content.py` 已适配新路径；它会重写网站图片和文案配置，应在明确需要重新导入时使用。
