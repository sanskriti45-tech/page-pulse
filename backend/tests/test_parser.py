"""
test_parser.py

Unit tests for backend/parser.py.

These tests exercise the HTML-parsing logic ONLY. They never touch
the network, the FastAPI app, or a real website - every test builds
a small HTML string in memory and passes it straight into the
functions under test. That keeps them fast and 100% deterministic.

Run with:
    pytest
or, from the backend/ directory:
    pytest tests/test_parser.py -v
"""

import sys
from pathlib import Path

# Allow `import parser` to work when pytest is run from the backend/
# directory (where main.py also does `from parser import build_report`),
# without needing a package/__init__.py setup.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup

from parser import (
    build_report,
    count_h1,
    count_images_missing_alt,
    count_words,
    extract_meta_description,
    extract_title,
)


# ---------------------------------------------------------------------
# Happy path: a representative page with every field populated
# ---------------------------------------------------------------------

HAPPY_PATH_HTML = """
<html>
<head>
    <title>Welcome to Acme Corp</title>
    <meta name="description" content="Acme Corp builds fine widgets.">
</head>
<body>
    <h1>Our Products</h1>
    <h1>More Great Products</h1>
    <img src="hero.jpg" alt="A hero banner showing our factory">
    <img src="team.jpg" alt="">
    <img src="logo.png">
    <img src="spacer.gif" alt="   ">
    <p>We build widgets that make your life easier every single day.</p>
</body>
</html>
"""


def test_happy_path_returns_all_expected_fields():
    report = build_report(HAPPY_PATH_HTML)

    assert report["title"] == "Welcome to Acme Corp"
    assert report["meta_description"] == "Acme Corp builds fine widgets."
    assert report["h1_count"] == 2
    # 3 of the 4 images are missing usable alt text:
    # team.jpg (alt=""), logo.png (no alt attr), spacer.gif (alt="   ")
    assert report["images_missing_alt"] == 3
    # "We build widgets that make your life easier every single day."
    # is 12 visible words; the heading text adds more.
    assert report["word_count"] > 0


def test_happy_path_word_count_is_exact():
    # Isolate word counting on a small, fully-known snippet so the
    # expected count isn't just "greater than zero" but exact.
    html = "<html><body><p>one two three four five</p></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert count_words(soup) == 5


def test_happy_path_title_extracted():
    soup = BeautifulSoup(HAPPY_PATH_HTML, "html.parser")
    assert extract_title(soup) == "Welcome to Acme Corp"


def test_happy_path_meta_description_extracted():
    soup = BeautifulSoup(HAPPY_PATH_HTML, "html.parser")
    assert extract_meta_description(soup) == "Acme Corp builds fine widgets."


def test_happy_path_h1_count():
    soup = BeautifulSoup(HAPPY_PATH_HTML, "html.parser")
    assert count_h1(soup) == 2


def test_happy_path_images_missing_alt_breakdown():
    """
    Confirms the three distinct "missing alt" scenarios are all
    counted: no alt attribute at all, alt="", and alt="   ".
    A properly-described image (alt="A hero banner...") must NOT
    be counted.
    """
    soup = BeautifulSoup(HAPPY_PATH_HTML, "html.parser")
    assert count_images_missing_alt(soup) == 3


# ---------------------------------------------------------------------
# Edge case 1: a bare-bones page with none of the optional elements
# ---------------------------------------------------------------------

def test_page_with_no_title_no_meta_no_h1_no_images():
    html = "<html><body><p>Just some plain text on this page.</p></body></html>"
    report = build_report(html)

    assert report["title"] is None
    assert report["meta_description"] is None
    assert report["h1_count"] == 0
    assert report["images_missing_alt"] == 0
    assert report["word_count"] == 7  # "Just some plain text on this page." -> 7 words


# ---------------------------------------------------------------------
# Edge case 2: multiple images with a mix of missing/empty/whitespace
# alt text, isolated from any other page content
# ---------------------------------------------------------------------

def test_multiple_images_mixed_alt_states():
    html = """
    <html><body>
        <img src="a.jpg" alt="Photo of a mountain">
        <img src="b.jpg" alt="">
        <img src="c.jpg">
        <img src="d.jpg" alt="    ">
        <img src="e.jpg" alt="Photo of a river">
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")

    # 3 missing (b: empty string, c: no attribute, d: whitespace-only)
    # 2 valid (a, e)
    assert count_images_missing_alt(soup) == 3


# ---------------------------------------------------------------------
# Edge case 3: completely empty HTML input
# ---------------------------------------------------------------------

def test_empty_html_input_does_not_crash():
    report = build_report("")

    assert report["title"] is None
    assert report["meta_description"] is None
    assert report["h1_count"] == 0
    assert report["images_missing_alt"] == 0
    assert report["word_count"] == 0


# ---------------------------------------------------------------------
# Edge case 4: script/style content must never be counted as visible
# page text, even when it's the only content on the page
# ---------------------------------------------------------------------

def test_script_and_style_content_excluded_from_word_count():
    html = """
    <html>
    <head>
        <style>
            body { font-family: sans-serif; color: red; background: white; }
        </style>
    </head>
    <body>
        <script>
            var greeting = "hello world this should not be counted";
            console.log(greeting);
        </script>
    </body>
    </html>
    """
    report = build_report(html)

    # No visible text anywhere on the page - only <script> and <style>
    # content, which must be excluded entirely.
    assert report["word_count"] == 0


def test_script_and_style_excluded_alongside_real_text():
    """
    Same as above, but with real visible text also present, to prove
    script/style text isn't silently added into the total.
    """
    html = """
    <html>
    <head>
        <style>.hidden { display: none; padding: 10px 20px 30px 40px; }</style>
    </head>
    <body>
        <script>function track() { doSomethingWithManyWords(); }</script>
        <p>Only these five words count.</p>
    </body>
    </html>
    """
    report = build_report(html)
    assert report["word_count"] == 5


# ---------------------------------------------------------------------
# Edge case 5: whitespace-only title / meta description should be
# treated the same as missing (matches the documented behavior in
# extract_title / extract_meta_description)
# ---------------------------------------------------------------------

def test_whitespace_only_title_is_treated_as_missing():
    html = "<html><head><title>   </title></head><body></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert extract_title(soup) is None


def test_whitespace_only_meta_description_is_treated_as_missing():
    html = (
        '<html><head><meta name="description" content="   "></head>'
        "<body></body></html>"
    )
    soup = BeautifulSoup(html, "html.parser")
    assert extract_meta_description(soup) is None
