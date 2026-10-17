"""Read-only AMap navigation metadata; never changes routing coordinates."""
import math
from ...geo_utils import haversine_km

class AmapArrivalProvider:
    def __init__(self,client):self.client=client
    def fetch(self,ids):
        if not 1<=len(ids)<=10:raise ValueError('ID batch requires 1..10 identities')
        result=self.client.get('/v5/place/detail',{'id':'|'.join(ids),'show_fields':'navi'})
        return {p['id']:{'id':p['id'],'navi':p.get('navi',{})} for p in result.get('pois',[]) if p.get('id') in ids}

def entrance_coordinate(navi,target):
    """Only entr_location is parsed as coordinates; navi_poiid remains opaque."""
    value=navi.get('entr_location') if isinstance(navi,dict) else None
    if not isinstance(value,str):return None
    try:
        lng,lat=map(float,value.split(','))
        if not all(math.isfinite(x) for x in (lat,lng)) or not(30<=lat<=32 and 120<=lng<=123):return None
        if haversine_km((lat,lng),target)>0.5:return None
        return dict(lat=lat,lng=lng,coordinate_system='GCJ02')
    except (ValueError,TypeError):return None
