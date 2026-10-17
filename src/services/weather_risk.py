"""Central deterministic product rules; risks are observations, never decisions."""
import re
from ..weather_models import CurrentWeather, WeatherForecast, WeatherForecastDay

HEAT_THRESHOLD_C = 35
COLD_THRESHOLD_C = 0
STRONG_WIND_MIN_BEAUFORT = 6
TEXT_RULES = (
    ('THUNDERSTORM', ('雷',)),
    ('HEAVY_RAIN', ('暴雨', '大雨')),
    ('SNOW', ('雪',)),
    ('RAIN', ('雨',)),
)


def wind_strength(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'\s*(\d{1,2})(?:\s*[-–~]\s*(\d{1,2}))?\s*级?\s*', value)
    if not match:
        return None
    low = int(match[1]); high = int(match[2] or match[1])
    # The whole reported range must meet the threshold, never guess '<3' or prose.
    return low if 0 <= low <= high <= 17 else None


class WeatherRiskClassifier:
    def classify(self, weather):
        if isinstance(weather, WeatherForecast):
            if weather.data_status == 'UNAVAILABLE':
                return []
            return sorted(set(risk for day in weather.days for risk in self.classify(day)))
        if isinstance(weather, CurrentWeather):
            if weather.data_status == 'UNAVAILABLE':
                return []
            texts, temperatures, powers = [weather.weather_text], [weather.temperature_c], [weather.wind_power]
        elif isinstance(weather, WeatherForecastDay):
            texts = [weather.day_weather, weather.night_weather]
            temperatures = [weather.day_temperature_c, weather.night_temperature_c]
            powers = [weather.day_wind_power, weather.night_wind_power]
        else:
            return []
        risks = set()
        for text in texts:
            if not isinstance(text, str):
                continue
            matched = {code for code, terms in TEXT_RULES if any(term in text for term in terms)}
            if matched & {'THUNDERSTORM', 'HEAVY_RAIN'}:
                matched.discard('RAIN')
            risks.update(matched)
        if any(t is not None and t >= HEAT_THRESHOLD_C for t in temperatures):
            risks.add('EXTREME_HEAT')
        if any(t is not None and t <= COLD_THRESHOLD_C for t in temperatures):
            risks.add('EXTREME_COLD')
        if any((strength := wind_strength(p)) is not None and strength >= STRONG_WIND_MIN_BEAUFORT for p in powers):
            risks.add('STRONG_WIND')
        return sorted(risks)
