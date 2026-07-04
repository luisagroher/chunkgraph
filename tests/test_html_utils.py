"""ZOMBIES tests for HTML cleaning helpers."""

from bs4 import BeautifulSoup

from parser.html_utils import clean_html, get_text_clean, next_nonempty_text_element


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_zero_clean_html_on_empty_soup():
    # Zero: an empty document survives cleaning without error.
    soup = _soup("<html><body></body></html>")
    assert clean_html(soup).get_text() == ""


def test_one_get_text_clean_collapses_whitespace():
    # One: whitespace inside a single element is collapsed to single spaces.
    soup = _soup("<div>  Item   1A.\n\nRisk   Factors  </div>")
    assert get_text_clean(soup.div) == "Item 1A. Risk Factors"


def test_many_next_nonempty_text_element_skips_multiple_empty_divs():
    # Many: skips several empty wrapper elements before finding real text.
    soup = _soup(
        '<html><body><div id="x"></div><div></div>'
        '<div><span style="font-weight:700">ITEM 1A. RISK FACTORS</span></div>'
        "</body></html>"
    )
    anchor = soup.find(id="x")
    found = next_nonempty_text_element(anchor)
    assert found is not None
    assert get_text_clean(found) == "ITEM 1A. RISK FACTORS"


def test_boundary_next_nonempty_text_element_returns_none_at_document_end():
    # Boundary: no non-empty text anywhere after the element.
    soup = _soup('<html><body><div id="x"></div><div></div></body></html>')
    anchor = soup.find(id="x")
    assert next_nonempty_text_element(anchor) is None


def test_interface_next_nonempty_text_element_honors_matches_predicate():
    # Interface: an optional predicate skips non-empty text that isn't
    # what the caller is looking for.
    soup = _soup(
        '<html><body><div id="x"></div>'
        "<div>skip me</div><div>Item 1A. Risk Factors</div>"
        "</body></html>"
    )
    anchor = soup.find(id="x")
    found = next_nonempty_text_element(anchor, matches=lambda t: t.startswith("Item"))
    assert found is not None
    assert get_text_clean(found) == "Item 1A. Risk Factors"
