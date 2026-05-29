"""ZOMBIES tests for the Section model."""

from dataclasses import asdict

from parser.models.cross_reference import CrossReference
from parser.models.section import Section


def test_zero_default_xrefs_and_count():
    # Zero: a freshly-constructed section has no xrefs and explicit char_count.
    s = Section(section_id="item_1", title="Item 1. Business", text="", char_count=0)
    assert s.xrefs == []
    assert s.char_count == 0


def test_boundary_empty_text_has_zero_char_count_via_factory():
    # Boundary: from_text on empty text yields char_count 0.
    s = Section.from_text("item_1b", "Item 1B.", "")
    assert s.char_count == 0


def test_one_from_text_sets_char_count():
    # One: from_text derives char_count from the text length.
    s = Section.from_text("item_1a", "Item 1A. Risk Factors", "abcde")
    assert s.char_count == 5
    assert s.text == "abcde"


def test_many_xrefs_attach_to_section():
    # Many: a section can hold multiple cross-references.
    s = Section.from_text("item_7", "Item 7. MD&A", "see Note 3 and Note 4")
    s.xrefs = [
        asdict(CrossReference("item_7", "Note 3", "note_3", "...")),
        asdict(CrossReference("item_7", "Note 4", "note_4", "...")),
    ]
    assert len(s.xrefs) == 2
    assert s.xrefs[0]["target_section"] == "note_3"


def test_default_factory_isolates_xrefs_between_instances():
    # Default factory must not share the same list across instances.
    a = Section.from_text("item_1", "t", "x")
    b = Section.from_text("item_2", "t", "y")
    a.xrefs.append("edge")
    assert b.xrefs == []
