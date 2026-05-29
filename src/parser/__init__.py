"""
parser — SEC 10-K HTML → structured JSON.

Parses locally-downloaded SEC EDGAR 10-K .htm filings into one structured JSON
file per filing: canonical sections (Item 1, 1A, ...), notes to the financial
statements, and the cross-reference edges between them.

Currently holds the shared dataclasses (`models/`) and the ScrapeGraphAI
comparison spike (`scrapegraph_extractor.py`), used alongside — not in place of —
src/parse_10ks.py and the src/parse_10ks_using_unstructured*.py spikes.
"""
