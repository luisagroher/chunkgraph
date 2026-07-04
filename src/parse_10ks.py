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

import json
import csv
import argparse
from pathlib import Path
from dataclasses import asdict

from bs4 import BeautifulSoup

from parser.models import Section, ParsedFiling
from parser.html_utils import clean_html
from parser.section_detector import (
    extract_toc_anchors,
    find_section_elements_via_anchors,
    find_section_elements_via_regex,
    extract_section_text,
    extract_notes,
    resolve_title,
)
from parser.xref_extractor import SECTION_PATTERNS, extract_xrefs_from_text


# ── Main parse function ────────────────────────────────────────────────────────

def parse_filing(
    filepath:     Path,
    cik:          str  = "",
    company_name: str  = "",
    filing_date:  str  = "",
) -> ParsedFiling:
    """
    Parse a single 10-K HTML filing.
    Returns a ParsedFiling dataclass.
    """
    filing = ParsedFiling(
        cik          = cik,
        company_name = company_name,
        filing_date  = filing_date,
        source_file  = str(filepath),
    )

    raw_html = filepath.read_bytes()
    soup     = BeautifulSoup(raw_html, "lxml")
    soup     = clean_html(soup)

    # ── Section boundary detection ─────────────────────────────────────────────
    toc_anchors = extract_toc_anchors(soup)
    if toc_anchors:
        section_elements = find_section_elements_via_anchors(soup, toc_anchors)
        filing.parse_warnings.append(f"Section detection: TOC anchors ({len(section_elements)} found)")
    else:
        section_elements = find_section_elements_via_regex(soup)
        filing.parse_warnings.append(f"Section detection: regex fallback ({len(section_elements)} found)")

    # ── Extract section text ───────────────────────────────────────────────────
    section_ids = list(SECTION_PATTERNS.keys())
    found_ids   = [sid for sid in section_ids if sid in section_elements]

    for i, section_id in enumerate(found_ids):
        start_el = section_elements[section_id]
        # End at the next found section
        next_id  = found_ids[i + 1] if i + 1 < len(found_ids) else None
        end_el   = section_elements[next_id] if next_id else None

        text  = extract_section_text(start_el, end_el)
        title = resolve_title(start_el, section_id)

        filing.sections[section_id] = Section(
            section_id = section_id,
            title      = title,
            text       = text,
            char_count = len(text),
        )

    # ── Extract notes ──────────────────────────────────────────────────────────
    notes = extract_notes(soup)
    filing.sections.update(notes)

    if not notes:
        filing.parse_warnings.append("No notes to financial statements detected")

    # ── Extract cross-references ───────────────────────────────────────────────
    for section_id, section in filing.sections.items():
        xrefs = extract_xrefs_from_text(section.text, section_id)
        section.xrefs = [asdict(x) for x in xrefs]
        filing.xref_edges.extend(xrefs)

    return filing


# ── Serialization ──────────────────────────────────────────────────────────────

def filing_to_dict(filing: ParsedFiling) -> dict:
    """Convert ParsedFiling to a JSON-serializable dict."""
    return {
        "cik":            filing.cik,
        "company_name":   filing.company_name,
        "filing_date":    filing.filing_date,
        "source_file":    filing.source_file,
        "parse_warnings": filing.parse_warnings,
        "section_count":  len(filing.sections),
        "xref_count":     len(filing.xref_edges),
        "sections": {
            sid: {
                "section_id": s.section_id,
                "title":      s.title,
                "char_count": s.char_count,
                "xrefs":      s.xrefs,
                "text":       s.text,
            }
            for sid, s in filing.sections.items()
        },
        "xref_edges": [asdict(x) for x in filing.xref_edges],
    }


def save_parsed_filing(filing: ParsedFiling, output_dir: Path) -> Path:
    """Write parsed filing to JSON. Returns output path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename    = f"{filing.cik}_{filing.filing_date}.json"
    output_path = output_dir / filename
    with open(output_path, "w") as f:
        json.dump(filing_to_dict(filing), f, indent=2)
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────

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
        print(f"Parsing: {filepath.name}")
        filing   = parse_filing(filepath)
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
