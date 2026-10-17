# Frontend design refresh — 2026-10-13

- Cover Plan my walk: larger purple CTA with slow sweeping highlight and reduced-motion support.
- Brand logo/name links to #home.
- Planning questions grouped into required and optional, with Must-select labels, larger consistent headings, and guidance on route effects.
- Arrival: remove visible reached banner, simplify metadata, show Cultural Bridge as readable plain prose, keep What to notice on the same surface, use distinct colored action buttons for nearby services and entrance map.
- Remove static weather/active-stop colored boxes; simplify route stop metadata. Existing content, images, routing, and arrival history remain.
- `web_server.py --demo` explicitly enables simulation; omission explicitly disables it regardless of inherited environment.

## Running local versions
- Demo: http://127.0.0.1:8788/
- Standard: http://127.0.0.1:8789/
- Both are full application versions, with live integrations as configured locally. Standard retains real GPS and manual arrival.
- Restart with `python web_server.py --demo --port 8788` and `python web_server.py --port 8789` respectively if processes stop.

## Verification
- 24 targeted frontend contract/image/arrival tests passed.
- 11 targeted backend ArrivalTests passed, including rejecting simulated coordinates with demo disabled.
- `scripts/test_frontend_refresh.cjs` passed: shine, image loading, brand navigation, required/optional grouping, readable arrival narrative, action backgrounds, mobile overflow, both HTTP endpoints and demo flags.
- Browser route generation performed on an offline test server (8790), avoiding redundant live provider calls. Live versions checked read-only for page availability and configuration.
- Screenshots: `examples/frontend_refresh/`.
