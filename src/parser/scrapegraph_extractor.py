"""
scrapegraph_extractor — LLM-driven section/cross-reference extraction.

Comparison spike alongside src/parse_10ks.py (BeautifulSoup + TOC-anchor/regex
detection) and the two src/parse_10ks_using_unstructured*.py scripts. Instead of
locating section boundaries deterministically, this asks an LLM (via
scrapegraphai's DocumentScraperGraph) to identify the canonical 10-K sections and
the cross-references between them directly from the filing text.

ScrapeGraphAI chunks long documents by the configured model's token limit and,
for multi-chunk filings, merges each chunk's extraction with one further LLM call
that never sees the original raw text. So `Section.text` produced here is an LLM
reconstruction, not a verbatim extraction like parse_10ks.py's — see
src/parser/fidelity_compare.py for a way to measure that gap on a real filing.
"""

import re
from dataclasses import asdict
from typing import List

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from scrapegraphai.graphs import DocumentScraperGraph

from parser.models import CrossReference, ParsedFiling, Section

DEFAULT_MODEL = "openai/gpt-4o-mini"

EXTRACTION_PROMPT = (
    "This document is a SEC 10-K filing. Extract each canonical Item section "
    "(Item 1, 1A, 1B, 2, 3, 7, 7A, 8, 9A) and each numbered Note to the financial "
    "statements. For each, give its section_id (e.g. 'item_1a' or 'note_7'), its "
    "heading title, and its body text reproduced as closely to verbatim as "
    "possible. Also list every explicit cross-reference it makes to another Item "
    "or Note (phrases like 'see Note 7' or 'refer to Item 1A'), giving the raw "
    "matched phrase, the normalized target section id, and the surrounding "
    "sentence as context."
)

# Tags removed before handing text to ScrapeGraphAI. DocumentScraperGraph runs
# with parse_html=False, so it does no HTML-aware stripping itself — this is
# pure token-cost control, not section-detection logic.
_BOILERPLATE_TAGS = ["script", "style", "meta", "link", "ix:header"]


# ── Schema ──────────────────────────────────────────────────────────────────────

class ExtractedCrossReference(BaseModel):
    target_raw:     str = Field(description="Raw matched phrase, e.g. 'see Note 7'")
    target_section: str = Field(description="Normalized target id, e.g. 'note_7'")
    context:        str = Field(description="Surrounding sentence")


class ExtractedSection(BaseModel):
    section_id: str                            = Field(description="Normalized id, e.g. 'item_1a' or 'note_7'")
    title:      str                            = Field(description="Heading text as it appears in the filing")
    text:       str                            = Field(description="Body text of the section")
    xrefs:      List[ExtractedCrossReference]  = Field(default_factory=list)


class ExtractedFiling(BaseModel):
    sections: List[ExtractedSection] = Field(default_factory=list)


# ── Prompt / pre-clean / config ──────────────────────────────────────────────────

def build_prompt() -> str:
    """Fixed extraction instruction; per-filing variation lives in `source`."""
    return EXTRACTION_PROMPT


def strip_html_boilerplate(html: bytes | str) -> str:
    """
    Remove script/style/meta/link/XBRL-header noise, unwrap inline ix: tags.

    Accepts raw bytes (preferred -- BeautifulSoup auto-detects the declared
    encoding, same as parse_10ks.py's clean_html) or an already-decoded str.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_BOILERPLATE_TAGS):
        tag.decompose()
    for tag in soup.find_all(re.compile(r"^ix:")):
        tag.unwrap()
    return str(soup)


def build_config(api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """ScrapeGraphAI graph config for the OpenAI backend."""
    return {
        "llm":      {"api_key": api_key, "model": model},
        "verbose":  False,
        "headless": False,
    }


# ── Extraction ────────────────────────────────────────────────────────────────

def run_extraction(html: bytes | str, config: dict) -> ExtractedFiling:
    """
    Run the ScrapeGraphAI DocumentScraperGraph extraction over one filing's HTML.

    Raises pydantic.ValidationError if the LLM's response doesn't match the schema
    (including scrapegraphai's own {"error": ..., "raw_response": ...} shape on a
    timeout or unparseable response — that also fails schema validation here).
    """
    graph = DocumentScraperGraph(
        prompt = build_prompt(),
        source = strip_html_boilerplate(html),
        config = config,
        schema = ExtractedFiling,
    )
    result = graph.run()
    return ExtractedFiling.model_validate(result)


def to_parsed_filing(
    extracted:    ExtractedFiling,
    cik:          str,
    company_name: str,
    filing_date:  str,
    source_file:  str,
    model:        str = DEFAULT_MODEL,
) -> ParsedFiling:
    """Convert ScrapeGraphAI's schema output into the shared ParsedFiling model."""
    filing = ParsedFiling(
        cik          = cik,
        company_name = company_name,
        filing_date  = filing_date,
        source_file  = source_file,
    )
    filing.parse_warnings.append(f"Extraction backend: scrapegraphai (model={model})")

    for ext_section in extracted.sections:
        section = Section.from_text(
            section_id = ext_section.section_id,
            title      = ext_section.title,
            text       = ext_section.text,
        )
        for ext_xref in ext_section.xrefs:
            xref = CrossReference(
                source_section = ext_section.section_id,
                target_raw     = ext_xref.target_raw,
                target_section = ext_xref.target_section,
                context        = ext_xref.context,
            )
            section.xrefs.append(asdict(xref))
            filing.xref_edges.append(xref)

        filing.sections[section.section_id] = section

    return filing
