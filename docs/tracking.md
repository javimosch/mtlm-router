# Tracking plan (vigie)

Site `mtlm-router.intrane.fr` is registered on the shared vigie instance
(`vigie.intrane.fr`, sqlite at `/opt/vigie/vigie.db` on dk1). The snippet
loads via `<script defer src="https://vigie.intrane.fr/vigie.js"
data-site="mtlm-router.intrane.fr">` in `site/layout.html` and inline on
standalone pages (`catalog.html`, `pricing.html`, `lanes/*.html`).

**API contract:** `window.vigie(name, props)` — a function, NOT
`vigie.track()`. It is `defer`-loaded, so page-load events must fire on
`DOMContentLoaded`; click events can fire any time. The delegated
`data-track` listener in `layout.html` fires `vigie(data-track, {href,page})`
for any tagged element.

## Events

| event | where | props | meaning |
|---|---|---|---|
| `pageview` | auto | — | every page + SPA nav |
| `playground` | index/fr | `{route,action}` | successful `/demo/route` call |
| `playground_error` | index/fr | `{status}` | demo call failed — dead-demo alarm |
| `lane_select` | index/fr | `{lane}` | which lane tab a prospect picks |
| `lane_page_view` | lanes/*.html | `{lane}` | per-lane landing view (DOMContentLoaded) |
| `lane_demo_chip` | lanes/*.html | `{lane,q}` | curated example clicked |
| `lane_demo_try` | lanes/*.html | `{lane,q}` | pinned playground submitted |
| `lane_demo_result` | lanes/*.html | `{lane,action,route,set_size}` | pinned demo result |
| `lane_demo_error` | lanes/*.html | `{lane,status}` | pinned demo failure |
| `lane_pack_dl` | lanes/*.html, catalog | `{lane}` | lanepack tarball download click |
| `cta_*` | tagged links | `{href,page}` | `cta_github`, `cta_article`, `cta_wallet`, `cta_release`, `cta_custom_lane`, `cta_catalog`, `cta_pricing`, `cta_peage`, `cta_dedicated` |
| `lead` | contact/mailto | — | explicit contact intent |
| `cta_pricing` etc | vigie auto | — | text-regex fallback on untagged CTAs |

## Goals (vigie `goals` table)

`demo_playground`→`playground`, `lane_demo`→`lane_demo_result`,
`custom_lane_lead`→`cta_custom_lane`, `lead`→`lead`,
`pack_download`→`lane_pack_dl`, `catalog_visit`→path `/catalog.html`.

## Funnels (vigie `funnels` table, session-stitched by sid)

- `homepage-demo`: `/` → `playground` → `cta_pricing`
- `lane-demo`: `lane_page_view` → `lane_demo_try` → `lane_demo_result` → `cta_custom_lane`
- `demo-to-lead`: `/` → `playground` → `lead`

Query from dk1:

```sh
cd /opt/vigie
./vigie-cloud funnel show --site mtlm-router.intrane.fr --name lane-demo --since 30d
./vigie-cloud stats goals --site mtlm-router.intrane.fr --since 30d
./vigie-cloud stats event-props --site mtlm-router.intrane.fr --event lane_demo_result --since 30d
```

Do NOT add `track_rules` rows for elements already carrying `data-track`
— vigie's rule matcher and our delegated listener would both fire,
double-counting.
