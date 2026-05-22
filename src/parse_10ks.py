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

import re
import json
import csv
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict

from bs4 import BeautifulSoup, Tag


# ── Section definitions ────────────────────────────────────────────────────────

# Canonical 10-K sections we care about, in order.
# Keys are normalized identifiers; values are regex patterns to match headings.
SECTION_PATTERNS = {
    "item_1":    r"item\s*1(?!\w|a|b)\b",            # Business
    "item_1a":   r"item\s*1a\b",                      # Risk Factors
    "item_1b":   r"item\s*1b\b",                      # Unresolved Staff Comments
    "item_2":    r"item\s*2\b",                        # Properties
    "item_3":    r"item\s*3\b",                        # Legal Proceedings
    "item_7":    r"item\s*7(?!\w|a)\b",               # MD&A
    "item_7a":   r"item\s*7a\b",                      # Quantitative Disclosures
    "item_8":    r"item\s*8\b",                        # Financial Statements
    "item_9a":   r"item\s*9a\b",                      # Controls and Procedures
}

# Notes to financial statements get their own pattern
NOTE_PATTERN = re.compile(
    r"note\s*(\d+)\s*[—\-–]?\s*(.{0,60})",
    re.IGNORECASE,
)

# ── Cross-reference patterns ───────────────────────────────────────────────────

XREF_PATTERNS = [
    # "see Note 7", "see Notes 3 and 4"
    re.compile(r"see\s+notes?\s*(\d+(?:\s*(?:and|,)\s*\d+)*)", re.IGNORECASE),
    # "see Item 1A", "see Item 7"
    re.compile(r"see\s+item\s*(\d+[a-z]?)", re.IGNORECASE),
    # "as described in Note 3", "as discussed in Item 7"
    re.compile(r"(?:as\s+(?:described|discussed|noted|defined)\s+in)\s+(?:note|item|section)\s*(\d+[a-z]?)", re.IGNORECASE),
    # "refer to Note 5", "refer to Item 1A"
    re.compile(r"refer\s+to\s+(?:note|item|section)\s*(\d+[a-z]?)", re.IGNORECASE),
    # "described in Note 7 to the consolidated financial statements"
    re.compile(r"in\s+note\s*(\d+)\s+to\s+the", re.IGNORECASE),
]


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class CrossReference:
    source_section: str          # section where reference appears
    target_raw:     str          # raw matched string e.g. "Note 7"
    target_section: str          # normalized target e.g. "note_7"
    context:        str          # surrounding sentence for context


@dataclass
class Section:
    section_id:      str
    title:           str
    text:            str
    char_count:      int         = 0
    xrefs:           list        = field(default_factory=list)


@dataclass
class ParsedFiling:
    cik:             str
    company_name:    str
    filing_date:     str
    source_file:     str
    sections:        dict        = field(default_factory=dict)   # section_id → Section
    xref_edges:      list        = field(default_factory=list)   # all CrossReference objects
    parse_warnings:  list        = field(default_factory=list)


# ── HTML cleaning ──────────────────────────────────────────────────────────────

