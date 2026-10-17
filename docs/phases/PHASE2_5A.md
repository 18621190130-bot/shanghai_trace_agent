# Phase 2.5A — West Bund POI Pipeline Architecture & Source Layer

Status: implemented; real pilot collected; awaiting human acceptance. Phase 2 remains frozen. No Phase 2.5B enrichment, scoring, candidate approval or production import is implemented.

## Data flow and contracts

`External sources → RawCandidate → normalize_candidate → boundary audit → deduplicate_candidates → CanonicalCandidate → EvidenceBundle`

Code lives in `src/poi_pipeline/`; all runtime code uses the Python standard library. Nothing in the route engine imports this package. `RawCandidate`, `NormalizedCandidate`, `CanonicalCandidate` and `EvidenceBundle` are staging contracts, deliberately incompatible with the required production `POI` schema. They contain no generated interest/experience/culture tags or visit timings.

Each raw record retains provider ID, Chinese/English names where available, aliases, address, original coordinates and CRS, provider category/tags, source URL/name/type, retrieval time, short snippets and supported fact categories. Missing English names and coordinates remain missing. Canonical records keep `merged_source_records`, `sources`, `field_sources`, boundary status and issues. Evidence bundles separate identity, coordinates, map, OSM, official, history, public-space, access and opening evidence, and explicitly list gaps. Historical page dates do not establish current opening status.

The baseline analyzer reads `POIRepository`, including the actual nested `walk_zone.id`, `metadata.tag_taxonomy`, and repository coordinate conversion. Area POIs use their representative coordinates through that repository. The pipeline does not duplicate or modify production schema validation. DeepSeek remains exclusively in the existing intent extraction flow and is never imported or called here.

## Sources and transport

- **Amap:** bounded keyword and nearby discovery, pagination, detail and geocoding methods. Detail/geocoding are available but unnecessary for the initial pilot because discovery returns coordinates. Credentials are read only from process `AMAP_API_KEY` and supplied outside cache identity. Provider category and district checks exclude ordinary services, shops, parking, charging and temporary photo points; all exclusions are auditable. Gate M complex names are explicit discovery exceptions, not shop approvals.
- **OSM:** one regional Overpass query for named museums, galleries, artwork, historic features, parks, gardens, sports spaces, theatres, arts/community centers, piers, cranes, works, industrial features, squares and pedestrian streets. Ways/relations use bounding-box centers, not verified entrances. No Nominatim, no OSM-to-ShanghaiTrace semantic tag mapping. Attribution: © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright).
- **Official:** crawl the West Bund project directory for relevant venue/public-space detail links and fetch known municipal/cultural-authority pages. A place name must occur in fetched HTML. Script/style contents are ignored. Store at most three excerpts of 180 characters per name, plus compact link metadata, not full HTML. Overview pages and logistics-only directory entries are not independent route-node candidates. This is bounded discovery, not an exhaustive general web crawler.
- **HTTP:** 20-second timeout, at most three attempts, exponential backoff, minimum 1.1 seconds between requests to a host, 4 MB response cap, atomic success cache writes, success hashes and timestamps. HTTP transient failures are retried; persistent failures have separate safe metadata caches. Cache replay makes no requests. `--retry-failed --live` reattempts transport failures; successful pages remain cached. Provider-declared errors remain visible rather than being treated as empty success.

Every adapter isolates errors; orchestration retains records already yielded before a source fails. Errors deliberately contain exception classes rather than potentially credential-bearing exception text. No key goes into request parameters saved on disk, cache identity, raw records or logs. Cached provider bodies are also redacted if they echo a supplied credential.

## Boundary, normalization and identity

The pilot uses a hand-defined eight-vertex GCJ-02 corridor around the existing Star Museum–Gate M cluster, following the river bend sufficiently to exclude obvious opposite-bank candidates. It does not claim to be the full official waterfront, a surveyed shoreline or an administrative polygon. Vertices and rationale are saved in the collection report. Points within 150 m of either side of the boundary, and records without coordinates, are `needs_review`. Clearly outside points stay in raw output and the exclusion audit, not canonical output. Amap records explicitly outside Xuhui are rejected during discovery. Official-only mentions have no inferred spatial acceptance.

Normalization applies Unicode NFKC, whitespace normalization, case/punctuation-insensitive match keys, alias deduplication, address cleanup, category cleanup and validated WGS84→GCJ-02 conversion using the existing geographic utility. Raw fields remain available. Shanghai administrative prefixes may be ignored in identity comparison; branch and building suffixes are not discarded.

Deduplication requires compatible entity kinds, names/aliases, and coordinates within 100 m for exact names, or within 160 m for >=0.90 name similarity plus >=0.85 address similarity. Complete-link clusters prevent a proximity chain from joining distant endpoints. Unknown entity kinds and missing-coordinate records are not automatically merged. Distinct OSM IDs remain separate because tanks, galleries and buildings may overlap or share names. This favors false negatives over destructive false merges. Stable IDs are deterministic for a fixed set of source IDs; cluster membership changes can change the canonical ID.

General source order is government → official operator → Amap → OSM → secondary. Coordinate selection independently prefers Amap, then OSM; field provenance records this choice. No map marketing copy supports complex cultural conclusions. Official snippets are evidence excerpts, not validated historical assertions. Before later semantic enrichment, unresolved official/map identity links and nested venue identities require review.

## Run and test

From the project directory:

```powershell
# Credential already configured in process environment; never print it.
python scripts/collect_west_bund.py --live

# Repeat entirely from cache, without network or credentials.
python scripts/collect_west_bund.py

# Explicitly retry a cached failed external request.
python scripts/collect_west_bund.py --live --retry-failed

python -m unittest discover -s tests -t . -q
```

If a newly configured Windows user variable has not propagated, load it only into the process with `$env:AMAP_API_KEY = [Environment]::GetEnvironmentVariable('AMAP_API_KEY', 'User')`. Do not print it. The current pilot used an already inherited process variable.

Output root defaults to `data/poi_pipeline/`; `--output PATH` selects another staging directory. Results overwrite the corresponding staging JSON files. Cache entries preserve original retrieval times; there is no automatic freshness policy. For a fresh snapshot, use a new output directory. No collection command writes `data/pois.json`.

- `raw/west_bund_raw_candidates.json`: discovered candidates, including later boundary exclusions.
- `canonical/west_bund_canonical_candidates.json`: unreviewed canonical candidates.
- `canonical/west_bund_evidence_bundles.json`: bundles keyed by candidate ID.
- `west_bund_baseline_report.json`: current production baseline.
- `west_bund_collection_report.json`: counts, provenance coverage, boundary, exclusions, partial failures and production hash.
- `cache/*.json`: compact cached responses and request metadata; `*.failure.json` stores failed request metadata.

See [PHASE 2.5A REPORT](../history/phase2_5/PHASE2_5A_REPORT.md) for actual pilot counts, representative candidates, limitations and acceptance stop point.
