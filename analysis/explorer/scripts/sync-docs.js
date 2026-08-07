// Render the repository's documentation to static HTML for the explorer's
// Documentation page. Runs automatically before `npm run dev` / `npm run
// build` (predev/prebuild hooks); output goes to static/project-docs/
// (gitignored — the markdown in the repo stays the source of truth).
import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { marked } from 'marked';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'static', 'project-docs');

// slug -> [repo path, title]
const DOCS = {
  'project-report': ['docs/PROJECT-REPORT.md', 'End-to-End Project Report'],
  'user-manual': ['docs/USER-MANUAL.md', 'User Manual (reviewers & deans)'],
  'replication': ['docs/REPLICATION.md', 'Replication Log & Hazard Catalogue'],
  'final-dataset-method': ['docs/FINAL-DATASET-METHOD.md', 'Final-Clean Dataset Method'],
  'design-proposal': ['docs/commerce-review-and-proposal.md', 'Original Design Document'],
  'readme': ['README.md', 'Repository README'],
  'dev-todo': ['DEV-TODO.md', 'Development TODO'],
  'analysis-readme': ['analysis/README.md', 'Analysis Layer & Explorer'],
  'resolutions-readme': ['resolutions/README.md', 'Adjudication Register Guide'],
  'extractors-readme': ['extractors/README.md', 'Extractors Guide'],
};

const CSS = `
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font: 16px/1.65 Roboto, system-ui, sans-serif;
  margin: 0; color: #14232f; background: #f4f6f8; }
@media (prefers-color-scheme: dark) {
  body { color: #dbe4ea; background: #0d161e; }
  a { color: #7fcdf0; }
  code, pre { background: #ffffff12; }
  th { background: #00243A; color: #fff; }
  tr, th, td, hr, h1, h2 { border-color: #2c3b47 !important; }
  .src { background: #12202b; }
}
.site-header { background: #00243A; color: #fff; border-bottom: 3px solid #0098DB;
  padding: .85rem 1.4rem; display: flex; gap: .9rem; align-items: baseline;
  flex-wrap: wrap; }
.site-header .uni { font-family: Montserrat, sans-serif; font-weight: 600;
  font-size: .66rem; letter-spacing: .2em; text-transform: uppercase;
  color: #0098DB; }
.site-header .name { font-family: Montserrat, sans-serif; font-weight: 300;
  font-size: 1.05rem; margin: 0; color: #fff; }
.site-header .name b { font-weight: 700; }
.site-header a.back { margin-left: auto; color: #7fcdf0; font-size: .8rem;
  text-decoration: none; }
.site-header a.back:hover { text-decoration: underline; }
.src { background: #e9eef2; font-size: .78rem; padding: .45rem 1.4rem;
  color: inherit; opacity: .8; }
.src code { background: none; padding: 0; }
main { max-width: 46rem; margin: 0 auto; padding: 1.5rem 1.2rem 4rem; }
a { color: #0074A8; }
h1, h2, h3 { font-family: Montserrat, sans-serif; letter-spacing: .01em; }
h1 { font-weight: 300; font-size: 1.7rem; border-bottom: 1px solid #d5dde3;
  padding-bottom: .35rem; }
h2 { font-weight: 600; font-size: 1.2rem; margin-top: 2.2rem;
  border-bottom: 1px solid #d5dde3; padding-bottom: .3rem; }
h3 { font-weight: 600; font-size: 1.02rem; margin-top: 1.8rem; }
code { font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: .875em; background: #0b0b0b0d; padding: .1em .3em; border-radius: 3px; }
pre { background: #0b0b0b0d; padding: .8rem 1rem; border-radius: 4px;
  overflow-x: auto; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; display: block; overflow-x: auto;
  font-size: .9rem; }
th, td { border: 1px solid #d5dde3; padding: .35rem .6rem; text-align: left; }
th { background: #00243A; color: #fff; font-family: Montserrat, sans-serif;
  font-weight: 600; font-size: .72rem; letter-spacing: .06em;
  text-transform: uppercase; }
blockquote { border-left: 3px solid #0098DB; margin-left: 0;
  padding-left: 1rem; opacity: .9; }
`;

// rewrite cross-links between the synced documents to their html slugs
function rewriteLinks(md) {
  for (const [slug, [path]] of Object.entries(DOCS)) {
    const base = path.split('/').pop().replace(/\./g, '\\.');
    md = md.replace(new RegExp(`\\((?:\\.\\./)*(?:docs/)?${base}(#[^)]*)?\\)`, 'g'),
      `(${slug}.html$1)`);
  }
  return md;
}

mkdirSync(OUT, { recursive: true });
for (const [slug, [path, title]] of Object.entries(DOCS)) {
  const md = rewriteLinks(readFileSync(join(ROOT, path), 'utf8'));
  const body = marked.parse(md, { gfm: true });
  writeFileSync(join(OUT, `${slug}.html`), `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title} — UCT Faculty Handbook Explorer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;600;700&family=Roboto:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" href="/favicon.ico" sizes="16x16">
<style>${CSS}</style></head>
<body>
<header class="site-header">
  <img src="/uct-official-dark.svg" alt="University of Cape Town" height="26" style="align-self:center;">
  <p class="name"><b>Faculty Handbook</b> Explorer — documentation</p>
  <a class="back" href="/documentation">&larr; all documents</a>
</header>
<div class="src">Source: <code>${path}</code> — regenerated from the repository markdown on every build</div>
<main>
${body}
</main></body></html>`);
  console.log(`synced ${path} -> project-docs/${slug}.html`);
}
// the Word copy of the user manual, for download
copyFileSync(join(ROOT, 'docs', 'UCT-Handbook-Dataset-User-Manual.docx'),
  join(OUT, 'UCT-Handbook-Dataset-User-Manual.docx'));
console.log('copied UCT-Handbook-Dataset-User-Manual.docx');
