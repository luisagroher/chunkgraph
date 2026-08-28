"""ParsedFiling — the full result of parsing one 10-K filing."""

from dataclasses import dataclass, field


@dataclass
class ParsedFiling:
    """Everything extracted from a single 10-K .htm filing.

    `sections` maps section_id → Section. `xref_edges` is the flat list of all
    CrossReference objects across every section. `parse_warnings` records
    non-fatal issues (fallback detection used, combined filing, etc.).
    """

    cik:            str
    company_name:   str
    filing_date:    str
    source_file:    str
    sections:       dict = field(default_factory=dict)   # section_id → Section
    xref_edges:     list = field(default_factory=list)   # all CrossReference
    parse_warnings: list = field(default_factory=list)
