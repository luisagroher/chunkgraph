"""
fetch_10ks.py

Downloads 10-K filings from SEC EDGAR for a target sector.
Uses EDGAR's public JSON APIs — no authentication required.

EDGAR rate limit: max 10 requests/sec. Script stays well under.
Required header: User-Agent identifying yourself (SEC policy).

Usage:
    pip install requests beautifulsoup4 lxml pandas
    python fetch_10ks.py --sector energy --max_companies 30 --year 2023

Output:
    data/raw/10ks/           raw .htm filing files
    data/manifest.csv        index of all downloaded filings
"""

import requests
import time
import json
import csv
import argparse
from pathlib import Path

# ── Required by SEC: identify yourself in User-Agent ──────────────────────────
HEADERS = {
    "User-Agent": "YOUR_NAME your@email.com",   # <-- update this
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/html",
}

EDGAR_BASE = "https://data.sec.gov"
SEC_BASE   = "https://www.sec.gov"

# ── SIC codes by sector ────────────────────────────────────────────────────────
SECTOR_SIC = {
    "energy": ["1311", "1381", "2911", "4911", "4931", "4941", "4991"],
    "utilities": ["4911", "4931", "4941", "4991", "4924", "4922"],
    "industrials": ["3559", "3714", "3312", "3317", "3490"],
    "financials": ["6020", "6021", "6022", "6311", "6321", "6331"],
    "tech": ["7372", "7371", "7374", "3674", "3672"],
}


def get_all_company_tickers() -> dict:
    """
    Fetch the full SEC company ticker list (~10k companies).
    Returns dict keyed by CIK: {cik, name, ticker}.
    This is the cleanest way to get a company universe.
    """
    url = f"{SEC_BASE}/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    raw = resp.json()
    # Rekey by zero-padded CIK string
    return {
        str(v["cik_str"]).zfill(10): {
            "cik": str(v["cik_str"]).zfill(10),
            "name": v["title"],
            "ticker": v["ticker"],
        }
        for v in raw.values()
    }


def get_company_submissions(cik: str) -> dict:
    """Fetch submission history for one company."""
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return {}
    return resp.json()


def get_company_facts(cik: str) -> dict:
    """
    Fetch XBRL company facts (SIC code lives here under entityInfo).
    Used to filter companies by sector.
    """
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return {}
    return resp.json()


def find_companies_by_sector(sector: str, max_companies: int) -> list[dict]:
    """
    Strategy: pull all tickers, then check each company's SIC code
    from their submissions JSON. Filter to target SIC codes.

    This is slower than a direct SIC search but more reliable with EDGAR's API.
    For speed, we stop once we hit max_companies.
    """
    target_sics = set(SECTOR_SIC[sector])
    print(f"Loading company ticker list...")
    tickers = get_all_company_tickers()
    print(f"  {len(tickers)} companies in universe")

    results = []
    checked = 0
    for cik, info in tickers.items():
        if len(results) >= max_companies:
            break
        if checked % 50 == 0:
            print(f"  Checked {checked} companies, found {len(results)} in sector...")

        data = get_company_submissions(cik)
        checked += 1
        time.sleep(0.12)  # stay under 10 req/sec

        sic = str(data.get("sic", ""))
        if sic not in target_sics:
            continue

        results.append({
            "cik": cik,
            "name": data.get("name", info["name"]),
            "ticker": info["ticker"],
            "sic": sic,
            "sic_description": data.get("sicDescription", ""),
        })
        print(f"    ✓ {info['name']} (SIC {sic})")

    return results


def get_10k_accessions(cik: str, year: int) -> list[dict]:
    """
    Return list of 10-K accession metadata filed in `year`.
    Each item: {accession_number, filing_date, primary_document, index_url}
    """
    data = get_company_submissions(cik)
    if not data:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms   = recent.get("form", [])
    dates   = recent.get("filingDate", [])
    accs    = recent.get("accessionNumber", [])
    docs    = recent.get("primaryDocument", [])

    results = []
    for form, date, acc, doc in zip(forms, dates, accs, docs):
        if form not in ("10-K", "10-K/A"):
            continue
        if not date.startswith(str(year)):
            continue

        acc_nodash = acc.replace("-", "")
        cik_int    = int(cik)
        results.append({
            "accession_number": acc,
            "filing_date":      date,
            "primary_document": doc,
            # Direct URL to the primary filing document
            "doc_url": (
                f"{SEC_BASE}/Archives/edgar/data/"
                f"{cik_int}/{acc_nodash}/{doc}"
            ),
            # Filing index page (useful for finding full-submission SGML)
            "index_url": (
                f"{SEC_BASE}/Archives/edgar/data/"
                f"{cik_int}/{acc_nodash}/{acc}-index.htm"
            ),
        })

    return results


def download_filing(url: str, output_path: Path) -> bool:
    """Download raw filing HTML/text to disk."""
    if output_path.exists():
        print(f"    [skip] {output_path.name}")
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=45)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        print(f"    [ok]   {output_path.name} ({len(resp.content)//1024} KB)")
        return True
    except Exception as e:
        print(f"    [err]  {url}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download 10-K filings from EDGAR")
    parser.add_argument("--sector",        default="energy", choices=SECTOR_SIC.keys())
    parser.add_argument("--max_companies", type=int, default=30)
    parser.add_argument("--year",          type=int, default=2023)
    parser.add_argument("--output_dir",    default="./data/raw/10ks")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir.parent.parent).mkdir(parents=True, exist_ok=True)

    print(f"\n=== EDGAR 10-K Downloader ===")
    print(f"Sector: {args.sector} | Year: {args.year} | Target: {args.max_companies} companies\n")

    companies = find_companies_by_sector(args.sector, args.max_companies)
    print(f"\nFound {len(companies)} companies. Fetching 10-K filings for {args.year}...\n")

    manifest = []
    for i, company in enumerate(companies):
        cik  = company["cik"]
        name = company["name"]
        print(f"[{i+1}/{len(companies)}] {name}")

        filings = get_10k_accessions(cik, args.year)
        if not filings:
            print(f"  No 10-K for {args.year}")
            continue

        # Take only the first (most recent) 10-K per company
        filing = filings[0]

        safe_name  = "".join(c if c.isalnum() else "_" for c in name)[:40]
        filename   = f"{safe_name}_{cik}_{filing['filing_date']}.htm"
        out_path   = output_dir / filename

        success = download_filing(filing["doc_url"], out_path)
        time.sleep(0.15)

        if success:
            manifest.append({
                "company_name":     name,
                "ticker":           company["ticker"],
                "cik":              cik,
                "sic":              company["sic"],
                "sic_description":  company["sic_description"],
                "accession_number": filing["accession_number"],
                "filing_date":      filing["filing_date"],
                "year":             args.year,
                "local_file":       str(out_path),
                "source_url":       filing["doc_url"],
                "index_url":        filing["index_url"],
            })

    # Write manifest
    manifest_path = output_dir.parent.parent / "manifest.csv"
    if manifest:
        with open(manifest_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=manifest[0].keys())
            writer.writeheader()
            writer.writerows(manifest)
        print(f"\n✓ Done. {len(manifest)} filings → {output_dir}")
        print(f"  Manifest: {manifest_path}")
    else:
        print("\nNo filings downloaded. Check your User-Agent header and internet connection.")


if __name__ == "__main__":
    main()