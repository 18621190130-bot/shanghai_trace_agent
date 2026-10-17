# Phase 2.5B — Evidence-Grounded Semantic Enrichment

This phase produces review proposals only. Production `data/pois.json`, taxonomy, route scoring, clarification and route composition are not changed. Phase 2.5A canonical/evidence files are immutable inputs for this workflow.

## Contracts and responsibilities

`preparation.py` applies the user's two explicit route-node consolidations: 西岸艺术中心 + A馆 (including its official-only record), and 西岸穹顶艺术中心 + 北广场. Original candidate IDs, component coordinates and provenance are retained. The main venue's existing coordinate remains the representative point. This is a composite route-node scope, not a claim that a plaza and a building are the same entity. B1/N/D halls remain separate pending review.

Each input EvidenceBundle becomes a catalog of fine-grained evidence atoms with deterministic IDs, source URL/type, retrieval time, record ID and original value. Quotes, category facts and coordinate facts remain distinguishable. Official-only records without geometry are not assigned guessed coordinates or automatically linked to similarly named map entries.

`POISemanticEnricher` uses the existing `DeepSeekLLMClient`. The shared provider gained an optional output-token parameter and returned usage metadata; intent parsing retains the original 1200-token default, thinking disabled, no automatic provider retry. Semantic enrichment uses 3600 tokens and at most four total attempts per candidate by default, including earlier cached attempts. JSON parsing and strict schema validation reuse existing project utilities. No second HTTP/provider stack was introduced.

The model receives the candidate, evidence catalog, current taxonomy, approximate nearby geometry and schema. It does **not** receive coverage counts. The prompt explicitly states **Coverage gaps are NOT evidence for assigning a tag**. Validated tags enter the coverage function only afterwards.

## Output and validation

The strict LLM schema contains category; three tag lists and tag references; route role with primary/eligible/confidence and explanations for all three roles; citywalk value; extractive summary/culture bridge drafts; product-estimate visit profiles; semantic confidence; stability; missing information; referenced factual slots; and optional taxonomy extension discussion entries.

Coordinates are excluded from the LLM output schema and inherited from the specific coordinate source selected in Phase 2.5A. The validator checks coordinate consistency against its evidence, allowed vocabulary, reference existence, tag-evidence completeness, evidence gates, duplicate tags, role consistency, anchor value, short transition visits, monotonic visit estimates and extra fields. Unknown tags/fields are rejected. Empty culture tags are valid.

Sensitive factual slots (opening hours, ticket prices, reservations, historical dates, former functions, architect names, official designations) must quote a literal substring of an appropriate cited evidence value. Historical/architect/designation claims require an official source. Summary and culture bridge are also extractive drafts; interpretation is separated into City Walk and role reasons. Dynamic facts remain dated source claims, not verified current operating conditions.

Deterministic validation is deliberately conservative and does not prove arbitrary natural-language reasoning. Lexical evidence gates may produce false negatives; all proposals remain subject to human review. Existing source confidence is distinct from model semantic confidence. API/validation failures never become fabricated enrichment; failed rows retain explicit low-confidence review placeholders rather than being silently accepted.

After bounded model retries, an offline supported-subset pass may reject individual **known** tags whose cited evidence fails the same gates. `rejected_tag_proposals` preserves their original references and rejection reasons. This pass never invents replacement tags, never rescues unknown vocabulary/schema/reference/factual failures, and still validates all remaining fields strictly. Every filtered record is forced to review or reject because the interpretive reasons may need reconciliation with the smaller tag set. Reports distinguish fully valid proposals from supported-subset recoveries and unresolved failures. No additional API call is needed for this step.

## Admission and priority

`evaluate_citywalk_candidate()` considers source/existence, location, semantic value, City Walk/connector value, stability, geography and duplicate identities. Generic food/retail, temporary events, clearly outside candidates and confirmed production duplicates are rejected as additions. Unknown location/stability, weak role semantics, possible duplicates and composite visit scopes stay in review. An `accept` is only a recommendation for human review, never an import.

`marginal_coverage_gain()` uses `sum(1 / (1 + baseline frequency))` over already validated tags. This is a fixed-baseline priority measure; scores cannot be summed to estimate portfolio coverage. The preview separately counts actual accepted tag additions. Review/reject rows are excluded, so proposed coverage may legitimately remain unchanged. No tag is added merely to improve coverage.

Approximate geographic usefulness compares candidate distance to existing production nodes and whether it lies between two nearby anchors within a 1.25 geometric detour ratio, with at least 150 m separation. These are representative-point Haversine distances, not street access or walking routes. Geometry contributes to priority only after semantic validation. Non-museum art cases are listed separately without forcing `museum_visit`.

## Reproduction

From the project directory:

```powershell
python -m unittest discover -s tests -t . -q
python scripts/enrich_west_bund.py --live --max-attempts 4
python scripts/enrich_west_bund.py
```

`DEEPSEEK_API_KEY` must already be present in the live process environment. Never print it. `--workers` supports one to three concurrent independent calls. The default command without `--live` revalidates and replays cache/checkpoints without network access. Logs contain IDs, counts and dispositions, not keys. API output and diagnostics are redacted before persistence. `DEEPSEEK_DEBUG` is disabled for batch collection.

Per-candidate success caches include request identity, prompt version, safe provider usage and attempts; invalid outputs are preserved separately for audit. Matching checkpoints permit continuation and revalidation after stricter validation without calling the API for already-valid outputs. Four total attempts is a cap, not a success quota; attempts and validation failures are reported. Use `--test-result "..."` only to record an actually completed test result in the generated report.

Outputs in `data/poi_pipeline/semantic/`:

- `west_bund_enriched_candidates.json`
- `west_bund_review.json` (complete evidence catalogs, role reasons, visit proposals, confidence, priority and disposition)
- `west_bund_coverage_preview.json`
- `west_bund_prepared_candidates.json`, `west_bund_prepared_evidence.json`, `west_bund_merge_manifest.json`
- `west_bund_enrichment_run.json`, `cache/`, `checkpoint/`

Human-readable output: [PHASE 2.5B REPORT](../history/phase2_5/PHASE2_5B_REPORT.md), grouped by Recommended Accept / Needs Review / Reject and ending with up to 25 priority review candidates.

STOP: Human acceptance is required before any later promotion design. This phase does not run a live/final Route Engine regression, generate routes, implement role composition or overwrite production POIs. The full offline unittest suite is run as explicitly requested.
