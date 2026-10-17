"""Compatibility import; all implementation lives in NearbyService."""
from .nearby_service import NearbyService, normalize_categories, rank, merge

NearbyRestStopService = NearbyService
