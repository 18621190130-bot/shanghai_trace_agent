from typing import Protocol
from ..weather_models import CurrentWeather, WeatherForecast


class WeatherProvider(Protocol):
    def get_current_weather(self, adcode: str) -> CurrentWeather: ...
    def get_weather_forecast(self, adcode: str) -> WeatherForecast: ...
