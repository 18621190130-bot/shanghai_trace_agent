"""Small strict JSON Schema validator for the subset used by our public contracts."""

import math

from .intent_models import RouteMode
from .models import RequestValidationError
from .poi_repository import TAG_GROUPS


def nullable(schema):
    return {"oneOf": [schema, {"type": "null"}]}


def object_schema(properties, required=None):
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties) if required is None else required}


def array(schema):
    return {"type": "array", "items": schema}


OPTION_SCHEMA = object_schema({"label": {"type": "string", "minLength": 1},
                               "value": {"oneOf": [{"type": "string"}, {"type": "integer"}]}})
CLARIFICATION_SCHEMA = object_schema({
    "field": {"type": "string"}, "question": {"type": "string", "minLength": 1},
    "input_type": {"type": "string", "enum": ["single_choice", "multi_choice", "text", "location"]},
    "options": array(OPTION_SCHEMA), "required": {"type": "boolean"},
    "max_choices": nullable({"type": "integer", "minimum": 1})})


def candidate_schema(repository):
    props = {
        "available_minutes": nullable({"type": "integer", "minimum": 1}),
        "start_location_text": nullable({"type": "string", "minLength": 1}),
        **{g: array({"type": "string", "enum": list(repository.taxonomy[g])}) for g in TAG_GROUPS},
        "travel_pace": {"type": "string", "enum": ["quick", "standard", "deep"]},
        "preferred_zone": nullable({"type": "string", "enum": list(repository.zone_order)}),
        "max_walking_km": nullable({"type": "number", "exclusiveMinimum": 0}),
        "must_go_place_names": array({"type": "string", "minLength": 1}),
        "avoid_tags": array({"type": "string", "enum": sorted({t for g in repository.taxonomy.values() for t in g})}),
        "avoid_place_names": array({"type": "string", "minLength": 1}),
        "unresolved_negative_preferences": array({"type": "string", "minLength": 1})}
    required = list(props)
    vocabulary = sorted({t for group in repository.taxonomy.values() for t in group})
    props['semantic_concepts'] = array(object_schema({
        'concept': {'type': 'string', 'minLength': 1},
        'primary': {'type': 'string', 'enum': vocabulary},
        'secondary': {**array({'type': 'string', 'enum': vocabulary}), 'maxItems': 2}}))
    return object_schema(props, required)



def route_intent_schema(repository):
    props = candidate_schema(repository)["properties"].copy()
    props.pop("must_go_place_names")
    props.pop("avoid_place_names")
    props.update({
        "route_mode": {"type": "string", "enum": list(RouteMode)},
        "start_poi_id": nullable({"type": "string", "enum": [p.id for p in repository.get_all_pois()]}),
        "start_lat": nullable({"type": "number", "minimum": -90, "maximum": 90}),
        "start_lng": nullable({"type": "number", "minimum": -180, "maximum": 180}),
        "start_coordinate_system": {"type": "string", "enum": ["GCJ-02", "WGS84"]},
        "must_go_poi_ids": array({"type": "string", "enum": [p.id for p in repository.get_all_pois()]}),
        "avoid_poi_ids": array({"type": "string", "enum": [p.id for p in repository.get_all_pois()]}),
        "visit_mode_overrides": {"type": "object", "additionalProperties": False,
            "properties": {p.id: {"type": "string", "enum": list(p.visit_profile.supported_modes)}
                           for p in repository.get_all_pois()}},
        "surprise_seed": {"type": "integer"}, "needs_clarification": {"type": "boolean"},
        "missing_fields": array({"type": "string"}), "warnings": array({"type": "string"}),
        "clarification_requests": {**array(CLARIFICATION_SCHEMA), "maxItems": 2}})
    return object_schema(props, ["route_mode"])


def validate_json(value, schema, path="$"):
    if "oneOf" in schema:
        valid = 0
        for item in schema["oneOf"]:
            try:
                validate_json(value, item, path)
                valid += 1
            except RequestValidationError:
                pass
        if valid != 1:
            raise RequestValidationError(f"{path}: expected exactly one allowed type")
        return
    typ = schema.get("type")
    types = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
             "string": lambda v: isinstance(v, str), "integer": lambda v: type(v) is int,
             "number": lambda v: type(v) in (int, float) and math.isfinite(v),
             "boolean": lambda v: type(v) is bool, "null": lambda v: v is None}
    if typ and not types[typ](value):
        raise RequestValidationError(f"{path}: expected {typ}")
    if "enum" in schema and value not in schema["enum"]:
        raise RequestValidationError(f"{path}: value outside allowed vocabulary")
    if typ == "object":
        props = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            raise RequestValidationError(f"{path}: missing required property")
        if schema.get("additionalProperties") is False and set(value) - set(props):
            raise RequestValidationError(f"{path}: unknown properties")
        for key, item in value.items():
            if key in props:
                validate_json(item, props[key], f"{path}.{key}")
    if typ == "array":
        if len(value) > schema.get("maxItems", float("inf")):
            raise RequestValidationError(f"{path}: too many items")
        for index, item in enumerate(value):
            validate_json(item, schema["items"], f"{path}[{index}]")
    if typ == "string" and len(value.strip()) < schema.get("minLength", 0):
        raise RequestValidationError(f"{path}: empty string")
    if typ in ("integer", "number"):
        if (("minimum" in schema and value < schema["minimum"]) or
                ("maximum" in schema and value > schema["maximum"]) or
                ("exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"])):
            raise RequestValidationError(f"{path}: out of range")
