"""HTML cleaning helpers shared by section detection and text extraction."""

import re

from bs4 import BeautifulSoup, Tag

# How far forward to scan for next_nonempty_text_element before giving up.
# Some filers nest a section's TOC anchor deep inside a local sub-index
# (e.g. Item 7's own "Overview" / "Results of Operations" sub-TOC before
# Item 7A's real heading), so this needs to be generous; the predicate-based
# pattern match keeps a wide scan from picking up the wrong text.
_FORWARD_SCAN_LIMIT = 200


def clean_html(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove tags that carry no text content."""
    for tag in soup(["script", "style", "meta", "link", "ix:header"]):
        tag.decompose()
    # Remove XBRL inline tags but keep their text
    for tag in soup.find_all(re.compile(r"^ix:")):
        tag.unwrap()
    return soup


def get_text_clean(element) -> str:
    """Extract clean text from a BS4 element."""
    text = element.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def next_nonempty_text_element(el: Tag, matches=None) -> Tag | None:
    """
    Scan forward in document order for the first element with non-empty
    visible text. Some TOC anchors resolve to an empty placeholder element
    (e.g. `<div id="...">` ) sitting just before the real heading, whose
    own text would otherwise be blank.

    `matches`, if given, is a predicate over the candidate's clean text —
    used by callers that know what the real heading should look like (so a
    page's repeated "Table of Contents" nav text isn't mistaken for it).
    Returns None if nothing is found within the scan limit.
    """
    for count, candidate in enumerate(el.find_all_next(True)):
        if count >= _FORWARD_SCAN_LIMIT:
            break
        text = get_text_clean(candidate)
        if not text:
            continue
        if matches is None or matches(text):
            return candidate
    return None
