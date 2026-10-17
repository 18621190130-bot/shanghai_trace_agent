"""Named Phase 3A business scenario, independent of changes to optional POI selection.

The scenario contains p29 -> p43 -> p5, all still valid production identities.
Current production planning still runs. Only the initial scenario under test is
pinned to its archived approved plan; all later actions use the current repository.
This preserves the original skip/add/must-go/time/version assertions unchanged.
"""
from pathlib import Path
from tools.demos.trip_agent_demo import build_agent as build_current_agent
from tools.demos.trip_demo import load_fixture

ROOT=Path(__file__).resolve().parents[1]

def build_agent(**kwargs):
    agent=build_current_agent(**kwargs)
    generate=agent.entry.generate
    used=False
    def scenario(intent):
        nonlocal used
        result=generate(intent)
        if not used and intent.preferred_zone=='west_bund' and intent.available_minutes==180 and not intent.must_go_poi_ids and set(intent.interest_tags)=={'architecture','industrial_heritage','waterfront'}:
            fixture=ROOT/'tests/fixtures/trip_semantics_initial.json'
            plan,_=load_fixture(fixture)
            assert [s.poi_id for s in plan.ordered_pois]==['p29','p43','p5']
            assert all(agent.repository.get_poi_by_id(s.poi_id) is not None for s in plan.ordered_pois)
            result.route_plan=agent.entry.walking_service.hydrate_walking_route(plan)
            result.status='success'
            used=True
        return result
    agent.entry.generate=scenario
    return agent
