"""All external sources use local fixtures; no live HTTP or LLM calls."""
from dataclasses import asdict, replace
from email.message import Message
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.poi_pipeline.models import RawCandidate
from src.poi_pipeline.normalization import normalize_candidate
from src.poi_pipeline.boundary import boundary_status
from src.poi_pipeline.deduplication import deduplicate_candidates
from src.poi_pipeline.evidence import build_evidence_bundle
from src.poi_pipeline.coverage import WestBundCoverageAnalyzer
from src.poi_pipeline.collection import collect_sources
from src.poi_pipeline.sources.base import CachedHTTP, Source, SourceError
from src.poi_pipeline.sources.amap_source import AmapSource
from src.poi_pipeline.sources.osm_source import OSMSource
from src.poi_pipeline.sources.official_source import extract_page, OfficialSource
from src.poi_pipeline.discovery_scope import discovery_exclusion
from .helpers import baseline_repository


def candidate(pid="1", **kwargs):
    values = dict(source_candidate_id=pid, source_type="amap", source_name="fixture",
                  source_url="https://example.org/poi/" + pid, retrieved_at="2026-10-04T00:00:00+00:00",
                  name_zh="测试美术馆", coordinates=(31.175, 121.466), coordinate_system="GCJ-02",
                  source_category="museum", entity_kind="venue")
    values.update(kwargs)
    return RawCandidate(**values)


class Response:
    def __init__(self, content):
        self.content = content.encode()
        self.headers = Message()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, size):
        return self.content[:size]


