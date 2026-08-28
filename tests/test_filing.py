"""ZOMBIES tests for the ParsedFiling model."""

from parser.models.filing import ParsedFiling
from parser.models.section import Section


def test_zero_empty_filing_has_empty_collections():
    # Zero: no sections, edges, or warnings by default.
    f = ParsedFiling(cik="0000821189", company_name="EOG", filing_date="2023-02-23", source_file="x.htm")
    assert f.sections == {}
    assert f.xref_edges == []
    assert f.parse_warnings == []


def test_one_section_keyed_by_id():
    # One: a single section is stored under its section_id.
    f = ParsedFiling(cik="c", company_name="n", filing_date="d", source_file="s")
    f.sections["item_1"] = Section.from_text("item_1", "Item 1. Business", "body")
    assert list(f.sections) == ["item_1"]
    assert f.sections["item_1"].char_count == 4


def test_many_sections_and_warnings():
    # Many: filing holds many sections, edges, and warnings.
    f = ParsedFiling(cik="c", company_name="n", filing_date="d", source_file="s")
    for sid in ("item_1", "item_1a", "item_7"):
        f.sections[sid] = Section.from_text(sid, sid, "t")
    f.parse_warnings.append("Section detection: regex fallback")
    assert len(f.sections) == 3
    assert f.parse_warnings


def test_default_factories_isolate_instances():
    # Default factories must not be shared across instances.
    a = ParsedFiling(cik="a", company_name="n", filing_date="d", source_file="s")
    b = ParsedFiling(cik="b", company_name="n", filing_date="d", source_file="s")
    a.parse_warnings.append("w")
    a.sections["item_1"] = Section.from_text("item_1", "t", "x")
    assert b.parse_warnings == []
    assert b.sections == {}
