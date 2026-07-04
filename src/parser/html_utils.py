"""HTML cleaning helpers shared by section detection and text extraction."""

import re

from bs4 import BeautifulSoup


def clean_html(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove tags that carry no text content."""
    for tag in soup(["script", "style", "meta", "link", "ix:header"]):
        tag.decompose()
    # Remove XBRL inline tags but keep their text
    for tag in soup.find_all(re.compile(r"^ix:")):
        tag.unwrap()
    return soup


def get_text_clean(element) -> str:
    """Extract clean text from a BS4 element."""
    text = element.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
