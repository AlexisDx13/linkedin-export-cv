"""Generate a clean cv.md from a LinkedIn data export ZIP.

Reads the relevant CSVs from the zip directly: Profile, Positions, Education,
Certifications, Skills, Languages, Projects, Email Addresses, messages (the
last one only to infer your own LinkedIn profile URL).

Known LinkedIn export bug: some "Location" fields in Positions.csv come out
in Russian (e.g. "Виладекавальс" instead of "Viladecavalls"). That's a
source-data issue: review the generated cv.md by hand before passing it to
cv-to-pdf.

Usage:
    zip-to-cv <export.zip> [-o cv.md]
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Language names come in whatever language your LinkedIn profile itself
# uses; they're normalized to English so the Languages section stays
# consistent with the rest of the CV. Closed vocabulary (language names),
# not free-form translation.
LANGUAGE_NAMES_EN = {
    "inglés": "English",
    "español": "Spanish",
    "catalán": "Catalan",
    "francés": "French",
    "alemán": "German",
    "italiano": "Italian",
    "portugués": "Portuguese",
}


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    """Read a CSV from the zip as a list of dicts; [] if the file is missing."""
    try:
        raw = zf.read(name)
    except KeyError:
        logger.warning("%s not found in the zip", name)
        return []
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def _parse_date(text: str) -> datetime | None:
    """LinkedIn already exports dates as 'Mon YYYY' (e.g. 'Jan 2009')."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%b %Y")
    except ValueError:
        return None


def _newest_first(
    rows: list[dict[str, str]],
    start_field: str,
    end_field: str,
    ongoing_is_newest: bool = False,
) -> list[dict[str, str]]:
    """Sort by end date descending; ties are broken by start date."""

    def key(row: dict[str, str]) -> tuple[int, datetime, datetime]:
        start = _parse_date(row.get(start_field, "")) or datetime.min
        end_raw = row.get(end_field, "").strip()
        if not end_raw and ongoing_is_newest:
            return (2, start, start)
        end = _parse_date(end_raw) or start
        return (1, end, start)

    return sorted(rows, key=key, reverse=True)


# LinkedIn flattens paragraph breaks in free-text fields when exporting to
# CSV: sometimes it leaves a double space, and sometimes it strips them
# entirely, gluing the trailing period to the next capital letter (e.g.
# "...embedded systems.Previously worked..."). Paragraphs are reconstructed
# by detecting those patterns; it's a heuristic patch over the source data,
# not real grammar, so it can misfire on unusual abbreviations.
_PARAGRAPH_BREAK_RE = re.compile(r"\n+|  +|(?<=[.!?])(?=[A-ZÁÉÍÓÚÑ])")


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in _PARAGRAPH_BREAK_RE.split(text or "") if p.strip()]


def _format_description(description: str) -> str:
    """Reconstruct blank-line-separated paragraphs from the CSV field."""
    return "\n\n".join(_split_paragraphs(description))


def _find_own_linkedin_url(zf: zipfile.ZipFile, full_name: str) -> str:
    """Infer your own public LinkedIn profile URL.

    Profile.csv doesn't include it, but whenever someone messages you, the
    "RECIPIENT PROFILE URLS" column in messages.csv contains your own URL.
    Uses the first row where "TO" matches your name.
    """
    if not full_name:
        return ""
    for row in _read_csv(zf, "messages.csv"):
        if row.get("TO", "").strip() == full_name:
            url = row.get("RECIPIENT PROFILE URLS", "").strip()
            if url:
                return url
    return ""


def build_profile_section(
    profile_rows: list[dict[str, str]],
    email_rows: list[dict[str, str]],
    linkedin_url: str,
) -> str:
    if not profile_rows:
        return ""
    profile = profile_rows[0]

    name = f"{profile.get('First Name', '')} {profile.get('Last Name', '')}".strip()
    headline = profile.get("Headline", "").strip()
    location = (profile.get("Geo Location") or profile.get("Location") or "").strip()
    summary = profile.get("Summary", "").strip()

    email = next(
        (r.get("Email Address", "") for r in email_rows if r.get("Primary", "").strip().lower() == "yes"),
        email_rows[0].get("Email Address", "") if email_rows else "",
    )
    # Phone number is deliberately excluded: it's an invasive piece of data
    # for a CV that may end up pasted into plain-text job board forms. The
    # LinkedIn link serves the same purpose as a contact channel.
    linkedin = f"[LinkedIn]({linkedin_url})" if linkedin_url else ""

    lines: list[str] = []
    if name:
        lines += [f"# {name}", ""]
    if headline:
        lines += [f"**{headline}**", ""]

    contact = " | ".join(p for p in (location, email, linkedin) if p)
    if contact:
        lines += [contact, ""]

    if summary:
        lines += ["## Summary", "", _format_description(summary), ""]

    return "\n".join(lines).rstrip() + "\n"


def _format_duration(start: datetime, end: datetime) -> str:
    """Duration between two 'Mon YYYY' dates, counting both months inclusive.

    With only month+year precision, this replicates the calculation
    LinkedIn itself does on its web/PDF (e.g. Dec 2020 - Jul 2026 ->
    "5 years 8 months").
    """
    total_months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    if total_months < 1:
        return ""
    years, months = divmod(total_months, 12)
    parts = []
    if years:
        parts.append(f"{years} year" + ("s" if years != 1 else ""))
    if months:
        parts.append(f"{months} month" + ("s" if months != 1 else ""))
    return " ".join(parts)


