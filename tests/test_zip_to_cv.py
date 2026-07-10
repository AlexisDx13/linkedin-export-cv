import csv
import io
import zipfile
from datetime import datetime

from linkedin_export_cv.zip_to_cv import (
    _find_own_linkedin_url,
    _format_description,
    _format_duration,
    _newest_first,
    _parse_date,
    build_cv_markdown,
    build_education_section,
    build_experience_section,
    build_languages_section,
    build_profile_section,
    build_projects_section,
    build_skills_section,
)


def _zip_with_csvs(csvs: dict[str, list[dict[str, str]]]) -> zipfile.ZipFile:
    """Build an in-memory zip with one CSV per (filename, rows) entry."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for filename, rows in csvs.items():
            text = io.StringIO()
            if rows:
                writer = csv.DictWriter(text, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            zf.writestr(filename, text.getvalue())
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


# -- _parse_date --------------------------------------------------------


def test_parse_date_valid():
    assert _parse_date("Jan 2009") == datetime(2009, 1, 1)


def test_parse_date_empty_or_invalid():
    assert _parse_date("") is None
    assert _parse_date("not a date") is None


# -- _newest_first -------------------------------------------------------


def test_newest_first_sorts_by_end_date_descending():
    rows = [
        {"start": "Jan 2009", "end": "Apr 2017"},
        {"start": "Sep 2017", "end": "Dec 2020"},
    ]
    result = _newest_first(rows, "start", "end")
    assert [r["start"] for r in result] == ["Sep 2017", "Jan 2009"]


def test_newest_first_breaks_ties_by_start_date():
    # Four projects that all end Apr 2017 but started at different times:
    # this is the exact tie-breaking bug found while building the tool.
    rows = [
        {"title": "PowerStudio", "start": "Jan 2009", "end": "Apr 2017"},
        {"title": "CirCarlife", "start": "Jun 2015", "end": "Apr 2017"},
        {"title": "SQL Export", "start": "Mar 2010", "end": "Apr 2017"},
        {"title": "CirPark", "start": "May 2011", "end": "Apr 2017"},
    ]
    result = _newest_first(rows, "start", "end")
    assert [r["title"] for r in result] == ["CirCarlife", "CirPark", "SQL Export", "PowerStudio"]


def test_newest_first_ongoing_is_newest():
    rows = [
        {"start": "Jan 2020", "end": "Dec 2022"},
        {"start": "Jan 2023", "end": ""},  # ongoing, no end date
    ]
    result = _newest_first(rows, "start", "end", ongoing_is_newest=True)
    assert result[0]["start"] == "Jan 2023"


# -- _format_description / paragraph reconstruction ----------------------


def test_format_description_splits_glued_sentences():
    # LinkedIn sometimes strips the paragraph break entirely, gluing the
    # period to the next capital letter.
    text = "First sentence.Second sentence."
    assert _format_description(text) == "First sentence.\n\nSecond sentence."


def test_format_description_splits_on_double_space():
    text = "First sentence.  Second sentence."
    assert _format_description(text) == "First sentence.\n\nSecond sentence."


def test_format_description_no_false_positive_on_acronyms():
    # Acronyms with slashes or no period shouldn't be split.
    text = "Protocols: TCP/IP, S32K, NFC."
    assert _format_description(text) == "Protocols: TCP/IP, S32K, NFC."


def test_format_description_single_paragraph_untouched():
    text = "Just one sentence with no break."
    assert _format_description(text) == text


# -- _format_duration ------------------------------------------------------


def test_format_duration_years_and_months():
    # Matches LinkedIn's own displayed duration for the same date range.
    assert _format_duration(datetime(2020, 12, 1), datetime(2026, 7, 1)) == "5 years 8 months"


def test_format_duration_with_leftover_months():
    assert _format_duration(datetime(2020, 1, 1), datetime(2021, 11, 1)) == "1 year 11 months"


def test_format_duration_exact_years():
    assert _format_duration(datetime(2020, 1, 1), datetime(2021, 12, 1)) == "2 years"


def test_format_duration_less_than_a_year():
    assert _format_duration(datetime(2024, 1, 1), datetime(2024, 3, 1)) == "3 months"


def test_format_duration_single_month_singular():
    assert _format_duration(datetime(2024, 1, 1), datetime(2024, 1, 1)) == "1 month"


# -- build_profile_section --------------------------------------------------


def test_build_profile_section_excludes_phone_includes_linkedin():
    profile_rows = [
        {
            "First Name": "Jane",
            "Last Name": "Doe",
            "Headline": "Software Engineer",
            "Geo Location": "Barcelona",
            "Summary": "Summary text.",
        }
    ]
    email_rows = [{"Email Address": "jane@example.com", "Primary": "Yes"}]

    result = build_profile_section(profile_rows, email_rows, "https://www.linkedin.com/in/jane-doe")

    assert "Jane Doe" in result
    assert "jane@example.com" in result
    assert "[LinkedIn](https://www.linkedin.com/in/jane-doe)" in result
    assert "phone" not in result.lower()


def test_build_profile_section_no_linkedin_url_omits_link():
    profile_rows = [{"First Name": "Jane", "Last Name": "Doe"}]
    result = build_profile_section(profile_rows, [], "")
    assert "LinkedIn" not in result


# -- build_experience_section: open-ended "Present" -------------------------


def test_build_experience_section_present_when_no_end_date():
    rows = [{"Company Name": "Acme", "Title": "Engineer", "Started On": "Dec 2020", "Finished On": ""}]
    result = build_experience_section(rows)
    assert "Present" in result


# -- build_projects_section: open-ended "Present" ---------------------------


def test_build_projects_section_present_when_no_end_date():
    rows = [{"Title": "EBOX TCU", "Started On": "Jul 2022", "Finished On": ""}]
    result = build_projects_section(rows)
    assert "Jul 2022 - Present" in result


def test_build_projects_section_keeps_real_end_date():
    rows = [{"Title": "ATOM TCU", "Started On": "Dec 2020", "Finished On": "Jun 2022"}]
    result = build_projects_section(rows)
    assert "Dec 2020 - Jun 2022" in result
    assert "Present" not in result


# -- build_education_section -------------------------------------------------


def test_build_education_section_includes_degree_and_dates():
    rows = [{"School Name": "UAB", "Degree Name": "Computer Science", "Start Date": "2003", "End Date": "2008"}]
    result = build_education_section(rows)
    assert "**Computer Science**" in result
    assert "*2003 - 2008*" in result


# -- build_skills_section: case-insensitive dedup ----------------------------


def test_build_skills_section_deduplicates_case_insensitively():
    rows = [{"Name": "Python"}, {"Name": "python"}, {"Name": "Git"}]
    result = build_skills_section(rows)
    assert result.count("Python") == 1
    assert "Git" in result


# -- build_languages_section: name normalization -----------------------------


def test_build_languages_section_translates_known_names():
    rows = [{"Name": "Catalán", "Proficiency": "Native or bilingual proficiency"}]
    result = build_languages_section(rows)
    assert "Catalan" in result
    assert "Catalán" not in result


# -- _find_own_linkedin_url ---------------------------------------------------


def test_find_own_linkedin_url_matches_recipient_row():
    zf = _zip_with_csvs(
        {
            "messages.csv": [
                {"TO": "Jane Doe", "RECIPIENT PROFILE URLS": "https://www.linkedin.com/in/jane-doe"},
                {"TO": "Someone Else", "RECIPIENT PROFILE URLS": "https://www.linkedin.com/in/someone-else"},
            ]
        }
    )
    assert _find_own_linkedin_url(zf, "Jane Doe") == "https://www.linkedin.com/in/jane-doe"


def test_find_own_linkedin_url_missing_file_returns_empty():
    zf = _zip_with_csvs({})
    assert _find_own_linkedin_url(zf, "Jane Doe") == ""


# -- build_cv_markdown: end-to-end over an in-memory zip ----------------------


def test_build_cv_markdown_end_to_end():
    zf = _zip_with_csvs(
        {
            "Profile.csv": [
                {
                    "First Name": "Jane",
                    "Last Name": "Doe",
                    "Headline": "Engineer",
                    "Geo Location": "Remote",
                    "Summary": "",
                }
            ],
            "Positions.csv": [
                {
                    "Company Name": "Acme",
                    "Title": "Engineer",
                    "Location": "Remote",
                    "Started On": "Jan 2020",
                    "Finished On": "",
                    "Description": "",
                }
            ],
            "Education.csv": [],
            "Certifications.csv": [],
            "Projects.csv": [],
            "Skills.csv": [{"Name": "Python"}],
            "Languages.csv": [],
            "Email Addresses.csv": [{"Email Address": "jane@example.com", "Primary": "Yes"}],
            "messages.csv": [],
        }
    )
    result = build_cv_markdown(zf)

    assert result.startswith("# Jane Doe")
    assert "## Experience" in result
    assert "### Acme" in result
    assert "## Skills" in result
    # Sections with no data are omitted entirely, not left as empty headers.
    assert "## Education" not in result
    assert "## Languages" not in result
