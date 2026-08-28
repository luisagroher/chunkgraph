"""Canonical section patterns and explicit cross-reference extraction."""

import re

from parser.models.cross_reference import CrossReference

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
