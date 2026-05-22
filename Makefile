.PHONY: env update lint format clean

# ── Environment ────────────────────────────────────────────────────────────────
env:
	conda env create -f environment.yml

update:
	conda env update -f environment.yml --prune

export:
	conda env export > environment.yml

# ── Code quality ───────────────────────────────────────────────────────────────
# UPDATE lint
# UPDATE format

# ── Pipeline ───────────────────────────────────────────────────────────────────
fetch:
	python src/fetch_10ks.py --sector energy --max_companies 30 --year 2023

parse:
	python src/parse_10ks.py --manifest data/manifest.csv

graph:
	python src/build_graph.py --parsed_dir data/processed/parsed/

pipeline: fetch parse graph

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	find . -type f -name "*.pyc" -delete
	find .
