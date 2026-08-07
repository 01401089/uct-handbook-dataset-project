// Adds the Firebase (@uct.ac.za) auth gate to the built site:
//   - injects auth/config.json into auth/login.html -> build/login.html
//   - injects the project id into auth/_worker.js  -> build/_worker.js
// Skips (with a loud warning) while auth/config.json still holds the
// FILL_ME_IN placeholder, so an unconfigured deploy stays public rather
// than locking everyone out. Runs from `npm run deploy`.
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const cfg = JSON.parse(readFileSync(join(ROOT, 'auth', 'config.json'), 'utf8'));
delete cfg._comment;

if (!cfg.apiKey || cfg.apiKey === 'FILL_ME_IN') {
  console.warn(
    '\n!!! auth/config.json has no apiKey — deploying WITHOUT the auth gate.\n' +
    '!!! Fill in the Firebase Web API Key to enable @uct.ac.za-only access.\n'
  );
  process.exit(0);
}

const login = readFileSync(join(ROOT, 'auth', 'login.html'), 'utf8')
  .replace('__FIREBASE_CONFIG__', () => JSON.stringify(cfg));

const worker = readFileSync(join(ROOT, 'auth', '_worker.js'), 'utf8')
  .replaceAll('__FIREBASE_PROJECT_ID__', cfg.projectId)
  .replaceAll('__FIREBASE_PROJECT_NUMBER__', cfg.projectNumber || '')
  .replace('__LOGIN_HTML__', () => JSON.stringify(login));
writeFileSync(join(ROOT, 'build', '_worker.js'), worker);

console.log(`auth gate enabled: project ${cfg.projectId}, @uct.ac.za only`);
