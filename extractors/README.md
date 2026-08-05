# Extractors

One package per faculty (`com`, `ebe`, `fhs`, `hum`, `law`, `sci`) plus `fees`
for the student fees handbook. Faculties present their curricula differently, so
extraction logic is deliberately **not** shared across faculties — only
university-wide grammar lives in `common/`.

Each extractor package should provide:

- `extract.py` — entry point: reads the raw PDF(s) for a given `--year`, writes
  its output tables to `data/processed/`, and page dumps to `data/interim/`.
- `overrides.py` (or `.csv`) — explicit, reviewable corrections for genuine
  handbook typos (never hand-edit outputs).
- `README.md` — notes on that faculty's handbook layout and quirks.

Build order (see docs/commerce-review-and-proposal.md §5):
`fees` → `com` → validation harness → `ebe`/`law`/`fhs` → `sci`/`hum`.
