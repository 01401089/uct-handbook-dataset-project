---
title: Method — why these numbers can be trusted
sidebar_position: 7
---

The full account is `docs/PROJECT-REPORT.md` in the repository; this page is
the condensed version a reviewer needs before quoting a number.

## Two layers, one provenance rule

The **as-printed layer** records exactly what the handbooks print — defects
included — for audit and replication. The **final-clean layer** (everything
this explorer shows) resolves those defects through documented rules and a
reviewable adjudication register. Every row of every table carries the
handbook edition and the PDF page it came from. Source PDFs are immutable;
outputs are never hand-edited; re-running one year or faculty provably cannot
alter another's rows.

## The ideal student

Handbooks list more than any student takes. Credit load and cost are computed
for a deterministic, documented selection: every core course; the
first-listed branch of any choice (alternates retained); elective slots at
their stated credits, priced at a median and always flagged as estimates;
minima taken exactly. It is a convention, not a behavioural claim — and it is
a boolean on every row, so "what if they took the other branch" is a filter,
not a re-count.

## Triangulated validation

<pre style="line-height:1.5">
   curriculum (courses + credits)  x  course fees   ->  computed year cost
        compared with                                   compared with
   the handbook's printed                      the fees book's published
   "Total credits per year"                    typical fee for that year
        and, summed across all study years, compared with
   the faculty rules' printed minimum credits for the whole degree
</pre>

The third leg — the **rules layer** — was extracted from the faculty-rules
sections (387 printed statements with page and verbatim quote). It dates the
credit re-think authoritatively and catches what per-year checks cannot: a
curriculum below its own faculty's floor, or a stated total the tables no
longer support.

## How discrepancies are resolved

| Rule | What it does | Confidence |
|:---|:---|:---|
| R0 | computed equals stated — nothing to do | high |
| R3 | a register entry applies (rationale + page evidence) | high |
| R1a | the gap exactly equals the non-taken choice branches — the printed total counted both | high |
| R2a | identical course set reconciles in ≥2 sibling editions | medium |
| R1b / R2b | misprint / extraction-gap detectors — file suggestions, never auto-resolve | — |
| R4 | nothing applies — carry computed, flag `unresolved`, queue for review | low |

"Computed" is the default because, where both sides can be tested, the rows
win: summing each taken course's fee reproduces UCT's own published
programme fees to the rand for most programmes. A **mismatch is a finding,
not an error** — most turn out to be defects in the books themselves, which
is precisely what a curriculum-review dataset should surface.

## Real (2025-rand) fees

Nominal fees rise ~4.3–5.8% per edition from price escalation alone. The
dataset derives its own deflator from the fees books: the median
year-over-year fee ratio across all course codes present in consecutive
editions (~3,900 matches per pair, spread of a few hundredths of a
percentage point), chained and rebased to 2025 = 1.0. Real series
(`v_fee_real`, and the "2025 rands" charts on the [fees](/fees) and
programme pages) divide nominal fees by this index — the correct series
for "fee income gain/loss", since credit changes are not proportional to
fee changes.

## Reading the labels

- **`no_anchor`** — Science/Humanities majors: no per-year total exists to
  reconcile against, by design. Never read a major's sum as a degree total.
- **`flat_annual` / `degree_flat`** — Law publishes one fee per stream,
  Science/Humanities one per degree: per-year fee divergence is structural.
- **`confidence`** — high (arithmetic or adjudicated), medium
  (cross-edition), low (default policy; see the
  [adjudication queue](/quality)).
- **Estimated fees** — elective-slot costs are median-based and carried
  separately, so exact-figure analyses can exclude them.

## Reproducing this site

```bash
python run_pipeline.py --years all        # rebuild the dataset from the PDFs
python analysis/build_database.py         # rebuild handbooks.duckdb
cd analysis/explorer && npm run sources && npm run dev
```
