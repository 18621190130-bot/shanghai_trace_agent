import os
from .base import Source, SourceError
from ..models import RawCandidate


class AmapSource(Source):
    name = "amap"
    keywords = ("西岸 美术馆", "西岸 艺术中心", "西岸 公园", "西岸 广场", "西岸 码头", "西岸 工业遗址", "西岸 剧院", "西岸 滑板")

    def __init__(self, http, config=None):
        super().__init__(http)
        self.config = config
        if config:
            self.keywords = config.discovery_terms

    def request(self, endpoint, parameters):
        key = os.environ.get("AMAP_API_KEY")
        if not key and not self.http.offline:
            raise SourceError("missing_AMAP_API_KEY")
        response = self.http.get(self.name, "https://restapi.amap.com/v3/" + endpoint,
                                 parameters, secret_params={"key": key} if key else {})
        if response["response"].get("status") != "1":
            raise SourceError("amap_provider_status_failure")
        return response

    def detail(self, poi_id):
        return self.request("place/detail", {"id": poi_id, "extensions": "base", "output": "JSON"})

    def geocode(self, address):
        return self.request("geocode/geo", {"address": address, "city": "上海", "output": "JSON"})

    @staticmethod
    def parse(poi, retrieved_at):
        location = poi.get("location", "")
        coordinates = None
        if isinstance(location, str) and "," in location:
            lng, lat = map(float, location.split(","))
            coordinates = (lat, lng)
        category = poi.get("type", "") or ""
        kind = "unknown"
        for word, value in (("美术馆", "venue"), ("博物馆", "venue"), ("剧院", "venue"), ("展览馆", "venue"),
                            ("剧场", "venue"), ("文化宫", "venue"), ("会展中心", "venue"),
                            ("公园", "public_space"), ("广场", "public_space"), ("雕塑", "artwork"), ("码头", "pier")):
            if word in category:
                kind = value
                break
        pid = str(poi["id"])
        return RawCandidate(pid, "amap", "Amap Web Service", "https://www.amap.com/detail/" + pid,
            retrieved_at, name_zh=poi.get("name", ""), address=poi.get("address") if isinstance(poi.get("address"), str) else "",
            coordinates=coordinates, coordinate_system="GCJ-02", source_category=category,
            raw_provider_tags={k: poi[k] for k in ("type", "typecode", "pname", "cityname", "adname") if k in poi},
            supports=["identity", "address", "coordinates", "basic_category"], entity_kind=kind)

    def collect(self):
        if not os.environ.get("AMAP_API_KEY") and not self.http.offline:
            self.error("configuration_missing_AMAP_API_KEY", SourceError())
            return
        queries = [("place/text", {"keywords": keyword, "city": "上海", "citylimit": "true"}) for keyword in self.keywords]
        if self.config is None:
            queries += [("place/around", {"location": "121.466,31.175", "radius": "2200", "types": "110000|140100", "sortrule": "distance"})]
        seen = set()
        for endpoint, parameters in queries:
            for page in range(1, 4):  # bounded pilot, explicit truncation diagnostic
                try:
                    result = self.request(endpoint, dict(parameters, page=str(page), offset="20", extensions="base", output="JSON"))
                    pois = result["response"].get("pois", [])
                    for poi in pois:
                        try:
                            record = self.parse(poi, result["retrieved_at"])
                            if record.source_candidate_id not in seen:
                                seen.add(record.source_candidate_id)
                                yield record
                        except (ValueError, TypeError, KeyError) as exc:
                            self.error("malformed_poi", exc)
                    if len(pois) < 20:
                        break
                    if page == 3 and int(result["response"].get("count", 0)) > 60:
                        self.errors.append(dict(source=self.name, status="discovery_truncated", request=parameters))
                except (SourceError, ValueError, TypeError) as exc:
                    self.error(endpoint, exc)
                    break
