# Fourth comparison spike: LLM-driven section/cross-reference extraction via
# ScrapeGraphAI, alongside parse_10ks.py (BeautifulSoup) and the two
# parse_10ks_using_unstructured*.py scripts (the `unstructured` library).
#
# Unlike those, this makes real, billed calls to the OpenAI API -- requires
# OPENAI_API_KEY in a local .env file (see .env.example). Even the smallest
# local sample filing chunks into several parallel calls plus one merge call
# (see src/parser/scrapegraph_extractor.py); still only on the order of cents
# at gpt-4o-mini pricing.
#
# Output goes to data/processed/parsed_scrapegraph/ -- a separate directory
# from parse_10ks.py's data/processed/parsed/, so both can be compared side by
# side (see src/parser/fidelity_compare.py).

import os
from pathlib import Path

from dotenv import load_dotenv

from parse_10ks import save_parsed_filing
from parser import scrapegraph_extractor as sge

DATA_DIR     = Path(__file__).resolve().parent.parent / "data" / "raw" / "10ks"
SAMPLE_FILE  = DATA_DIR / "EOG_RESOURCES_INC_0000821189_2023-02-23.htm"
TEST_FILE1  = DATA_DIR / "SOUTHERN_CO_0000092122_2023-02-16.htm"
CIK          = "0000821189"
COMPANY_NAME = "EOG Resources Inc"
FILING_DATE  = "2023-02-23"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "parsed_scrapegraph"


def main():
    load_dotenv()
    api_key = os.environ["OPENAI_API_KEY"]  # set in .env, see .env.example

    # html      = SAMPLE_FILE.read_bytes()
    html      = TEST_FILE1.read_bytes()
    config    = sge.build_config(api_key)
    extracted = sge.run_extraction(html, config)
    filing    = sge.to_parsed_filing(
        extracted,
        cik          = CIK,
        company_name = COMPANY_NAME,
        filing_date  = FILING_DATE,
        source_file  = str(SAMPLE_FILE),
    )

    out_path = save_parsed_filing(filing, OUTPUT_DIR)
    print(f"Sections: {len(filing.sections)}")
    print(f"Xrefs:    {len(filing.xref_edges)}")
    print(f"Output:   {out_path}")


if __name__ == "__main__":
    main()
