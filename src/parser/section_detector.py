"""Section boundary detection: TOC anchors (preferred), regex fallback, notes."""

import re

from bs4 import BeautifulSoup, Tag

from parser.html_utils import get_text_clean
from parser.models.section import Section
from parser.xref_extractor import SECTION_PATTERNS, NOTE_PATTERN


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
