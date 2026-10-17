"""Provider facts, with explicit Shanghai calendar semantics and nullable fields."""
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
from .world_models import WorldDTO, LiveDataStatus

SHANGHAI = ZoneInfo('Asia/Shanghai')


def local_time(value=None):
    if value is None:
        return datetime.now(SHANGHAI)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('A timezone-aware datetime is required')
    return value.astimezone(SHANGHAI)


@dataclass(frozen=True)
class CurrentWeather(WorldDTO):
    provider: str = 'amap'
    province: str | None = None
    city: str | None = None
    district: str | None = None
    adcode: str | None = None
    weather_text: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_direction: str | None = None
    wind_power: str | None = None
    report_time: str | None = None
    data_status: str = LiveDataStatus.UNAVAILABLE
    fetched_at: str | None = None
    cache_hit: bool = False
    error_code: str | None = None
    # Regeo context is separate: never invent weather-provider district/city.
    resolved_location: dict | None = None
    origin_source: str | None = None
    origin_core_poi_id: str | None = None


@dataclass(frozen=True)
class WeatherForecastDay(WorldDTO):
    date: str | None = None
    day_weather: str | None = None
    night_weather: str | None = None
    day_temperature_c: float | None = None
    night_temperature_c: float | None = None
    day_wind_direction: str | None = None
    night_wind_direction: str | None = None
    day_wind_power: str | None = None
    night_wind_power: str | None = None


@dataclass(frozen=True)
class WeatherForecast(WorldDTO):
    provider: str = 'amap'
    province: str | None = None
    city: str | None = None
    district: str | None = None
    adcode: str | None = None
    report_time: str | None = None
    days: tuple[WeatherForecastDay, ...] = field(default_factory=tuple)
    precision: str = 'DAILY'
    data_status: str = LiveDataStatus.UNAVAILABLE
    fetched_at: str | None = None
    cache_hit: bool = False
    error_code: str | None = None
    resolved_location: dict | None = None
    origin_source: str | None = None
    origin_core_poi_id: str | None = None
