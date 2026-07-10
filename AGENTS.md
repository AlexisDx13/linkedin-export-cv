# AGENTS

## Language

Code, comments, docstrings, commit messages and docs are all in English — this is a public repo.

## Workflow

Work on a branch, not directly on `main` — even for solo work. Commit as often as you want on the branch (granular commits make it easy to track what changed and to roll back a single step). When the task is done, squash the branch's commits into one with the final message (`git reset --soft <branch start>` + commit), then merge that single commit into `main` — since the branch is exactly one commit ahead, this is a fast-forward that reuses the commit as-is, with no new commit or duplicated message. `main` should never need a force-push: if you're tempted to amend or force-push something already merged to `main`, that's a sign the work should have stayed on a branch a little longer.

## Project structure

Two independent CLI commands (`src/linkedin_export_cv/zip_to_cv.py`, `src/linkedin_export_cv/cv_to_pdf.py`), each with a `main()` entry point wired in `pyproject.toml`. They're deliberately separate steps, not one pipeline: `zip-to-cv` output is meant to be reviewed and hand-edited before `cv-to-pdf` runs on it (see README's "Getting the export" note on LinkedIn's Russian-location export bug). Don't merge them into a single command.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Both modules are plain functions over dicts/strings with no hidden I/O beyond `zipfile`/`csv`, so most logic is unit-testable without a real LinkedIn export — see `tests/` for the in-memory-zip pattern. Add a test for any parsing/formatting change; several existing tests are direct regressions of bugs found during development (date tie-breaking, paragraph-reconstruction heuristics, sidebar section ordering) and exist specifically to keep them from coming back silently.

## Design decisions worth knowing before changing things

- No phone number in the generated CV — replaced by the LinkedIn profile link (inferred from `messages.csv`, since `Profile.csv` doesn't include it). Deliberate, not an oversight.
- Skills, Languages and Certifications render in the PDF sidebar in a fixed order (`SIDEBAR_ORDER` in `cv_to_pdf.py`), independent of their order in `cv.md`.
- The paragraph-reconstruction heuristic in `zip_to_cv.py` (`_PARAGRAPH_BREAK_RE`) is a patch over LinkedIn's own export quirks (it flattens paragraph breaks inconsistently), not general-purpose text processing — don't generalize it further without a concrete LinkedIn CSV sample showing the new case.
- PyPI releases are published via Trusted Publishing (OIDC, `.github/workflows/publish.yml`) — there is no API token anywhere, and there shouldn't be; if publishing ever seems to need one, something is misconfigured. The workflow triggers on a GitHub Release and is gated behind the `pypi` environment's required-reviewer approval, since PyPI versions are immutable once published and a Release is otherwise a point of no return.
