"""
parser.py

All HTML-parsing logic for Page Pulse lives here, separate from the
FastAPI route in main.py. This keeps main.py focused on HTTP/API
concerns, and keeps this file focused on "given HTML text, extract
these metrics."
"""

from bs4 import BeautifulSoup


def extract_title(soup: BeautifulSoup) -> str | None:
    """Return the text inside <title>, or None if there isn't one."""
    if soup.title and soup.title.string:
        text = soup.title.string.strip()
        return text if text else None
    return None


def extract_meta_description(soup: BeautifulSoup) -> str | None:
    """Return the content of <meta name="description">, or None."""
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        content = tag["content"].strip()
        return content if content else None
    return None


def count_h1(soup: BeautifulSoup) -> int:
    """Count all <h1> elements on the page."""
    return len(soup.find_all("h1"))


def count_images_missing_alt(soup: BeautifulSoup) -> int:
    """
    Count <img> elements where alt is either missing entirely or
    present but empty/whitespace-only (e.g. alt="" or alt="   ").
    """
    missing = 0
    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt is None or alt.strip() == "":
            missing += 1
    return missing


def count_words(soup: BeautifulSoup) -> int:
    """
    Approximate the visible word count.

    We work on a copy of the soup and strip out <script> and <style>
    tags first, since their contents are not visible text and
    shouldn't count as "words" on the page.
    """
    # Work on a copy so we don't mutate the soup the caller might
    # still want to use for other extraction.
    soup_copy = BeautifulSoup(str(soup), "html.parser")

    for tag in soup_copy(["script", "style"]):
        tag.decompose()

    text = soup_copy.get_text(separator=" ")
    words = text.split()
    return len(words)


def build_report(html: str) -> dict:
    """
    Parse raw HTML text and return a dict of all the metrics we
    care about. This is the single function main.py calls.
    """
    soup = BeautifulSoup(html, "html.parser")

    return {
        "title": extract_title(soup),
        "meta_description": extract_meta_description(soup),
        "h1_count": count_h1(soup),
        "images_missing_alt": count_images_missing_alt(soup),
        "word_count": count_words(soup),
    }
