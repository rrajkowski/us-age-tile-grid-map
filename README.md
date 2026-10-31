# Children and Seniors, State by State

An interactive tile-grid map showing how each US state's population under 18 and 65-and-older has shifted from 1970 to 2025. Every state gets its own small line chart, so you can compare all 50 at a glance and watch the "crossover" years where seniors began to outnumber children.

<!-- Add a screenshot or GIF here, e.g. docs/screenshot.png -->

- **50 small multiples** in a geographic tile layout (AK top-left, ME top-right, HI bottom-left, FL bottom-right)
- **Hover** a tile for exact values at the year under your cursor and the state's crossover year
- **Click** a tile for a large chart with summary metrics
- **Timeline slider** (with Play) that scrubs every tile at once; tiles tint when 65+ outnumber under-18
- **Shared or per-state y-axis**, light/dark mode, and a compact legend with a live **crossed over** count (for example `17/50`)
- No build step: static HTML with bundled D3, CSS, fonts, and Census data in `vendor/` and `census-data.js`

## Quick start

### View the bundled Census data (recommended)

This repo ships **2000–2025** Census Bureau data in `census-data.js`. Open `index.html` in a browser (double-click or drag into a window). The badge should read **Census Bureau data**. No Python or local server required for the bundled copy.

If the badge says **Illustrative mock data**, the page could not load `census-data.js` (wrong working directory) or you are overriding data with `?data=`.

### Local preview with a server

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000>. The page still prefers `census-data.js`; `states_age_1970_2025.json` is the HTTP fallback.

### Rebuild data from Census sources

```bash
python3 -m venv .venv --clear
source .venv/bin/activate
python -m pip install -r requirements.txt
python fetch_census_data.py
python -m http.server 8000
```

`fetch_census_data.py` writes **2000–2025** by default and updates both `states_age_1970_2025.json` and `census-data.js`. For **1970–2025**, pass decennial anchors:

```bash
python fetch_census_data.py --historical-csv decennial_1970_1990.csv
```

Optional ACS cross-check (needs a free [Census API key](https://api.census.gov/data/key_signup.html)):

```bash
python fetch_census_data.py --validate-acs --acs-key YOUR_KEY
```

### Host on GitHub Pages

One-time setup (repo **Settings**, you need admin access):

1. **Actions → General → Workflow permissions** → choose **Read and write permissions** → **Save**. (If this stays on read-only, deploy steps can fail with permission errors.)
2. **Pages → Build and deployment → Source** → **GitHub Actions**. Save. This creates the Pages site; the workflow cannot do this step with `GITHUB_TOKEN` alone.

Then push to `main` or re-run **Actions → Deploy to GitHub Pages**. The workflow copies static files to `_site` and publishes them.

Public URL: <https://rrajkowski.github.io/us-age-tile-grid-map/>

> **Illustrative mock data** remains in `index.html` as a fallback if neither bundled nor fetched JSON loads. The bundled repo copy uses real Census data.

## Data

Output schema, one record per state per year:

```json
{ "state": "Oregon", "state_code": "OR", "year": 2025, "pct_under_18": 19.0, "pct_65_plus": 21.0 }
```

| Years | Source | Notes |
| --- | --- | --- |
| 2000-2025 | U.S. Census Bureau, Population Estimates Program: state population by single year of age (`st-est00int-agesex`, `SC-EST2020-AGESEX-CIV`, `sc-est2025-agesex-civ`) | Single-year ages make "under 18" exact. The 2010+ files are civilian population. |
| 1970-1999 | Decennial census counts you supply via `--historical-csv` | Census Bureau state files for these years use five-year age groups, which cannot give an exact "under 18". |
| Optional check | ACS 1-year, Table S0101, via the Census Data API | `--validate-acs --acs-key KEY` compares PEP against ACS. Not used to build the dataset. |

Historical CSV columns: `state_code, year, pop_total, pop_under_18, pop_65_plus`, with rows for 1970, 1980 and 1990. Without it, the script writes 2000-2025 only and the page adjusts its range.

Years between census counts are filled with a monotone cubic spline (PCHIP). Unlike a natural cubic spline it never overshoots between points, and unlike linear interpolation it has no kinks at census years. The page draws its lines with `d3.curveMonotoneX` for the same reason.

**Crossover year** is the first year from which 65+ exceed under-18 in every later year, so one noisy year does not count.

DC and Puerto Rico are not included (the layout is the 50 states).

## Files

| File | Purpose |
| --- | --- |
| `index.html` | The visualization, tile layout, mock fallback, and UI |
| `census-data.js` | Bundled Census rows loaded by the page (GitHub Pages–friendly) |
| `states_age_1970_2025.json` | Same data as JSON; used when served over HTTP |
| `fetch_census_data.py` | Rebuilds the JSON and `census-data.js` from Census sources |
| `requirements.txt` | Pinned Python deps for the fetch script |
| `.github/workflows/pages.yml` | GitHub Pages deploy on push to `main` |
| `LICENSE` | MIT license for this project's code |

## Acknowledgments and notices

- Data: U.S. Census Bureau. Census Bureau data are works of the U.S. government and are not subject to copyright, but please cite the source.
- *This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.*
- Tile-grid maps were popularized by NPR and others; this layout is an independent implementation.
- Bundled assets in `vendor/`: D3 v7 (ISC), compiled Tailwind CSS (MIT), Inter and Source Serif 4 (SIL OFL)
- Python dependencies (via `requirements.txt`): pandas, NumPy, SciPy (BSD), requests (Apache-2.0)
- If you build the 1970-1999 anchors from IPUMS NHGIS, follow their [terms of use](https://www.nhgis.org/terms-use): cite NHGIS and do not redistribute their data files.

## License

Copyright (c) 2026 3R Webs. Code is released under the [MIT License](LICENSE). The license covers this project's code, not the underlying Census data or third-party data you add.
