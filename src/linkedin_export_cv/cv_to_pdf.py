"""Render a CV Markdown file into a styled, print-ready A4 PDF.

Meant to run on the `cv.md` produced by zip-to-cv, once corrected by hand
(e.g. the LinkedIn export's Russian-location bug).

Usage:
    cv-to-pdf <cv.md> [-o cv.pdf]
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# cv.md "## " sections that go in the sidebar column instead of the main
# column, in the order they should appear there (not necessarily the order
# they appear in in cv.md). Contact isn't listed here: it isn't a real
# section in cv.md, it's synthesized from the profile header's contact
# line and always placed first in the sidebar (see _split_into_columns).
SIDEBAR_ORDER = ["skills", "languages", "certifications"]

# A4 template with a full-height dark sidebar, inspired by LinkedIn's own
# native profile PDF export (Resources -> Save to PDF on your profile page).
# Designed for 1-3 page resumes.
_SIDEBAR_BG = "#2c3e46"
_SIDEBAR_FG = "#e8e8e8"

# Width of the sidebar's fixed background rectangle, in mm, so it matches
# the actual width of the .sidebar cell (35% of the page's content area,
# i.e. 35% of 210mm - 8mm right margin). "35%" can't be used directly on
# the fixed element: its percentage resolves against the full page width
# (210mm), not the content area.
_SIDEBAR_WIDTH_MM = 0.35 * (210 - 8)

_CSS = f"""
@page {{
    size: A4;
    margin: 0 8mm 6mm 0;
    @bottom-right {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        font-family: Arial, sans-serif;
        color: #777;
    }}
}}
body {{
    font-family: Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: #333;
    margin: 0;
    padding: 0;
}}
h1 {{
    font-size: 20pt;
    font-weight: bold;
    color: #111;
    margin: 0 0 4px 0;
}}
p {{
    margin: 0 0 10px 0;
}}
strong {{
    color: #111;
}}
h1 + p {{
    font-size: 11pt;
    color: #0056b3;
    font-weight: bold;
    margin-bottom: 8px;
}}
h1 + p + p {{
    font-size: 9.5pt;
    color: #666;
    margin-bottom: 15px;
}}
h2 {{
    font-size: 12pt;
    color: #111;
    border-bottom: 1px solid #aaa;
    padding-bottom: 3px;
    margin: 18px 0 10px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
h3 {{
    font-size: 10.5pt;
    color: #111;
    margin: 12px 0 4px 0;
}}
h3 + p {{
    font-style: italic;
    color: #555;
    margin-bottom: 6px;
    font-size: 9pt;
}}
/* Experience's date + location line (the only *emphasis* in cv.md): an
   explicit marker because "second paragraph after the h3" doesn't work to
   single it out, since in Projects that same slot is the description. */
em {{
    color: #555;
    font-size: 9pt;
}}
ul {{
    margin: 0 0 10px 0;
    padding-left: 0;
    list-style: none;
}}
li {{
    margin-bottom: 4px;
}}
hr {{
    display: none;
}}
a {{
    color: #0056b3;
    text-decoration: none;
}}
.sidebar-bg {{
    position: fixed;
    top: 0;
    left: 0;
    width: {_SIDEBAR_WIDTH_MM}mm;
    height: 297mm;
    background: {_SIDEBAR_BG};
    z-index: -1;
}}
.cv-body {{
    display: table;
    width: 100%;
    table-layout: fixed;
}}
.sidebar, .main-column {{
    box-sizing: border-box;
}}
.sidebar {{
    display: table-cell;
    width: 35%;
    color: {_SIDEBAR_FG};
    padding: 12mm 8mm 12mm 8mm;
    vertical-align: top;
}}
.sidebar h2, .sidebar h3, .sidebar strong {{
    color: #ffffff;
}}
.sidebar h2 {{
    font-size: 10.5pt;
    border-bottom-color: #5b7480;
}}
.sidebar h3 + p {{
    color: #b8c4cc;
}}
.sidebar a {{
    color: #bcd4e6;
}}
.main-column {{
    display: table-cell;
    width: 65%;
    padding: 12mm 0 12mm 8mm;
    vertical-align: top;
}}
"""


def _split_into_columns(markdown_content: str) -> tuple[str, str]:
    """Split the markdown into a sidebar column and a main column.

    Everything before the first "## " section is "name + headline +
    contact": the first two lines (name, headline) head the main column;
    the contact info moves to the sidebar. The remaining sections are
    distributed according to SIDEBAR_ORDER.
    """
    chunks = re.split(r"(?m)^## ", markdown_content)
    header_paragraphs = chunks[0].strip().split("\n\n")
    name_and_headline = "\n\n".join(header_paragraphs[:2])
    contact_line = "\n\n".join(header_paragraphs[2:])

    # Location is the first field of the contact line (see
    # build_profile_section in zip_to_cv.py: "location | email | linkedin").
    # It goes under the headline as a subtitle, not as sidebar contact info.
    location, _, rest_contact = contact_line.partition(" | ")
    main_header = "\n\n".join(p for p in (name_and_headline, location) if p)

    sidebar_by_title: dict[str, str] = {}
    main_parts = [main_header] if main_header else []
    for chunk in chunks[1:]:
        title = chunk.splitlines()[0].strip()
        section_md = "## " + chunk.strip()
        if title.lower() in SIDEBAR_ORDER:
            sidebar_by_title[title.lower()] = section_md
        else:
            main_parts.append(section_md)

    sidebar_parts = [f"## Contact\n\n{rest_contact}"] if rest_contact else []
    sidebar_parts += [sidebar_by_title[title] for title in SIDEBAR_ORDER if title in sidebar_by_title]

    return "\n\n".join(sidebar_parts), "\n\n".join(main_parts)


def convert_md_to_pdf(markdown_content: str, pdf_path: Path) -> bool:
    try:
        import markdown
        from weasyprint import HTML
    except ImportError:
        logger.error("Missing dependencies. Install them with: pip install weasyprint markdown")
        return False

    sidebar_md, main_md = _split_into_columns(markdown_content)
    extensions = ["tables", "fenced_code"]
    sidebar_html = markdown.markdown(sidebar_md, extensions=extensions)
    main_html = markdown.markdown(main_md, extensions=extensions)

    html_body = f"""<div class="sidebar-bg"></div>
<div class="cv-body">
<aside class="sidebar">{sidebar_html}</aside>
<div class="main-column">{main_html}</div>
</div>
"""
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CV</title>
<style>{_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>
"""

    try:
        HTML(string=html).write_pdf(str(pdf_path))
        return True
    except Exception as e:
        logger.error("Failed to generate the PDF: %s", e)
        return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(description="Convert a CV Markdown file into a PDF")
    parser.add_argument("source", type=Path, help="CV Markdown file (e.g. cv.md)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output PDF file (default: same name, .pdf extension)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        logger.error("File not found: %s", args.source)
        return 1

    output_path = args.output or args.source.with_suffix(".pdf")
    markdown_content = args.source.read_text(encoding="utf-8")

    if convert_md_to_pdf(markdown_content, output_path):
        print(f"PDF generated: {output_path}")
        return 0

    logger.error("Failed to generate the PDF.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
