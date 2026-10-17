"""Configurable provider taxonomy and conservative ambiguous beverage handling."""
import json
from pathlib import Path
import re
from .nearby_models import ServicePoiCategory

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'data/amap_service_categories.json'


class AmapCategoryMapping:
    def __init__(self, path=DEFAULT_PATH):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        categories = data['categories']; priority = data['primary_priority']
        if set(categories) != set(ServicePoiCategory) or len(priority) != len(ServicePoiCategory) or set(priority) != set(ServicePoiCategory): raise ValueError('Exactly seven service categories required')
        for rule in categories.values():
            for field in ('query_types', 'type_prefixes', 'exact_types', 'type_labels'):
                if not isinstance(rule[field], list) or any(not isinstance(v, str) or not v for v in rule[field]): raise ValueError('Invalid category rule')
            if not rule['query_types'] or any(not re.fullmatch(r'\d{6}', v) for v in rule['query_types'] + rule['exact_types']): raise ValueError('Invalid provider typecode')
            if any(not re.fullmatch(r'\d{2,6}', v) for v in rule['type_prefixes']): raise ValueError('Invalid type prefix')
        groups = data['query_groups']
        members = [c for group in groups.values() for c in group]
        if len(members) != len(ServicePoiCategory) or set(members) != set(ServicePoiCategory): raise ValueError('Query groups must partition categories')
        self._rules = categories; self._priority = tuple(priority); self._groups = groups
        self._tea = data['tea_disambiguation']; self._mall_exclusions = data['mall_exclusions']
        self._excluded_restrooms = set(data['excluded_restroom_types'])
        self._excluded_restroom_labels = set(v.casefold() for v in data['excluded_restroom_type_labels'])

    def query_types(self, category): return '|'.join(self._rules[ServicePoiCategory(category)]['query_types'])

    def query_groups(self, categories):
        requested = set(categories); output = []
        for members in self._groups.values():
            selected = tuple(ServicePoiCategory(c) for c in members if c in requested)
            if not selected: continue
            codes = sorted({code for category in selected for code in self._rules[category]['query_types']})
            output.append((selected, '|'.join(codes)))
        return tuple(output)

    def classify_with_source(self, provider_typecode=None, provider_type=None, *, structured_category=None, name=None):
        codes = re.findall(r'(?<!\d)\d{6}(?!\d)', provider_typecode or '')
        labels = {s.strip().casefold() for s in re.split(r'[;；|]', provider_type or '')}
        output = set(); source = 'PROVIDER_TYPECODE' if codes else 'PROVIDER_TYPE'
        for category in self._priority:
            rule = self._rules[category]
            if codes:
                matched = any(code in rule['exact_types'] or any(code.startswith(prefix) for prefix in rule['type_prefixes']) for code in codes)
            else:
                matched = bool(labels.intersection(v.casefold() for v in rule['type_labels']))
            if matched: output.add(ServicePoiCategory(category))
        # Broad shopping-plaza code alone cannot distinguish a mall from a department store.
        if codes and '060100' in codes and labels.intersection(v.casefold() for v in self._rules['MALL']['type_labels']):
            output.add(ServicePoiCategory.MALL); source = 'PROVIDER_TYPE'
        tea = self._tea
        eligible = (any(code in tea['eligible_exact_types'] or any(code.startswith(prefix) for prefix in tea['eligible_prefixes']) for code in codes)
                    if codes else bool(labels.intersection(v.casefold() for v in tea['eligible_type_labels'])))
        structured = ((provider_type or '')+';'+(structured_category or '')).casefold()
        label = (name or '').casefold()
        has_modern_tea = eligible and any(keyword.casefold() in structured for keyword in tea['structured_keywords'])
        name_fallback = eligible and not has_modern_tea and any(keyword.casefold() in label for keyword in tea['name_keywords'])
        if has_modern_tea or name_fallback:
            output.add(ServicePoiCategory.TEA_DRINK)
            # Ambiguous cold-drink/dessert coding is evidence of drink taxonomy, not that milk tea is dessert.
            if codes and all(code in tea['eligible_exact_types'] or any(code.startswith(prefix) for prefix in tea['eligible_prefixes']) for code in codes):
                output.discard(ServicePoiCategory.RESTAURANT)
                if not any(keyword.casefold() in (structured_category or '').casefold() for keyword in tea['dessert_structured_keywords']): output.discard(ServicePoiCategory.DESSERT_ICE_CREAM)
            source = 'STRUCTURED_CATEGORY' if has_modern_tea else 'NAME_FALLBACK'
        if ServicePoiCategory.CAFE in output and any(keyword.casefold() in (structured_category or '').casefold() for keyword in tea['dessert_structured_keywords']):
            output.add(ServicePoiCategory.DESSERT_ICE_CREAM)
            if source != 'NAME_FALLBACK': source = 'STRUCTURED_CATEGORY'
        if any(code in self._excluded_restrooms for code in codes) or labels.intersection(self._excluded_restroom_labels): output.discard(ServicePoiCategory.RESTROOM)
        if ServicePoiCategory.MALL in output and (labels.intersection(v.casefold() for v in self._mall_exclusions['type_labels']) or any(keyword.casefold() in label for keyword in self._mall_exclusions['name_keywords'])):
            output.discard(ServicePoiCategory.MALL)
        return tuple(ServicePoiCategory(c) for c in self._priority if c in output), source

    def classify(self, provider_typecode=None, provider_type=None, *, structured_category=None, name=None):
        return self.classify_with_source(provider_typecode,provider_type,structured_category=structured_category,name=name)[0]


def classify_service_poi(provider_typecode=None, provider_type=None, *, mapping=None, structured_category=None, name=None):
    return (mapping if mapping is not None else AmapCategoryMapping()).classify(provider_typecode, provider_type,structured_category=structured_category,name=name)
