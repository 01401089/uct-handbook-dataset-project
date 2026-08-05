"""Year-aware CSV writing shared by extractors and the assembler.

Processed tables accumulate multiple handbook years side by side (the `year`
column is part of every schema). Re-running the pipeline for one year must
replace exactly that year's rows and leave every other year byte-identical —
so pipeline re-runs are reviewable as git diffs touching one year only.
"""
import csv
from pathlib import Path


def write_year_rows(path: str | Path, rows: list[dict], year: int | str):
    """Replace `year`'s rows in the CSV at `path`, preserving other years.

    Existing rows of other years keep their stored order; the new rows are
    appended after them in extraction order. Field names come from the new
    rows (the current schema); older rows missing a newer column get "".
    """
    path = Path(path)
    year = str(year)
    if not rows:
        print(f"WARNING: no rows for {path.name} (year {year} unchanged)")
        return
    existing = []
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            existing = [r for r in csv.DictReader(f) if r.get("year") != year]

    fieldnames = list(rows[0].keys())
    for r in existing:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        w.writeheader()
        for r in existing + rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
