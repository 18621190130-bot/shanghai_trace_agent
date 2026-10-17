# Phase 3B_4 read-only API contracts

The approved Phase 3A / 3B_1 / 3B_2 / 3B_3 layers are frozen. This layer adds observations only. `WorldContextService.from_environment()` shares one existing `AmapClient` with location, POI and nearby providers.

```python
world.get_current_weather(current_location=None, *, current_core_poi_id=None,
                          trip_state=None, route_version=None)
world.get_weather_forecast(current_location=None, *, current_core_poi_id=None,
                           trip_state=None, route_version=None)
world.check_route_reality(trip_state, route_version, current_location=None, now=None)
```

All DTOs have `to_dict()`, suitable for JSON serialization. A `TripState` or defensive serialized snapshot and the current `RouteVersion` or its serialized snapshot are accepted. `route_version` must contain `version_id` and `route_snapshot`; a historical version is rejected. The caller supplies an already hydrated version. The service has no TripStore, replan, walking hydration or route mutation capability.

## Weather

Origin priority: explicit GPS, explicit/current logical Core, then first unvisited and unskipped Core in the supplied route. Production Repository coordinates are already effective GCJ02 routing coordinates: AREA/LINEAR use approved anchors. A logical current stop is only a fallback, not evidence of physical presence. Missing origin yields UNAVAILABLE.

LocationService performs official conversion, reverse geocoding and location caching. Adcode must be six digits. Weather queries use `/v3/weather/weatherInfo`, `city=adcode`, `extensions=base/all`, through the existing client. Provider time without an offset is interpreted as Shanghai local time; serialized times carry `+08:00`. All new calendar/ETA operations use `ZoneInfo('Asia/Shanghai')`. An injected `now` must be timezone aware.

`CurrentWeather`: provider, province, city, district, adcode, weather_text, temperature_c, humidity_pct, wind_direction, wind_power, report_time, data_status, fetched_at. Missing/invalid individual fields stay null. Temperatures accept finite -100..100 C, humidity 0..100. Weather-provider district usually stays null: regeo district is separately exposed in `resolved_location`, never synthesized into weather facts. Provider region can be broader than queried adcode; returned adcode/city stay as returned.

`WeatherForecast`: provider region, report_time, fetched_at, data_status, precision=DAILY, days. Each `WeatherForecastDay` has date, day/night weather, temperature, wind direction and wind power. No hourly/minute inference. Cache keys are `(provider, queried_adcode, current|forecast)`; TTL 600/1800 seconds, defensive bounded cache. Regeo and coordinate conversion caches are reused. Failures are not cached. Context is attached after cache retrieval, so two locations in one district retain their respective origins.

AVAILABLE means expected observation fields are present (native district is optional); PARTIAL means some provider fields are missing; UNAVAILABLE means origin/regeo/provider/response failure. `error_code` uses safe fixed provider diagnostics. Additional context: cache_hit, origin_source, origin_core_poi_id, resolved_location.

## Risk rules

Rules are centralized in `src/services/weather_risk.py`. The classifier returns sorted risk codes for current facts or aggregate daily forecast facts; reality checks use current weather only.

| Risk | Deterministic rule |
| --- | --- |
| RAIN | Text contains 雨; redundant RAIN suppressed for thunder/heavy rain |
| HEAVY_RAIN | Text contains 大雨 or 暴雨 |
| THUNDERSTORM | Text contains 雷 |
| SNOW | Text contains 雪; rain/snow can coexist |
| STRONG_WIND | Numeric Beaufort single value/range; entire range >=6, valid range 0..17 |
| EXTREME_HEAT | Temperature >=35 C |
| EXTREME_COLD | Temperature <=0 C |

Wind prose, inequalities and ambiguous ranges are not guessed. Forecast risk codes imply daily conditions only. UNAVAILABLE observations do not create risks. No classifier action changes a route.

## Reality result

