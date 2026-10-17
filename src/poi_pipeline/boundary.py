"""Conservative pilot envelope; not an administrative boundary or zone change."""
import math

# GCJ-02: existing waterfront cluster from Star Museum to Gate M.
# North/south scope intentionally smaller than the complete official waterfront.
BOUNDS = (31.157, 121.458, 31.192, 121.476)  # S, W, N, E
REVIEW_MARGIN_M = 150
# Approximate west-bank corridor, clockwise (lat, lng). The eastern edge follows
# the bend in the waterfront and avoids treating Pudong as part of West Bund.
POLYGON = ((31.157, 121.458), (31.157, 121.467), (31.170, 121.467),
           (31.1775, 121.4648), (31.182, 121.4665), (31.1895, 121.473),
           (31.1895, 121.466), (31.180, 121.458))


def boundary_status(coordinates, polygon=None, review_margin_m=REVIEW_MARGIN_M):
    if coordinates is None:
        return "needs_review"
    polygon = tuple(polygon or POLYGON)
    lat, lng = coordinates
    inside, edge = False, float("inf")
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[0] > lat) != (b[0] > lat) and lng < (b[1]-a[1])*(lat-a[0])/(b[0]-a[0])+a[1]:
            inside = not inside
        # Local metric projection is sufficient for this ~4 km pilot boundary.
        ax, ay = (a[1]-lng)*95100, (a[0]-lat)*111200
        bx, by = (b[1]-lng)*95100, (b[0]-lat)*111200
        dx, dy = bx-ax, by-ay
        denominator = dx*dx+dy*dy
        t = max(0, min(1, -(ax*dx+ay*dy)/denominator)) if denominator else 0
        edge = min(edge, math.hypot(ax+t*dx, ay+t*dy))
    if edge <= review_margin_m:
        return "needs_review"
    return "inside_pilot" if inside else "outside_pilot"
