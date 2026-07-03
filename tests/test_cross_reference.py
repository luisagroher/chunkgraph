"""ZOMBIES tests for the CrossReference model."""

from dataclasses import asdict

from parser.models.cross_reference import CrossReference


def test_zero_empty_strings_allowed():
    # Zero: a reference can hold empty fields without error.
    xref = CrossReference(source_section="", target_raw="", target_section="", context="")
    assert xref.source_section == ""
    assert xref.target_section == ""


def test_one_fields_populated():
    # One: a fully-populated reference keeps its values.
    xref = CrossReference(
        source_section="item_7",
        target_raw="see Note 7",
        target_section="note_7",
        context="See Note 7 to the consolidated financial statements.",
    )
    assert xref.source_section == "item_7"
    assert xref.target_raw == "see Note 7"
    assert xref.target_section == "note_7"
    assert "consolidated" in xref.context


def test_simple_round_trips_through_asdict():
    # Simple/Interface: serializes cleanly to a dict for JSON output.
    xref = CrossReference("item_1a", "refer to Item 7", "item_7", "...refer to Item 7...")
    d = asdict(xref)
    assert d == {
        "source_section": "item_1a",
        "target_raw": "refer to Item 7",
        "target_section": "item_7",
        "context": "...refer to Item 7...",
    }
    assert CrossReference(**d) == xref
