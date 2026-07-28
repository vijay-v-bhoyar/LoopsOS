import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const src = join(root, "src");
const allowed = new Set([
  "src/styles/fluent2.tokens.css",
]);
const findings = [];
const patterns = [
  { name: "hex color", re: /#[0-9a-fA-F]{3,8}\b/g },
  { name: "rgb literal", re: /\brgba?\(/g },
  { name: "hsl literal", re: /\bhsla?\(/g },
  { name: "tailwind arbitrary value", re: /(?:bg|text|border|shadow|p|m|w|h|min|max|grid|rounded)-\[/g },
  { name: "inline font size", re: /fontSize\s*:/g },
  { name: "inline radius", re: /borderRadius\s*:/g },
  { name: "inline shadow", re: /boxShadow\s*:/g },
];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      walk(path);
      continue;
    }
    if (!/\.(css|ts|tsx)$/.test(name)) continue;
    const rel = relative(root, path).replaceAll("\\", "/");
    if (allowed.has(rel)) continue;
    const text = readFileSync(path, "utf8");
    const lines = text.split(/\r?\n/);
    lines.forEach((line, index) => {
      if (line.includes("f2-escape:")) return;
      for (const pattern of patterns) {
        pattern.re.lastIndex = 0;
        if (pattern.re.test(line)) {
          findings.push(`${rel}:${index + 1} ${pattern.name}`);
        }
      }
    });
  }
}

walk(src);

if (findings.length) {
  console.error("Design token violations:");
  findings.forEach((finding) => console.error(`- ${finding}`));
  process.exit(1);
}

console.log("Design token check passed");
