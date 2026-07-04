"""
parse_10k.py

Parses a single 10-K HTML filing into sections and extracts
cross-references between sections to build a chunk dependency graph.

Strategy:
    1. Strip HTML boilerplate, extract clean text per section
    2. Detect section boundaries via TOC anchor links (preferred)
       with fallback to regex on bold/caps text patterns
    3. Extract cross-references within each section
    4. Output a structured JSON file per filing

Usage:
    python parse_10k.py --input data/raw/10ks/COMPANY_CIK_DATE.htm
    python parse_10k.py --manifest data/manifest.csv  # batch mode

Output:
    data/processed/parsed/{cik}_{date}.json
"""

import csv
import argparse
from pathlib import Path

from parser.pipeline import parse_filing, save_parsed_filing
from parser.single_file_functions import update_cik_for_filing, update_filing_date_for_filing, update_company_name_for_filing


def main():
    parser = argparse.ArgumentParser(description="Parse 10-K filings into sections and cross-references")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input",    help="Single .htm filing to parse")
    group.add_argument("--manifest", help="manifest.csv for batch mode")
    parser.add_argument("--output_dir", default="./data/processed/parsed")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.input:
        # ── Single file mode ───────────────────────────────────────────────────
        filepath = Path(args.input)
        # print(f"Parsing: {filepath.name}\n")
        filing   = parse_filing(filepath)
        filing   = update_cik_for_filing(filepath, filing)
        filing   = update_filing_date_for_filing(filepath, filing)
        filing   = update_company_name_for_filing(filepath, filing)
        out_path = save_parsed_filing(filing, output_dir)
        print(f"  Sections:  {len(filing.sections)}")
        print(f"  Xrefs:     {len(filing.xref_edges)}")
        print(f"  Warnings:  {filing.parse_warnings}")
        print(f"  Output:    {out_path}")

    else:
        # ── Batch mode ─────────────────────────────────────────────────────────
        manifest_path = Path(args.manifest)
        with open(manifest_path) as f:
            rows = list(csv.DictReader(f))

        print(f"Batch parsing {len(rows)} filings...\n")
        success, failed = 0, 0

        for i, row in enumerate(rows):
            filepath = Path(row["local_file"])
            if not filepath.exists():
                print(f"[{i+1}/{len(rows)}] MISSING: {filepath}")
                failed += 1
                continue

            print(f"[{i+1}/{len(rows)}] {row['company_name']}")
            try:
                filing = parse_filing(
                    filepath,
                    cik          = row.get("cik", ""),
                    company_name = row.get("company_name", ""),
                    filing_date  = row.get("filing_date", ""),
                )
                out_path = save_parsed_filing(filing, output_dir)
                print(f"  sections={len(filing.sections)} xrefs={len(filing.xref_edges)} → {out_path.name}")
                success += 1
            except Exception as e:
                print(f"  [error] {e}")
                failed += 1

        print(f"\n✓ Done. {success} parsed, {failed} failed → {output_dir}")


if __name__ == "__main__":
    main()
