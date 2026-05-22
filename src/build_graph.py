"""
build_graph.py

Builds a chunk dependency graph from a parsed 10-K JSON file.
Nodes are sections (item_1a, item_7, note_7, etc.).
Edges are explicit cross-references extracted by parse_10ks.py.

Usage:
    python src/build_graph.py --input data/processed/parsed/0000004904_2023-02-23.json
    python src/build_graph.py --parsed_dir data/processed/parsed/   # batch mode

Output:
    data/processed/graphs/{cik}_{date}.json   node-link graph per filing
    data/processed/graphs/summary.csv         cross-filing summary stats
"""

import json
import csv
import argparse
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


# ── Graph construction ─────────────────────────────────────────────────────────

def build_graph(parsed: dict) -> nx.DiGraph:
    """
    Build a directed graph from a parsed filing dict.

    Nodes: sections (section_id as node key)
    Edges: cross-references (source_section → target_section)

    Node attributes: title, char_count, text (truncated for serialization)
    Edge attributes: target_raw, context, count (parallel edges are collapsed)
    """
    G = nx.DiGraph()
    G.graph["cik"]          = parsed["cik"]
    G.graph["company_name"] = parsed["company_name"]
    G.graph["filing_date"]  = parsed["filing_date"]

    # ── Add nodes ──────────────────────────────────────────────────────────────
    for section_id, section in parsed["sections"].items():
        G.add_node(
            section_id,
            title      = section["title"],
            char_count = section["char_count"],
            # Truncate text — full text lives in the parsed JSON
            text_preview = section["text"][:500] if section.get("text") else "",
        )

    # ── Add edges ──────────────────────────────────────────────────────────────
    # Collapse parallel edges (same source → target) into a single edge
    # with a count attribute and all context strings preserved.
    edge_map = {}   # (source, target) → {count, contexts, raw_matches}

    for xref in parsed["xref_edges"]:
        src = xref["source_section"]
        tgt = xref["target_section"]

        # Skip self-references
        if src == tgt:
            continue

        # Skip references to sections not present in this filing
        # (dangling references are noted but not added as edges)
        if tgt not in parsed["sections"]:
            continue

        key = (src, tgt)
        if key not in edge_map:
            edge_map[key] = {"count": 0, "contexts": [], "raw_matches": []}

        edge_map[key]["count"]       += 1
        edge_map[key]["contexts"].append(xref["context"][:200])
        edge_map[key]["raw_matches"].append(xref["target_raw"])

    for (src, tgt), attrs in edge_map.items():
        G.add_edge(
            src, tgt,
            count       = attrs["count"],
            contexts    = attrs["contexts"],
            raw_matches = attrs["raw_matches"],
        )

    return G


# ── Graph statistics ───────────────────────────────────────────────────────────

def graph_stats(G: nx.DiGraph, parsed: dict) -> dict:
    """Compute summary statistics for a filing graph."""
    dangling = [
        xref["target_section"]
        for xref in parsed["xref_edges"]
        if xref["target_section"] not in parsed["sections"]
           and xref["source_section"] != xref["target_section"]
    ]

    # Most referenced nodes (highest in-degree)
    in_degrees  = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)
    top_targets = [f"{node}({deg})" for node, deg in in_degrees[:5] if deg > 0]

    # Most referencing nodes (highest out-degree)
    out_degrees  = sorted(G.out_degree(), key=lambda x: x[1], reverse=True)
    top_sources  = [f"{node}({deg})" for node, deg in out_degrees[:5] if deg > 0]

    return {
        "cik":              G.graph["cik"],
        "company_name":     G.graph["company_name"],
        "filing_date":      G.graph["filing_date"],
        "node_count":       G.number_of_nodes(),
        "edge_count":       G.number_of_edges(),
        "density":          round(nx.density(G), 4),
        "dangling_xrefs":   len(dangling),
        "top_targets":      " | ".join(top_targets),
        "top_sources":      " | ".join(top_sources),
        "is_dag":           nx.is_directed_acyclic_graph(G),
    }


# ── Serialization ──────────────────────────────────────────────────────────────

def save_graph(G: nx.DiGraph, output_dir: Path) -> Path:
    """Serialize graph to node-link JSON. Returns output path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename    = f"{G.graph['cik']}_{G.graph['filing_date']}.json"
    output_path = output_dir / filename
    data        = json_graph.node_link_data(G, edges='edges')
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    return output_path

def load_graph(path: Path) -> nx.DiGraph:
    """Load a graph from node-link JSON."""
    with open(path) as f:
        data = json.load(f)
    return json_graph.node_link_graph(data, directed=True, edges='edges')

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build chunk dependency graphs from parsed 10-K filings")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input",      help="Single parsed JSON file")
    group.add_argument("--parsed_dir", help="Directory of parsed JSONs for batch mode")
    parser.add_argument("--output_dir", default="./data/processed/graphs")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input:
        # ── Single file mode ───────────────────────────────────────────────────
        path = Path(args.input)
        with open(path) as f:
            parsed = json.load(f)

        G        = build_graph(parsed)
        out_path = save_graph(G, output_dir)
        stats    = graph_stats(G, parsed)

        print(f"Company:       {G.graph['company_name']}")
        print(f"Nodes:         {stats['node_count']}")
        print(f"Edges:         {stats['edge_count']}")
        print(f"Density:       {stats['density']}")
        print(f"Dangling xrefs:{stats['dangling_xrefs']}")
        print(f"Top targets:   {stats['top_targets']}")
        print(f"Top sources:   {stats['top_sources']}")
        print(f"Is DAG:        {stats['is_dag']}")
        print(f"Output:        {out_path}")

    else:
        # ── Batch mode ─────────────────────────────────────────────────────────
        parsed_dir = Path(args.parsed_dir)
        json_files = sorted(parsed_dir.glob("*.json"))

        if not json_files:
            print(f"No parsed JSON files found in {parsed_dir}")
            return

        print(f"Building graphs for {len(json_files)} filings...\n")

        all_stats = []
        success, failed = 0, 0

        for i, path in enumerate(json_files):
            try:
                with open(path) as f:
                    parsed = json.load(f)

                # Skip empty parses
                if parsed["section_count"] == 0:
                    print(f"[{i+1}/{len(json_files)}] SKIP (0 sections): {path.name}")
                    failed += 1
                    continue

                G        = build_graph(parsed)
                out_path = save_graph(G, output_dir)
                stats    = graph_stats(G, parsed)
                all_stats.append(stats)

                print(
                    f"[{i+1}/{len(json_files)}] {parsed['company_name'][:35]:<35} "
                    f"nodes={stats['node_count']:>3} "
                    f"edges={stats['edge_count']:>3} "
                    f"density={stats['density']:.3f}"
                )
                success += 1

            except Exception as e:
                print(f"[{i+1}/{len(json_files)}] ERROR {path.name}: {e}")
                failed += 1

        # ── Write summary CSV ──────────────────────────────────────────────────
        if all_stats:
            summary_path = output_dir / "summary.csv"
            with open(summary_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=all_stats[0].keys())
                writer.writeheader()
                writer.writerows(all_stats)
            print(f"\n✓ Done. {success} graphs built, {failed} skipped → {output_dir}")
            print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()
