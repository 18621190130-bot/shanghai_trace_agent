from .base import Source, SourceError
from ..models import RawCandidate


class OSMSource(Source):
    name = "osm"
    endpoint = "https://overpass-api.de/api/interpreter"
    # Expanded WGS84 discovery envelope; exact pilot filtering occurs in GCJ-02.
    bbox = "31.155,121.452,31.198,121.478"
    selectors = ('[tourism~"^(museum|gallery|artwork|attraction|viewpoint)$"]', '[historic]',
                 '[leisure~"^(park|garden|pitch|sports_centre)$"]', '[amenity~"^(theatre|arts_centre|community_centre)$"]',
                 '[man_made~"^(pier|crane|works)$"]', '[industrial]', '[place=square]', '[highway=pedestrian][name]')

    def __init__(self, http, config=None):
        super().__init__(http)
        if config:
            s,w,n,e=config.bounds
            # Conservative WGS84 discovery envelope; final filtering is GCJ-02.
            self.bbox=f'{s-.008},{w-.008},{n+.008},{e+.008}'

    @staticmethod
    def parse(element, retrieved_at):
        tags = element.get("tags", {})
        center = element.get("center", element)
        coords = (center["lat"], center["lon"]) if "lat" in center and "lon" in center else None
        kind = "unknown"
        if tags.get("tourism") in ("museum", "gallery") or tags.get("amenity") in ("theatre", "arts_centre", "community_centre"):
            kind = "venue"
        elif tags.get("tourism") == "artwork":
            kind = "artwork"
        elif tags.get("man_made") == "pier":
            kind = "pier"
        elif tags.get("leisure") in ("park", "garden", "pitch", "sports_centre") or tags.get("place") == "square":
            kind = "public_space"
        elif tags.get("highway") == "pedestrian":
            kind = "street"
        elif "historic" in tags or "building" in tags:
            kind = "building"
        default = tags.get("name", "")
        zh = tags.get("name:zh", default if any('\u4e00' <= c <= '\u9fff' for c in default) else "")
        en = tags.get("name:en", default if not zh else "")
        pid = f"{element['type']}/{element['id']}"
        supports = ["identity", "coordinates", "basic_category"]
        snippets = []
        for key, group in (("description", "identity"), ("opening_hours", "opening"), ("access", "access")):
            if tags.get(key):
                snippets.append(dict(text=tags[key][:400], supports=[group], provider_field=key))
                supports.append(group)
        return RawCandidate(pid, "osm", "OpenStreetMap contributors / Overpass", "https://www.openstreetmap.org/" + pid,
            retrieved_at, name_zh=zh, name_en=en,
            aliases=[a for key in ("alt_name", "old_name", "short_name") for a in tags.get(key, "").split(";") if a],
            address=tags.get("addr:full", " ".join(tags.get(k, "") for k in ("addr:city", "addr:street", "addr:housenumber")).strip()),
            coordinates=coords, source_category=";".join(f"{k}={tags[k]}" for k in ("tourism", "historic", "leisure", "amenity", "man_made", "place", "highway") if k in tags),
            raw_provider_tags=tags, snippets=snippets, supports=supports, entity_kind=kind)

    def collect(self):
        query = '[out:json][timeout:25];(' + ''.join(f'nwr{s}({self.bbox});' for s in self.selectors) + ');out center tags;'
        try:
            result = self.http.get(self.name, self.endpoint, {"data": query})
            payload = result["response"]
            if payload.get("remark"):
                self.error("overpass_server_remark", SourceError())
            for element in payload.get("elements", []):
                try:
                    if any(element.get("tags", {}).get(k) for k in ("name", "name:zh", "name:en")):
                        yield self.parse(element, result["retrieved_at"])
                except (KeyError, TypeError, ValueError) as exc:
                    self.error("malformed_element", exc)
        except (SourceError, ValueError, TypeError) as exc:
            self.error("regional_overpass_query", exc)
