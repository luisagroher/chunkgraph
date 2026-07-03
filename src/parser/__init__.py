"""
parser — SEC 10-K HTML → structured JSON.

Parses locally-downloaded SEC EDGAR 10-K .htm filings into one structured JSON
file per filing: canonical sections (Item 1, 1A, ...), notes to the financial
statements, and the cross-reference edges between them.
"""
