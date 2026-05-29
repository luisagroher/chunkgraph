"""
fidelity_compare — measures how closely ScrapeGraphAI's reconstructed section
text matches the verbatim text parse_10ks.py extracted for the same section.

ScrapeGraphAI's multi-chunk merge step (see scrapegraph_extractor.py) never sees
the original document text, so its output is a paraphrase/summary rather than a
verbatim extraction. This module makes that fidelity gap observable instead of
just asserting it in prose -- run it against parse_10ks.py's and
parse_10ks_using_scrapegraph.py's outputs for the same filing/section to see the
gap directly.
"""

from difflib import SequenceMatcher


def compare_section_text(bs4_text: str, scrapegraph_text: str) -> dict:
    """
    Compare two extractions of "the same" section.

    length_ratio: scrapegraph_text length / bs4_text length. 1.0 means same
        length; well below 1.0 is the expected signature of summarization.
        `inf` if bs4_text is empty but scrapegraph_text isn't (fabricated
        content); 1.0 if both are empty.
    char_overlap_ratio: difflib.SequenceMatcher similarity ratio (0..1), a
        cheap, deterministic proxy for how much of bs4_text's content survives
        verbatim in scrapegraph_text.
    """
    bs4_len = len(bs4_text)
    sg_len  = len(scrapegraph_text)

    if bs4_len == 0:
        length_ratio = 1.0 if sg_len == 0 else float("inf")
    else:
        length_ratio = sg_len / bs4_len

    char_overlap_ratio = SequenceMatcher(None, bs4_text, scrapegraph_text).ratio()

    return {
        "bs4_length":         bs4_len,
        "scrapegraph_length": sg_len,
        "length_ratio":       length_ratio,
        "char_overlap_ratio": char_overlap_ratio,
    }
