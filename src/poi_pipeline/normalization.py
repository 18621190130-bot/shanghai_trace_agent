import math
import re
import unicodedata
from ..geo_utils import to_gcj02
from .boundary import boundary_status
from .models import NormalizedCandidate


def clean(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def match_key(value):
    key = "".join(c for c in clean(value).casefold() if c.isalnum())
    return re.sub(r"^(上海市|上海)", "", key)


def normalize_candidate(raw, config=None):
    issues = []
    coordinates = None
    if raw.coordinates is not None:
        try:
            if any(isinstance(v, bool) for v in raw.coordinates):
                raise ValueError()
            lat, lng = map(float, raw.coordinates)
            if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError()
            coordinates = to_gcj02(lat, lng, raw.coordinate_system)
        except (ValueError, TypeError, OverflowError):
            issues.append("invalid_or_unsupported_coordinates")
    else:
        issues.append("missing_coordinates")
    aliases = sorted({clean(a) for a in raw.aliases if clean(a)})
    return NormalizedCandidate(raw, clean(raw.name_zh), clean(raw.name_en), aliases,
                               clean(raw.address), coordinates, clean(raw.source_category).casefold(),
                               raw.entity_kind, boundary_status(coordinates, config.polygon, config.boundary_review_margin_m) if config else boundary_status(coordinates), issues)
