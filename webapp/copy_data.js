import fs from 'fs';
import path from 'path';

const WEBAPP_DIR = path.resolve(process.cwd());
const PROJECT_DIR = path.resolve(WEBAPP_DIR, '..');
const PUBLIC_DIR = path.join(WEBAPP_DIR, 'public');

const DATA_SRC = path.join(PROJECT_DIR, 'data', 'processed');
const DOCS_SRC = path.join(PROJECT_DIR, 'docs');

const DATA_DEST = path.join(PUBLIC_DIR, 'data');
const DOCS_DEST = path.join(PUBLIC_DIR, 'docs');

// Create directories if they don't exist
if (!fs.existsSync(DATA_DEST)) fs.mkdirSync(DATA_DEST, { recursive: true });
if (!fs.existsSync(DOCS_DEST)) fs.mkdirSync(DOCS_DEST, { recursive: true });

function copyDirContent(src, dest) {
    if (!fs.existsSync(src)) return;
    const files = fs.readdirSync(src);
    for (const file of files) {
        const srcFile = path.join(src, file);
        const destFile = path.join(dest, file);
        if (fs.statSync(srcFile).isFile()) {
            fs.copyFileSync(srcFile, destFile);
        }
    }
}

console.log('Copying CSV data to public/data...');
copyDirContent(DATA_SRC, DATA_DEST);

console.log('Copying markdown docs to public/docs...');
copyDirContent(DOCS_SRC, DOCS_DEST);

console.log('Copy complete.');
