"""Section — one extracted section of a 10-K (an Item or a Note)."""

from dataclasses import dataclass, field


@dataclass
class Section:
    """A contiguous section of a filing, with its extracted text and xrefs.

    `xrefs` holds CrossReference objects (or their dict form after
    serialization); it is populated by the cross-reference extractor.
    """

    section_id: str               # normalized id, e.g. "item_1a" / "note_7"
    title:      str               # heading text as it appears in the document
    text:       str               # cleaned, whitespace-collapsed body text
    char_count: int  = 0
    xrefs:      list = field(default_factory=list)

    @classmethod
    def from_text(cls, section_id: str, title: str, text: str) -> "Section":
        """Build a Section, deriving char_count from the text."""
        return cls(
            section_id=section_id,
            title=title,
            text=text,
            char_count=len(text),
        )
