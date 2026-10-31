#!/usr/bin/env python3
"""
Build states_age_1970_2025.json: % of each state's population under 18 and 65+, 1970-2025.

Output schema (one record per state-year, 50 states):
    {"state": "Oregon", "state_code": "OR", "year": 2025, "pct_under_18": 19.0, "pct_65_plus": 21.0}

Sources
-------
2000-2025  Census Bureau Population Estimates Program (PEP), state population by single year of age.
             2000-2009  st-est00int-agesex.csv      (intercensal, vintage 2000-2010)
             2010-2019  SC-EST2020-AGESEX-CIV.csv   (vintage 2020)
             2020-2025  sc-est2025-agesex-civ.csv   (vintage 2025)
           Single-year ages let "under 18" and "65+" be computed exactly. The 2010+ files are
           civilian population; the difference from the resident population is small.
1970-1999  Decennial census counts. The Census Bureau's own 1970-1999 state files use five-year
           age groups, which cannot give an exact "under 18", so supply a small CSV via
           --historical-csv (see HISTORICAL CSV below). Years between census years are filled
           with a monotone cubic (PCHIP) fit, the same curve the HTML page draws.
Optional   ACS 1-year Table S0101 (percent columns) for 2005-2024 via the Census API, used only to
           cross-check the PEP numbers (--validate-acs). A free key is at
           https://api.census.gov/data/key_signup.html

HISTORICAL CSV
--------------
Columns: state_code, year, pop_total, pop_under_18, pop_65_plus
Rows for 1970, 1980, 1990 (2000 is optional; PEP already covers it). Good sources are the IPUMS
NHGIS decennial time series and the Census Bureau's decennial summary files. Extra years are
fine; every year below 2000 that you supply becomes a spline knot.

Usage
-----
    python3 -m venv .venv --clear && source .venv/bin/activate
    python -m pip install -r requirements.txt
    python fetch_census_data.py --historical-csv decennial_1970_1990.csv
    python fetch_census_data.py --historical-csv decennial_1970_1990.csv --validate-acs --acs-key YOUR_KEY
    python fetch_census_data.py            # 2000-2025 only (the page then shows 2000-2025)

Writes states_age_1970_2025.json and census-data.js (the copy index.html loads).
Both are static files, so the folder can be published as-is on GitHub Pages or
Cloudflare Pages. Local preview:
    python -m http.server
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.interpolate import PchipInterpolator

# FIPS -> (name, USPS code). 50 states only; DC and Puerto Rico are dropped to match the tile grid.
STATES = {
    1: ("Alabama", "AL"), 2: ("Alaska", "AK"), 4: ("Arizona", "AZ"), 5: ("Arkansas", "AR"),
    6: ("California", "CA"), 8: ("Colorado", "CO"), 9: ("Connecticut", "CT"), 10: ("Delaware", "DE"),
    12: ("Florida", "FL"), 13: ("Georgia", "GA"), 15: ("Hawaii", "HI"), 16: ("Idaho", "ID"),
    17: ("Illinois", "IL"), 18: ("Indiana", "IN"), 19: ("Iowa", "IA"), 20: ("Kansas", "KS"),
    21: ("Kentucky", "KY"), 22: ("Louisiana", "LA"), 23: ("Maine", "ME"), 24: ("Maryland", "MD"),
    25: ("Massachusetts", "MA"), 26: ("Michigan", "MI"), 27: ("Minnesota", "MN"), 28: ("Mississippi", "MS"),
    29: ("Missouri", "MO"), 30: ("Montana", "MT"), 31: ("Nebraska", "NE"), 32: ("Nevada", "NV"),
    33: ("New Hampshire", "NH"), 34: ("New Jersey", "NJ"), 35: ("New Mexico", "NM"), 36: ("New York", "NY"),
    37: ("North Carolina", "NC"), 38: ("North Dakota", "ND"), 39: ("Ohio", "OH"), 40: ("Oklahoma", "OK"),
    41: ("Oregon", "OR"), 42: ("Pennsylvania", "PA"), 44: ("Rhode Island", "RI"), 45: ("South Carolina", "SC"),
    46: ("South Dakota", "SD"), 47: ("Tennessee", "TN"), 48: ("Texas", "TX"), 49: ("Utah", "UT"),
    50: ("Vermont", "VT"), 51: ("Virginia", "VA"), 53: ("Washington", "WA"), 54: ("West Virginia", "WV"),
    55: ("Wisconsin", "WI"), 56: ("Wyoming", "WY"),
}
CODE_TO_NAME = {code: name for name, code in STATES.values()}

BASE = "https://www2.census.gov/programs-surveys/popest/datasets"
PEP_SOURCES = [  # (url, first year, last year) to take from each file
    (f"{BASE}/2000-2010/intercensal/state/st-est00int-agesex.csv", 2000, 2009),
    (f"{BASE}/2010-2020/state/asrh/SC-EST2020-AGESEX-CIV.csv", 2010, 2019),
    (f"{BASE}/2020-2025/state/asrh/sc-est2025-agesex-civ.csv", 2020, 2025),
]
YEAR_COL = re.compile(r"^(?:POPESTIMATE|POPEST)(\d{4})(?:_CIV)?$")


def download(url: str, cache_dir: Path) -> pd.DataFrame:
    """Fetch a CSV once and cache it on disk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / url.rsplit("/", 1)[-1]
    if not path.exists():
        print(f"  downloading {url}", file=sys.stderr)
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    return pd.read_csv(path, encoding="latin-1")


