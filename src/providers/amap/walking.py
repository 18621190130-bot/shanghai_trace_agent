"""Normalize Amap v3 walking and GPS coordinate conversion responses."""
from datetime import datetime, timezone
import math

from ..base import ProviderResponseError
from ...walking_models import Location, WalkingRouteResult, WalkingStep, merge_geometry


def number(value, *, optional=False):
    if optional and (value is None or value == '' or value == []):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = float(value)
        if not math.isfinite(result) or result < 0:
            raise ValueError()
        return result
    except (ValueError, TypeError, OverflowError):
        pass
    raise ProviderResponseError()


def parse_polyline(value):
    try:
        if not isinstance(value, str) or not value:
            raise ValueError()
        points = []
        for raw in value.split(';'):
            lng, lat = map(float, raw.split(','))
            loc = Location(lat, lng, 'GCJ02')
            points.append((loc.lng, loc.lat))
        return merge_geometry([points])
    except (ValueError, TypeError, OverflowError):
        pass
    raise ProviderResponseError()


class AmapWalkingProvider:
    def __init__(self, client):
        self.client = client

    def normalize_location_for_amap(self, location):
        if location.coordinate_system == 'GCJ02':
            return location
        data = self.client.get('/v3/assistant/coordinate/convert',
                               {'locations': location.amap_value(), 'coordsys': 'gps'})
        points = parse_polyline(data.get('locations'))
        if len(points) != 1:
            raise ProviderResponseError()
        return Location(points[0][1], points[0][0], 'GCJ02')

    def get_walking_route(self, origin, destination):
        origin = self.normalize_location_for_amap(origin)
        destination = self.normalize_location_for_amap(destination)
        data = self.client.get('/v3/direction/walking',
                               {'origin': origin.amap_value(), 'destination': destination.amap_value()})
        try:
            path = data['route']['paths'][0]
            distance = number(path['distance'])
            duration = number(path['duration'])
            raw_steps = path['steps']
            if not isinstance(raw_steps, list) or not raw_steps:
                raise ProviderResponseError()
            steps = []
            for item in raw_steps:
                def text_field(key):
                    value = item.get(key)
                    return self.client.redact_text(value) if isinstance(value, str) else None
                steps.append(WalkingStep(text_field('instruction'), text_field('road'),
                                         number(item.get('distance'), optional=True),
                                         number(item.get('duration'), optional=True),
                                         parse_polyline(item.get('polyline'))))
            geometry = merge_geometry(s.polyline for s in steps)
            if not geometry:
                raise ProviderResponseError()
            return WalkingRouteResult(origin, destination, distance, duration, tuple(steps), geometry,
                                      'amap', datetime.now(timezone.utc).isoformat())
        except (KeyError, TypeError, IndexError, AttributeError):
            pass
        raise ProviderResponseError()
