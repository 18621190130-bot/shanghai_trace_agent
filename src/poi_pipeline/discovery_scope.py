"""Syntactic source-query hygiene, not final POI suitability scoring.

Retain rejected provider records in the HTTP cache and log IDs/reasons. Candidate
quality, access, permanence and route-node suitability still require human review.
"""


def discovery_exclusion(raw):
    name = raw.name_zh or raw.name_en
    if raw.source_type == "amap":
        district = raw.raw_provider_tags.get("adname", "")
        if district and district != "徐汇区":
            return "provider_district_not_xuhui"
        if any(word in name for word in ("停车场", "充电站", "售票处", "票务中心", "巴士", "打卡", "花卉节", "培训", "教学")):
            return "ancillary_service_or_temporary_photo_event"
        category = raw.source_category
        if any(word in category for word in ("餐饮", "住宿", "汽车服务", "生活服务", "培训机构", "文艺团体")):
            return "generic_service_category"
        if "购物服务" in category and name not in ("Gate M西岸梦中心", "GATE M 西岸凤巢"):
            return "generic_shop"
        if "商务住宅" in category:
            return "generic_office"
    return None
