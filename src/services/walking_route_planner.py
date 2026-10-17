"""Compose the frozen planning engine with final-route walking hydration."""
from ..route_engine import RouteEngine
from .walking_route_service import default_walking_service


class WalkingRoutePlanner:
    def __init__(self, repository, *, walking_service=None):
        self.engine = RouteEngine(repository)
        self.walking_service = walking_service if walking_service is not None else default_walking_service()

    def generate_route(self, request):
        return self.walking_service.hydrate_walking_route(self.engine.generate_route(request))
