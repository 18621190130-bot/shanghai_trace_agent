"""Import user-supplied editorial assets without changing routing or Core data."""
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def write(path,value):(ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    from src.poi_repository import POIRepository
    repo=POIRepository();anchors={p.id for p in repo.get_all_pois() if p.route_role_primary=='anchor'}
    content=read('frontend/content.json');manifest=read('data/poi_images.json');arrival=read('data/poi_arrival_content.json')
    editorial=read('examples/content_fill/editorial.json');other=read('examples/content_fill/nonanchor_notice.json')
    assert set(editorial)==anchors
    assert set(other)|anchors=={p.id for p in repo.get_all_pois()}
    audit={'image_mappings':[],'content_mappings':[],'corrections':[
        'User confirmed: 外滩·陈毅广场+p4.JPG maps to p14, not p4.',
        'User confirmed: 星美术馆+p41.jpg maps to p31, not p41.',
        'p4 residence dates corrected to 1933–1936 using Shanghai government source.',
        'p14 comparison wording corrected: New York is not a European financial district.'
    ],'source_document':'materials/content/地点内容.docx','document_sha256':digest(ROOT/'materials/content/地点内容.docx'),
      'historical_reference':'https://www.shanghai.gov.cn/nw4411/20240925/4d47a4ab740042d4935bebbbed45b3d7.html'}
    cover={'architecture':'architecture.jpg','local_life':'local life.jpg','art':'art.jpg','waterfront':'by the water.JPG','history':'history.jpg','literature':'literature.jpg','parks':'parks and gardens.jpg','modern_city':'modern city.jpg'}
    target=ROOT/'frontend/assets/hero';target.mkdir(exist_ok=True)
    for slot in content['hero']:
        original=ROOT/'materials/photos/cover'/cover[slot['label']];dest=target/(slot['label']+'.jpg');shutil.copy2(original,dest)
        slot['src']='/assets/hero/'+dest.name
        audit['image_mappings'].append(dict(slot=slot['id'],source=str(original.relative_to(ROOT)),asset=slot['src'],sha256=digest(dest)))
    target=ROOT/'frontend/assets/poi-images';target.mkdir(exist_ok=True)
    records={r['poi_id']:r for r in manifest['records']};matched=set()
    for original in (ROOT/'materials/photos/anchors').iterdir():
        if original.name.startswith('._') or original.suffix.lower() not in ('.jpg','.jpeg','.png'):continue
        pid=re.search(r'\+\s*(p(?:z_[a-z0-9]+|\d+))',original.stem).group(1)
        if '外滩' in original.name:pid='p14'
        if '星美术馆' in original.name:pid='p31'
        assert pid in anchors and pid not in matched,(original,pid)
        matched.add(pid);dest=target/(pid+original.suffix.lower());shutil.copy2(original,dest)
        url='/assets/poi-images/'+dest.name
        content['pois'][pid]={**content['pois'].get(pid,{}),'src':url}
        records[pid].update(source='CURATED',status='AVAILABLE',reviewed=True,image_url=url,reason='USER_CURATED_IMAGE',
             source_name='User supplied TraceMate image collection',source_file=str(original.relative_to(ROOT)),retrieved_at='2026-10-08',
             usage_note='Provided and selected by the user for this project; original website/license not supplied.',sha256=digest(dest))
        audit['image_mappings'].append(dict(poi_id=pid,source=str(original.relative_to(ROOT)),asset=url,sha256=digest(dest)))
    assert matched==anchors
    with ZipFile(ROOT/'materials/content/地点内容.docx') as z:document=ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs=[''.join(t.text or '' for t in p.findall('.//w:t',ns)) for p in document.findall('.//w:p',ns)]
    sections={};pid=None
    for paragraph in paragraphs:
        match=re.search(r'\+\s*(p(?:z_[a-z0-9]+|\d+))\s*$',paragraph)
        if match:
            pid=match.group(1);assert pid not in sections;sections[pid]=dict(title=paragraph,body=[])
        elif paragraph.strip():
            assert pid;sections[pid]['body'].append(paragraph)
    assert set(sections)==anchors
    for pid,section in sections.items():
        body='\n\n'.join(section['body'])
        if pid=='p4':body=body.replace('from 1927 until his death in 1936','from 1933 until his death in 1936')
        if pid=='p14':body=body.replace('European financial districts such as London or New York','financial districts in London or New York')
        sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z])',body)
        en={'paragraphs':[' '.join(sentences[i:i+3]) for i in range(0,len(sentences),3)]}
        content['cultural_bridge']['places'][pid]={'en':en,'zh':editorial[pid]['zh'],
            'provenance':{'source':'USER_DOCUMENT','source_file':'materials/content/地点内容.docx','source_heading':section['title'],
                          'english':'user text, paragraph breaks plus recorded factual corrections',
                          'chinese':'concise localized retelling of user text'}}
        audit['content_mappings'].append(dict(poi_id=pid,heading=section['title']))
    for poi in repo.get_all_pois():
        row=arrival.setdefault('records',{}).setdefault(poi.id,{})
        row.update(content_status='AVAILABLE',what_to_notice=editorial[poi.id]['notice'] if poi.id in anchors else other[poi.id],
                   notice_provenance={'source':'USER_DOCUMENT_DERIVED' if poi.id in anchors else 'EDITORIAL_OBSERVATION_GUIDANCE',
                       'source_file':'materials/content/地点内容.docx' if poi.id in anchors else None,'prepared_at':'2026-10-08'})
    write('frontend/content.json',content);write('data/poi_images.json',manifest);write('data/poi_arrival_content.json',arrival)
    audit['counts']={'hero_photos':len(cover),'anchor_photos':len(matched),'cultural_bridges':len(sections),'what_to_notice':len(arrival['records'])}
    write('examples/content_fill/import_audit.json',audit);print(json.dumps(audit['counts']))
if __name__=='__main__':
    import sys
    sys.path.insert(0,str(ROOT));main()
