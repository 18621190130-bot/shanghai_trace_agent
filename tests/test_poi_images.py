import copy
import unittest
from unittest.mock import patch
from scripts.enrich_poi_images import build_candidates,select_photos,commit,inputs,read,AUDIT

URL='https://store.is.autonavi.com/example.jpg'
class ImageEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.pois,self.mapping,self.spatial,self.curated=inputs()
        self.p=next(p for p in self.pois if p['route_role']['primary']!='anchor' and self.mapping[p['id']]['identity_mapping_status']=='MATCHED')
    def build(self,photos):
        return build_candidates([self.p],self.mapping,self.spatial,{}, {self.mapping[self.p['id']]['amap_poi_id']:{'photos':photos}})['records'][0]
    def test_matched_non_anchor(self):
        row=self.build([{'url':URL,'title':'外观'}]);self.assertEqual(row['source'],'AMAP');self.assertFalse(row['reviewed']);self.assertEqual(row['source_poi_id'],self.mapping[self.p['id']]['amap_poi_id'])
    def test_deterministic_selection(self):
        a,b=select_photos([{'url':URL,'title':'室内'},{'url':URL+'2','title':'外观'},{'url':URL},{'url':URL+'3','title':'二维码'},{'url':'javascript:alert(1)'}]);self.assertEqual(a[0]['image_url'],URL+'2');self.assertEqual(len(a),2);self.assertEqual(len(b),3)
    def test_no_photos_and_not_found(self):
        self.assertEqual(self.build([])['reason'],'NO_PROVIDER_PHOTOS')
        m=copy.deepcopy(self.mapping);m[self.p['id']]['identity_mapping_status']='NOT_FOUND'
        row=build_candidates([self.p],m,self.spatial,{}, {})['records'][0];self.assertEqual(row['reason'],'IDENTITY_NOT_FOUND')
    def test_spatial_requires_human_review(self):
        for kind in ('AREA','LINEAR'):
            spatial={self.p['id']:{'spatial_type':kind}}
            row=build_candidates([self.p],self.mapping,spatial,{}, {self.mapping[self.p['id']]['amap_poi_id']:{'photos':[{'url':URL}]}})['records'][0]
            self.assertEqual(row['review_requirement'],'SPATIAL_CONCEPT');self.assertFalse(row['reviewed'])
    def test_all_anchors_reserved_and_curated_kept(self):
        anchors=[p for p in self.pois if p['route_role']['primary']=='anchor'];self.assertEqual(len(anchors),22)
        curated={p['id']:{'src':'/assets/poi-images/'+p['id']+'.webp'} for p in anchors}
        result=build_candidates(anchors,self.mapping,self.spatial,curated,{})
        for row in result['records']:self.assertEqual(row['image_url'],curated[row['poi_id']]['src']);self.assertEqual(row['source'],'CURATED')
        reserved=build_candidates(anchors,self.mapping,self.spatial,{}, {})
        self.assertTrue(all(r['image_url'] is None for r in reserved['records']))
    def test_commit_requires_matching_review_and_selected_url(self):
        audit=read(AUDIT/'image_audit.json')
        with self.assertRaises(ValueError):commit(audit,{'decisions':{'p13':{'decision':'accept','image_url':URL}}})
        from hashlib import sha256
        import json
        digest=sha256(json.dumps(audit,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        r=next(r for r in audit['records'] if r['source']=='AMAP')
        out=commit(audit,{'candidate_digest':digest,'decisions':{r['poi_id']:{'decision':'accept','image_url':r['image_url']}}})
        accepted=next(x for x in out['records'] if x['poi_id']==r['poi_id']);self.assertTrue(accepted['reviewed']);self.assertEqual(accepted['image_url'],r['image_url'])
        self.assertEqual([x['poi_id'] for x in out['records']],[p['id'] for p in self.pois])
        for row in out['records']:
            if row['route_role']=='anchor':
                self.assertEqual(row['image_url'],self.curated.get(row['poi_id'],{}).get('src'))
                self.assertEqual(row['source'],'CURATED')
    def test_unreviewed_candidates_fallback(self):
        out=commit(read(AUDIT/'image_audit.json'),{'decisions':{}})
        self.assertEqual(len(out['records']),58)
        for row in out['records']:
            expected=self.curated.get(row['poi_id'],{}).get('src')
            self.assertEqual(row['image_url'],expected)
            if expected:
                self.assertEqual(row['source'],'CURATED');self.assertEqual(row['status'],'AVAILABLE');self.assertTrue(row['reviewed'])
            else:
                self.assertFalse(row['reviewed']);self.assertIn(row['status'],('MISSING','FALLBACK'))
    def test_without_curated_images_unreviewed_candidates_stay_empty(self):
        with patch('scripts.enrich_poi_images.inputs',return_value=(self.pois,self.mapping,self.spatial,{})):
            out=commit(read(AUDIT/'image_audit.json'),{'decisions':{}})
        self.assertEqual(len(out['records']),58)
        self.assertTrue(all(row['image_url'] is None for row in out['records']))
    def test_provider_decision_cannot_override_curated_anchor(self):
        import hashlib,json
        audit=read(AUDIT/'image_audit.json')
        anchor=next(p for p in self.pois if p['route_role']['primary']=='anchor' and self.curated.get(p['id'],{}).get('src'))
        digest=hashlib.sha256(json.dumps(audit,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        out=commit(audit,{'candidate_digest':digest,'decisions':{anchor['id']:{'decision':'accept','image_url':URL}}})
        row=next(r for r in out['records'] if r['poi_id']==anchor['id'])
        self.assertEqual(row['image_url'],self.curated[anchor['id']]['src']);self.assertEqual(row['source'],'CURATED')
    def test_manual_local_asset_requires_provenance(self):
        from hashlib import sha256
        import json
        audit=read(AUDIT/'image_audit.json');digest=sha256(json.dumps(audit,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        decision={'decision':'manual','image_url':'/assets/poi-images/p35.webp','source_url':'https://example.org/place','source_name':'Official venue','usage_note':'Permission recorded'}
        with patch('pathlib.Path.is_file',return_value=True):
            result=commit(audit,{'candidate_digest':digest,'decisions':{'p35':decision}})
            self.assertEqual(next(x for x in result['records'] if x['poi_id']=='p35')['source'],'MANUAL_WEB')
            with self.assertRaises(ValueError):commit(audit,{'candidate_digest':digest,'decisions':{'p35':dict(decision,image_url='/assets/../secret.jpg')}})
if __name__=='__main__':unittest.main()
