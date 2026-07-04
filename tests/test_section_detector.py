"""ZOMBIES tests for TOC-anchor and regex-fallback section detection."""

from pathlib import Path

from bs4 import BeautifulSoup

from parser.html_utils import clean_html
from parser.section_detector import (
    extract_toc_anchors,
    extract_section_text,
    find_section_elements_via_anchors,
    find_section_elements_via_regex,
    resolve_title,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_zero_extract_toc_anchors_no_anchors_found():
    # Zero: a document with no hyperlinks yields no anchors.
    soup = _soup("<html><body><p>Item 1A. Risk Factors</p></body></html>")
    assert extract_toc_anchors(soup) == {}


def test_one_extract_toc_anchors_label_inside_anchor_tag():
    # One / regression guard: label inside the <a> itself still matches
    # directly (the layout that already worked before this fix).
    soup = _soup('<html><body><a href="#x">Item&#160;1A</a></body></html>')
    assert extract_toc_anchors(soup) == {"item_1a": "x"}


def test_exception_extract_toc_anchors_label_in_sibling_td_uses_tr_text():
    # Exception case (bug 1): label and title sit in sibling <td> cells and
    # only a bare page number is wrapped in <a> — must fall back to the
    # enclosing row's text.
    soup = _soup(
        """
        <html><body><table><tr>
            <td><span>1A</span></td>
            <td><span>Risk Factors</span></td>
            <td><a href="#i8af612e789af49f28932152c327dbde7_58">32</a></td>
        </tr></table></body></html>
        """
    )
    assert extract_toc_anchors(soup) == {"item_1a": "i8af612e789af49f28932152c327dbde7_58"}


def test_boundary_extract_toc_anchors_ignores_oversized_row_text():
    # Boundary: if the enclosing block's text is too long to be a plausible
    # TOC row, it must not be treated as a match.
    long_text = "Risk Factors " + ("filler " * 40)
    soup = _soup(f'<html><body><div>{long_text}<a href="#x">32</a></div></body></html>')
    assert extract_toc_anchors(soup) == {}


def test_exception_extract_toc_anchors_ignores_bare_digit_without_title_keyword():
    # Exception: a bare leading digit ("7") is common throughout a filing
    # (table row labels, footnote markers) and must NOT be mistaken for
    # Item 7 unless the row also carries the canonical title keyword.
    soup = _soup(
        """
        <html><body><table><tr>
            <td>7</td>
            <td>Total assets</td>
            <td><a href="#x">32</a></td>
        </tr></table></body></html>
        """
    )
    assert extract_toc_anchors(soup) == {}


def test_many_find_section_elements_via_regex_matches_bold_span_in_div():
    # Many (bug 2): heading text lives in a bold-styled <span> inside a
    # plain <div>, invisible to the original h1-h4/b/strong/p candidate list.
    soup = _soup(
        """
        <html><body>
            <div><span style="font-weight:700">ITEM 1A.&#160;&#160;&#160;RISK FACTORS</span></div>
            <div><span style="font-weight:700">ITEM 2.&#160;&#160;&#160;PROPERTIES</span></div>
        </body></html>
        """
    )
    elements = find_section_elements_via_regex(soup)
    assert set(elements) == {"item_1a", "item_2"}


def test_boundary_find_section_elements_via_regex_ignores_incidental_body_text():
    # Boundary: an ordinary, non-bold, short paragraph that happens to
    # mention "Item 7" mid-sentence must not be mistaken for a heading by
    # the new bold-style pass (it has no font-weight style at all).
    soup = _soup("<html><body><div><span>as discussed in Item 7 above</span></div></body></html>")
    assert find_section_elements_via_regex(soup) == {}


def test_one_resolve_title_reads_start_element_directly():
    # One: the regex-fallback path's start_el already IS the heading.
    soup = _soup("<html><body><p>Item 1A. Risk Factors</p></body></html>")
    assert resolve_title(soup.p, "item_1a") == "Item 1A. Risk Factors"


def test_exception_resolve_title_scans_forward_past_empty_anchor_div():
    # Exception (bug 3): the TOC anchor resolves to an empty placeholder
    # div sitting just before the real heading.
    soup = _soup(
        '<html><body><div id="x"></div><hr/>'
        '<div><span style="font-weight:700">ITEM 1A. RISK FACTORS</span></div>'
        "</body></html>"
    )
    start_el = soup.find(id="x")
    assert resolve_title(start_el, "item_1a") == "ITEM 1A. RISK FACTORS"


def test_exception_resolve_title_skips_boilerplate_nav_text_between_anchor_and_heading():
    # Exception (bug 3 regression guard): a repeated "Table of Contents"
    # nav link sits between the empty anchor and the real heading — must
    # not be mistaken for the title just because it's the first non-empty
    # text found.
    soup = _soup(
        '<html><body><div id="x"></div>'
        '<div>Table of Contents Index to Financial Statements</div>'
        '<div><span style="font-weight:700">ITEM 1A. RISK FACTORS</span></div>'
        "</body></html>"
    )
    start_el = soup.find(id="x")
    assert resolve_title(start_el, "item_1a") == "ITEM 1A. RISK FACTORS"


def test_boundary_resolve_title_returns_empty_string_when_nothing_follows():
    # Boundary: no non-empty text anywhere after start_el.
    soup = _soup('<html><body><div id="x"></div></body></html>')
    assert resolve_title(soup.find(id="x"), "item_1a") == ""


def test_one_extract_section_text_reads_a_direct_sibling_paragraph():
    # One: the simple case, a single sibling paragraph.
    soup = _soup('<html><body><div id="start"></div><p>Body text.</p></body></html>')
    start_el = soup.find(id="start")
    assert extract_section_text(start_el, None) == "Body text."


def test_exception_extract_section_text_survives_nested_wrapper_div():
    # Exception (bug 4): a later paragraph is wrapped in extra <div>s, so it
    # has no direct-sibling relationship to start_el. Sibling-walking would
    # stop as soon as start_el's own wrapper ends, truncating this text.
    soup = _soup(
        """
        <html><body>
            <div id="start"></div>
            <p>First paragraph.</p>
            <div><div><p>Second paragraph, nested two levels deep.</p></div></div>
        </body></html>
        """
    )
    start_el = soup.find(id="start")
    text = extract_section_text(start_el, None)
    assert "First paragraph." in text
    assert "Second paragraph, nested two levels deep." in text


def test_boundary_extract_section_text_stops_at_end_el():
    # Boundary: text extraction stops at end_el, not past it.
    soup = _soup(
        '<html><body><div id="start"></div><p>Included.</p>'
        '<div id="end"></div><p>Not included.</p></body></html>'
    )
    start_el = soup.find(id="start")
    end_el = soup.find(id="end")
    text = extract_section_text(start_el, end_el)
    assert "Included." in text
    assert "Not included." not in text


def test_zero_extract_section_text_no_content_between_boundaries():
    # Zero: start_el immediately followed by end_el yields empty text.
    soup = _soup('<html><body><div id="start"></div><div id="end"></div></body></html>')
    start_el = soup.find(id="start")
    end_el = soup.find(id="end")
    assert extract_section_text(start_el, end_el) == ""


def test_many_extract_section_text_does_not_double_count_inline_tags():
    # Many: a paragraph with an inline <a> cross-reference must contribute
    # its surrounding text exactly once, not duplicated by both the <p>
    # and its <a> child contributing the same substring.
    soup = _soup(
        '<html><body><div id="start"></div>'
        "<p>See <a href=\"#note7\">Note 7</a> for details.</p>"
        "</body></html>"
    )
    start_el = soup.find(id="start")
    text = extract_section_text(start_el, None)
    assert text == "See Note 7 for details."


def test_interface_parses_real_aep_toc_fragment_end_to_end():
    # Interface: a trimmed real fragment (split-cell TOC, empty anchor
    # placeholder, inline <a> inside a paragraph) run through the whole
    # anchor -> title -> text pipeline together, not just each fix in
    # isolation. This is the actual filing (AEP) that used to parse to
    # zero sections before these fixes.
    raw = (FIXTURES / "aep_toc_and_item1a.htm").read_bytes()
    soup = clean_html(BeautifulSoup(raw, "lxml"))

    anchors = extract_toc_anchors(soup)
    assert anchors["item_1a"] == "i8af612e789af49f28932152c327dbde7_58"
    assert anchors["item_1b"] == "i8af612e789af49f28932152c327dbde7_61"

    elements = find_section_elements_via_anchors(soup, anchors)
    title = resolve_title(elements["item_1a"], "item_1a")
    text = extract_section_text(elements["item_1a"], elements["item_1b"])

    assert title == "ITEM 1A. RISK FACTORS"
    assert "GENERAL RISKS OF REGULATED OPERATIONS" in text
    assert "see Note 6 for details" in text
    assert "UNRESOLVED STAFF COMMENTS" not in text  # stops at item_1b
