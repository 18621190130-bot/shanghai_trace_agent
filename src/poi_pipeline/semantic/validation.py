"""Fail closed on contract, references, coordinates and unsupported factual fields.

Extractive summaries/factual slots avoid claiming that lexical checks can prove
arbitrary generated prose. Interpretive reasons remain explicit review drafts.
"""
import copy
import json
import re
from ...intent_schema import validate_json
from ...models import RequestValidationError
from ...geo_utils import to_gcj02, haversine_km
from .schema import semantic_schema, FACTS

# Conservative evidence gates for easily over-inferred tags. No coverage input.
TAG_GATES = {
    'parks': r'公园|花园|leisure.*(?:park|garden)|\bpark\b|\bgarden\b',
    'local_life': r'居民|市民|社区|社群|日常生活|community|residents',
    'social_observation': r'居民|市民|社群|公共生活|community|residents',
    'local_atmosphere': r'居民|市民|社区|社群|街坊|community|residents',
    'quiet_walk': r'安静|幽静|宁静|quiet|tranquil',
    'neighborhood_walk': r'街区|街坊|邻里|社区|neighbou?rhood',
    'industrial_transformation': r'改造|转变|前身|再利用|converted|reuse|former.*factory',
    'urban_renewal': r'改造|更新|转变|再利用|renewal|regeneration|converted|reuse',
    'adaptive_reuse': r'改造|转变|前身|再利用|converted|reuse',
    'industrial_heritage': r'工业|厂房|飞机制造|油罐|煤|塔吊|铁路|industrial|factory|crane|railway',
    'modern_shanghai': r'历史|旧|前身|原址|工业|机场|铁路|history|historic|former',
    'public_life': r'居民|市民|社群|公共生活|公众参与|community|residents',
    'architecture': r'建筑|设计|厂房|构筑|building|architect|design',
    'architecture_detail': r'建筑|设计|厂房|构筑|building|architect|design',
    'museum_visit': r'美术馆|博物馆|museum|gallery',
    'art': r'艺术|美术|雕塑|剧场|剧院|art|gallery|museum|theatre',
    'waterfront': r'滨江|滨水|沿江|江景|码头|waterfront|riverside|pier',
    'riverside_walk': r'滨江|滨水|沿江|江景|waterfront|riverside',
    'photogenic': r'摄影|视觉|雕塑|建筑|景观|观景|artwork|sculpture|viewpoint|architecture|photo',
    'modern_city': r'现代|当代|商业综合|购物中心|写字楼|综合体|modern|contemporary|mall',
    'shopping_lifestyle': r'商场|购物|商业|商店|mall|shopping|retail',
    'history': r'历史|古|旧|前身|原址|historic|heritage|former',
    'literature': r'文学|作家|诗人|literature|writer|poet',
    'religion': r'宗教|寺|教堂|庙|religio|temple|church',
    'modern_china_history': r'近代|现代史|革命|民国|modern.*history',
    'music': r'音乐|演奏|爵士|music|concert|jazz',
    'gardens': r'园林|园艺|花园|garden|horticultur',
    'iconic_landmark': r'地标|标志性|landmark|iconic',
    'street_scene': r'街道|街景|道路|步行街|street|pedestrian',
    'bookish': r'书店|图书|阅读|book|library|reading',
    'shopping_leisure': r'商场|购物|商业|商店|mall|shopping|retail',
    'old_city': r'老城|城厢|old city',
    'shikumen': r'石库门|shikumen',
    'lane_life': r'弄堂|里弄|lane life',
    'literary_shanghai': r'文学|作家|诗人|literature|writer|poet',
    'religious_culture': r'宗教|寺|教堂|庙|religio|temple|church',
    'sino_foreign_exchange': r'中外|中法|国际.*交流|文化.*交流|cross.cultural',
    'political_history': r'革命|政治|民国|political|revolution',
    'garden_culture': r'园林|造园|古典园|garden culture',
    'music_culture': r'音乐|演奏|爵士|music|concert|jazz',
}

FACT_GATES = {
    'opening_hours': r'开放时间|营业时间|闭馆|opening_hours|\d[:：]\d',
    'ticket_prices': r'票价|门票|免费|\d.*元|ticket|admission',
    'reservation_requirements': r'预约|reservation|booking',
    'historical_dates': r'\d{4}|世纪|century',
    'former_functions': r'原址|前身|原.*机场|旧厂|former|formerly',
    'architect_names': r'建筑师|设计师|architect|担纲设计',
    'official_designations': r'文物|保护单位|历史建筑|认定|designation|listed',
}


def evidence_text(catalog, refs):
    if not refs or any(ref not in catalog for ref in refs):
        raise RequestValidationError('missing or unknown evidence reference')
    return '\n'.join(str(catalog[r]['field']) + ': ' + json.dumps(catalog[r]['value'], ensure_ascii=False) for r in refs)


def validate_cited(item, catalog, *, extractive=False):
    evidence_text(catalog, item['evidence_refs'])
    if extractive and not any(isinstance(catalog[r]['value'], str) and item['text'] in catalog[r]['value'] for r in item['evidence_refs']):
        raise RequestValidationError('factual draft must quote a literal substring of a cited evidence value')


def tag_support_errors(item, catalog):
    text = evidence_text(catalog,item['evidence_refs'])
    tag,group=item['tag'],item['group']
    errors=[]
    if tag in TAG_GATES and not re.search(TAG_GATES[tag],text,re.I):
        errors.append(f'{tag} unsupported by cited evidence; remove or cite explicit matching description')
    if group=='culture_tags' and not any(catalog[r]['group'] in ('history','public_space','official') or catalog[r]['field'] in ('historic','description') for r in item['evidence_refs']):
        errors.append(f'culture tag {tag} needs description rather than name/category alone')
    return errors


