from .helpers import baseline_repository, PRE_PHASE2_5_PATH
import copy
import unittest
from src import POIRepository
from src.models import DataValidationError
from .helpers import write_repository, subset


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = baseline_repository()

    def test_load_and_all_queries(self):
        self.assertEqual(len(self.repo.get_all_pois()), 27)
        self.assertEqual(self.repo.get_poi_by_id("p13").name_en, "Wukang Mansion")
        self.assertIsNone(self.repo.get_poi_by_id("not-a-poi"))
        self.assertEqual(len(self.repo.get_pois_by_zone("wukang_fuxing_xujiahui")), 8)
        for method, tag, attr in (
            (self.repo.get_pois_by_interest_tag, "architecture", "interest_tags"),
            (self.repo.get_pois_by_experience_tag, "quiet_walk", "experience_tags"),
            (self.repo.get_pois_by_culture_tag, "literary_shanghai", "culture_tags")):
            pois = method(tag)
            self.assertTrue(pois)
            self.assertTrue(all(tag in getattr(p, attr) for p in pois))
        with self.assertRaises(ValueError):
            self.repo.get_pois_by_interest_tag("invented")

    def test_missing_coordinates_preserved(self):
        self.assertEqual(self.repo.get_missing_coordinate_ids(), [])
        raw = self.repo.get_raw_data()
        next(p for p in raw["pois"] if p["id"] == "p24")["location"]["lat"] = None
        repo = write_repository(self, raw)
        self.assertEqual(repo.get_missing_coordinate_ids(), ["p24"])
        p24 = repo.get_poi_by_id("p24")
        self.assertIsNone(p24.coordinates)
        self.assertIsNotNone(p24.original_coordinates[1])

    def test_coordinates_converted_without_changing_raw(self):
        p25 = self.repo.get_poi_by_id("p25")
        self.assertNotEqual(p25.coordinates, p25.original_coordinates)
        self.assertEqual(next(p for p in self.repo.get_raw_data()["pois"] if p["id"] == "p25")["location"]["lat"], p25.original_coordinates[0])
        raw = self.repo.get_raw_data()
        raw["pois"][0]["name"]["en"] = "Changed"
        self.assertNotEqual(self.repo.get_all_pois()[0].name_en, "Changed")

    def test_reject_core_corruption(self):
        mutations = [
            lambda r: r["pois"][0].pop("name"),
            lambda r: r["pois"][0]["tags"]["interest_tags"].append("invented"),
            lambda r: r["pois"][0]["location"].update(representative_lat=91),
            lambda r: r["pois"][0]["visit_profile"]["modes"]["walk_stop"].update(deep=1),
            lambda r: r["pois"][0].update(walk_zone={"id": "invalid"}),
            lambda r: r["pois"][0]["location"].update(coordinate_system="unknown"),
            lambda r: r["route_engine_defaults"].update(walking_speed_m_per_min=0),
            lambda r: r["metadata"].update(poi_count=999),
            lambda r: r["pois"][0]["planning"].update(ticket_required="unknown"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                raw = self.repo.get_raw_data()
                mutate(raw)
                with self.assertRaises(DataValidationError):
                    write_repository(self, raw)

    def test_duplicate_ids_rejected(self):
        raw = self.repo.get_raw_data()
        raw["pois"][1]["id"] = raw["pois"][0]["id"]
        with self.assertRaises(DataValidationError):
            write_repository(self, raw)

    def test_nullable_planning_fields_are_unknown(self):
        p13 = self.repo.get_poi_by_id("p13")
        self.assertIsNone(p13.opening_hours)
        self.assertIsNone(p13.ticket_required)
        self.assertIsNone(p13.reservation_required)


if __name__ == "__main__":
    unittest.main()
