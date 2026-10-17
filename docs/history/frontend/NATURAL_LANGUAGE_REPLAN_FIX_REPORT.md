# Natural Language Replan Reliability & Result Feedback

Status: READY FOR MANUAL ACCEPTANCE — 2026-10-08
Preview (with cover): http://127.0.0.1:8783/

## 1. Scope
Implemented the six requested changes: original route and complete adjustment history; removal of the active-stop Skip button; natural-language-first editing with three quick actions and Advanced options; selected park/start inclusion; duration-free Places in mind; semantic execution reliability and truthful change feedback. No new phase or Cultural RAG.

## 2. Shortening root cause
The old action protocol had no reduction goal. Its prompt mapped tired/relaxed to deep pace (longer visits), while time target changes updated a budget without requiring a shorter route. Generic success messaging did not verify reduction. This diagnosis follows executable code and the reported symptoms; an original failing live-provider response was not retained.

## 3. Quantity insertion root cause
The schema lacked a count and an unnamed-add action. Matching insertion was restricted to ADD_INTEREST; its executor inserted one candidate and stopped. Thus a valid desire to add two ordinary places could fail validation or lose quantity.

## 4. Semantic protocol and validation
Added SHORTEN_ROUTE with duration/walking/stops/easier goal, and ADD_MATCHING_STOPS with requested_count (1–20). The LLM interprets semantic intent. No raw-input phrase routing or special-case execution for the two example strings. Existing fixtures remain schema-compatible. Named additions, must-go, skips, reorder, preferences, hard availability and clarification retain their typed path. New structured Advanced controls use normalization too.

## 5. Reduction implementation
Existing RouteMutationService tests bounded one-stop deletions, preserves required destinations, modes and relative order, and retains a nonempty route. It compares the same logical origin and RouteEngine estimator before and after. Walking requires lower distance; duration/easier requires lower duration without greater estimated walking; stops requires fewer stops. The combined proposed result is verified before commit. No improvement returns NO_CHANGE without a new version. This is a bounded local search, not a proof that no globally better route exists.

## 6. Addition, quantity and preferences
Candidates use the saved zone, preferences, avoids, progress exclusions, visit materialization and insertion scoring. Count+interest can narrow the new candidates without replacing existing preferences. Explicit requests can create 6–7 stops; default generation caps are unchanged. A requested count is bounded at 20 and candidate availability. Insertion preserves existing relative order, excludes visited/skipped and duplicates, and reports full/partial/no result. A soft target yields an overrun warning; an existing hard limit remains enforced.

## 7. Authoritative feedback DTO
web_route_feedback.py computes remaining-route differences from saved before/after TripState snapshots. Fields include request_text, interpreted_intent, execution_status, reason_code, previous/current route version IDs, before/after metrics, added/removed/reordered IDs, mode changes, preserved must-go, requested/actual count, warnings and explanation. Completed visits are separate progress facts, not route-removal claims. A partially saved compound request is not reported as fully applied.

## 8. Metric basis
UI shows Stops, Time and Walking as before → after, explicitly labeled comparable planning estimates. Both sides use the same estimator and origin; neither is mixed with a provider distance. Live AMap route geometry remains on the route/map. Reductions here verify planning estimates, not a guarantee about actual walking time or a new survey of street geometry. Real walking integration was not changed or re-tested unnecessarily.

## 9. Result status examples
- APPLIED: 5→7 stops, two distinct additions.
- PARTIALLY_APPLIED: request 20, only eligible candidates inserted; actual count shown.
- NO_CHANGE: every remaining stop must-go, or no eligible additional candidate; no new route version.
- NEEDS_CLARIFICATION: ambiguous museum / unclear request; state unchanged.
- FAILED: provider/domain failure or infeasible hard limit; safe UI wording, no schema traceback.
- Preference/time-only edits explicitly say the route remains the same when metrics and sequence are unchanged.

