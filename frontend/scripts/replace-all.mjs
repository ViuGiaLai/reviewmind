import { readFileSync, writeFileSync } from "fs";

const path = "src/main.tsx";
let c = readFileSync(path, "utf8");

// Map emoji -> Lucide icon JSX
const map = {
  "\u{1F3AF}": '<Target size={14} />',
  "\u{1F527}": '<Wrench size={14} />',
  "\u{274C}": '<CircleX size={14} />',
  "\u{1F4E1}": '<Radio size={14} />',
  "\u{26F6}": '<Maximize size={14} />',
  "\u{1F44B}": '<Hand size={14} />',
  "\u{1F6E0}\uFE0F": '<Wrench size={14} />',
  "\u{1F4C8}": '<TrendingUp size={14} />',
  "\u{23F1}": '<Clock size={14} />',
  "\u{2600}": '<Sun size={14} />',
  "\u{1F319}": '<Moon size={14} />',
  "\u{1F3E0}": '<House size={14} />',
  "\u{1F41B}": '<Bug size={14} />',
  "\u{1F4E4}": '<Upload size={14} />',
  "\u{1F4D5}": '<BookX size={14} />',
  "\u{1F4D8}": '<BookOpen size={14} />',
  "\u{270F}": '<Pencil size={14} />',
  "\u{1F680}": '<Rocket size={14} />',
  "\u{1F504}": '<RefreshCw size={14} />',
  "\u{2696}": '<Scale size={14} />',
  "\u{1F5D1}": '<Trash2 size={14} />',
  "\u{1F441}": '<Eye size={14} />',
  "\u{1F7E0}": '<CircleAlert size={14} />',
  "\u{1F4BD}": '<FloppyDisk size={14} />',
};

// Pre-handle specific known patterns

// Severity emojis in dashboard stats
c = c.replace(
  /{ icon: "(\u{1F534}|\u{1F7E1}|\u{1F7E2}|\u{2705}|\u{1F4CC}|\u{1F4CA})", val: /gu,
  (m, emoji) => {
    const iconMap = {
      "\u{1F534}": '"\u{1F534}"',
      "\u{1F7E1}": '"\u{1F7E1}"',
      "\u{1F7E2}": '"\u{1F7E2}"',
      "\u{2705}": '"\u{2705}"',
      "\u{1F4CC}": '"\u{1F4CC}"',
      "\u{1F4CA}": '"\u{1F4CA}"',
    };
    return `{ icon: ${iconMap[emoji] || `"${emoji}"`}, val: `;
  }
);

// Replace all remaining emoji characters with span-wrapped Lucide icons
let result = "";
let i = 0;
while (i < c.length) {
  const cp = c.codePointAt(i);
  if (cp !== undefined && (
    (cp >= 0x1F300 && cp <= 0x1F9FF) ||
    (cp >= 0x2600 && cp <= 0x26FF) ||
    (cp >= 0x2700 && cp <= 0x27BF) ||
    cp === 0x2705 || cp === 0x274C
  )) {
    const emoji = String.fromCodePoint(cp);
    const next = i + (cp > 0xFFFF ? 2 : 1);
    // Check for variation selector
    const nextCp = c.codePointAt(next);
    let fullEmoji = emoji;
    let skip = next;
    if (nextCp === 0xFE0F) {
      fullEmoji += String.fromCodePoint(nextCp);
      skip = next + 1;
    }
    // Skip known severity/status emojis that are handled separately
    const skipEmojis = new Set(["\u{1F534}", "\u{1F7E1}", "\u{1F7E2}", "\u{26AA}"]);
    if (skipEmojis.has(emoji)) {
      result += emoji;
      i = skip;
      continue;
    }
    if (map[fullEmoji]) {
      result += `<span className="icon">${map[fullEmoji]}</span>`;
    } else if (map[emoji]) {
      result += `<span className="icon">${map[emoji]}</span>`;
    } else {
      // Keep as-is if no mapping
      result += emoji;
    }
    i = skip;
  } else {
    result += c[i];
    i++;
  }
}

// Only keep sevIcon-specific severity emojis in the function itself
// They are used as ReactNode return values

// Collect used icon names for import
const iconPattern = /<(\w+)\s+size=\{/g;
const usedIcons = new Set();
let match;
while ((match = iconPattern.exec(result)) !== null) {
  usedIcons.add(match[1]);
}

const iconList = [...usedIcons].sort();
const importLine = `import { ${iconList.join(", ")} } from "lucide-react";\n`;

// Update or add import
if (result.includes('from "lucide-react"')) {
  result = result.replace(/import \{ [^}]+ \} from "lucide-react";?\n?/, importLine);
} else {
  result = result.replace(
    /(import .+? from "[^"]+";\n)(?!.*import)/,
    "$1" + importLine
  );
}

writeFileSync(path, result, "utf8");
console.log("Done. Used icons:", iconList.length);
