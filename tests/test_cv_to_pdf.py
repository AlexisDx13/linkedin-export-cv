from linkedin_export_cv.cv_to_pdf import _split_into_columns, convert_md_to_pdf

SAMPLE_CV = """# Jane Doe

**Senior Engineer**

Remote | jane@example.com | [LinkedIn](https://www.linkedin.com/in/jane-doe)

## Summary

A short summary.

## Experience

### Acme

**Engineer**
*Jan 2020 - Present*
*Remote*

Did engineering things.

---

## Certifications

### Some Certificate

**Issuer** | Jan 2022

## Skills

Python, Git

## Languages

- **English**: Native
"""


def test_split_into_columns_moves_skills_languages_certifications_to_sidebar():
    sidebar, main = _split_into_columns(SAMPLE_CV)

    assert "## Skills" in sidebar
    assert "## Languages" in sidebar
    assert "## Certifications" in sidebar
    assert "## Experience" not in sidebar
    assert "## Summary" not in sidebar


def test_split_into_columns_orders_sidebar_by_sidebar_order_not_source_order():
    # In SAMPLE_CV, Certifications appears before Skills/Languages in the
    # source, but the sidebar must still render Skills, then Languages,
    # then Certifications (SIDEBAR_ORDER) -- this is the exact bug found
    # when Certifications was moved into the sidebar.
    sidebar, _ = _split_into_columns(SAMPLE_CV)

    skills_pos = sidebar.index("## Skills")
    languages_pos = sidebar.index("## Languages")
    certifications_pos = sidebar.index("## Certifications")

    assert skills_pos < languages_pos < certifications_pos


def test_split_into_columns_location_goes_to_main_not_contact():
    sidebar, main = _split_into_columns(SAMPLE_CV)

    assert "Remote" in main  # location, under the headline
    assert "## Contact" in sidebar
    assert "jane@example.com" in sidebar
    assert "[LinkedIn]" in sidebar


def test_split_into_columns_main_keeps_name_and_experience():
    _, main = _split_into_columns(SAMPLE_CV)

    assert main.startswith("# Jane Doe")
    assert "## Experience" in main
    assert "### Acme" in main


def test_convert_md_to_pdf_smoke(tmp_path):
    output = tmp_path / "cv.pdf"
    ok = convert_md_to_pdf(SAMPLE_CV, output)

    assert ok is True
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
