"""
Gated live-integration test for scrapegraph_extractor.

Hits the real OpenAI API via scrapegraphai's DocumentScraperGraph -- skipped
unless OPENAI_API_KEY is set, and NOT part of the default test run for anyone
without a key (CI, fresh clones). Uses a small, single-chunk fixture so a run
that does execute stays fast and cheap rather than exercising the multi-chunk
map-reduce path real filings would trigger.
"""

import os
from pathlib import Path

import pytest

from parser import scrapegraph_extractor as sge

FIXTURE = Path(__file__).parent / "fixtures" / "live_sample_filing.htm"

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set -- skipping live ScrapeGraphAI call",
)


def test_live_extraction_against_real_openai_api():
    html      = FIXTURE.read_text()
    config    = sge.build_config(os.environ["OPENAI_API_KEY"])
    extracted = sge.run_extraction(html, config)
    filing    = sge.to_parsed_filing(
        extracted,
        cik          = "0000000000",
        company_name = "Test Co",
        filing_date  = "2023-01-01",
        source_file  = str(FIXTURE),
    )

    assert filing.sections, "expected at least one section extracted from the live API"
    assert any(s.xrefs for s in filing.sections.values()), "expected at least one cross-reference extracted"
