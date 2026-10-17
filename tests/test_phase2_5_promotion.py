"""Authorized display numbering, immutable identities and production selection."""
import contextlib,copy,io,unittest
from unittest.mock import patch
from tools.demos import route_entry_demo, chat_demo
from scripts.promote_phase2_5 import SOURCE,FINAL,BACKUP,PRODUCTION,OUT,EXPECTED,REMOVALS,OLD_SHA,load,sha,diff_check
from src.poi_repository import POIRepository
from src.kb_selection import resolve_poi_repository

class FinalPromotionTests(unittest.TestCase):
 def setUp(self):self.source=load(SOURCE);self.final=load(FINAL)
 def test_actual_final_counts_and_schema(self):
  repo=POIRepository(FINAL)
  self.assertEqual(len(repo.get_all_pois()),59)
  for z,n in EXPECTED.items():self.assertEqual(len(repo.get_pois_by_zone(z)),n)
  self.assertEqual([p['display_order'] for p in self.final['pois']],list(range(1,60)))
 def test_removals_and_all_other_fields_exactly_preserved(self):
  self.assertTrue(diff_check(self.source,self.final)['passed'])
  index={p['id']:p for p in self.final['pois']}
  self.assertEqual(set(index),{p['id'] for p in self.source['pois']}-set(REMOVALS))
  for p in self.source['pois']:
   if p['id'] not in REMOVALS:
    a=copy.deepcopy(p);b=copy.deepcopy(index[p['id']]);a.pop('display_order');b.pop('display_order');self.assertEqual(a,b)
 def test_diff_rejects_hidden_role_or_id_change(self):
  for change in ('id','role'):
   raw=copy.deepcopy(self.final)
   if change=='id':raw['pois'][0]['id']='wrong-stable-id'
   else:raw['pois'][0]['route_role']['primary']='anchor' if raw['pois'][0]['route_role']['primary']!='anchor' else 'supporting_stop'
   with self.assertRaises(AssertionError):diff_check(self.source,raw)
 def test_backup_and_existing_ids_west_bund_frozen(self):
  self.assertEqual(sha(BACKUP),OLD_SHA);self.assertEqual(len(load(BACKUP)['pois']),27)
  index={p['id']:p for p in self.final['pois']}
  self.assertTrue({p['id'] for p in load(BACKUP)['pois']}<=set(index))
  self.assertEqual([p for p in self.final['pois'] if p['walk_zone']['id']=='west_bund'],[p for p in self.source['pois'] if p['walk_zone']['id']=='west_bund'])
  self.assertTrue(set('p'+str(i) for i in range(36,44))<=set(index))
 def test_deletion_regression_and_cross_modes(self):
  r=load(OUT/'pre_regression.json');self.assertTrue(r['passed']);self.assertTrue(all(r['checks'].values()))
  self.assertEqual(len(r['cross_modes']),12);self.assertTrue(all(row['passed'] for row in r['cross_modes']))
 def test_default_selection_with_actual_final_production_fixture(self):
  # Exercise the real default resolver and both shared entry points before the
  # disk switch as well as after it, without changing runtime default behavior.
  with patch('src.kb_selection.POIRepository',side_effect=lambda *args:POIRepository(FINAL)), patch('tools.demos.route_entry_demo.POIRepository',side_effect=lambda *args:POIRepository(FINAL)):
   self.assertEqual(len(resolve_poi_repository().get_all_pois()),59)
   for entry in (route_entry_demo.main,chat_demo.main):
    output=io.StringIO()
    with contextlib.redirect_stdout(output):self.assertEqual(entry(['--list-places']),0)
    self.assertIn('POI KB: production',output.getvalue());self.assertIn('POI Count: 59',output.getvalue())
 def test_actual_disk_default_is_old_before_or_final_after_atomic_switch(self):
  repo=resolve_poi_repository();self.assertEqual(repo.path,PRODUCTION)
  if sha(PRODUCTION)==OLD_SHA:self.assertEqual(len(repo.get_all_pois()),27)
  else:
   self.assertEqual(sha(PRODUCTION),'e580f86656255fac52b459b499570c5df1d89e8c12e897026d623b62cea7bcea');self.assertEqual(len(repo.get_all_pois()),58)
