"""Batch pipeline runner — process one or more handbook years end to end.

For each year: fees extractor -> COM extractor -> main-dataset assembly ->
validation, then a per-year yield summary. Years already in the processed
tables are replaced row-for-row (merge-by-year), never duplicated.

Usage (from the repo root):
    python run_pipeline.py --years all          # every year with com+fees PDFs
    python run_pipeline.py --years 2021-2024    # inclusive range
    python run_pipeline.py --years 2021,2023    # explicit list
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "faculty-handbooks-undergraduate"

# Faculty extractors run when the year's PDF is present; fees always runs.
FACULTY_EXTRACTORS = [
    ("com", "com"), ("ebe", "ebe"), ("law", "law"), ("fhs", "fhs"),
]


def steps_for(year: int):
    steps = [("fees", [sys.executable, "-m", "extractors.fees.extract"])]
    for name, slug in FACULTY_EXTRACTORS:
        if (RAW / f"{year}-{slug}-ug.pdf").exists():
            steps.append((name, [sys.executable, "-m", f"extractors.{name}.extract"]))
    steps += [
        ("assemble", [sys.executable, str(ROOT / "build_main_dataset.py")]),
        ("validate", [sys.executable, str(ROOT / "validation" / "validate.py")]),
    ]
    return steps

# Final-clean layer: run for EVERY year in the dataset after the per-year
# loop, because cross-edition rules (R2) mean any year's change can
# legitimately update other years' final rows.
FINAL_STEPS = [
    ("finalise", [sys.executable, str(ROOT / "build_final_dataset.py")]),
    ("validate-final", [sys.executable, str(ROOT / "validation" / "validate_final.py")]),
]


def discover_years():
    """Years for which both the COM and the fees handbook are present."""
    com = {int(m.group(1)) for f in RAW.glob("*-com-ug.pdf")
           if (m := re.match(r"(\d{4})-com-ug\.pdf$", f.name))}
    fees = {int(m.group(1)) for f in RAW.glob("*-_fees.pdf")
            if (m := re.match(r"(\d{4})-_fees\.pdf$", f.name))}
    return sorted(com & fees)


def parse_years(spec: str):
    if spec == "all":
        return discover_years()
    if re.fullmatch(r"\d{4}-\d{4}", spec):
        a, b = map(int, spec.split("-"))
        available = set(discover_years())
        return [y for y in range(a, b + 1) if y in available]
    return [int(y) for y in spec.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", required=True,
                    help='"all", a range "2021-2026", or a list "2021,2023"')
    ap.add_argument("--skip-dump", action="store_true",
                    help="reuse existing interim page dumps")
    args = ap.parse_args()

    years = parse_years(args.years)
    if not years:
        raise SystemExit("no matching years found in faculty-handbooks-undergraduate/")
    print(f"processing years: {years}\n")

    results = {}
    for year in years:
        print(f"{'=' * 60}\nYEAR {year}\n{'=' * 60}")
        log = []
        year_steps = steps_for(year)
        for name, cmd in year_steps:
            full = cmd + ["--year", str(year)]
            if args.skip_dump and name in ("fees", "com", "ebe", "law", "fhs"):
                full.append("--skip-dump")
            r = subprocess.run(full, cwd=ROOT, capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip()
            print(f"--- {name}\n{out}")
            log.append((name, r.returncode, out))
            if r.returncode != 0:
                print(f"!!! {name} FAILED for {year} — stopping this year")
                break
        results[year] = log
        print()

    # ---- final-clean layer over ALL loaded years -------------------------
    import csv as _csv
    md = ROOT / "data" / "processed" / "main_dataset.csv"
    all_years = sorted({r["year"] for r in _csv.DictReader(
        open(md, encoding="utf-8-sig"))}) if md.exists() else []
    print(f"{'=' * 60}\nFINAL-CLEAN LAYER (all loaded years: {all_years})\n{'=' * 60}")
    final_ok = True
    for year in all_years:
        for name, cmd in FINAL_STEPS:
            r = subprocess.run(cmd + ["--year", str(year)], cwd=ROOT,
                               capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip()
            print(f"--- {name} {year}\n{out}")
            if r.returncode != 0:
                print(f"!!! {name} FAILED for {year}")
                final_ok = False
                break
    print()

    print(f"{'=' * 60}\nSUMMARY\n{'=' * 60}")
    failed = False
    for year, log in results.items():
        n_steps = len(steps_for(year))
        steps_ok = sum(1 for _, rc, _ in log if rc == 0)
        status = "OK" if steps_ok == n_steps else f"FAILED at {log[-1][0]}"
        failed = failed or steps_ok != n_steps
        print(f"{year}: {steps_ok}/{n_steps} steps — {status}")
    print(f"final-clean layer: {'OK' if final_ok else 'FAILED'}")
    sys.exit(1 if failed or not final_ok else 0)


if __name__ == "__main__":
    main()
