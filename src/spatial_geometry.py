"""Pure small-area geometry helpers; never connected to Trip automation."""
import math
from .geo_utils import haversine_km
from .spatial_profiles import point

EARTH_M=6371008.8

def xy(value,reference):
    p=point(value);r=point(reference)
    return math.radians(p.lng-r.lng)*EARTH_M*math.cos(math.radians(r.lat)),math.radians(p.lat-r.lat)*EARTH_M

def distance_to_segment_m(location,start,end):
    p=point(location);point(start);point(end)
    # Locally projected tangent coordinates; intended for Shanghai City Walk extents.
    a=xy(start,location);b=xy(end,location);dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,-(a[0]*dx+a[1]*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    return math.hypot(a[0]+t*dx,a[1]+t*dy)

def point_in_polygon(location,vertices):
    point(location)
    if len(vertices)<4 or vertices[0]!=vertices[-1]:raise ValueError('Closed polygon required')
    for p in vertices:point(p)
    inside=False;x,y=location['lng'],location['lat']
    for a,b in zip(vertices,vertices[1:]):
        if distance_to_segment_m(location,a,b)<.001:return True
        if (a['lat']>y)!=(b['lat']>y):
            crossing=(b['lng']-a['lng'])*(y-a['lat'])/(b['lat']-a['lat'])+a['lng']
            if x<crossing:inside=not inside
    return inside

def distance_to_linear_extent_m(location,extent):
    if extent['type']=='START_END':vertices=[extent['start'],extent['end']]
    elif extent['type']=='POLYLINE':vertices=extent['vertices']
    else:raise ValueError('Linear extent required')
    if len(vertices)<2:raise ValueError('Two endpoints required')
    return min(distance_to_segment_m(location,a,b) for a,b in zip(vertices,vertices[1:]))

def within_extent(location,extent):
    if extent['type']=='POLYGON':return point_in_polygon(location,extent['vertices'])
    if extent['type']=='CENTER_RADIUS':
        p,c=point(location),point(extent['center'])
        return haversine_km((p.lat,p.lng),(c.lat,c.lng))*1000<=extent['radius_m']
    raise ValueError('Area extent required')

def polygon_is_simple(vertices):
    def cross(a,b,c):return (b['lng']-a['lng'])*(c['lat']-a['lat'])-(b['lat']-a['lat'])*(c['lng']-a['lng'])
    edges=list(zip(vertices,vertices[1:]));n=len(edges)
    for i,(a,b) in enumerate(edges):
        if a==b:return False
        for j,(c,d) in enumerate(edges):
            if j<=i+1 or i==0 and j==n-1:continue
            if cross(a,b,c)*cross(a,b,d)<=0 and cross(c,d,a)*cross(c,d,b)<=0:
                # Collinear disjoint segments do not intersect.
                if max(min(a['lng'],b['lng']),min(c['lng'],d['lng']))<=min(max(a['lng'],b['lng']),max(c['lng'],d['lng'])) and max(min(a['lat'],b['lat']),min(c['lat'],d['lat']))<=min(max(a['lat'],b['lat']),max(c['lat'],d['lat'])):return False
    return True
