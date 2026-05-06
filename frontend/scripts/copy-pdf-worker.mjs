// Copies the pdf.js worker out of node_modules into public/ so the browser can
// fetch it from a stable URL. Idempotent; safe to re-run.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");
const src = resolve(repoRoot, "node_modules/pdfjs-dist/build/pdf.worker.min.mjs");
const dstDir = resolve(repoRoot, "public");
const dst = resolve(dstDir, "pdf.worker.min.mjs");

if (!existsSync(src)) {
  console.warn(`[copy-pdf-worker] source not found, skipping: ${src}`);
  process.exit(0);
}
if (!existsSync(dstDir)) mkdirSync(dstDir, { recursive: true });
copyFileSync(src, dst);
console.log(`[copy-pdf-worker] ${src} -> ${dst}`);