`RealityCheckResult`: checked_at, route_version (version_id), status, warnings, weather, metrics, data_quality. Each `RealityWarning`: code, severity LOW/MEDIUM/HIGH, poi_id (nullable), leg_index (original version index, nullable), message, details, source, confidence LOW/MEDIUM/HIGH.

| Status | Meaning |
| --- | --- |
| OK | Remaining checks complete and no warning, or no remaining stops |
| WARNING | Complete actionable observations with warning(s) |
| PARTIAL | Critical timing/opening/weather/budget observation is missing; usable checks continue |
| UNAVAILABLE | Weather unavailable, walking timing incomplete, and every remaining POI live observation unavailable |

Missing optional POI fields such as ratings do not degrade usable opening checks. NOT_APPLICABLE mapping absence is legal and creates no opening warning. Input/programmer errors such as naive time or historical version are rejected; external provider failures are isolated.

## ETA, progress and budget

Visited and skipped stops are excluded. ETA starts at `now`, adds each remaining stop's existing incoming walking leg, then its `estimated_stay_minutes` already selected by `selected_visit_mode`. No duration is inferred from `effective_primary_role`. The original first stop without a specified route start needs no incoming leg. A later first remaining stop still uses its existing incoming leg. Missing required legs are unavailable, never zero minutes.

No GPS-to-next walking query occurs. A leg from a visited/skipped predecessor still describes the original version, not a newly planned shortcut. Missing duration makes downstream ETA and adjusted budget null; known subtotal is separately reported. Missing selected stay also makes dependent ETA/budget unavailable. Arrival and departure are explicitly offset Shanghai times; confidence propagates through earlier fallback/unknown timing.

`remaining_live_walking_minutes` sums only AVAILABLE legs. `remaining_reference_walking_minutes` includes supplied fallback estimates only if all durations exist. `reality_adjusted_remaining_minutes` is reference walking + selected visits, without adding planner buffer or return travel. Compare with snapshot `remaining_minutes`; warn only when excess >5 minutes. Budget remains soft, including any frozen hard-limit metadata: this observer never enforces it. Remaining budget is the logical snapshot budget; this layer does not advance elapsed time using wall clock.

## Seven warning codes

| Code | Trigger / details |
| --- | --- |
| LIVE_ROUTE_EXCEEDS_BUDGET | Adjusted remaining duration > snapshot budget +5; details budget, adjusted_duration, excess_minutes, tolerance; HIGH confidence only with all live legs, MEDIUM/LOW with estimates |
| POI_CLOSED | Arrival is explicitly outside valid today-hours; details estimated_arrival, opening_hours, provider_status |
| POI_MAY_CLOSE_BEFORE_ARRIVAL | Arrival open, selected visit departure after continuous opening interval ends; details closes_at, planned_visit_minutes |
| OPENING_HOURS_UNKNOWN | Meaningful FULL/LIMITED visit has absent/unparseable/stale arrival-day hours; confidence LOW |
| WEATHER_RISK | Current rule risk and known remaining walking >1 minute or >100 m; details risk_type, facts and optional outdoor/mixed POIs |
| LIVE_ROUTE_DATA_UNAVAILABLE | Any remaining leg FALLBACK_ESTIMATE/UNAVAILABLE or missing/invalid; details affected_legs with original indices and statuses |
| WEATHER_DATA_UNAVAILABLE | Current weather fails; fixed error_code, other checks continue |

Opening precedence per POI: CLOSED > MAY_CLOSE > UNKNOWN; a currently open POI that will be closed at ETA gets only CLOSED. FULL/LIMITED applicability and explicit visit scope govern checking; route role never does. An explicitly exterior-only walk_stop may waive interior hours. N/A streets/districts/plazas have no opening checks. The existing strict today-hours grammar is reused, with small interval/closing-time extensions; weekly prose is not interpreted. Today's hours are not reused at an arrival on another Shanghai calendar day. Split intervals, midnight endpoints and overnight closing windows are supported. Departure exactly at closing is permitted.

The result cannot remove POIs, change must-go/modes/order, replan, commit CAS or append a route version. Adjustments belong to a future explicit user/Agent decision through Phase 3A.
