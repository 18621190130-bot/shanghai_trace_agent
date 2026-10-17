"""Validated spatial sidecar. Identity IDs are deliberately not a routing prerequisite."""
import copy
import json
import math
from pathlib import Path
from .walking_models import Location

DEFAULT_SPATIAL_PATH=Path(__file__).resolve().parents[1]/'data/core_spatial_profiles.json'
SPATIAL_TYPES={'POINT','AREA','LINEAR'}
ANCHOR_SOURCES={'AMAP_POI','AMAP_ENTRANCE','CORE_EXISTING','TRACEMATE_CURATED'}
EXTENT_SOURCES={'PROVIDER','DERIVED','TRACEMATE_CURATED'}

def confidence(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid spatial confidence')

def point(value):
    if not isinstance(value,dict) or value.get('coordinate_system')!='GCJ02':raise ValueError('Spatial coordinates must be explicit GCJ02')
    return Location(value.get('lat'),value.get('lng'),'GCJ02')

def anchor(value):
    p=point(value)
    if value.get('source') not in ANCHOR_SOURCES:raise ValueError('Invalid anchor source')
    confidence(value.get('confidence'))
    if not value.get('notes'):raise ValueError('Anchor justification required')
    return p

def validate_extent(value,spatial_type):
    if not isinstance(value,dict) or value.get('coordinate_system')!='GCJ02':raise ValueError('Invalid extent')
    if value.get('extent_source') not in EXTENT_SOURCES:raise ValueError('Invalid extent provenance')
    confidence(value.get('extent_confidence'))
    if not value.get('notes') or not isinstance(value.get('evidence'),list):raise ValueError('Extent justification/evidence required')
    if value['extent_source']=='PROVIDER' and not value.get('provider_boundary_reference'):raise ValueError('Provider boundary needs explicit boundary evidence')
    kind=value.get('type')
    if spatial_type=='AREA' and kind not in ('POLYGON','CENTER_RADIUS'):raise ValueError('Invalid area extent type')
    if spatial_type=='LINEAR' and kind not in ('START_END','POLYLINE'):raise ValueError('Invalid linear extent type')
    if kind=='CENTER_RADIUS':
        point(value.get('center'));r=value.get('radius_m')
        if isinstance(r,bool) or not isinstance(r,(int,float)) or not math.isfinite(r) or r<=0:raise ValueError('Invalid radius')
    elif kind=='START_END':
        a,b=point(value.get('start')),point(value.get('end'))
        if a==b:raise ValueError('Linear extent must have distinct endpoints')
    else:
        vertices=value.get('vertices')
        minimum=4 if kind=='POLYGON' else 2
        if not isinstance(vertices,list) or len(vertices)<minimum:raise ValueError('Insufficient extent vertices')
        points=[point(p) for p in vertices]
        if kind=='POLYGON':
            if points[0]!=points[-1] or len(set((p.lat,p.lng) for p in points[:-1]))<3:raise ValueError('Polygon must be closed and nondegenerate')
            area=sum(a.lng*b.lat-b.lng*a.lat for a,b in zip(points,points[1:]))
            if abs(area)<1e-12:raise ValueError('Degenerate polygon')
            from .spatial_geometry import polygon_is_simple
            if not polygon_is_simple(vertices):raise ValueError('Self-intersecting polygon')
        elif len(set((p.lat,p.lng) for p in points))<2:raise ValueError('Degenerate polyline')

class SpatialProfileRepository:
    def __init__(self,path=DEFAULT_SPATIAL_PATH,*,records=None,core_ids=None):
        records=records if records is not None else json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(records,dict):raise ValueError('Spatial sidecar must be an object')
        if core_ids is not None and set(records)!=set(core_ids):raise ValueError('Spatial/Core identity sets differ')
        for pid,row in records.items():
            if not isinstance(row,dict) or row.get('core_id')!=pid or row.get('spatial_type') not in SPATIAL_TYPES:raise ValueError('Invalid spatial profile')
            if type(row.get('reviewed')) is not bool or not row.get('notes'):raise ValueError('Missing spatial review metadata')
            anchor(row.get('route_anchor'))
            if row.get('anchor_source')!=row['route_anchor']['source']:raise ValueError('Inconsistent anchor source')
            if row['spatial_type']=='POINT':
                if row.get('spatial_extent') is not None:raise ValueError('Point does not require extent')
            else:
                extent=row.get('spatial_extent')
                if extent is None:
                    if row.get('extent_status')!='REVIEW_REQUIRED':raise ValueError('Missing extent must be explicitly flagged')
                else:
                    validate_extent(extent,row['spatial_type'])
                    if row.get('extent_source')!=extent['extent_source'] or row.get('extent_confidence')!=extent['extent_confidence']:raise ValueError('Inconsistent extent provenance')
                if row['spatial_type']=='LINEAR':anchor(row.get('secondary_anchor'))
        self._records=copy.deepcopy(records)
    def get(self,pid):return copy.deepcopy(self._records.get(pid))
    def all(self):return copy.deepcopy(self._records)
