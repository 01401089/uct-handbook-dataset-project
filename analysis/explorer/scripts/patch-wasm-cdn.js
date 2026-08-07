// Cloudflare Pages rejects files over 25 MiB, and Evidence bundles the
// DuckDB-WASM engine (~33-39 MiB per flavour) as a static asset. This
// post-build step rewrites the two asset-URL chunks to load the SAME
// pinned version from jsDelivr (which serves CORS-enabled wasm), then
// removes the oversized local copies from build/. Run via `npm run deploy`.
import { readFileSync, writeFileSync, readdirSync, unlinkSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const version = JSON.parse(readFileSync(
  join(ROOT, 'node_modules', '@duckdb', 'duckdb-wasm', 'package.json'),
  'utf8'
)).version;

const chunksDir = join(ROOT, 'build', '_app', 'immutable', 'chunks');
const assetsDir = join(ROOT, 'build', '_app', 'immutable', 'assets');

let patched = 0;
for (const flavour of ['eh', 'mvp']) {
  const cdn = `https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@${version}/dist/duckdb-${flavour}.wasm`;
  for (const f of readdirSync(chunksDir)) {
    if (!f.startsWith(`duckdb-${flavour}.`) || !f.endsWith('.js')) continue;
    const p = join(chunksDir, f);
    const src = readFileSync(p, 'utf8');
    const out = src.replace(
      new RegExp(`"/_app/immutable/assets/(duckdb-${flavour}\\.[^"]+\\.wasm)"`),
      (_, asset) => {
        const local = join(assetsDir, asset);
        if (existsSync(local)) unlinkSync(local);
        return JSON.stringify(cdn);
      }
    );
    if (out !== src) {
      writeFileSync(p, out);
      patched++;
      console.log(`patched ${f} -> ${cdn}`);
    }
  }
}
if (patched === 0) {
  console.error('nothing patched — chunk layout may have changed; check build/_app/immutable/chunks');
  process.exit(1);
}
