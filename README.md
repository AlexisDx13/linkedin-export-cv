# linkedin-export-cv

Generate a Markdown and PDF CV from a LinkedIn data export, reading the zip's CSVs directly.

## Why

LinkedIn is already the single source of truth for your professional history. Keeping a CV by hand in two formats — plain text for job boards that only accept text, and a PDF for everything else — means editing both every time something changes, and they drift out of sync. `linkedin-export-cv` re-derives both from the export instead: a clean `cv.md` straight from the relevant CSVs, and a styled PDF rendered from that same file.

## Getting the export

1. Go to your LinkedIn profile and open **Settings & Privacy**.
2. Go to **Data privacy**.
3. Click **Download your data**.
4. Select **"Download larger data archive, including connections, verifications, contacts, account history, and information we infer about you based on your profile and activity."**
5. Click **Request archive**.

LinkedIn emails you a download link once the archive is ready. Use the "larger" archive specifically: it's the one that includes `messages.csv`, needed to infer your own profile URL for the Contact section.

## Usage

```bash
pip install -e .

zip-to-cv Complete_LinkedInDataExport.zip
# review cv.md by hand: LinkedIn exports some locations in Russian
# (a known bug in their own export, not in this tool)

cv-to-pdf cv.md
```

`zip-to-cv` and `cv-to-pdf` are deliberately separate steps: you're expected to review and fix `cv.md` by hand in between.

Both commands take an optional `-o/--output` to pick a different path; by default `zip-to-cv` writes `cv.md` and `cv-to-pdf` writes a PDF next to its input with the same name (`cv.md` -> `cv.pdf`).

## What the CV includes

Profile, Experience, Education, Certifications, Projects, Skills, Languages — in that order, each section sorted newest-first where it applies. Experience shows each role's tenure duration (e.g. "5 years 8 months"), calculated the same way LinkedIn itself does. Contact info is your email and your LinkedIn profile link (inferred from `messages.csv`) — no phone number, it's too invasive for a CV that might end up pasted into a plain-text job board form. Anything from LinkedIn that isn't relevant to a CV (Member Since, Birth Date, Connections, endorsements, recommendations, etc.) is left out.

## PDF

`cv-to-pdf` uses `weasyprint` + `markdown` to render an A4 page with a full-height dark sidebar (Contact, Skills, Languages, Certifications) and a main column (Summary, Experience, Education, Projects), inspired by LinkedIn's own native profile PDF export — the one you get from your profile page by clicking **Resources → Save to PDF**.

## License

[GPL-2.0](LICENSE).
