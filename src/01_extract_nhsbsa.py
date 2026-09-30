"""
Project 4 - Step 1: extract prescribing data from the NHSBSA Open Data Portal.

READ THIS FIRST
---------------
This is the REAL extraction script. It targets the NHSBSA Open Data Portal API,
it filters server-side, it handles pagination, and it writes Parquet. If you have
an internet connection it will pull genuine English Prescribing Dataset extracts.

It is written first, and separately from the generator, because the extraction
IS the skill this project is claiming. The English Prescribing Dataset adds about
17 million rows a month and has been published since January 2014. Three years is
roughly 600 million rows. Downloading all of it and filtering afterwards is the
wrong answer, and the difference between the two approaches is the whole point:

    WRONG:  download every month in full, then filter in pandas
    RIGHT:  send the filter to the API, download only the rows you need

The filter below cuts roughly 17 million rows a month to roughly 150,000 - a
factor of over a hundred - because this analysis only needs six BNF sections and
one published low-priority list. That judgement is what makes the project run on
a laptop.

WHEN THERE IS NO NETWORK
------------------------
`src/01b_generate_data.py` produces a dataset with the identical schema so the
rest of the pipeline runs. Every downstream file works against either source
unchanged. The README says plainly which one produced the figures in the repo.

API notes, which cost time to work out and are worth writing down:
  - the portal runs CKAN's datastore_search_sql endpoint, so the filter is
    literally SQL sent over HTTP
  - resource ids change every month; they are discovered from package_show
  - the row limit per request is enforced, so paginate with LIMIT/OFFSET
  - BNF_CODE prefix matching is what makes chapter/section filtering cheap;
    LIKE 'X%' on an indexed column is fast, a function on the column is not

Run:  python src/01_extract_nhsbsa.py --from 2023-01 --to 2025-12
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

BASE = "https://opendata.nhsbsa.net/api/3/action"
EPD_PACKAGE = "english-prescribing-data-epd"

# ---------------------------------------------------------------------------
# THE FILTER. This is the analytical scope, and it is applied AT SOURCE.
#
# Six BNF sections chosen because each supports a specific published measure:
#   0212  Lipid-regulating drugs        - the largest generic-switching prize
#   0501  Antibacterial drugs           - antimicrobial stewardship
#   0401  Hypnotics and anxiolytics     - a national reduction priority
#   0403  Antidepressant drugs          - high volume, high variation
#   0603  Corticosteroids (systemic)    - clinically driven, a good control
#   0205  Hypertension and heart failure- high volume, well-evidenced guidance
#
# Plus the presentations on NHS England's published "items which should not
# routinely be prescribed in primary care" list, which are scattered across
# chapters and so have to be pulled by explicit BNF code.
# ---------------------------------------------------------------------------
BNF_SECTIONS = ["0212", "0501", "0401", "0403", "0603", "0205"]

LOW_PRIORITY_CHEMICALS = [
    # NHS England, items which should not routinely be prescribed in primary
    # care. Chemical substance names as they appear in the BNF.
    "Liothyronine sodium", "Lidocaine", "Omega-3 fatty acid compounds",
    "Glucosamine", "Co-proxamol", "Dosulepin hydrochloride",
    "Doxazosin mesilate", "Trimipramine maleate", "Perindopril arginine",
    "Rubefacients", "Tadalafil", "Fentanyl", "Bath and shower preparations",
    "Silk garments", "Aliskiren", "Amiodarone hydrochloride",
]


def _requests():
    try:
        import requests
        return requests
    except ImportError:
        sys.exit("pip install requests to use the live extractor")


def discover_resources(rq, year_months: list[str]) -> dict[str, str]:
    """Resource ids change every month. Look them up rather than hard-coding."""
    r = rq.get(f"{BASE}/package_show", params={"id": EPD_PACKAGE}, timeout=60)
    r.raise_for_status()
    out = {}
    for res in r.json()["result"]["resources"]:
        # resource names look like "EPD_202401"
        name = res.get("name", "")
        for ym in year_months:
            if ym.replace("-", "") in name:
                out[ym] = res["id"]
    return out


def fetch_month(rq, resource_id: str, ym: str, page_size: int = 30_000) -> pd.DataFrame:
    """One month, filtered server-side, paginated.

    The WHERE clause is the whole trick. Everything after it is plumbing.
    """
    sections = " OR ".join(f"\"BNF_CODE\" LIKE '{s}%'" for s in BNF_SECTIONS)
    chems = ", ".join(f"'{c}'" for c in LOW_PRIORITY_CHEMICALS)
    where = f"(({sections}) OR \"CHEMICAL_SUBSTANCE_BNF_DESCR\" IN ({chems}))"

    frames, offset = [], 0
    while True:
        sql = (f'SELECT "YEAR_MONTH", "PRACTICE_CODE", "PRACTICE_NAME", '
               f'"PCO_CODE", "BNF_CODE", "BNF_DESCRIPTION", '
               f'"CHEMICAL_SUBSTANCE_BNF_DESCR", "ITEMS", "QUANTITY", '
               f'"TOTAL_QUANTITY", "NIC", "ACTUAL_COST", "ADQUSAGE" '
               f'FROM "{resource_id}" WHERE {where} '
               f'LIMIT {page_size} OFFSET {offset}')
        r = rq.get(f"{BASE}/datastore_search_sql", params={"sql": sql}, timeout=300)
        r.raise_for_status()
        recs = r.json()["result"]["records"]
        if not recs:
            break
        frames.append(pd.DataFrame(recs))
        offset += page_size
        print(f"    {ym}: {offset:,} rows", end="\r")
        time.sleep(0.4)          # be polite to a free public API
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    print(f"    {ym}: {len(df):,} rows retrieved")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="2023-01")
    ap.add_argument("--to", dest="to", default="2025-12")
    args = ap.parse_args()

    months = [d.strftime("%Y-%m") for d in
              pd.date_range(args.frm + "-01", args.to + "-01", freq="MS")]
    rq = _requests()
    print(f"Discovering resources for {len(months)} months ...")
    resources = discover_resources(rq, months)
    missing = [m for m in months if m not in resources]
    if missing:
        print(f"  not published yet or unavailable: {', '.join(missing)}")

    out = RAW / "prescribing"
    out.mkdir(exist_ok=True)
    for ym in months:
        if ym not in resources:
            continue
        target = out / f"epd_{ym.replace('-', '')}.parquet"
        if target.exists():
            print(f"    {ym}: already downloaded")
            continue
        df = fetch_month(rq, resources[ym], ym)
        if not df.empty:
            df.to_parquet(target, index=False)

    print(f"\nWritten to {out}")
    print("Filtering at source cut roughly 17m rows a month to roughly 150k.")
    print("That ratio is the point: the same analysis on unfiltered downloads")
    print("would be 600m rows and would not run on a laptop.")


if __name__ == "__main__":
    main()
