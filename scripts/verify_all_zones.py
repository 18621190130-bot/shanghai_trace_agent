"""Offline duration diagnostics and full unittest verification of the candidate."""
import itertools
import time
import unittest
from datetime import datetime, timezone
from src.models import RouteRequest
from src.poi_repository import POIRepository
from src.route_engine import RouteEngine
from src.route_composition import composition_assessment
from scripts.finalize_all_zones import validation_fingerprint, finalize
from scripts.run_poi_pipeline import OUT, FINAL, ROOT, load, write


def duration_diagnostics():
 repo=POIRepository(FINAL);engine=RouteEngine(repo);rows=[]
 for zone in repo.zone_order:
  for minutes in (120,150,180):
   req=RouteRequest(minutes,preferred_zone=zone)
   plan=engine.generate_route(req)
   row=dict(zone=zone,minutes=minutes,status=plan.status,stops=len(plan.ordered_pois),
    composition=plan.composition_diagnostics,selected_ids=[s.poi_id for s in plan.ordered_pois],
    estimated_minutes=plan.total_estimated_minutes)
   row['minimum_viable_passed']=row['stops']>=3 and bool(plan.composition_diagnostics.get('route_composition_passed'))
   if not row['minimum_viable_passed']:
    visits=[engine.visits.resolve(p,req) for p in repo.get_pois_by_zone(zone) if p.counts_as_route_stop and not engine._avoided(p,req)]
    visits=[v for v in visits if v is not None]
    options=[]
    for subset in itertools.combinations(visits,3):
     route=engine._shortest_order(list(subset),None)
     if composition_assessment(route,True)['route_composition_passed'] and engine._fits(route,req,None):
      options.append(route)
    best=min(options,key=lambda r:engine._metrics(r,None)[3]) if options else None
    row['default_mode_feasible_triple_exists']=best is not None
    row['diagnostic_example_ids']=[p.id for p in best] if best else []
    row['diagnostic_note']='Budget/role feasibility only; example is not a recommended route and does not override ranking or quality gates. No expansion inferred.'
   rows.append(row)
 write(OUT/'duration_sweep.json',rows)


if __name__=='__main__':
 duration_diagnostics()
 suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
 started=time.monotonic()
 with (OUT/'full_test_output.txt').open('w',encoding='utf-8') as stream:
  result=unittest.TextTestRunner(stream=stream,verbosity=1).run(suite)
 report=dict(command='python -m scripts.verify_all_zones (unittest discover tests)',
  tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
  successful=result.wasSuccessful(),elapsed_seconds=round(time.monotonic()-started,3),
  completed_at=datetime.now(timezone.utc).isoformat(),validation_fingerprint=validation_fingerprint(load(FINAL)))
 write(OUT/'full_test_report.json',report)
 print(report)
 finalize(False)
 if not result.wasSuccessful():raise SystemExit(1)