def build_experience_section(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""

    lines = ["## Experience", ""]
    for row in _newest_first(rows, "Started On", "Finished On", ongoing_is_newest=True):
        company = row.get("Company Name", "").strip()
        title = row.get("Title", "").strip()
        location = row.get("Location", "").strip()
        start = row.get("Started On", "").strip()
        end = row.get("Finished On", "").strip() or "Present"

        lines.append(f"### {company}")

        start_date = _parse_date(start)
        end_date = datetime.now() if end == "Present" else _parse_date(end)
        duration = _format_duration(start_date, end_date) if start_date and end_date else ""
        date_line = f"{start} - {end}" + (f" ({duration})" if duration else "")

        # Role, dates and location share a single paragraph with hard line
        # breaks (two trailing spaces) instead of three separate paragraphs:
        # that way they share one margin and read as a block, not as three.
        header_lines = [f"**{title}**"] if title else []
        header_lines.append(f"*{date_line}*")
        if location:
            header_lines.append(f"*{location}*")
        lines += ["  \n".join(header_lines), ""]

        description = _format_description(row.get("Description", ""))
        if description:
            lines += [description, ""]

        lines += ["---", ""]

    return "\n".join(lines).rstrip() + "\n"


def build_education_section(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""

    lines = ["## Education", ""]
    for row in _newest_first(rows, "Start Date", "End Date"):
        school = row.get("School Name", "").strip()
        degree = row.get("Degree Name", "").strip()
        start = row.get("Start Date", "").strip()
        end = row.get("End Date", "").strip()

        lines.append(f"### {school}")
        header_lines = [f"**{degree}**"] if degree else []
        date_range = " - ".join(p for p in (start, end) if p)
        if date_range:
            header_lines.append(f"*{date_range}*")
        if header_lines:
            lines.append("  \n".join(header_lines))
        lines.append("")

        notes = row.get("Notes", "").strip()
        if notes:
            lines += [f"> {notes}", ""]

        activities = row.get("Activities", "").strip()
        if activities:
            lines += [f"Activities: {activities}", ""]

        lines += ["---", ""]

    return "\n".join(lines).rstrip() + "\n"


def build_certifications_section(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""

    lines = ["## Certifications", ""]
    for row in _newest_first(rows, "Started On", "Finished On"):
        name = row.get("Name", "").strip()
        if not name:
            continue

        lines.append(f"### {name}")
        authority = row.get("Authority", "").strip()
        date = row.get("Started On", "").strip()
        meta_parts = [f"**{authority}**"] if authority else []
        if date:
            meta_parts.append(date)
        if meta_parts:
            lines.append(" | ".join(meta_parts))

        url = row.get("Url", "").strip()
        if url:
            lines += ["", f"[View Certificate]({url})"]

        lines += ["", "---", ""]

    return "\n".join(lines).rstrip() + "\n"


def build_skills_section(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""

    seen_lower: set[str] = set()
    skills: list[str] = []
    for row in rows:
        name = row.get("Name", "").strip()
        if name and name.lower() not in seen_lower:
            skills.append(name)
            seen_lower.add(name.lower())

    return "## Skills\n\n" + ", ".join(skills) + "\n"


def build_languages_section(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""

    lines = ["## Languages", ""]
    for row in rows:
        name = row.get("Name", "").strip()
        if not name:
            continue
        name = LANGUAGE_NAMES_EN.get(name.lower(), name)
        proficiency = row.get("Proficiency", "").strip()
        lines.append(f"- **{name}**: {proficiency}" if proficiency else f"- {name}")

    return "\n".join(lines) + "\n"


def build_projects_section(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""

    lines = ["## Projects", ""]
    for row in _newest_first(rows, "Started On", "Finished On"):
        title = row.get("Title", "").strip()
        if not title:
            continue

        lines.append(f"### {title}")
        start = row.get("Started On", "").strip()
        end = row.get("Finished On", "").strip()
        if start:
            lines.append(f"{start} - {end or 'Present'}")
        elif end:
            lines.append(end)

        description = _format_description(row.get("Description", ""))
        if description:
            lines += ["", description]

        url = row.get("Url", "").strip()
        if url:
            lines += ["", f"[View Project]({url})"]

        lines += ["", "---", ""]

    return "\n".join(lines).rstrip() + "\n"


def build_cv_markdown(zf: zipfile.ZipFile) -> str:
    profile_rows = _read_csv(zf, "Profile.csv")
    full_name = ""
    if profile_rows:
        first = profile_rows[0]
        full_name = f"{first.get('First Name', '')} {first.get('Last Name', '')}".strip()

    sections = [
        build_profile_section(
            profile_rows,
            _read_csv(zf, "Email Addresses.csv"),
            _find_own_linkedin_url(zf, full_name),
        ),
        build_experience_section(_read_csv(zf, "Positions.csv")),
        build_education_section(_read_csv(zf, "Education.csv")),
        build_certifications_section(_read_csv(zf, "Certifications.csv")),
        build_projects_section(_read_csv(zf, "Projects.csv")),
        build_skills_section(_read_csv(zf, "Skills.csv")),
        build_languages_section(_read_csv(zf, "Languages.csv")),
    ]
    return "\n\n".join(s.strip() for s in sections if s.strip()) + "\n"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(description="Convert a LinkedIn export ZIP into a clean cv.md")
    parser.add_argument("source", type=Path, help="LinkedIn export ZIP file")
    parser.add_argument("-o", "--output", type=Path, default=Path("cv.md"), help="Output file (default: cv.md)")
    args = parser.parse_args()

    if not args.source.exists():
        logger.error("File not found: %s", args.source)
        return 1

    with zipfile.ZipFile(args.source) as zf:
        cv_markdown = build_cv_markdown(zf)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(cv_markdown, encoding="utf-8")
    print(f"CV generated: {args.output}")
    print(
        "Remember to review location fields by hand (known LinkedIn bug: "
        "some cities come out in Russian) before generating the PDF."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
