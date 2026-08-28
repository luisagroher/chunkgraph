"""Functions needed specifically for a using with parsing a single file"""

from pathlib import Path
import re

from parser.models import ParsedFiling


def update_cik_for_filing(filepath: Path, filing: ParsedFiling, ) -> ParsedFiling:
    """
    To update the blank cik attribute of a filing dataclass
    """
    result = re.search(r"\d{10}", str(filepath))

    if result is not None:
        filing.cik = result[0]
    return filing

def update_filing_date_for_filing(filepath: Path, filing: ParsedFiling, ) -> ParsedFiling:
    """
        To update the blank filing date attribute of a filing dataclass
    """
    result = re.search(r"\d{4}-\d{2}-\d{2}", str(filepath))

    if result is not None:
        filing.filing_date = result[0]
    return filing

def update_company_name_for_filing(filepath: Path, filing: ParsedFiling, ) -> ParsedFiling:
    """
        To update the blank company name attribute of a filing dataclass
    """
    # TODO: Add code for replace of extra underscores
    result = re.search(r"[\w_]{1,}_", str(filepath))

    if result is not None:
        result_list = result[0].split("_")
        for word in result_list[:-2]:
            filing.company_name += word + " "

        filing.company_name = filing.company_name[:-1]

    return filing
