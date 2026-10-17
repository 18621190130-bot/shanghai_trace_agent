"""Minimal positive concept expansion, separate from negative preferences."""
import re

from .models import RequestValidationError


# Known minimal mappings also support older providers without concept metadata.
# Unlisted concepts are supplied by the same intent extractor, not a second LLM.
CONCEPTS = (
    (r'old shanghai atmosphere', 'history', ('architecture', 'local_life')),
    (r'natural scenery', 'scenery', ()),
    (r'(?:river|riverside|waterfront) (?:views?|scenery)', 'waterfront', ()),
    (r'literature', 'literature', ()),
    (r'art', 'art', ()),
)
NEGATION = re.compile(r"\b(?:don't|do not|not interested in|dislike|hate|avoid|without|no|neither|not)\b", re.I)


def positive_surface(text, start):
    prefix = text[:start]
    clause = re.split(r'\b(?:and|but|however)\b|[.;!?]', prefix, flags=re.I)[-1]
    return not NEGATION.search(clause)


def expand_semantic_concepts(text, fields, repository):
    """One grounded positive concept has one primary and at most two secondaries."""
    concepts, spans = [], []
    for pattern, primary, secondary in CONCEPTS:
        for match in re.finditer(r'\b'+pattern+r'\b', text, re.I):
            if not positive_surface(text, match.start()):
                continue
            if primary == 'scenery':
                waterfront_context = (fields.get('preferred_zone') == 'west_bund' or
                                      bool(re.search(r'\b(?:river|riverside|waterfront|west bund)\b', text, re.I)))
                primary, secondary = ('waterfront', ('parks',)) if waterfront_context else ('parks', ())
            concepts.append(dict(concept=match.group(), primary=primary, secondary=list(secondary)))
            spans.append(match.span())
    for item in fields.get('semantic_concepts', []):
        match = re.search(re.escape(item['concept']), text, re.I)
        if match is None:
            raise RequestValidationError('Semantic concept must be grounded in a phrase in the user text')
        if not positive_surface(text, match.start()):
            continue
        # A known narrow concept must not be expanded by an over-broad provider.
        if any(match.start() < end and match.end() > start for start, end in spans):
            continue
        concepts.append(item)
    group_for = {tag: group for group, tags in repository.taxonomy.items() for tag in tags}
    avoid = set(fields.get('avoid_tags', []))
    result, seen = [], set()
    for item in concepts:
        if item['primary'] in avoid:
            continue
        secondary = list(dict.fromkeys(t for t in item['secondary'] if t != item['primary'] and t not in avoid))
        item = dict(concept=item['concept'], primary=item['primary'], secondary=secondary)
        key = (item['concept'].casefold(), item['primary'], tuple(secondary))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        for tag in [item['primary'], *secondary]:
            group = group_for[tag]
            fields[group] = list(dict.fromkeys(fields[group] + [tag]))
    fields['semantic_concepts'] = result
    return fields
