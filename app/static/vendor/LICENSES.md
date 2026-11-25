# Vendored front-end assets

These files used to be loaded from cdn.jsdelivr.net and fonts.googleapis.com.
They are served from this folder instead so that a blocked CDN, an ad blocker,
a captive portal or an offline demo can never take the interface's layout, its
icons or its charts down with it.

| Folder | Package | Version | Licence |
| --- | --- | --- | --- |
| `bootstrap/` | `bootstrap` (dist css + bundle js) | 5.1.3 | MIT |
| `bootstrap-icons/` | `bootstrap-icons` (css + woff/woff2) | 1.11.0 | MIT |
| `chartjs/` | `chart.js` (`dist/chart.umd.min.js`) | 4.4.0 | MIT |
| `marked/` | `marked` (`marked.min.js`) | 9.1.6 | MIT |
| `inter/` | `@fontsource/inter` woff2, latin, weights 400–800 | 5.x | SIL OFL 1.1 |

All are unmodified upstream builds. To upgrade one, download the same file path
from the package on jsdelivr (or npm) into the matching folder and bump the
version here; `inter/inter.css` also lists each weight it declares.