def clean_html(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove tags that carry no text content."""
    for tag in soup(["script", "style", "meta", "link", "ix:header"]):
        tag.decompose()
    # Remove XBRL inline tags but keep their text
    for tag in soup.find_all(re.compile(r"^ix:")):
        tag.unwrap()
    return soup


def get_text_clean(element) -> str:
    """Extract clean text from a BS4 element."""
    text = element.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Section boundary detection ─────────────────────────────────────────────────

def extract_toc_anchors(soup: BeautifulSoup) -> dict[str, str]:
    """
    Extract anchor hrefs from the table of contents.
    Returns dict mapping normalized section_id → anchor id/name.

    10-Ks often have a TOC like:
        <a href="#item1a">Item 1A. Risk Factors</a>
    Following these anchors is the most reliable section boundary signal.
    """
    anchors = {}
    for a_tag in soup.find_all("a", href=True):
        href  = a_tag["href"]
        text  = get_text_clean(a_tag).lower()
        if not href.startswith("#"):
            continue
        anchor_id = href.lstrip("#")
        for section_id, pattern in SECTION_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                anchors[section_id] = anchor_id
                break
    return anchors


def find_section_elements_via_anchors(
    soup: BeautifulSoup,
    toc_anchors: dict[str, str],
) -> dict[str, Tag]:
    """
    Given TOC anchor ids, find the corresponding elements in the document.
    Returns dict mapping section_id → BS4 Tag where that section starts.
    """
    elements = {}
    for section_id, anchor_id in toc_anchors.items():
        # Try id= attribute first, then name=
        el = soup.find(id=anchor_id) or soup.find(attrs={"name": anchor_id})
        if el:
            elements[section_id] = el
    return elements


def find_section_elements_via_regex(soup: BeautifulSoup) -> dict[str, Tag]:
    """
    Fallback: scan all bold/heading elements for section header patterns.
    Returns dict mapping section_id → BS4 Tag.
    """
    elements   = {}
    candidates = soup.find_all(["h1", "h2", "h3", "h4", "b", "strong", "p"])

    for el in candidates:
        text = get_text_clean(el).lower()
        if len(text) > 120:
            continue                          # too long to be a heading
        for section_id, pattern in SECTION_PATTERNS.items():
            if section_id in elements:
                continue                      # already found
            if re.search(pattern, text, re.IGNORECASE):
                elements[section_id] = el
                break

    return elements


def extract_section_text(
    start_el: Tag,
    end_el:   Tag | None,
) -> str:
    """
    Extract text between start_el and end_el by walking siblings.
    If end_el is None, collect until end of document.
    """
    texts  = []
    el     = start_el.next_sibling

    while el is not None:
        if end_el and el == end_el:
            break
        if isinstance(el, Tag):
            texts.append(get_text_clean(el))
        el = el.next_sibling

    return " ".join(t for t in texts if t)


# ── Note extraction ────────────────────────────────────────────────────────────

def extract_notes(soup: BeautifulSoup) -> dict[str, Section]:
    """
    Extract individual notes to financial statements as separate sections.
    Notes are identified by "NOTE X — Title" heading patterns.
    Returns dict mapping "note_N" → Section.
    """
    notes    = {}
    headings = soup.find_all(["h1", "h2", "h3", "h4", "b", "strong", "p"])

    note_elements = []
    for el in headings:
        text  = get_text_clean(el)
        match = NOTE_PATTERN.match(text)
        if match:
            note_num   = match.group(1)
            note_title = match.group(2).strip(" —-")
            note_elements.append((note_num, note_title, el))

    for i, (note_num, note_title, el) in enumerate(note_elements):
        next_el = note_elements[i + 1][2] if i + 1 < len(note_elements) else None
        text    = extract_section_text(el, next_el)
        note_id = f"note_{note_num}"
        notes[note_id] = Section(
            section_id = note_id,
            title      = f"Note {note_num} — {note_title}",
            text       = text,
            char_count = len(text),
        )

    return notes


# ── Cross-reference extraction ─────────────────────────────────────────────────

def normalize_target(raw: str) -> str:
    """
    Normalize a cross-reference target string to a section_id.
    e.g. "Note 7" → "note_7", "Item 1A" → "item_1a"
    """
    raw   = raw.strip().lower()
    match = re.match(r"(note|item|section)\s*(\d+[a-z]?)", raw)
    if not match:
        return raw.replace(" ", "_")
    kind = match.group(1)
    num  = match.group(2).replace(" ", "")
    return f"{kind}_{num}"


def extract_xrefs_from_text(text: str, source_section: str) -> list[CrossReference]:
    """
    Find all cross-references in a block of text.
    Returns list of CrossReference objects.
    """
    xrefs     = []
    sentences = re.split(r"(?<=[.;])\s+", text)

    for sentence in sentences:
        for pattern in XREF_PATTERNS:
            for match in pattern.finditer(sentence):
                raw_target    = match.group(0)
                target_num    = match.group(1)
                # Reconstruct normalized target from context
                kind_match    = re.search(r"(note|item|section)", raw_target, re.IGNORECASE)
                kind          = kind_match.group(1).lower() if kind_match else "note"
                target_section = normalize_target(f"{kind} {target_num}")

                xrefs.append(CrossReference(
                    source_section = source_section,
                    target_raw     = raw_target,
                    target_section = target_section,
                    context        = sentence[:200],
                ))

    return xrefs


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
        title = get_text_clean(start_el)

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
