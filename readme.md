# chunkgraph
Standard RAG pipelines treat documents as bags of independent chunks but many document types have internal dependencies that chunking destroys. `chunkgraph` is a pilot project to test cross-referenced retrieval using SEC 10-K filings.


---

## Problem

Standard RAG pipelines treat chunks as independent retrieval units. SEC 10-K filings are not. A 10-K contains hundreds of explicit cross-references — MD&A sections pointing to financial notes, risk factors referencing legal proceedings, liquidity discussions depending on footnotes. These references are not decorative. The referencing chunk is incomplete without the referenced chunk.

Fixed-size chunking with overlap has no mechanism for representing dependencies between non-adjacent sections. Cross-references are discarded at parse time. A retrieval system built on top has no way to know what it is missing.

This project demonstrates the failure concretely on energy and utilities sector 10-K filings from SEC EDGAR, then tests whether chunk-aware contrastive training (CPE, from the SKIM paper) recovers the cross-reference signal that naive chunking loses.

---

## Why This Is Not a GraphRAG Problem

GraphRAG frameworks extract entity relationships inferred from content — people, organizations, concepts.

The cross-references in a 10-K are explicit. "See Note 7 to the consolidated financial statements" is a string in the document, not a latent relationship. It does not require extraction. It requires that the parser not throw it away.

Knowledge graphs model entity relationships inferred from content. Chunk dependency graphs model structural dependencies explicit in the document. The failure mode being addressed here is the second: a retrieval system that returns chunk A without chunk B, where B is required to interpret A.

---

## Approach

**Phase 1 — Demonstrate the failure**

Construct evaluation queries that require cross-reference resolution. Measure how often naive chunking returns an incomplete answer. Establish a baseline.

**Phase 2 — Chunk Prediction Embeddings**

Train chunk embeddings using CPE contrastive learning on the chunk dependency graph. Measure retrieval delta against the Phase 1 baseline.

---

## Data

SEC EDGAR public filings. Energy and utilities sector (SIC codes 1311, 1381, 2911, 4911, 4931). Fiscal year 2023. No authentication required.

```bash
# Update User-Agent in fetch_10ks.py with your name and email (SEC requirement)
python src/fetch_10ks.py --sector energy --max_companies 30 --year 2023
```

Filings saved to `data/10ks/` with a `manifest.csv` index.

---

## Status

- [x] EDGAR data pipeline
- [ ] Section extractor and cross-reference parser
- [ ] Chunk dependency graph builder
- [ ] Naive chunking baseline and evaluation
- [ ] CPE training pipeline
- [ ] Retrieval evaluation against baseline

---

## References

- [SKIM / CPE paper](#) — chunk-aware contrastive training
- [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar) — data source
- [BEIR Benchmark](https://github.com/beir-cellar/beir) — retrieval evaluation framework

---
