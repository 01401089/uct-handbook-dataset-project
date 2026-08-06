// Regenerate docs/UCT-Handbook-Dataset-User-Manual.docx (the Word copy for
// circulation) from docs/USER-MANUAL.md whenever the manual changes.
// Usage, from the repo root:  node docs/make_user_manual_docx.js .
// Requires the `docx` npm package (npm install docx).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow,
  TableCell, WidthType, AlignmentType, TableOfContents, LevelFormat,
  ShadingType, BorderStyle,
} = require("docx");

const ROOT = process.argv[2] || ".";
const SRC = path.join(ROOT, "docs", "USER-MANUAL.md");
const OUT = path.join(ROOT, "docs", "UCT-Handbook-Dataset-User-Manual.docx");
const md = fs.readFileSync(SRC, "utf8").replace(/\r\n/g, "\n");

// ---------- inline markdown -> TextRuns ----------
function inlineRuns(text, base = {}) {
  // links: keep the text, drop internal .md/.csv targets
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
  const runs = [];
  const re = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    if (m[2] !== undefined) runs.push(new TextRun({ text: m[2], bold: true, ...base }));
    else if (m[3] !== undefined) runs.push(new TextRun({ text: m[3], italics: true, ...base }));
    else runs.push(new TextRun({ text: m[4], font: "Consolas", size: 18, ...base }));
    last = m.index + m[0].length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...base }));
  return runs.length ? runs : [new TextRun({ text: "", ...base })];
}

// ---------- block-level parse ----------
const lines = md.split("\n");
let i = 0;
// front matter: "# title", italic lines, "---"
while (i < lines.length && !/^## /.test(lines[i])) i++;

const children = [];
const spacing = { after: 120 };

// Title block (content mirrors USER-MANUAL.md's front matter)
const frontItalics = md.split("\n## ")[0].match(/\*([^*]+)\*/gs) || [];
const audience = (frontItalics[0] || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
const version = (frontItalics[1] || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
children.push(
  new Paragraph({ heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: "UCT Handbook Dataset", bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: "User Manual", size: 36 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: audience, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: version, italics: true })] }),
  new Paragraph({ children: [], pageBreakBefore: false, spacing: { after: 600 } }),
  new Paragraph({ children: [new TextRun({ text: "Contents", bold: true, size: 28 })], spacing: { after: 200 } }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
);

const USABLE = 9026; // A4 minus 1" margins, twips

function makeTable(rows) {
  // rows: array of arrays of cell strings; rows[0] is the header
  const ncol = Math.max(...rows.map(r => r.length));
  const maxLen = Array(ncol).fill(1);
  rows.forEach(r => r.forEach((c, j) => { maxLen[j] = Math.max(maxLen[j], Math.min(c.length, 60)); }));
  const total = maxLen.reduce((a, b) => a + b, 0);
  const widths = maxLen.map(l => Math.round((l / total) * USABLE));
  widths[ncol - 1] = USABLE - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  return new Table({
    columnWidths: widths,
    width: { size: USABLE, type: WidthType.DXA },
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0,
      children: Array.from({ length: ncol }, (_, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: "DEEAF6" } : undefined,
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [new Paragraph({ spacing: { after: 0 }, children: inlineRuns(r[j] || "", ri === 0 ? { bold: true } : {}) })],
      })),
    })),
  });
}

function splitTableRow(line) {
  return line.replace(/^\|/, "").replace(/\|\s*$/, "").split("|").map(c => c.trim());
}

while (i < lines.length) {
  const line = lines[i];
  if (/^## /.test(line)) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 }, children: inlineRuns(line.slice(3)) }));
    i++;
  } else if (/^### /.test(line)) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 140 }, children: inlineRuns(line.slice(4)) }));
    i++;
  } else if (/^\s*$/.test(line) || /^---\s*$/.test(line)) {
    i++;
  } else if (/^```/.test(line)) {
    i++;
    const code = [];
    while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
    i++; // closing fence
    code.forEach((c, k) => children.push(new Paragraph({
      spacing: { after: k === code.length - 1 ? 160 : 0 },
      children: [new TextRun({ text: c || " ", font: "Consolas", size: 17 })],
    })));
  } else if (/^\|/.test(line)) {
    const tbl = [];
    while (i < lines.length && /^\|/.test(lines[i])) { tbl.push(lines[i]); i++; }
    const rows = tbl.filter(r => !/^\|[\s:|-]+\|?\s*$/.test(r)).map(splitTableRow);
    children.push(makeTable(rows));
    children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  } else if (/^\d+\. /.test(line) || /^- /.test(line)) {
    const ordered = /^\d+\. /.test(line);
    while (i < lines.length && (ordered ? /^\d+\. /.test(lines[i]) : /^- /.test(lines[i]))) {
      let item = lines[i].replace(ordered ? /^\d+\. / : /^- /, "");
      i++;
      while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*[-|]/.test(lines[i])) {
        item += " " + lines[i].trim(); i++;
      }
      children.push(new Paragraph({
        numbering: { reference: ordered ? "ol" : "ul", level: 0 },
        spacing: { after: 80 },
        children: inlineRuns(item),
      }));
    }
    children.push(new Paragraph({ spacing: { after: 40 }, children: [] }));
  } else if (/^> /.test(line)) {
    let quote = line.slice(2);
    i++;
    while (i < lines.length && /^> ?/.test(lines[i])) { quote += " " + lines[i].replace(/^> ?/, ""); i++; }
    children.push(new Paragraph({ indent: { left: 480 }, spacing, children: inlineRuns(quote, { italics: true }) }));
  } else {
    // paragraph: join wrapped lines
    let para = line;
    i++;
    while (i < lines.length && lines[i].trim() && !/^(#|```|\||- |\d+\. |---|> )/.test(lines[i])) {
      para += " " + lines[i].trim(); i++;
    }
    children.push(new Paragraph({ spacing, alignment: AlignmentType.JUSTIFIED, children: inlineRuns(para) }));
  }
}

const doc = new Document({
  creator: "UCT Handbook Dataset Project",
  title: "UCT Handbook Dataset — User Manual",
  features: { updateFields: true },
  numbering: {
    config: [
      { reference: "ul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: "ol", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
    ],
  },
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 21 }, paragraph: { spacing: { line: 264 } } },
      title: { run: { size: 56 } },
      heading1: { run: { color: "2E74B5", size: 30, bold: true } },
      heading2: { run: { color: "2E74B5", size: 25, bold: true } },
    },
  },
  sections: [{ children }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log("wrote", OUT, buf.length, "bytes");
});