def pep_shares(df: pd.DataFrame, first: int, last: int) -> pd.DataFrame:
    """Percent under 18 and 65+ per state-year from a PEP single-year-of-age file.

    Rows: SEX 0 = both sexes, AGE 0..84 single years and 85 = "85 and older"
    (AGE 999 is a published total; it is excluded and recomputed so the shares always add up).
    """
    df = df[(df["SEX"] == 0) & (df["AGE"].between(0, 85)) & (df["STATE"].isin(STATES))]
    year_cols = {int(m.group(1)): c for c in df.columns if (m := YEAR_COL.match(c))}
    out = []
    for year in range(first, last + 1):
        if year not in year_cols:
            raise KeyError(f"year {year} not found in columns {sorted(year_cols)}")
        col = year_cols[year]
        total = df.groupby("STATE")[col].sum()
        under = df[df["AGE"] < 18].groupby("STATE")[col].sum()
        over = df[df["AGE"] >= 65].groupby("STATE")[col].sum()
        out.append(pd.DataFrame({
            "fips": total.index, "year": year,
            "pct_under_18": (100 * under / total).values,
            "pct_65_plus": (100 * over / total).values,
        }))
    res = pd.concat(out, ignore_index=True)
    res["state_code"] = res["fips"].map(lambda f: STATES[f][1])
    return res.drop(columns="fips")


def load_pep(cache_dir: Path) -> pd.DataFrame:
    print("Population Estimates Program (2000-2025)", file=sys.stderr)
    return pd.concat([pep_shares(download(u, cache_dir), a, b) for u, a, b in PEP_SOURCES], ignore_index=True)


def load_historical(path: Path) -> pd.DataFrame:
    """Decennial anchors (pre-2000) from a user-supplied CSV; returns percentages."""
    h = pd.read_csv(path)
    need = {"state_code", "year", "pop_total", "pop_under_18", "pop_65_plus"}
    if not need <= set(h.columns):
        raise SystemExit(f"{path} must have columns {sorted(need)}; found {sorted(h.columns)}")
    h = h[h["year"] < 2000].copy()
    h["pct_under_18"] = 100 * h["pop_under_18"] / h["pop_total"]
    h["pct_65_plus"] = 100 * h["pop_65_plus"] / h["pop_total"]
    return h[["state_code", "year", "pct_under_18", "pct_65_plus"]]


