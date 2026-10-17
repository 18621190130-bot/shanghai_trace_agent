"""Strict staging schema reuses the existing project's JSON validator."""
from ...intent_schema import object_schema as obj, array, nullable

ROLES = ('anchor', 'supporting_stop', 'transition_stop')
LEVELS = ('high', 'medium', 'low')
CATEGORIES = ('museum', 'cultural_venue', 'performance_venue', 'public_art', 'public_space', 'park',
              'architecture', 'heritage', 'sports_space', 'commercial_complex', 'generic_cafe',
              'generic_restaurant', 'ordinary_shop', 'temporary_event', 'unknown')
FACTS = ('opening_hours', 'ticket_prices', 'reservation_requirements', 'historical_dates',
         'former_functions', 'architect_names', 'official_designations')


def semantic_schema(taxonomy):
    text = {'type': 'string', 'minLength': 1}
    level = {'type': 'string', 'enum': list(LEVELS)}
    refs = array(text)
    cited = obj({'text': text, 'evidence_refs': refs})
    props = {
        'category': {'type': 'string', 'enum': list(CATEGORIES)},
        **{group: array({'type': 'string', 'enum': list(tags)}) for group, tags in taxonomy.items()},
        'tag_evidence': array(obj({'group': {'type': 'string', 'enum': list(taxonomy)}, 'tag': text, 'evidence_refs': refs})),
        'category_evidence_refs': refs,
        'route_role': obj({'primary': {'type': 'string', 'enum': list(ROLES)},
            'eligible': array({'type': 'string', 'enum': list(ROLES)}), 'confidence': level,
            'reason': text, 'independent_destination_value': level, 'route_connector_value': level,
            'alternatives_reason': obj({role: text for role in ROLES})}),
        'citywalk_value': obj({'level': level, 'reason': text, 'evidence_refs': refs}),
        'summary_draft': cited,
        'culture_bridge_draft': nullable(cited),
        'visit_profile_proposal': obj({'walk_stop': obj({p: {'type': 'integer', 'minimum': 1, 'maximum': 240} for p in ('quick','standard','deep')}),
            'full_visit': nullable(obj({p: {'type': 'integer', 'minimum': 1, 'maximum': 480} for p in ('quick','standard','deep')})),
            'time_basis': {'type': 'string', 'enum': ['product_planning_estimate']}, 'scope': text}),
        'semantic_confidence': level,
        'stability': {'type': 'string', 'enum': ['stable', 'temporary', 'unknown']},
        'missing_information': array(text),
        'factual_fields': obj({field: nullable(cited) for field in FACTS}),
        'taxonomy_extension_candidate': array(obj({'label': text, 'reason': text, 'evidence_refs': refs})),
    }
    return obj(props)
