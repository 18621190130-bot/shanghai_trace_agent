"""Amap weather adapter; HTTP, pacing, redaction and errors belong to AmapClient."""
from datetime import datetime, date
import math
import re
from ..base import ProviderResponseError
from .world import optional_text
from ...weather_models import CurrentWeather, WeatherForecast, WeatherForecastDay, SHANGHAI
from ...world_models import LiveDataStatus


def number(value, minimum=-100, maximum=100):
    try:
        if isinstance(value, bool):
            return None
        result = float(value)
        return result if math.isfinite(result) and minimum <= result <= maximum else None
    except (TypeError, ValueError, OverflowError):
        return None


def report_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
        # Amap documents a Shanghai local publication time without an offset.
        return (parsed.replace(tzinfo=SHANGHAI) if parsed.tzinfo is None else parsed.astimezone(SHANGHAI)).isoformat()
    except ValueError:
        return None


def forecast_date(value):
    try:
        return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
    except ValueError:
        return None


class AmapWeatherProvider:
    provider = 'amap'

    def __init__(self, client):
        self.client = client

    def _fetch(self, adcode, kind, collection):
        if not isinstance(adcode, str) or not re.fullmatch(r'\d{6}', adcode):
            raise ProviderResponseError()
        data = self.client.get('/v3/weather/weatherInfo', {'city': adcode, 'extensions': kind})
        rows = data.get(collection)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or not rows[0]:
            raise ProviderResponseError()
        return rows[0]

    def _common(self, raw):
        text = lambda v: optional_text(v, self.client)
        adcode = text(raw.get('adcode'))
        if adcode and not re.fullmatch(r'\d{6}', adcode):
            adcode = None
        return dict(province=text(raw.get('province')), city=text(raw.get('city')),
                    district=text(raw.get('district')), adcode=adcode,
                    report_time=report_time(raw.get('reporttime')),
                    fetched_at=datetime.now(SHANGHAI).isoformat())

    def get_current_weather(self, adcode):
        raw = self._fetch(adcode, 'base', 'lives')
        text = lambda v: optional_text(v, self.client)
        fields = dict(self._common(raw), weather_text=text(raw.get('weather')),
                      temperature_c=number(raw.get('temperature_float', raw.get('temperature'))),
                      humidity_pct=number(raw.get('humidity_float', raw.get('humidity')), 0, 100),
                      wind_direction=text(raw.get('winddirection')), wind_power=text(raw.get('windpower')))
        required = ('province', 'city', 'adcode', 'report_time', 'weather_text',
                    'temperature_c', 'humidity_pct', 'wind_direction', 'wind_power')
        status = LiveDataStatus.AVAILABLE if all(fields[k] is not None for k in required) else LiveDataStatus.PARTIAL
        return CurrentWeather(**fields, data_status=status)

    def get_weather_forecast(self, adcode):
        raw = self._fetch(adcode, 'all', 'forecasts')
        casts = raw.get('casts')
        if casts is None:
            casts = []
        if not isinstance(casts, list) or any(not isinstance(day, dict) for day in casts):
            raise ProviderResponseError()
        text = lambda v: optional_text(v, self.client)
        days = tuple(WeatherForecastDay(
            date=forecast_date(day.get('date')), day_weather=text(day.get('dayweather')),
            night_weather=text(day.get('nightweather')), day_temperature_c=number(day.get('daytemp')),
            night_temperature_c=number(day.get('nighttemp')), day_wind_direction=text(day.get('daywind')),
            night_wind_direction=text(day.get('nightwind')), day_wind_power=text(day.get('daypower')),
            night_wind_power=text(day.get('nightpower'))) for day in casts)
        fields = self._common(raw)
        complete = all(fields[k] is not None for k in ('province', 'city', 'adcode', 'report_time'))
        complete = complete and bool(days) and all(all(v is not None for v in day.to_dict().values()) for day in days)
        return WeatherForecast(**fields, days=days, data_status=LiveDataStatus.AVAILABLE if complete else LiveDataStatus.PARTIAL)
