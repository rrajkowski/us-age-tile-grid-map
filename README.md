# Children and Seniors, State by State

An interactive tile-grid map showing how each US state's population under 18 and 65-and-older has shifted from 1970 to 2025. Every state gets its own small line chart, so you can compare all 50 at a glance and watch the "crossover" years where seniors began to outnumber children.

<!-- Add a screenshot or GIF here, e.g. docs/screenshot.png -->

- **50 small multiples** in a geographic tile layout (AK top-left, ME top-right, HI bottom-left, FL bottom-right)
- **Hover** a tile for exact values at the year under your cursor and the state's crossover year
- **Click** a tile for a large chart with summary metrics
- **Timeline slider** (with Play) that scrubs every tile at once; tiles tint when 65+ outnumber under-18
- **Shared or per-state y-axis**, and light/dark mode
- No build step: one HTML file using [D3 v7](https://d3js.org/) and [Tailwind CSS](https://tailwindcss.com/) from CDNs

## Quick start

### Look at it with the built-in mock data

Open `index.html` in a browser. You need an internet connection for the CDN scripts and fonts.

> **The built-in numbers are illustrative mock data, not official statistics.** They are built from rough per-state anchor values and smoothed with the same curve fitting the real pipeline uses. A badge on the page says "Illustrative mock data" whenever they are in use.

### Use real Census data

```bash
python3 -m venv .venv --clear
source .venv/bin/activate
python -m pip install -r requirements.txt
python fetch_census_data.py
python -m http.server 8000
```

Then open <http://localhost:8000>. The page loads `states_age_1970_2025.json` automatically and the badge changes to "Census Bureau data". You can also point it at another file with `?data=URL`.

A local server is needed because browsers block a page opened from disk from reading a neighbouring JSON file.

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
| `index.html` | The visualization, including the embedded mock dataset and the grid layout coordinates |
| `fetch_census_data.py` | Builds `states_age_1970_2025.json` from Census sources |
| `LICENSE` | MIT license for this project's code |

## Acknowledgments and notices

- Data: U.S. Census Bureau. Census Bureau data are works of the U.S. government and are not subject to copyright, but please cite the source.
- *This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.*
- Tile-grid maps were popularized by NPR and others; this layout is an independent implementation.
- Libraries loaded at runtime from CDNs, not bundled: D3 (ISC license), Tailwind CSS (MIT). Fonts from Google Fonts: Inter and Source Serif 4 (SIL Open Font License).
- Python dependencies: pandas, NumPy, SciPy (BSD), requests (Apache-2.0).
- If you build the 1970-1999 anchors from IPUMS NHGIS, follow their [terms of use](https://www.nhgis.org/terms-use): cite NHGIS and do not redistribute their data files.

## License

Copyright (c) 2026 3R Webs. Code is released under the [MIT License](LICENSE). The license covers this project's code, not the underlying Census data or third-party data you add.
