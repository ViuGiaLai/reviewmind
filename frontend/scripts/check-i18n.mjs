import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const sourceRoot = path.join(root, "src");
const locales = {
  en: JSON.parse(fs.readFileSync(path.join(sourceRoot, "locales/en.json"), "utf8")),
  vi: JSON.parse(fs.readFileSync(path.join(sourceRoot, "locales/vi.json"), "utf8")),
};

function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? files(target) : /\.(ts|tsx)$/.test(entry.name) ? [target] : [];
  });
}
function hasKey(object, key) {
  return key.split(".").every(part => {
    if (!object || !Object.prototype.hasOwnProperty.call(object, part)) return false;
    object = object[part];
    return true;
  });
}
function flatten(object, prefix = "") {
  return Object.entries(object).flatMap(([key, value]) => {
    const pathKey = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === "object" ? flatten(value, pathKey) : [pathKey];
  });
}

const usages = [];
const literalCall = /\bt\s*\(\s*(["'])([^"'\\]*(?:\\.[^"'\\]*)*)\1/g;
for (const file of files(sourceRoot)) {
  const source = fs.readFileSync(file, "utf8");
  for (const match of source.matchAll(literalCall)) {
    const line = source.slice(0, match.index).split("\n").length;
    usages.push({ key: match[2], file, line });
  }
}

const missing = [];
for (const usage of usages) {
  for (const [language, catalog] of Object.entries(locales)) {
    if (!hasKey(catalog, usage.key)) missing.push({ ...usage, language });
  }
}
const enKeys = new Set(flatten(locales.en));
const viKeys = new Set(flatten(locales.vi));
for (const key of enKeys) if (!viKeys.has(key)) missing.push({ key, file: path.join(sourceRoot, "locales/vi.json"), line: 1, language: "vi" });
for (const key of viKeys) if (!enKeys.has(key)) missing.push({ key, file: path.join(sourceRoot, "locales/en.json"), line: 1, language: "en" });

if (missing.length) {
  for (const item of missing) console.error(`${path.relative(root, item.file)}:${item.line} missing ${item.language}.${item.key}`);
  process.exit(1);
}
console.log(`i18n OK: ${new Set(usages.map(item => item.key)).size} literal keys; en/vi catalogs are aligned`);