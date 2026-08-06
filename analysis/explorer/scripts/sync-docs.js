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
body { font: 16px/1.65 system-ui, -apple-system, 'Segoe UI', sans-serif;
  margin: 0; padding: 2rem 1rem 4rem; color: #0b0b0b; background: #fcfcfb; }
@media (prefers-color-scheme: dark) {
  body { color: #e8e8e3; background: #1a1a19; }
  a { color: #86b6ef; } .top a { color: #86b6ef; }
  code, pre { background: #26262450; }
  th { background: #26262480; }
  tr, th, td, hr, h1, h2 { border-color: #383835 !important; }
}
main { max-width: 46rem; margin: 0 auto; }
a { color: #256abf; }
h1, h2 { border-bottom: 1px solid #e1e0d9; padding-bottom: .3rem; }
h1 { font-size: 1.7rem; } h2 { font-size: 1.25rem; margin-top: 2.2rem; }
h3 { font-size: 1.05rem; margin-top: 1.8rem; }
code { font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: .875em; background: #0b0b0b0d; padding: .1em .3em; border-radius: 4px; }
pre { background: #0b0b0b0d; padding: .8rem 1rem; border-radius: 8px;
  overflow-x: auto; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; display: block; overflow-x: auto;
  font-size: .9rem; }
th, td { border: 1px solid #e1e0d9; padding: .35rem .6rem; text-align: left; }
th { background: #0b0b0b08; }
blockquote { border-left: 3px solid #009ADA; margin-left: 0;
  padding-left: 1rem; color: inherit; opacity: .9; }
.top { font-size: .85rem; margin-bottom: 1.5rem; }
.brand { display: inline-block; background: #00243A; color: #fff;
  font-weight: 800; padding: .1rem .5rem; border-radius: 6px;
  letter-spacing: .05em; margin-right: .5rem; }
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
<title>${title} — UCT Handbook Dataset</title>
<style>${CSS}</style></head>
<body><main>
<p class="top"><span class="brand">UCT</span>
<a href="/documentation">&larr; Back to the explorer's documentation page</a>
&nbsp;·&nbsp; source: <code>${path}</code></p>
${body}
</main></body></html>`);
  console.log(`synced ${path} -> project-docs/${slug}.html`);
}
// the Word copy of the user manual, for download
copyFileSync(join(ROOT, 'docs', 'UCT-Handbook-Dataset-User-Manual.docx'),
  join(OUT, 'UCT-Handbook-Dataset-User-Manual.docx'));
console.log('copied UCT-Handbook-Dataset-User-Manual.docx');
