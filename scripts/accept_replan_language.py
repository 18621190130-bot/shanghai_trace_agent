"""Small, explicit live-model acceptance; secrets never enter artifacts."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.web_app import WebApplication
from src.route_entry import RouteEntryService
from src.poi_repository import POIRepository
from src.services.walking_route_service import WalkingRouteService
from src.llm_client import DeepSeekLLMClient
repo=POIRepository()
if not os.environ.get('DEEPSEEK_API_KEY'):raise SystemExit('Live model key unavailable')
# Live NLU, deterministic route estimates: no unrelated provider calls.
app=WebApplication(repository=repo,entry=RouteEntryService(repo,walking_service=WalkingRouteService()))
app.llm=DeepSeekLLMClient()
_,session=app.session()
r=app.generate(session,dict(intent=dict(route_mode='plan_for_me',available_minutes=180,interest_tags=['architecture','local_life'],preferred_zone='wukang_fuxing_xujiahui')))
app.action(session,dict(action='start',revision=r['trip']['state_revision']))
rows=[]
for text in ["I'm tired. Cut the route for me.",'Add another two places to the route.','I want less walking.']:
    trip=app.current_trip(session)
    r=app.turn(session,dict(text=text,revision=trip['state_revision']))
    rows.append(r['turn']['change_summary'])
    print(json.dumps(rows[-1],ensure_ascii=True),flush=True)
Path('examples/replan_feedback/live_language.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
assert all(x['execution_status']=='APPLIED' for x in rows)
assert rows[1]['actual_added_count']==2
