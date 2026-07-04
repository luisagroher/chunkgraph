"""Section boundary detection: TOC anchors (preferred), regex fallback, notes."""

import re

from bs4 import BeautifulSoup, Tag

from parser.html_utils import get_text_clean
from parser.models.section import Section
from parser.xref_extractor import SECTION_PATTERNS, NOTE_PATTERN

# Row/block text is only trusted as a TOC-label match up to this length, so we
# don't accidentally match against an entire wrapping container's text.
_TOC_ROW_MAX_LEN = 150

# Filer-agent-rendered "bold" heading style, used as a second regex-fallback
# pass when the real heading text lives in a styled <span>/<div> rather than
# a semantic heading/bold tag (see find_section_elements_via_regex).
_BOLD_STYLE_RE = re.compile(r"font-weight\s*:\s*(?:bold|[7-9]\d\d)", re.IGNORECASE)

# Some TOC layouts split a row into "<item code>" / "<title>" / "<page num>"
# cells and never spell out the word "Item" at all (e.g. a bare "1A" cell).
# Maps the bare code to its section_id so a row's leading token can still be
# recognized even without "item" text.
_ITEM_CODE_TO_SECTION_ID = {
    section_id[len("item_"):]: section_id
    for section_id in SECTION_PATTERNS
    if section_id.startswith("item_")
}

# A bare leading digit ("1", "2", "3", "7", "8"...) is common throughout a
# filing (table row labels, footnote markers, exhibit numbers) — nowhere near
# unique enough to trust on its own. Requiring the row to ALSO contain the
# section's canonical title keyword is what actually makes a TOC row
# identifiable, mirroring how "1A" + "Risk Factors" together (but neither
# alone) means Item 1A.
_ITEM_TITLE_KEYWORDS = {
    "item_1":   r"business",
    "item_1a":  r"risk factors",
    "item_1b":  r"unresolved staff comments",
    "item_2":   r"properties",
    "item_3":   r"legal proceedings",
    "item_7":   r"management.{0,3}s discussion",
    "item_7a":  r"quantitative and qualitative disclosures",
    "item_8":   r"financial statements",
    "item_9a":  r"controls and procedures",
}


def _match_section_id(text: str) -> str | None:
    for section_id, pattern in SECTION_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return section_id
    return None


def _match_row_leading_code(text: str) -> str | None:
    """
    Match a bare item code ("1A") as the row's first whitespace token, but
    only if the row also contains that item's canonical title keyword
    somewhere (e.g. "Risk Factors") — the code alone is too common
    elsewhere in a filing (table cells, footnote markers) to trust alone.
    """
    tokens = text.strip().split(None, 1)
    if not tokens:
        return None
    code = tokens[0].strip(".,").lower()
    section_id = _ITEM_CODE_TO_SECTION_ID.get(code)
    if section_id is None:
        return None
    keyword = _ITEM_TITLE_KEYWORDS.get(section_id)
    if keyword is None or not re.search(keyword, text, re.IGNORECASE):
        return None
    return section_id


def _match_toc_row(text: str) -> str | None:
    return _match_section_id(text) or _match_row_leading_code(text)


def _enclosing_row_text(a_tag: Tag) -> str | None:
    """
    Text of the anchor's enclosing table row (or nearest list/paragraph/div
    ancestor for non-tabular TOCs), for TOC layouts where the item label and
    the page-number hyperlink sit in separate cells and only the page number
    is wrapped in <a>. Returns None if there's no such ancestor, or if its
    text is too long to plausibly be a single TOC entry.
    """
    block = a_tag.find_parent("tr") or a_tag.find_parent(["li", "p", "div"])
    if block is None:
        return None
    text = get_text_clean(block)
    if len(text) > _TOC_ROW_MAX_LEN:
        return None
    return text


def extract_toc_anchors(soup: BeautifulSoup) -> dict[str, str]:
    """
    Extract anchor hrefs from the table of contents.
    Returns dict mapping normalized section_id → anchor id/name.

    10-Ks often have a TOC like:
        <a href="#item1a">Item 1A. Risk Factors</a>
    Following these anchors is the most reliable section boundary signal.

    Some filers instead split the label and the hyperlink across sibling
    table cells (label/title in one <td>, only the page number in another's
    <a>) — when the anchor's own text doesn't match, we fall back to the
    text of its enclosing row/block.
    """
    anchors = {}
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("#"):
            continue
        anchor_id = href.lstrip("#")

        section_id = _match_section_id(get_text_clean(a_tag).lower())
        if section_id is None:
            row_text = _enclosing_row_text(a_tag)
            if row_text is not None:
                section_id = _match_toc_row(row_text.lower())

        if section_id is not None:
            anchors[section_id] = anchor_id
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


def _scan_heading_candidates(candidates, elements: dict[str, Tag]) -> None:
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


def find_section_elements_via_regex(soup: BeautifulSoup) -> dict[str, Tag]:
    """
    Fallback: scan all bold/heading elements for section header patterns.
    Returns dict mapping section_id → BS4 Tag.

    Some filers render headings as a <span>/<div> with an inline bold
    font-weight style rather than a semantic heading/bold tag. That's
    covered by a second, additive pass so it can't change the outcome for
    filings the plain tag-based pass already handles.
    """
    elements = {}
    _scan_heading_candidates(soup.find_all(["h1", "h2", "h3", "h4", "b", "strong", "p"]), elements)

    if len(elements) < len(SECTION_PATTERNS):
        _scan_heading_candidates(soup.find_all(["span", "div"], style=_BOLD_STYLE_RE), elements)

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
