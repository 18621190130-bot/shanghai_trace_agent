"""Offline POI image enrichment. No planner mutations or provider image downloads."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.providers.amap import AmapClient
from src.providers.base import ExternalProviderError
from src.web_sdk import load_local_environment

AUDIT=ROOT/'examples/poi_images'
MANIFEST=ROOT/'data/poi_images.json'
BLOCKED=re.compile(r'菜单|二维码|广告|海报|商品|停车.*收费|价目|menu|qr.?code|advert|poster|price.?list|product',re.I)
SCENE=re.compile(r'外观|全景|街景|建筑|正门|入口|大门|景观|exterior|panorama|street|facade|entrance',re.I)

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def photo_url(value):
    if not isinstance(value,str):return None
    try:
        u=urlsplit(value)
        if u.scheme not in ('http','https') or u.username or u.password or u.port not in (None,80,443):return None
        host=(u.hostname or '').lower()
        if not any(host==d or host.endswith('.'+d) for d in ('amap.com','autonavi.com')):return None
        return urlunsplit(('https',host,u.path,u.query,''))
    except ValueError:return None

def select_photos(photos):
    accepted=[];rejected=[];seen=set()
    for index,photo in enumerate(photos if isinstance(photos,list) else []):
        if not isinstance(photo,dict):continue
        title=str(photo.get('title') or '');url=photo_url(photo.get('url'))
        reason='INVALID_OR_UNAPPROVED_URL' if not url else 'DUPLICATE_URL' if url in seen else 'UNSUITABLE_TITLE' if BLOCKED.search(title) else None
        row=dict(title=title,original_url=photo.get('url'),image_url=url,provider_order=index)
        if reason:rejected.append(dict(row,reason=reason));continue
        seen.add(url);accepted.append(row)
    accepted.sort(key=lambda x:(not bool(SCENE.search(x['title'])),x['provider_order']))
    return accepted,rejected

def inputs():
    return read(ROOT/'data/pois.json')['pois'],read(ROOT/'data/amap_poi_mappings.json'),read(ROOT/'data/core_spatial_profiles.json'),read(ROOT/'frontend/content.json').get('pois',{})

def build_candidates(pois,mappings,spatial,curated,details,errors=None):
    rows=[]
    for p in pois:
        pid=p['id'];role=p['route_role']['primary'];mapping=mappings.get(pid,{})
        row=dict(poi_id=pid,name=p['name'],route_role=role,spatial_type=spatial.get(pid,{}).get('spatial_type','UNKNOWN'),source_poi_id=mapping.get('amap_poi_id'),identity_status=mapping.get('identity_mapping_status','NOT_FOUND'),source='FALLBACK',status='MISSING',reviewed=False,image_url=None,photos=[],rejected_photos=[])
        src=curated.get(pid,{}).get('src')
        if src:
            row.update(source='CURATED',status='AVAILABLE',image_url=src,reason='KEEP_EXISTING_CURATED',reviewed=True)
        elif role=='anchor':row.update(source='CURATED',reason='ANCHOR_RESERVED')
        elif row['identity_status']!='MATCHED':row['reason']='IDENTITY_NOT_FOUND'
        else:
            provider=details.get(row['source_poi_id'],{})
            row['photos'],row['rejected_photos']=select_photos(provider.get('photos',[]))
            row['provider_name']=provider.get('name')
            if row['photos']:
                chosen=row['photos'][0]
                row.update(source='AMAP',status='AVAILABLE',image_url=chosen['image_url'],original_url=chosen['original_url'],reason='HUMAN_REVIEW_REQUIRED',review_requirement='SPATIAL_CONCEPT' if row['spatial_type']!='POINT' else 'PHOTO_QUALITY')
            else:row.update(status='REJECTED' if row['rejected_photos'] else 'MISSING',reason=(errors or {}).get(row['source_poi_id'],'ALL_PHOTOS_REJECTED' if row['rejected_photos'] else 'NO_PROVIDER_PHOTOS'))
        rows.append(row)
    return dict(schema_version=1,generated_at=datetime.now(timezone.utc).isoformat(),records=rows)

def queue(rows):
    return [dict(poi_id=r['poi_id'],name=r['name'],reason=r['reason'],source_poi_id=r.get('source_poi_id'),spatial_type=r['spatial_type'],status='NEEDS_MANUAL_IMAGE') for r in rows if r['route_role']!='anchor' and not(r['status']=='AVAILABLE' and r['reviewed'])]

def commit(candidate,decisions,existing=None):
    """Only explicit human decisions can release provider candidates; anchors never enriched."""
    pois,_,_,curated=inputs();known={p['id']:p for p in pois}
    decision_map=decisions.get('decisions',{})
    expected=hashlib.sha256(json.dumps(candidate,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if decision_map and decisions.get('candidate_digest')!=expected:raise ValueError('Review belongs to a different candidate audit')
    previous={r['poi_id']:r for r in (existing or {}).get('records',[])};records=[]
    for r in candidate['records']:
        pid=r['poi_id'];p=known[pid];old=previous.get(pid)
        out=dict(poi_id=pid,route_role=p['route_role']['primary'],source='FALLBACK',status='FALLBACK',reviewed=False,image_url=None,reason=r['reason'])
        curated_src=curated.get(pid,{}).get('src')
        if curated_src:out.update(source='CURATED',status='AVAILABLE',reviewed=True,image_url=curated_src,reason='KEEP_EXISTING_CURATED')
        elif old and old.get('source')=='CURATED' and old.get('status')=='AVAILABLE':out=old
        elif p['route_role']['primary']=='anchor':
            out=old if old and old.get('source')=='CURATED' and old.get('image_url') else dict(out,source='CURATED',status='MISSING',reason='ANCHOR_RESERVED')
        else:
            d=decision_map.get(pid,{})
            if d.get('decision')=='accept':
                photo=next((x for x in r['photos'] if x['image_url']==d.get('image_url')),None)
                if not photo:raise ValueError('Accepted photo must belong to the audited POI')
                out.update(source='AMAP',status='AVAILABLE',reviewed=True,image_url=photo['image_url'],original_url=photo['original_url'],source_poi_id=r['source_poi_id'],source_name='AMap POI photos',retrieved_at=candidate['generated_at'],reviewed_at=decisions.get('reviewed_at'),usage_note='Provider URL reference only; no persistent image download.',reason='HUMAN_ACCEPTED',review_note=d.get('note',''))
            elif d.get('decision')=='manual':
                src=d.get('image_url','');asset=(ROOT/'frontend'/src.lstrip('/')).resolve()
                if not re.fullmatch(r'/assets/poi-images/'+re.escape(pid)+r'\.(webp|jpg|jpeg|png)',src) or not asset.is_file():raise ValueError('Manual image must be a local POI-named asset')
                if not d.get('source_url') or not d.get('source_name') or not d.get('usage_note'):raise ValueError('Manual source provenance is required')
                out.update({k:d[k] for k in ('image_url','source_url','source_name','usage_note')},source='MANUAL_WEB',status='AVAILABLE',reviewed=True,retrieved_at=d.get('retrieved_at',decisions.get('reviewed_at')),reason='HUMAN_MANUAL_IMAGE')
            elif d.get('decision')=='reject':out.update(status='REJECTED',reason='HUMAN_REJECTED',reviewed=True,review_note=d.get('note',''))
            elif old and old.get('status')=='AVAILABLE':out=old
        records.append(out)
    if len(records)!=len(known) or {r['poi_id'] for r in records}!=set(known):raise ValueError('Core coverage mismatch')
    return dict(schema_version=1,policy=['CURATED','AMAP','MANUAL_WEB','FALLBACK'],generated_at=datetime.now(timezone.utc).isoformat(),records=records)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='Fetch candidates only; never writes production manifest')
    parser.add_argument('--commit',action='store_true');parser.add_argument('--review-file',type=Path)
    parser.add_argument('--from-audit',type=Path,help='Reuse saved candidates without API calls')
    args=parser.parse_args()
    if args.commit:
        if not args.review_file:parser.error('--commit requires --review-file')
        candidate=read(args.from_audit or AUDIT/'image_audit.json')
        manifest=commit(candidate,read(args.review_file),read(MANIFEST) if MANIFEST.exists() else None)
        write(AUDIT/'manifest_before_commit.json',read(MANIFEST) if MANIFEST.exists() else {})
        write(MANIFEST,manifest);write(AUDIT/'review_applied.json',read(args.review_file))
        by_id={r['poi_id']:r for r in manifest['records']}
        write(AUDIT/'missing_manual_review.json',queue([{**r,**by_id[r['poi_id']]} for r in candidate['records']]))
        merged=[{**r,**by_id[r['poi_id']]} for r in candidate['records']]
        write(AUDIT/'needs_manual_images.json',[r for r in queue(merged) if r['reason']!='HUMAN_REVIEW_REQUIRED'])
        print('Committed reviewed manifest.');return
    if args.from_audit:candidate=read(args.from_audit)
    else:
        pois,mappings,spatial,curated=inputs();ids=list(dict.fromkeys(mappings[p['id']]['amap_poi_id'] for p in pois if p['route_role']['primary']!='anchor' and not curated.get(p['id'],{}).get('src') and mappings.get(p['id'],{}).get('identity_mapping_status')=='MATCHED'))
        load_local_environment()
        if os.environ.get('AMAP_API_KEY'):os.environ['AMAP_WEB_SERVICE_KEY']=os.environ['AMAP_API_KEY']
        client=AmapClient(timeout_s=15);details={};errors={};batches=[]
        for i in range(0,len(ids),10):
            batch=ids[i:i+10]
            try:
                result=client.get('/v5/place/detail',{'id':'|'.join(batch),'show_fields':'photos'})
                for row in result.get('pois',[]):
                    if row.get('id') in batch:details[row['id']]={k:row.get(k) for k in ('id','name','photos')}
                batches.append(dict(ids=batch,status='SUCCESS'))
            except ExternalProviderError as exc:
                for pid in batch:errors[pid]=type(exc).__name__
                batches.append(dict(ids=batch,status=type(exc).__name__))
        write(AUDIT/'provider_photo_response.json',dict(retrieved_at=datetime.now(timezone.utc).isoformat(),batches=batches,pois=details))
        candidate=build_candidates(pois,mappings,spatial,curated,details,errors)
    write(AUDIT/'image_audit.json',candidate)
    write(AUDIT/'missing_manual_review.json',queue(candidate['records']))
    digest=hashlib.sha256(json.dumps(candidate,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    write(AUDIT/'review_template.json',dict(candidate_digest=digest,reviewed_at=None,decisions={}))
    print(json.dumps(dict(total=len(candidate['records']),candidates=sum(r['source']=='AMAP' for r in candidate['records']),anchors=sum(r['route_role']=='anchor' for r in candidate['records']),manual_queue=len(queue(candidate['records'])))))
if __name__=='__main__':main()