def fill_with_pchip(known: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
    """Annual series from sparse knots using a monotone cubic Hermite spline (PCHIP).

    Natural cubic splines overshoot between sparse points (a dip that never happened);
    linear interpolation leaves kinks at census years. PCHIP is shape-preserving: it stays
    between neighbouring knots and has a continuous slope. Known years are never altered.
    """
    rows = []
    for code, g in known.groupby("state_code"):
        g = g.sort_values("year").drop_duplicates("year")
        years = np.arange(max(start, int(g.year.min())), end + 1)
        fu = PchipInterpolator(g["year"], g["pct_under_18"])
        fo = PchipInterpolator(g["year"], g["pct_65_plus"])
        have = g.set_index("year")
        for y in years:
            if y in have.index:
                u, o = have.at[y, "pct_under_18"], have.at[y, "pct_65_plus"]
            else:
                u, o = float(fu(y)), float(fo(y))
            rows.append((code, int(y), u, o))
    return pd.DataFrame(rows, columns=["state_code", "year", "pct_under_18", "pct_65_plus"])


def acs_pct(year: int, key: str) -> pd.DataFrame:
    """ACS 1-year S0101 percent-of-population for under 18 and 65+, by state.

    Variable ids differ between years, so look them up by label in variables.json
    instead of hard-coding them.
    """
    root = f"https://api.census.gov/data/{year}/acs/acs1/subject"
    meta = requests.get(f"{root}/variables.json", timeout=60).json()["variables"]

    def find(suffix: str) -> str:
        ids = sorted(k for k, v in meta.items()
                     if re.fullmatch(r"S0101_C02_\d+E", k) and v.get("label", "").endswith("!!" + suffix))
        if not ids:
            raise LookupError(f"S0101 percent variable ending '{suffix}' not found for {year}")
        return ids[0]

    v_u, v_o = find("Under 18 years"), find("65 years and over")
    r = requests.get(root, params={"get": f"NAME,{v_u},{v_o}", "for": "state:*", "key": key}, timeout=60)
    r.raise_for_status()
    head, *body = r.json()
    df = pd.DataFrame(body, columns=head)
    df["fips"] = df["state"].astype(int)
    df = df[df["fips"].isin(STATES)]
    df["state_code"] = df["fips"].map(lambda f: STATES[f][1])
    return pd.DataFrame({"state_code": df["state_code"], "year": year,
                         "acs_u18": df[v_u].astype(float), "acs_65": df[v_o].astype(float)})


def validate_against_acs(final: pd.DataFrame, key: str) -> None:
    print("Cross-checking against ACS 1-year S0101", file=sys.stderr)
    frames = []
    for year in range(2005, 2025):
        if year == 2020:        # no standard 1-year ACS release for 2020
            continue
        try:
            frames.append(acs_pct(year, key))
        except Exception as exc:  # keep going; this check is advisory
            print(f"  {year}: skipped ({exc})", file=sys.stderr)
    if not frames:
        return
    m = final.merge(pd.concat(frames), on=["state_code", "year"])
    for ours, theirs, label in [("pct_under_18", "acs_u18", "under 18"), ("pct_65_plus", "acs_65", "65+")]:
        diff = (m[ours] - m[theirs]).abs()
        worst = m.loc[diff.idxmax()]
        print(f"  {label}: mean |diff| {diff.mean():.2f} pts, max {diff.max():.2f} pts "
              f"({worst.state_code} {int(worst.year)})", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--historical-csv", type=Path, help="decennial anchors for years before 2000")
    ap.add_argument("--out", type=Path, default=Path("states_age_1970_2025.json"))
    ap.add_argument("--cache-dir", type=Path, default=Path(".census_cache"))
    ap.add_argument("--validate-acs", action="store_true", help="compare with ACS 1-year S0101")
    ap.add_argument("--acs-key", help="Census API key (required with --validate-acs)")
    args = ap.parse_args()

    pep = load_pep(args.cache_dir)
    if args.historical_csv:
        known = pd.concat([load_historical(args.historical_csv), pep], ignore_index=True)
        final = fill_with_pchip(known, 1970, 2025)
    else:
        print("No --historical-csv given: writing 2000-2025 only.", file=sys.stderr)
        final = pep

    if args.validate_acs:
        if not args.acs_key:
            raise SystemExit("--validate-acs needs --acs-key")
        validate_against_acs(final, args.acs_key)

    final["state"] = final["state_code"].map(CODE_TO_NAME)
    final = final.sort_values(["state", "year"])
    final[["pct_under_18", "pct_65_plus"]] = final[["pct_under_18", "pct_65_plus"]].round(2)
    records = final[["state", "state_code", "year", "pct_under_18", "pct_65_plus"]].to_dict("records")
    assert len({r["state_code"] for r in records}) == 50, "expected 50 states"
    args.out.write_text(json.dumps(records, indent=1) + "\n")
    bundle = args.out.parent / "census-data.js"
    bundle.write_text(
        "/* Generated by fetch_census_data.py. Loaded by index.html. */\n"
        "window.CENSUS_ROWS = " + json.dumps(records, separators=(",", ":")) + ";\n"
    )
    print(f"Wrote {len(records)} rows to {args.out} and {bundle}", file=sys.stderr)


if __name__ == "__main__":
    main()