class PipelineTests(unittest.TestCase):
    def test_normalization_preserves_raw(self):
        raw = candidate(name_zh="  测试（西岸） \n", name_en=" Ｔｅｓｔ   Museum ", aliases=[" Alias ", "Alias"], address=" 路  1号 ")
        norm = normalize_candidate(raw)
        self.assertEqual(norm.name_zh, "测试(西岸)")
        self.assertEqual(norm.name_en, "Test Museum")
        self.assertEqual(norm.aliases, ["Alias"])
        self.assertEqual(norm.address, "路 1号")
        self.assertEqual(norm.raw.name_zh, "  测试（西岸） \n")

    def test_coordinates_conversion_and_invalid(self):
        raw = candidate(coordinate_system="WGS84")
        self.assertNotEqual(normalize_candidate(raw).coordinates, raw.coordinates)
        for coords, system in [((float("nan"), 121), "GCJ-02"), ((91, 121), "GCJ-02"), ((True, 121), "GCJ-02"), ((31, 121), "unknown")]:
            norm = normalize_candidate(replace(raw, coordinates=coords, coordinate_system=system))
            self.assertIsNone(norm.coordinates)
            self.assertEqual(norm.boundary_status, "needs_review")

    def test_boundary_edges_and_outside(self):
        self.assertEqual(boundary_status((31.170, 121.463)), "inside_pilot")
        self.assertEqual(boundary_status((31.1895, 121.469)), "needs_review")
        self.assertEqual(boundary_status((31.190, 121.469)), "needs_review")
        self.assertEqual(boundary_status((31.175, 121.475)), "outside_pilot")
        self.assertEqual(boundary_status((31.23, 121.48)), "outside_pilot")
        self.assertEqual(boundary_status(None), "needs_review")

    def test_alias_and_spatial_merge_preserves_provenance(self):
        a = candidate(aliases=["Test Museum"])
        b = candidate("2", source_type="osm", name_zh="", name_en="Test Museum", coordinates=(31.1751, 121.4661))
        merged = deduplicate_candidates([normalize_candidate(x) for x in (a, b)])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0].merged_source_records), 2)
        self.assertEqual(len(merged[0].sources), 2)
        self.assertEqual(merged[0].field_sources["coordinates"], "amap:1")
        self.assertEqual(merged[0].candidate_id, deduplicate_candidates([normalize_candidate(b), normalize_candidate(a)])[0].candidate_id)

    def test_neither_name_nor_proximity_alone_merges(self):
        a = candidate()
        others = [candidate("2", coordinates=(31.185, 121.466)),
                  candidate("2", name_zh="独立雕塑", entity_kind="artwork"),
                  candidate("2", name_zh="测试美术馆", entity_kind="district"),
                  candidate("2", coordinates=None), candidate("2", name_zh="另外美术馆")]
        for other in others:
            self.assertEqual(len(deduplicate_candidates([normalize_candidate(a), normalize_candidate(other)])), 2)

    def test_address_disambiguates_fuzzy_names(self):
        a = candidate(name_zh="West Bund Art Museum", address="龙腾大道123号")
        b = candidate("2", name_zh="West Bund Arts Museum", address="龙腾大道123号")
        self.assertEqual(len(deduplicate_candidates([normalize_candidate(a), normalize_candidate(b)])), 1)
        b.address = "其他路987号"
        self.assertEqual(len(deduplicate_candidates([normalize_candidate(a), normalize_candidate(b)])), 2)

    def test_no_transitive_chain_merge(self):
        records = [candidate(str(i), coordinates=(31.175 + i * .0007, 121.466)) for i in range(3)]
        self.assertEqual(len(deduplicate_candidates(list(map(normalize_candidate, records)))), 2)

    def test_evidence_supports_are_not_final_tags(self):
        raw = candidate(source_type="government", snippets=[dict(text="旧厂房改造", supports=["history"])])
        item = deduplicate_candidates([normalize_candidate(raw)])[0]
        bundle = build_evidence_bundle(item)
        self.assertEqual(bundle.evidence["history"][0]["text"], "旧厂房改造")
        self.assertEqual(bundle.evidence["history"][0]["url"], raw.source_url)
        self.assertIn("access", bundle.gaps)
        self.assertNotIn("culture_tags", asdict(item))
        self.assertFalse(bundle.enrichment_permitted)

    def test_partial_failure_retains_yielded_records_and_boundary_audit(self):
        class Broken(Source):
            name = "broken"
            def collect(self):
                yield candidate()
                raise TimeoutError("never log sensitive URL")
        class Good(Source):
            name = "good"
            def collect(self):
                yield candidate("2", coordinates=(31.23, 121.48))
        raw, canonical, bundles, report = collect_sources([Broken(None), Good(None)])
        self.assertEqual((len(raw), len(canonical)), (2, 1))
        self.assertTrue(report["partial_source_failure"])
        self.assertEqual(report["counts"]["boundary_excluded"], 1)
        self.assertNotIn("sensitive", json.dumps(report))

    def test_actual_coverage_and_taxonomy_unchanged(self):
        analyzer = WestBundCoverageAnalyzer(baseline_repository())
        taxonomy = json.dumps(analyzer.repository.taxonomy, sort_keys=True)
        report = analyzer.analyze()
        self.assertEqual(report["poi_count"], 5)
        self.assertEqual(report["museum_dependency"]["count"], 4)
        self.assertEqual(report["coverage"]["culture_tags"]["frequency"]["urban_renewal"], 5)
        self.assertIn("history", report["coverage"]["interest_tags"]["zero_coverage"])
        self.assertIn("modern_city", report["coverage"]["interest_tags"]["low_coverage"])
        self.assertEqual(json.dumps(analyzer.repository.taxonomy, sort_keys=True), taxonomy)

    def test_amap_fixture(self):
        record = AmapSource.parse(dict(id="A1", name="美术馆", address=[], location="121.466,31.175", type="科教文化服务;美术馆", typecode="140100"), "now")
        self.assertEqual(record.coordinates, (31.175, 121.466))
        self.assertEqual(record.coordinate_system, "GCJ-02")
        self.assertEqual(record.address, "")
        self.assertEqual(record.entity_kind, "venue")

    def test_osm_way_center_fixture(self):
        raw = OSMSource.parse(dict(type="way", id=23, center=dict(lat=31.175, lon=121.466),
            tags={"name": "滨江公园", "leisure": "park", "access": "yes", "alt_name": "别名一;别名二"}), "now")
        self.assertEqual(raw.source_candidate_id, "way/23")
        self.assertEqual(raw.entity_kind, "public_space")
        self.assertEqual(raw.aliases, ["别名一", "别名二"])
        self.assertEqual(raw.raw_provider_tags["leisure"], "park")
        self.assertFalse(hasattr(raw, "interest_tags"))

    def test_official_html_is_short_and_literal(self):
        result = extract_page('<script>虚构美术馆</script><p>真实美术馆原址为旧厂房。</p><a href="/detail_a.html">真实美术馆</a>', ["真实美术馆", "虚构美术馆"])
        self.assertEqual(result["excerpts"]["虚构美术馆"], [])
        self.assertIn("真实美术馆原址为旧厂房。", result["excerpts"]["真实美术馆"])
        self.assertEqual(result["links"][0]["href"], "/detail_a.html")

    def test_cache_replay_secret_redaction_retry_and_integrity(self):
        calls = []
        def opener(request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise TimeoutError("key=fixture-secret")
            return Response('{"status":"1","echo":"fixture-secret"}')
        with tempfile.TemporaryDirectory() as directory:
            http = CachedHTTP(directory, opener=opener, sleeper=lambda _: None)
            first = http.get("amap", "https://example.org/api", {"q": "museum"}, secret_params={"key": "fixture-secret"})
            self.assertEqual(len(calls), 2)
            saved = next(Path(directory).glob("*.json"))
            self.assertNotIn("fixture-secret", saved.read_text())
            replay = CachedHTTP(directory, offline=True)
            second = replay.get("amap", "https://example.org/api", {"q": "museum"})
            self.assertEqual(first, second)
            with self.assertRaises(SourceError):
                replay.get("osm", "https://example.org/miss")
            corrupt = json.loads(saved.read_text())
            corrupt["response"]["status"] = "0"
            saved.write_text(json.dumps(corrupt))
            with self.assertRaises(SourceError):
                replay.get("amap", "https://example.org/api", {"q": "museum"})

    def test_amap_provider_failure_and_missing_configuration(self):
        class HTTP:
            offline = False
            def get(self, *args, **kwargs):
                return {"response": {"status": "0"}, "retrieved_at": "now"}
        with patch.dict("os.environ", {"AMAP_API_KEY": "fixture-key"}):
            source = AmapSource(HTTP())
            self.assertEqual(list(source.collect()), [])
            self.assertTrue(source.errors)
        with patch.dict("os.environ", {}, clear=True):
            source = AmapSource(HTTP())
            self.assertEqual(list(source.collect()), [])
            self.assertEqual(source.errors[0]["request"], "configuration_missing_AMAP_API_KEY")

    def test_failure_cache_does_not_repeat_requests(self):
        calls = []
        def fail(*args, **kwargs):
            calls.append(1)
            raise TimeoutError("secret-do-not-log")
        with tempfile.TemporaryDirectory() as directory:
            http = CachedHTTP(directory, opener=fail, sleeper=lambda _: None, retries=1)
            for _ in range(2):
                with self.assertRaises(SourceError):
                    http.get("osm", "https://example.org/api")
            self.assertEqual(len(calls), 2)
            failure = next(Path(directory).glob("*.failure.json"))
            self.assertNotIn("secret-do-not-log", failure.read_text())
            self.assertEqual(json.loads(failure.read_text())["attempts"], 2)

    def test_ancillary_records_excluded_without_cultural_tagging(self):
        for raw in (candidate(name_zh="西岸美术馆停车场"), candidate(source_category="餐饮服务;咖啡厅"),
                    candidate(name_zh="美术馆-临时装置(打卡点)"), candidate(raw_provider_tags={"adname": "浦东新区"})):
            self.assertIsNotNone(discovery_exclusion(raw))
        self.assertIsNone(discovery_exclusion(candidate()))

    def test_distinct_osm_tanks_remain_separate(self):
        a = candidate("way/1", source_type="osm", name_zh="油罐艺术中心")
        b = replace(a, source_candidate_id="way/2")
        self.assertEqual(len(deduplicate_candidates(list(map(normalize_candidate, (a, b))))), 2)

    def test_existing_cluster_not_outside_pilot(self):
        for poi in WestBundCoverageAnalyzer().repository.get_pois_by_zone("west_bund"):
            self.assertNotEqual(boundary_status(poi.coordinates), "outside_pilot", poi.id)

    def test_official_collection_mock(self):
        class HTTP:
            def get(self, source, url, params=None, **kwargs):
                html = '<p>真实美术馆原址为旧厂房。</p>'
                return dict(response=kwargs['transform'](html), retrieved_at="fixture-time")
        with patch('src.poi_pipeline.sources.official_source.SEEDS', [("https://www.westbund.com/example.html", ["真实美术馆"], "venue")]):
            records = list(OfficialSource(HTTP()).collect())
        self.assertEqual(len(records), 1)
        self.assertIn("history", records[0].supports)
        self.assertIsNone(records[0].coordinates)

    def test_osm_partial_remark_and_malformed_record(self):
        class HTTP:
            def get(self, *args, **kwargs):
                return dict(retrieved_at="fixture-time", response={"remark": "timeout", "elements": [
                    {"tags": {"name": "broken"}},
                    {"type": "node", "id": 1, "lat": 31.17, "lon": 121.46, "tags": {"name": "公园", "leisure": "park"}}]})
        source = OSMSource(HTTP())
        self.assertEqual(len(list(source.collect())), 1)
        self.assertEqual(len(source.errors), 2)


if __name__ == "__main__":
    unittest.main()
