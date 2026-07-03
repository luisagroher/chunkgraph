"""CrossReference — one explicit reference from one section to another."""

from dataclasses import dataclass


@dataclass
class CrossReference:
    """A single cross-reference edge found inside a section's text.

    e.g. the sentence "See Note 7 to the consolidated financial statements"
    appearing in Item 7 yields:
        source_section = "item_7"
        target_raw     = "See Note 7"
        target_section = "note_7"
        context        = "<surrounding sentence>"
    """

    source_section: str   # section_id where the reference appears
    target_raw:     str   # raw matched substring, e.g. "see Note 7"
    target_section: str   # normalized target id, e.g. "note_7"
    context:        str    # surrounding sentence, for human inspection