## 10. Frontend and history
Adjust your walk has the input and update action first. Quick actions: Add a stop, Skip next stop, Change interests. No Shorten my walk quick chip. All structured operations are in Advanced options. The active target box only retains arrival confirmation. Original route, full feedback history and every immutable saved route version are readable. Failed/no-change attempts are retained too. History survives refresh and language changes in the current server session and is isolated on trip replacement. Loading disables repeat submission; revision CAS and response trip identity protect stale results. English/Chinese labels and km/mi comparison formatting are supported.

## 11. Initial planning fixes
Surprise me sends a Core start_poi_id rather than coordinates alone. Clarification validates it, resolves effective coordinates and includes it as required; the engine's final guard places it first before feasibility verification. Park starts are covered by tests. Remaining-route replanning clears the original start lock, preserving progress semantics.
Places in mind hides the duration control and sends no duration. The backend derives a sufficient planning estimate from the selected visits, a feasible path and existing buffer, then uses the existing feasibility/planning pipeline. It does not silently retain a fixed 180-minute cap. Explicit callers can still supply duration.

## 12. Real-route and real-model evidence
Production repository + real engine, fixture NLU:
| Route case | Stops | Duration (min) | Walking estimate (km) |
|---|---|---|---|
| Shorten A | 5 → 4 | 168.88 → 137.26 | 4.4157 → 4.2946 |
| Shorten B | 3 → 2 | 177.69 → 102.60 | 2.8266 → 2.8201 |
| Shorten C | 3 → 2 | 149.55 → 104.52 | 1.8414 → 1.8393 |
| Add two | 5 → 7 | 168.88 → 242.23 | 4.4157 → 5.4170 |

Small live DeepSeek acceptance (one three-turn run, deterministic geometry):
1. "I'm tired. Cut the route for me." → SHORTEN_ROUTE/easier; 5→4, 168.88→137.26 min.
2. "Add another two places to the route." → ADD_MATCHING_STOPS/count=2; 4→6, two actual additions and soft overrun warning.
3. "I want less walking." → walking goal; 5.4034→4.4157 km.

Evidence: examples/replan_feedback/shorten_real_routes.json, add_two_real_route.json, live_language.json. No credentials in artifacts. Live model success is an observed sample, not a universal language accuracy claim.

## 13. Verification
Passed targeted suites:
- Web adapter + interaction semantics + route engine: 128 tests.
- TripState + replanning + unified entry: 74 tests.
- Final adapter + new feedback cases: 38 tests (includes 10 new cases; overlaps adapter tests above).
- Frontend contract/arrival/image suites: 24 tests; final contract check: 14.
- Browser: cover present, duration hidden in Places in mind, active skip removed, Advanced collapsed, exactly three quick actions, real 5→7 insertion and 7→6 reduction, original route unchanged, all versions accessible, history retained after refresh/language switch, mobile without horizontal overflow.
- Live NLU: three calls as above.

Browser artifact: examples/replan_feedback/browser_checks.json; screenshots editor-desktop.png and editor-mobile.png. Test scripts: scripts/test_replan_feedback.cjs and scripts/accept_replan_language.py. The live script intentionally does not call unrelated provider APIs.

## 14. Frozen semantics, audit and limitations
Core POI data, route roles, spatial profiles, identity mappings, image layer, Arrival content and TripState implementation remain unchanged. 755 pre-existing src/data files match the start-of-task hash baseline; 12 existing files changed for the explicitly authorized fixes. Full list: examples/replan_feedback/frozen_audit.json. RouteEngine has only the selected-start guard; the prior engine freeze test verifies that removing this exact extension reproduces the historical engine hash. State/event replay, CAS, visited monotonicity and existing semantics passed affected regression.

History persistence follows the existing in-memory server/session lifecycle (24-hour idle expiration); restarting the server does not preserve trips. No database migration was added. Shortening currently removes one suitable optional stop per request, preserves visit modes and performs no global optimization. Result comparisons are planning estimates. Broader online semantic coverage and visual taste remain for human acceptance. Stop here; no next phase started.
