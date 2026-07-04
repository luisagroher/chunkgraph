"""ZOMBIES tests for the parse_filing/filing_to_dict/save_parsed_filing pipeline."""

import json
from pathlib import Path

from parser.models.filing import ParsedFiling
from parser.pipeline import filing_to_dict, parse_filing, save_parsed_filing

FIXTURES = Path(__file__).parent / "fixtures"


def test_zero_filing_to_dict_on_empty_filing():
    # Zero: an empty filing serializes to zero counts and empty collections.
    filing = ParsedFiling(cik="c", company_name="n", filing_date="d", source_file="s")
    d = filing_to_dict(filing)
    assert d["section_count"] == 0
    assert d["xref_count"] == 0
    assert d["sections"] == {}
    assert d["xref_edges"] == []


def test_one_parse_filing_finds_sections_and_titles_for_real_fixture():
    # One / interface: parse_filing end to end on a real trimmed fixture --
    # the AEP filing that used to parse to zero sections.
    filing = parse_filing(FIXTURES / "aep_toc_and_item1a.htm", cik="0000004904", filing_date="2023-02-23")
    assert "item_1a" in filing.sections
    assert filing.sections["item_1a"].title == "ITEM 1A. RISK FACTORS"
    assert "GENERAL RISKS OF REGULATED OPERATIONS" in filing.sections["item_1a"].text
    assert any("TOC anchors" in w for w in filing.parse_warnings)


def test_many_parse_filing_extracts_cross_references_from_body_text():
    # Many: the fixture's Item 1A body text contains a "see Note 6" xref.
    filing = parse_filing(FIXTURES / "aep_toc_and_item1a.htm", cik="0000004904", filing_date="2023-02-23")
    targets = {x.target_section for x in filing.xref_edges}
    assert "note_6" in targets


def test_interface_save_parsed_filing_writes_json_file(tmp_path):
    # Interface: save_parsed_filing writes a well-formed JSON file named
    # after the filing's cik/filing_date.
    filing = parse_filing(FIXTURES / "aep_toc_and_item1a.htm", cik="0000004904", filing_date="2023-02-23")
    out_path = save_parsed_filing(filing, tmp_path)
    assert out_path == tmp_path / "0000004904_2023-02-23.json"
    with open(out_path) as f:
        data = json.load(f)
    assert data["cik"] == "0000004904"
    assert data["section_count"] == len(filing.sections)
