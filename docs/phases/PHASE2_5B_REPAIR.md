# Phase 2.5B Repair — identity and route-node review

This repair is offline and confined to the candidate/enrichment layer. It does not recollect sources, rerun enrichment for the 58 records, promote POIs or change route behavior. It reads the immutable 2.5B prepared candidates/review and the current production repository.

## Identity and route-node boundaries

`ProductionIdentityResolver` distinguishes `existing_production`, `new_candidate`, `possible_duplicate`, and `unresolved`. Chinese/English names and aliases are normalized using the existing utility. A name match requires coordinate, address or known official-source corroboration for a confirmed production route-node match. Explicit production IDs and a provider identity registry are supported; material coordinate conflicts remain possible duplicates. Same-brand Gate M locations are not imported automatically.

`RouteNodeConsolidator` implements the specific reviewed West Bund groups, with recorded reasons. It is a pilot policy registry, not a generic claim that any nearby places are identical. Contradictory geometry fails closed. Source entities and route nodes have separate output files and IDs. Source entities are always nonselectable, including previously grouped components. Production route nodes appear once and count as zero new stops.

- Art Center A/B1/N/D are subvenues of one proposed route node. N hall's greater distance alone does not prove independent entrance and independent City Walk value.
- Dome + north plaza remain one node with two proposed scopes: exterior/plaza walk_stop and conditional venue/performance full_visit. Estimated minutes are product estimates. No event or ticket information is fabricated.
- Skate park naming variants combine official activity evidence and map/OSM identity; representative-point discrepancies remain visible.
- Runway Park naming variants form one linear-space node; its boundary needs review.
- Photography Center bilingual records share the specific venue identity and Longteng Avenue 2555 address; it remains distinct from Art Center.
- TANK geometries and its existing exterior walk_stop experience do not create additional stops. Nanpu station context stays with p31; Gate M internal entities are separately retained and nonselectable.
- Crane/plaza, historic-building/Art-Center, sports-park/skate-park and Gate M Fengchao relationships remain explicit possible duplicates. They are not silently resolved.

## Semantic adjudication

Selected nodes use an explicit evidence-policy table in `repair_review.py`. Each retained tag has a precise evidence selector and original citation. Output is still passed through the **unchanged** `validate_semantic_enrichment()`. Missing evidence is not supplied by general knowledge or coverage. This is labeled `targeted_deterministic_evidence_review`, not represented as a new DeepSeek result. Unaffected validated proposals are reused.

Production facts, tags, visit profiles and uncertainty notes are preserved in a snapshot. A separate role audit uses that known content and calibrated product visit estimates. Production tags restored to an audit row are not advertised as newly externally verified facts. A source object's previous failed enrichment cannot erase production knowledge.

Evidence about the skate community supports social_observation/public_life; generic waterfront language alone would not. Runway history, adaptive reuse and street system are supported by its official description; water systems do not establish a Huangpu riverside route. Equipment is not automatically art. Public accessibility and permanence of the OSM installation remain unresolved. Empty-tag records with no independently evidenced experience are rejected rather than assigned a filler transition role.

`route_selectable` is a staging assessment of independent-node eligibility, **not** production promotion or an instruction for the current Route Engine. A needs_review node may have this flag if its independent identity is plausible but access needs checking. `counts_as_new_stop=false` on all existing production nodes and all nonselectable entities prevents fake new richness. Current production routing is unchanged.

## Targeted retry

`TargetedRetryPolicy` permits only explicitly selected failed, identity-changed, merged, role-ambiguous or tag-reconciliation cases. Insufficient evidence means zero requests. At most two total attempts are allowed; a second attempt needs likely schema repair, a single omittable fact field or materially improved evidence. Unsupported tag guesses do not trigger repeated generation. Provider failures return to review.

`TargetedSemanticRepair` optionally uses the existing provider interface. It uses a compact evidence view retaining `also_supported_by` references and a conservative omit/null prompt. It still calls the existing strict validator. The repair export **does not instantiate a provider** and performs zero network/API calls. Historical error counts are reported separately; zero new calls is not called a measured model error-rate improvement.

## Reproduce

```powershell
python -m unittest discover -s tests -t . -q
python scripts/repair_west_bund.py
```

Outputs under `data/poi_pipeline/semantic/repair/`:

- `west_bund_review_repaired.json`: the reduced primary human-review table.
- `west_bund_route_nodes.json`: grouped route-node proposals, geometry observations and eligibility flags.
- `west_bund_source_entities.json`: source/component/child registry with lineage and `route_selectable=false`.
- `west_bund_production_identity_matches.json`: original candidate-to-production resolver decisions.
- `west_bund_repair_run.json`: before/after counts, failure analysis and protected-file hashes.
- `test_result.json`: the recorded completed offline test result.

The exporter records pending/BLOCKED until a passing test result has been recorded. It verifies protected input/production/code hashes across export. [PHASE 2.5B REPAIR REPORT](../history/phase2_5/PHASE2_5B_REPAIR_REPORT.md) contains all 15 requested sections and the final status. No Phase 2.5C or promotion follows automatically.
