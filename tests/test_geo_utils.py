import unittest
from src.geo_utils import haversine_km, to_gcj02


class GeoTests(unittest.TestCase):
    def test_haversine_known_equatorial_distance_and_symmetry(self):
        self.assertAlmostEqual(haversine_km((0, 0), (0, 1)), 111.19508, places=4)
        self.assertEqual(haversine_km((31, 121), (31, 121)), 0)
        self.assertEqual(haversine_km((31, 121), (32, 122)), haversine_km((32, 122), (31, 121)))

    def test_conversion_reference_vector(self):
        # Independently recorded eviltransform WGS84 -> GCJ-02 Beijing vector.
        lat, lng = to_gcj02(39.915, 116.404, "WGS84")
        self.assertAlmostEqual(lat, 39.91640428150164, places=6)
        self.assertAlmostEqual(lng, 116.41024449916938, places=6)
        self.assertEqual(to_gcj02(31, 121, "GCJ-02"), (31, 121))
        self.assertEqual(to_gcj02(40, -74, "WGS84"), (40, -74))
