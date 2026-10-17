"""Small local polygon diagnostics; no GIS dependency or routing claim."""
import math
from .boundary import boundary_status

def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def intersects(a,b,c,d):
    def on(a,b,p):
        return abs(cross(a,b,p))<1e-12 and all(min(a[i],b[i])-1e-12<=p[i]<=max(a[i],b[i])+1e-12 for i in (0,1))
    return (cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0) or any((on(a,b,c),on(a,b,d),on(c,d,a),on(c,d,b)))

def validate_polygon(polygon, seeds, margin=150):
    points=[tuple(p) for p in polygon]
    valid=len(points)>=3 and len(set(points))==len(points) and all(len(p)==2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in p) and 30<p[0]<32 and 120<p[1]<123 for p in points)
    if not valid: raise ValueError('Invalid Shanghai GCJ-02 polygon coordinates')
    edges=list(zip(points,points[1:]+points[:1]))
    crossings=[(i,j) for i,(a,b) in enumerate(edges) for j,(c,d) in enumerate(edges) if j>i+1 and not(i==0 and j==len(edges)-1) and intersects(a,b,c,d)]
    origin=points[0]
    projected=[((p[1]-origin[1])*95.1,(p[0]-origin[0])*111.2) for p in points]
    area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(projected,projected[1:]+projected[:1])))/2
    coverage=[dict(poi_id=p['poi_id'],name=p['name'],coordinates=p['coordinates'],status=boundary_status(p['coordinates'],points,margin)) for p in seeds]
    result=dict(polygon_valid=not crossings and area>.05,self_intersections=crossings,area_km2=round(area,4),
        reasonable_area=.05<area<15,not_administrative_scale=area<15,not_degenerate=area>.05,
        gcj02_coordinates_valid=True,seed_coverage=coverage,
        all_production_seeds_covered=all(p['status']!='outside_pilot' for p in coverage),
        area_policy='Product diagnostic range 0.05–15 km²; not a cadastral or surveyed area.')
    if not all(result[k] for k in ('polygon_valid','reasonable_area','not_administrative_scale','all_production_seeds_covered')):
        raise ValueError(str(result))
    return result
