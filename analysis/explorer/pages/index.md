---
title: "UCT Faculty Handbook Explorer: Change in Credit and Cost Tracker"
hide_title: true
---

```sql counts
SELECT *,
       (n_consistent + n_resolved)
         / nullif(spec_years - n_no_anchor, 0)::double AS reconciled_share
FROM handbooks.counts
```

<div style="margin:1.2rem 0 2rem;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; font-size:.72rem; letter-spacing:.2em; text-transform:uppercase; color:#0098DB; margin:0 0 .4rem;">University of Cape Town</p>
  <h1 style="font-family:Montserrat,sans-serif; font-weight:300; font-size:2rem; margin:0 0 .3rem; letter-spacing:.01em;"><b style="font-weight:700;">Faculty Handbook</b> Explorer</h1>
  <p style="font-size:1.05rem; opacity:.75; margin:0 0 1rem;">Change in Credit and Cost Tracker · handbook editions 2021–2026</p>
  <p style="max-width:44rem; margin:0;">
    UCT is re-thinking curriculum credit loads. This tool turns six editions
    of every faculty's undergraduate handbook — and the student fees books —
    into an explorable dataset, so you can see exactly how credit loads and
    costs have moved, programme by programme. <b>Every number traces back to
    the printed page it came from.</b>
  </p>
</div>

## Three questions this tool answers

<Grid cols=3 gapSize=md>

<a href="/trends" style="display:block; border:1px solid rgba(128,128,128,.3); border-top:3px solid #0098DB; border-radius:8px; padding:1rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:#0098DB; margin:0 0 .35rem;">Credits</p>
  <p style="font-weight:600; margin:0 0 .3rem;">How many credits does a student actually carry — and how has that changed?</p>
  <p style="font-size:.85rem; opacity:.65; margin:0;">Browse per-programme trend cards with the change from 2021 to the 2025 baseline.</p>
</a>

<a href="/fees" style="display:block; border:1px solid rgba(128,128,128,.3); border-top:3px solid #0098DB; border-radius:8px; padding:1rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:#0098DB; margin:0 0 .35rem;">Cost</p>
  <p style="font-weight:600; margin:0 0 .3rem;">What does that credit load cost — in real terms?</p>
  <p style="font-size:.85rem; opacity:.65; margin:0;">Computed fees checked against UCT's published figures, and restated in constant 2025 rands.</p>
</a>

<a href="/credit-rethink" style="display:block; border:1px solid rgba(128,128,128,.3); border-top:3px solid #0098DB; border-radius:8px; padding:1rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:#0098DB; margin:0 0 .35rem;">Rules</p>
  <p style="font-weight:600; margin:0 0 .3rem;">What must a whole degree total — and when did the requirement change?</p>
  <p style="font-size:.85rem; opacity:.65; margin:0;">Degree trajectories drawn against the minimum-credit floors printed in the faculty rules.</p>
</a>

</Grid>

## The dataset at a glance

<Grid cols=3 gapSize=md>

<div style="border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.9rem 1.1rem;">
  <p style="margin:0; font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; opacity:.6;">Coverage</p>
  <p style="margin:.2rem 0 0; font-size:1.4rem; font-weight:700;"><Value data={counts} column=faculties /> faculties · <Value data={counts} column=editions /> editions</p>
  <p style="margin:.15rem 0 0; font-size:.82rem; opacity:.65;">Every UCT undergraduate handbook plus the fees books, 2021–2026</p>
</div>

<div style="border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.9rem 1.1rem;">
  <p style="margin:0; font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; opacity:.6;">Curriculum as data</p>
  <p style="margin:.2rem 0 0; font-size:1.4rem; font-weight:700;"><Value data={counts} column=curriculum_records fmt='#,##0' /> records</p>
  <p style="margin:.15rem 0 0; font-size:.82rem; opacity:.65;"><Value data={counts} column=register_entries fmt='#,##0' /> programmes &amp; majors · <Value data={counts} column=rule_statements /> printed degree rules</p>
</div>

<div style="border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.9rem 1.1rem;">
  <p style="margin:0; font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; opacity:.6;">Verified</p>
  <p style="margin:.2rem 0 0; font-size:1.4rem; font-weight:700;"><Value data={counts} column=reconciled_share fmt=pct0 /> reconciled</p>
  <p style="margin:.15rem 0 0; font-size:.82rem; opacity:.65;">Programme-years matching their printed totals or resolved by documented rules — <a href="/method">how we check</a></p>
</div>

</Grid>

## Explore

<Grid cols=2 gapSize=md>

<a href="/trends" style="display:block; border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.85rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; margin:0;">Trend cards <span style="color:#0098DB;">→</span></p>
  <p style="font-size:.85rem; opacity:.65; margin:.2rem 0 0;">One card per programme: credits and real-2025 cost, with the 2021→2025 change. Filter by code, department or name.</p>
</a>

<a href="/credit-rethink" style="display:block; border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.85rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; margin:0;">The credit re-think <span style="color:#0098DB;">→</span></p>
  <p style="font-size:.85rem; opacity:.65; margin:.2rem 0 0;">Flagship degree trajectories against the printed rules floors, and every floor that moved between editions.</p>
</a>

<a href="/faculties" style="display:block; border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.85rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; margin:0;">Faculties <span style="color:#0098DB;">→</span></p>
  <p style="font-size:.85rem; opacity:.65; margin:.2rem 0 0;">One page per faculty: its programmes, reconciliation record and open findings.</p>
</a>

<a href="/programmes" style="display:block; border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.85rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; margin:0;">Programmes &amp; majors <span style="color:#0098DB;">→</span></p>
  <p style="font-size:.85rem; opacity:.65; margin:.2rem 0 0;">Drill into any programme: year-by-year credits, fees, and the ideal student's course lists with page references.</p>
</a>

<a href="/quality" style="display:block; border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.85rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; margin:0;">Data quality &amp; adjudication <span style="color:#0098DB;">→</span></p>
  <p style="font-size:.85rem; opacity:.65; margin:.2rem 0 0;">The reconciliation ledger, handbook defects surfaced as findings, and the review queue.</p>
</a>

<a href="/documentation" style="display:block; border:1px solid rgba(128,128,128,.3); border-radius:8px; padding:.85rem 1.1rem; text-decoration:none; color:inherit;">
  <p style="font-family:Montserrat,sans-serif; font-weight:600; margin:0;">Documentation <span style="color:#0098DB;">→</span></p>
  <p style="font-size:.85rem; opacity:.65; margin:.2rem 0 0;">The full project library: user manual, method, replication log and the end-to-end report.</p>
</a>

</Grid>

<p style="margin-top:2rem; font-size:.85rem; opacity:.65;">
Built on a fully documented pipeline: source PDFs are immutable, extraction
is deterministic, and every value carries its handbook edition and page.
Read <a href="/method">why these numbers can be trusted</a>, or start from
the <a href="/documentation">documentation library</a>.
</p>