def validated_supported_subset(output,candidate,catalog,taxonomy):
    """Reject unsupported known tag proposals individually, with a visible audit.

    Never rescue unknown taxonomy/schema/fact/reference failures. Remaining fields
    must pass the same strict validator; filtered records can only be review/reject.
    """
    validate_json(output,semantic_schema(taxonomy))
    value=copy.deepcopy(output)
    rejected=[]
    for item in value['tag_evidence']:
        if item['tag'] not in value[item['group']]:
            raise RequestValidationError('tag_evidence contains unassigned tag')
        errors=tag_support_errors(item,catalog)
        if errors:
            rejected.append(dict(group=item['group'],tag=item['tag'],evidence_refs=item['evidence_refs'],reasons=errors))
    rejected_keys={(i['group'],i['tag']) for i in rejected}
    for group in taxonomy:
        value[group]=[t for t in value[group] if (group,t) not in rejected_keys]
    value['tag_evidence']=[i for i in value['tag_evidence'] if (i['group'],i['tag']) not in rejected_keys]
    validated=validate_semantic_enrichment(value,candidate,catalog,taxonomy)
    validated['rejected_tag_proposals']=rejected
    if rejected:
        validated['verification']['interpretive_reasons_need_reconciliation']=True
    return validated


def validate_semantic_enrichment(output, candidate, catalog, taxonomy):
    value = copy.deepcopy(output)
    validate_json(value, semantic_schema(taxonomy))
    for group in taxonomy:
        value[group] = list(dict.fromkeys(value[group]))
    refs_by_tag, tag_errors = {}, []
    for item in value['tag_evidence']:
        group, tag = item['group'], item['tag']
        if tag not in value[group]:
            raise RequestValidationError('tag_evidence contains an unassigned/unknown tag')
        tag_errors.extend(tag_support_errors(item,catalog))
        refs_by_tag[(group,tag)] = item
    if tag_errors:
        raise RequestValidationError('; '.join(tag_errors))
    if set(refs_by_tag) != {(g,t) for g in taxonomy for t in value[g]}:
        raise RequestValidationError('every assigned tag needs evidence_refs')
    value['tag_evidence'] = list(refs_by_tag.values())
    evidence_text(catalog, value['category_evidence_refs'])
    role = value['route_role']
    role['eligible'] = list(dict.fromkeys(role['eligible']))
    if role['primary'] not in role['eligible']:
        raise RequestValidationError('primary route role must be in eligible')
    if role['primary'] == 'anchor' and role['independent_destination_value'] != 'high':
        raise RequestValidationError('anchor requires high independent destination value')
    visit = value['visit_profile_proposal']
    for mode in ('walk_stop','full_visit'):
        if visit[mode] and not visit[mode]['quick'] <= visit[mode]['standard'] <= visit[mode]['deep']:
            raise RequestValidationError('visit times must satisfy quick <= standard <= deep')
    if role['primary'] == 'transition_stop' and visit['walk_stop']['standard'] > 20:
        raise RequestValidationError('transition stop must propose a short visit (standard <= 20)')
    validate_cited(value['summary_draft'], catalog, extractive=True)
    if value['culture_bridge_draft']:
        validate_cited(value['culture_bridge_draft'], catalog, extractive=True)
    evidence_text(catalog, value['citywalk_value']['evidence_refs'])
    for field in FACTS:
        fact = value['factual_fields'][field]
        if fact:
            validate_cited(fact, catalog, extractive=True)
            text = evidence_text(catalog, fact['evidence_refs'])
            if not re.search(FACT_GATES[field], text, re.I):
                raise RequestValidationError(f'unsupported factual field {field}')
            if field in ('historical_dates','former_functions','architect_names','official_designations') and not any(catalog[r]['source_type'] in ('official','government') for r in fact['evidence_refs']):
                raise RequestValidationError(f'{field} needs an official authority excerpt')
    for extension in value['taxonomy_extension_candidate']:
        evidence_text(catalog, extension['evidence_refs'])
    # Coordinates are never in the LLM schema. Check inherited geometry against
    # the specific source record selected by Phase 2.5A, not against other POIs.
    if candidate['coordinates']:
        wanted = candidate['field_sources'].get('coordinates')
        options = [e for e in catalog.values() if e['field']=='coordinates' and e['record_id']==wanted]
        if not any(haversine_km(candidate['coordinates'], to_gcj02(*e['value']['coordinates'], e['value']['coordinate_system'])) < .001 for e in options):
            raise RequestValidationError('candidate coordinates do not match inherited evidence')
    # Interpretive prose cannot introduce numerical facts such as years/prices.
    prose = [role['reason'], *role['alternatives_reason'].values(), value['citywalk_value']['reason']]
    corpus = json.dumps(catalog, ensure_ascii=False)
    for text in prose:
        for token in re.findall(r'\d{4}年|\d+(?:\.\d+)?元|\d{1,2}:\d{2}', text):
            if token not in corpus:
                raise RequestValidationError('unsupported date/price/time in interpretive prose')
    value['coordinates'] = copy.deepcopy(candidate['coordinates'])
    value['coordinate_system'] = candidate['coordinate_system']
    value['verification'] = dict(status='human_review_required', facts='extractive_evidence_only',
                                 semantics='interpretation_requires_review', production_imported=False)
    value['rejected_tag_proposals'] = []
    return value
