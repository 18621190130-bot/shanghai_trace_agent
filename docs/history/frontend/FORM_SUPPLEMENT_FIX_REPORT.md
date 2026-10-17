# Form supplement and neighbourhood image fix — 2026-10-14

Updated deployed before-smart-start version only. Smart Start versions remain separate.

- Frontend submits both selected form intent and optional text.
- Backend supplies structured selections as context, retains missing time/interests deterministically, and rebuilds clarification state after merging.
- Explicit text changes can override form defaults. A named mandatory place determines the single zone rather than conflicting with the default area selection.
- Updated bilingual helper copy: text supplements the selected fields.
- Four user-provided JPEGs copied unchanged into frontend/assets/zones and mapped to old_city_central, wukang_fuxing_xujiahui, west_bund, hongkou_literary respectively.

Validation: 4 targeted backend tests + 14 frontend contracts passed. Live reproduction generated success: 240 minutes, art/industrial_heritage/waterfront, required p30, west_bund, no missing fields. Public browser verified all four photos load, combined request payload, same-origin API and absence of JS exceptions.

2026-10-17 maintenance note: the historical temporary sharing URL and Cloudflare deployment files were removed. The functionality described above is now present in the main project; see the root README for the current startup method.
