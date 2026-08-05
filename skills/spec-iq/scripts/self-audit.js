#!/usr/bin/env node
// ─────────────────────────────────────────────────────────────────────────────
// Self-audit for pre-filled PRDs. Run this BEFORE calling present_files.
//
// It converts the generated .docx to text and flags any leftover
// blank-template boilerplate that should have been replaced with real
// content or moved to a `gaps` entry. This is the check that would have
// caught the incident that motivated this script: a PRD that shipped with
// generic NFR content ("99.9% uptime SLA") and unfilled placeholders
// ("[Insert link]") on sections nobody had actually customized.
//
// Usage:  node scripts/self-audit.js /path/to/output.docx
// Exits 1 (and prints the offending lines) if any marker is still present.
// ─────────────────────────────────────────────────────────────────────────────
const { execSync } = require('child_process');
const fs = require('fs');

const docxPath = process.argv[2];
if (!docxPath || !fs.existsSync(docxPath)) {
  console.error('Usage: node scripts/self-audit.js /path/to/output.docx');
  process.exit(2);
}

// Markers that only make sense as unfilled defaults — if any of these
// survive into a pre-filled PRD, that section was never actually
// personalized. Keep this list in sync with the defaults in prd-content.js.
const MARKERS = [
  'Enter product / feature name',
  'Name, Title',
  '[Insert link',
  'YYYY-MM-DD',
  'Author Name',
  'Alex — Senior Account Manager',
  'Jordan — Operations Manager',
  'Alex Johnson',
  'Jane Smith',
  'API responses < 500ms',
  '99.9% uptime SLA',
  'AES-256',
  'WCAG 2.1 Level AA compliance',
  '10× current user volume',
  'GDPR, CCPA',
  'Chose React over Vue',
  'Do we support SSO at launch',
  'Monthly Active Users (MAU)',
  '[Product Name] PRD',
];

let text;
try {
  text = execSync(`pandoc -t plain "${docxPath}"`, { encoding: 'utf8', maxBuffer: 1024 * 1024 * 20 });
} catch (e) {
  console.error('Could not read docx via pandoc:', e.message);
  process.exit(2);
}

const hits = MARKERS.filter(m => text.includes(m));

if (hits.length === 0) {
  console.log('Self-audit passed — no leftover template boilerplate found.');
  process.exit(0);
}

console.error(`Self-audit FAILED — ${hits.length} section(s) still contain default template content:\n`);
hits.forEach(m => console.error(`  ✗ "${m}"`));
console.error('\nEach of these means a section was never personalized with real content from');
console.error('the source material. Either fill it in from the source in prd-content.js, or,');
console.error("if the source genuinely doesn't cover it, replace it with an explicit gap flag");
console.error('(add an entry to that section\'s `gaps` array) rather than leaving the default.');
process.exit(1);
