"""ZOMBIES tests for the scrapegraph_extractor module.

DocumentScraperGraph is mocked throughout -- no network, no real LLM calls, no
OPENAI_API_KEY required. See test_scrapegraph_extractor_live.py for the gated
test that hits the real API.
"""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from parser import scrapegraph_extractor as sge
from parser.scrapegraph_extractor import ExtractedFiling


def _mock_graph(monkeypatch, run_return):
    """Patch DocumentScraperGraph so .run() returns `run_return` with no network."""
    mock_instance = MagicMock()
    mock_instance.run.return_value = run_return
    mock_cls = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(sge, "DocumentScraperGraph", mock_cls)
    return mock_cls, mock_instance


def test_zero_no_sections_returns_empty_filing(monkeypatch):
    # Zero: an extraction with no sections produces an empty-but-valid filing.
    _mock_graph(monkeypatch, {"sections": []})
    extracted = sge.run_extraction("<html></html>", sge.build_config("k"))
    filing = sge.to_parsed_filing(extracted, "c", "n", "d", "s.htm")
    assert filing.sections == {}
    assert filing.xref_edges == []


def test_one_section_no_xrefs(monkeypatch):
    # One: a single section with no cross-references converts cleanly.
    _mock_graph(monkeypatch, {
        "sections": [
            {"section_id": "item_1", "title": "Item 1. Business", "text": "We do things."},
        ],
    })
    extracted = sge.run_extraction("<html></html>", sge.build_config("k"))
    filing = sge.to_parsed_filing(extracted, "c", "n", "d", "s.htm")
    assert list(filing.sections) == ["item_1"]
    assert filing.sections["item_1"].char_count == len("We do things.")
    assert filing.sections["item_1"].xrefs == []


def test_many_sections_and_xrefs_populate_xref_edges(monkeypatch):
    # Many: multiple sections/xrefs attach to both the section and the filing's
    # flat xref_edges list, mirroring parse_10ks.py's output shape.
    _mock_graph(monkeypatch, {
        "sections": [
            {
                "section_id": "item_7",
                "title": "Item 7. MD&A",
                "text": "See Note 3 and Note 4.",
                "xrefs": [
                    {"target_raw": "See Note 3", "target_section": "note_3", "context": "See Note 3."},
                    {"target_raw": "Note 4", "target_section": "note_4", "context": "and Note 4."},
                ],
            },
            {"section_id": "note_3", "title": "Note 3 — Leases", "text": "Lease details."},
        ],
    })
    extracted = sge.run_extraction("<html></html>", sge.build_config("k"))
    filing = sge.to_parsed_filing(extracted, "c", "n", "d", "s.htm")
    assert len(filing.sections) == 2
    assert len(filing.xref_edges) == 2
    assert filing.sections["item_7"].xrefs[0]["target_section"] == "note_3"
    assert filing.xref_edges[0].source_section == "item_7"


def test_boundary_missing_optional_xrefs_defaults_to_empty_list(monkeypatch):
    # Boundary: a section dict omitting the optional "xrefs" key validates fine.
    _mock_graph(monkeypatch, {
        "sections": [{"section_id": "item_2", "title": "Item 2. Properties", "text": "..."}],
    })
    extracted = sge.run_extraction("<html></html>", sge.build_config("k"))
    assert extracted.sections[0].xrefs == []


def test_exception_invalid_response_raises_validation_error(monkeypatch):
    # Exceptions: a response missing required fields raises pydantic's
    # ValidationError directly -- no custom wrapping.
    _mock_graph(monkeypatch, {"sections": [{"section_id": "item_1"}]})
    with pytest.raises(ValidationError):
        sge.run_extraction("<html></html>", sge.build_config("k"))


def test_interface_run_extraction_wires_prompt_source_and_config(monkeypatch):
    # Interface: run_extraction must construct DocumentScraperGraph with the
    # cleaned HTML as `source`, the fixed prompt, the given config, and the
    # ExtractedFiling schema -- asserted on the mock's call args, not just the
    # return value, so a wiring mistake (wrong kwarg name/nesting) is caught.
    mock_cls, _ = _mock_graph(monkeypatch, {"sections": []})
    config = sge.build_config("secret-key", model="openai/gpt-4o-mini")
    html  = "<html><script>noise()</script><body><p>Item 1. Business</p></body></html>"

    sge.run_extraction(html, config)

    _, kwargs = mock_cls.call_args
    assert kwargs["prompt"] == sge.build_prompt()
    assert kwargs["config"] == config
    assert kwargs["schema"] is ExtractedFiling
    assert "<script>" not in kwargs["source"]
    assert "Item 1. Business" in kwargs["source"]


def test_simple_build_config_shape():
    # Simple: build_config produces the exact shape ScrapeGraphAI expects.
    config = sge.build_config("secret-key")
    assert config == {
        "llm":      {"api_key": "secret-key", "model": sge.DEFAULT_MODEL},
        "verbose":  False,
        "headless": False,
    }
