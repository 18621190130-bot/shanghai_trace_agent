"""Read-only analysis of existing RouteVersion legs, selected visits and progress.

No TripStore, RouteEngine, walking provider or replan dependency exists here.
"""
from datetime import timedelta
import math
from ..weather_models import CurrentWeather, local_time
from ..world_models import PoiLiveInfo, OpenStatus, LiveInfoApplicability
from ..reality_models import RealityCheckResult, RealityWarning, RealityStatus, WarningCode as Code
from .weather_service import snapshot
from .weather_risk import WeatherRiskClassifier
from .opening_hours_evaluator import OpeningHoursEvaluator

BUDGET_TOLERANCE_MINUTES = 5
TRIVIAL_WALK_MINUTES = 1
TRIVIAL_WALK_METRES = 100


def nonnegative(value):
    return value if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 else None


class RouteRealityCheckService:
    def __init__(self, weather, poi_info, *, repository=None, opening=None, classifier=None):
        self.weather, self.poi_info, self.repository = weather, poi_info, repository
        self.opening = opening if opening is not None else OpeningHoursEvaluator()
        self.classifier = classifier if classifier is not None else WeatherRiskClassifier()

    @staticmethod
    def _hours_relevant(stop, applicability):
        if applicability not in (LiveInfoApplicability.FULL, LiveInfoApplicability.LIMITED):
            return False
        # Only explicit exterior scope waives interior opening constraints; role is irrelevant.
        scope = stop.get('visit_scope') or ''
        exterior = ('外观', '外部公共空间', '外围', 'exterior', 'outside only')
        interior = ('内部', '入内', '展厅', 'interior', 'inside')
        return not (stop.get('selected_visit_mode') == 'walk_stop' and
                    any(term in scope.lower() for term in exterior) and
                    not any(term in scope.lower() for term in interior))

    def check_route_reality(self, trip_state, route_version, current_location=None, now=None):
        now = local_time(now)
        trip, version = snapshot(trip_state), snapshot(route_version)
        if not isinstance(trip, dict) or not isinstance(version, dict) or not isinstance(version.get('route_snapshot'), dict):
            raise ValueError('TripState and RouteVersion snapshots are required')
        version_id = version.get('version_id')
        history = trip.get('route_versions', [])
        if not version_id or (history and history[-1]['version_id'] != version_id):
            raise ValueError('Reality check requires the current RouteVersion')
        route = version['route_snapshot']
        excluded = set(trip.get('visited_poi_ids', []) + trip.get('skipped_poi_ids', []))
        stops = [(i, s) for i, s in enumerate(route.get('ordered_pois', [])) if s['poi_id'] not in excluded]
        warnings, rows, affected_legs = [], [], []
        quality = dict(walking='AVAILABLE', weather='NOT_REQUESTED', poi_live_info={})
        budget = nonnegative(trip.get('remaining_minutes'))
        metrics = dict(remaining_poi_ids=[s['poi_id'] for _, s in stops], remaining_budget_minutes=budget,
                       budget_tolerance_minutes=BUDGET_TOLERANCE_MINUTES, stops=rows,
                       eta_basis='Existing RouteVersion walking legs; no GPS rerouting',
                       budget_is_soft=True)
        if not stops:
            metrics.update(remaining_live_walking_minutes=0, remaining_reference_walking_minutes=0,
                           remaining_planned_visit_minutes=0, reality_adjusted_remaining_minutes=0,
                           remaining_walking_distance_m=0)
            return RealityCheckResult(now.isoformat(), version_id, RealityStatus.OK, metrics=metrics, data_quality=quality)

        legs = route.get('walking_legs') or []
        by_destination = {}
        for index, leg in enumerate(legs):
            by_destination.setdefault(leg.get('to_poi_id'), []).append((index, leg))
        reference_walk = live_walk = distance = visits = 0
        walk_complete = distance_complete = visit_complete = True
        cursor = now
        eta_confidence = 'HIGH'
        partial = False
        for route_index, stop in stops:
            pid = stop['poi_id']
            matches = by_destination.get(pid, [])
            needs_leg = route_index > 0 or route.get('request', {}).get('start_lat') is not None
            leg_index, leg = matches[0] if len(matches) == 1 else (None, {})
            duration = nonnegative(leg.get('duration_s')) if leg else (0 if not needs_leg else None)
            metres = nonnegative(leg.get('distance_m')) if leg else (0 if not needs_leg else None)
            status = leg.get('status', 'UNAVAILABLE') if needs_leg or leg else 'AVAILABLE'
            if status not in ('AVAILABLE', 'FALLBACK_ESTIMATE', 'UNAVAILABLE'):
                status = 'UNAVAILABLE'
            if duration is None or metres is None or len(matches) > 1:
                status = 'UNAVAILABLE'
            if status != 'AVAILABLE':
                partial = True
                eta_confidence = 'LOW' if status == 'UNAVAILABLE' else ('MEDIUM' if eta_confidence == 'HIGH' else eta_confidence)
                affected_legs.append(dict(leg_index=leg_index, from_poi_id=leg.get('from_poi_id'),
                                          to_poi_id=pid, walking_status=status))
            if duration is None:
                walk_complete = False
                cursor = None
            else:
                reference_walk += duration / 60
                if status == 'AVAILABLE':
                    live_walk += duration / 60
                if cursor is not None:
                    cursor += timedelta(seconds=duration)
            if metres is None:
                distance_complete = False
            else:
                distance += metres
            stay = nonnegative(stop.get('estimated_stay_minutes'))
            if stay is None:
                visit_complete = False
                partial = True
            else:
                visits += stay
            arrival = cursor
            departure = arrival + timedelta(minutes=stay) if arrival is not None and stay is not None else None
            cursor = departure
            row = dict(poi_id=pid, leg_index=leg_index, walking_status=status, walking_minutes=duration / 60 if duration is not None else None,
                       selected_visit_mode=stop.get('selected_visit_mode'), visit_scope=stop.get('visit_scope'),
                       planned_visit_minutes=stay, estimated_arrival=arrival.isoformat() if arrival else None,
                       estimated_departure=departure.isoformat() if departure else None, eta_confidence=eta_confidence)
            rows.append(row)
            try:
                info = self.poi_info.get_poi_live_info(pid, current_local_time=now)
                if not isinstance(info, PoiLiveInfo):
                    raise TypeError('Invalid observation')
            except Exception:
                mapping = getattr(self.poi_info, 'mappings', None)
                try:
                    mapped = mapping.get(pid) if mapping is not None else None
                except Exception:
                    mapped = None
                info = PoiLiveInfo(core_poi_id=pid, live_info_applicability=mapped.get('live_info_applicability') if mapped else None,
                                   error_code='provider_response_invalid')
            quality['poi_live_info'][pid] = dict(data_status=info.live_data_status, applicability=info.live_info_applicability,
                                               error_code=info.error_code, cache_hit=info.cache_hit)
            row.update(provider_open_status=info.open_status, opening_hours=info.opentime_today,
                       live_info_applicability=info.live_info_applicability, provider_status=info.live_data_status)
            if not self._hours_relevant(stop, info.live_info_applicability):
                row['opening_evaluation'] = 'NOT_APPLICABLE'
                if info.live_info_applicability is None:
                    partial = True
                continue
            if info.live_data_status == 'UNAVAILABLE':
                partial = True
            at_arrival = (self.opening.evaluate_open_status(info.opentime_today, arrival, fetched_at=info.fetched_at)
                          if arrival is not None else OpenStatus.UNKNOWN)
            row['opening_evaluation'] = at_arrival
            details = dict(estimated_arrival=row['estimated_arrival'], estimated_departure=row['estimated_departure'],
                           opening_hours=info.opentime_today, provider_status=info.live_data_status,
                           current_open_status=info.open_status, planned_visit_minutes=stay)
            if at_arrival == OpenStatus.CLOSED:
                warnings.append(RealityWarning(Code.POI_CLOSED, 'HIGH', '预计到达时营业时间已结束或尚未开放。',
                                               details, pid, leg_index, 'poi_live_info', eta_confidence))
            elif at_arrival == OpenStatus.OPEN:
                close = self.opening.closes_at(info.opentime_today, arrival, fetched_at=info.fetched_at)
                row['closes_at'] = close.isoformat() if close else None
                if close is not None and departure is not None and departure > close:
                    warnings.append(RealityWarning(Code.POI_MAY_CLOSE_BEFORE_ARRIVAL, 'HIGH', '计划参观可能无法在关门前完成。',
                                                   dict(details, closes_at=close.isoformat()), pid, leg_index, 'poi_live_info', eta_confidence))
            elif arrival is not None or self.opening.evaluate_open_status(info.opentime_today, now, fetched_at=info.fetched_at) == OpenStatus.UNKNOWN:
                partial = True
                if arrival is None:
                    details['eta_unavailable'] = True
                warnings.append(RealityWarning(Code.OPENING_HOURS_UNKNOWN, 'LOW', '缺少可可靠解析的到达日营业时间。',
                                               details, pid, leg_index, 'poi_live_info', 'LOW'))
            else:
                partial = True
                row['opening_evaluation_reason'] = 'ETA_UNAVAILABLE'

        adjusted = reference_walk + visits if walk_complete and visit_complete else None
        walking_confidence = 'HIGH' if not affected_legs else ('LOW' if any(l['walking_status'] == 'UNAVAILABLE' for l in affected_legs) else 'MEDIUM')
        metrics.update(remaining_live_walking_minutes=live_walk, remaining_reference_walking_minutes=reference_walk if walk_complete else None,
                       known_walking_minutes=reference_walk, remaining_planned_visit_minutes=visits if visit_complete else None,
                       reality_adjusted_remaining_minutes=adjusted, remaining_walking_distance_m=distance if distance_complete else None,
                       budget_confidence=walking_confidence, timing_complete=walk_complete and visit_complete)
        if affected_legs:
            quality['walking'] = 'UNAVAILABLE' if any(l['walking_status'] == 'UNAVAILABLE' for l in affected_legs) else 'FALLBACK_ESTIMATE'
            warnings.append(RealityWarning(Code.LIVE_ROUTE_DATA_UNAVAILABLE, 'LOW', '部分剩余步行段缺少真实步行数据。',
                                           dict(affected_legs=affected_legs), source='route_version', confidence='LOW'))
        if adjusted is not None and budget is not None and adjusted > budget + BUDGET_TOLERANCE_MINUTES:
            warnings.append(RealityWarning(Code.LIVE_ROUTE_EXCEEDS_BUDGET, 'MEDIUM', '剩余步行及计划参观可能超出时间预算。',
                                           dict(budget=budget, adjusted_duration=adjusted, excess_minutes=adjusted - budget,
                                                tolerance_minutes=BUDGET_TOLERANCE_MINUTES, budget_is_soft=True),
                                           source='route_version', confidence=walking_confidence))
        if budget is None:
            partial = True
            quality['budget'] = 'UNAVAILABLE'
        try:
            weather = self.weather.get_current_weather(current_location, trip_state=trip, route_version=version)
            if not isinstance(weather, CurrentWeather):
                raise TypeError('Invalid weather')
        except Exception:
            weather = CurrentWeather(error_code='provider_response_invalid')
        quality['weather'] = weather.data_status
        if weather.data_status == 'UNAVAILABLE':
            partial = True
            warnings.append(RealityWarning(Code.WEATHER_DATA_UNAVAILABLE, 'LOW', '当前天气数据暂不可用；其他路线检查已继续。',
                                           dict(error_code=weather.error_code), source='weather', confidence='LOW'))
        else:
            if weather.data_status == 'PARTIAL':
                partial = True
            risks = self.classifier.classify(weather)
            if risks and (reference_walk > TRIVIAL_WALK_MINUTES or distance > TRIVIAL_WALK_METRES):
                affected = []
                if self.repository is not None:
                    for _, stop in stops:
                        poi = self.repository.get_poi_by_id(stop['poi_id'])
                        if poi is not None and getattr(poi, 'environment', None) in ('outdoor', 'mixed'):
                            affected.append(poi.id)
                warnings.append(RealityWarning(Code.WEATHER_RISK, 'MEDIUM', '明显天气风险可能影响剩余户外步行。',
                                               dict(risk_type=risks, weather=weather.weather_text, temperature=weather.temperature_c,
                                                    wind=weather.wind_power, remaining_walking_minutes=metrics['remaining_reference_walking_minutes'],
                                                    affected_poi_ids=affected), source='weather', confidence='HIGH'))
        status = RealityStatus.PARTIAL if partial else RealityStatus.WARNING if warnings else RealityStatus.OK
        if weather.data_status == 'UNAVAILABLE' and not walk_complete and all(r.get('provider_status') == 'UNAVAILABLE' for r in rows):
            status = RealityStatus.UNAVAILABLE
        return RealityCheckResult(now.isoformat(), version_id, status, tuple(warnings), weather.to_dict(), metrics, quality)
