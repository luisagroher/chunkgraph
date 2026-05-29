"""ZOMBIES tests for the fidelity_compare module."""

from parser.fidelity_compare import compare_section_text


def test_zero_both_empty_strings():
    # Zero: nothing to compare on either side -- no ZeroDivisionError, ratio 1.0.
    result = compare_section_text("", "")
    assert result["length_ratio"] == 1.0
    assert result["char_overlap_ratio"] == 1.0


def test_one_identical_strings_have_ratio_one():
    # One: identical text on both sides is a perfect match.
    text   = "See Note 7 for additional information."
    result = compare_section_text(text, text)
    assert result["length_ratio"] == 1.0
    assert result["char_overlap_ratio"] == 1.0


def test_many_partial_overlap_is_between_zero_and_one():
    # Many: text that shares some but not all content scores strictly between
    # zero and one on both metrics.
    bs4_text = "Our liquidity depends on cash flow from operations and credit facilities."
    sg_text  = "The company's liquidity relies on operating cash flow and credit lines."
    result   = compare_section_text(bs4_text, sg_text)
    assert 0.0 < result["char_overlap_ratio"] < 1.0
    assert result["length_ratio"] > 0.0


def test_boundary_bs4_empty_scrapegraph_nonempty_is_infinite_ratio():
    # Boundary: scrapegraph fabricating content where bs4 found none -- no
    # ZeroDivisionError, length_ratio signals "infinite" growth.
    result = compare_section_text("", "fabricated content")
    assert result["length_ratio"] == float("inf")
    assert result["char_overlap_ratio"] == 0.0


def test_boundary_scrapegraph_empty_bs4_nonempty_is_zero_ratio():
    # Boundary: scrapegraph dropping a section entirely.
    result = compare_section_text("real section text", "")
    assert result["length_ratio"] == 0.0
    assert result["char_overlap_ratio"] == 0.0


def test_simple_disjoint_strings_score_zero_overlap():
    # Simple: completely unrelated text has no character overlap.
    result = compare_section_text("abc", "xyz")
    assert result["char_overlap_ratio"] == 0.0
