import { readFileSync, writeFileSync } from "fs";

let c = readFileSync("src/main.tsx", "utf8");

const map = {
  "\u{1F534}": "Circle",      "\u{1F7E1}": "AlertCircle",
  "\u{1F7E2}": "CheckCircle",  "\u{26AA}": "Circle",
  "\u{1F7E0}": "AlertCircle",  "\u{274C}": "CircleX",
  "\u{2705}": "Check",        "\u{2713}": "Check",
  "\u{2716}": "X",            "\u{2715}": "X",
  "\u{1F3E0}": "House",       "\u{2699}\u{FE0F}": "Settings",
  "\u{2699}": "Settings",     "\u{1F4CC}": "Pin",
  "\u{1F50D}": "Search",      "\u{1F441}\u{FE0F}": "Eye",
  "\u{1F441}": "Eye",         "\u{26F6}": "Maximize",
  "\u{1F504}": "RefreshCw",   "\u{1F5D1}\u{FE0F}": "Trash2",
  "\u{1F5D1}": "Trash2",      "\u{1F4C4}": "FileText",
  "\u{1F4DD}": "FilePen",     "\u{1F4CB}": "ClipboardList",
  "\u{1F4CA}": "BarChart3",   "\u{1F4C8}": "TrendingUp",
  "\u{1F4C6}": "Calendar",    "\u{1F4C1}": "Folder",
  "\u{1F4D5}": "BookX",       "\u{1F4D8}": "BookOpen",
  "\u{1F4D6}": "Book",        "\u{1F4DA}": "BookOpen",
  "\u{1F4F0}": "Newspaper",   "\u{1F4DC}": "ScrollText",
  "\u{1F4E4}": "Upload",      "\u{1F4E1}": "Radio",
  "\u{1F3AF}": "Target",      "\u{1F527}": "Wrench",
  "\u{1F6E0}\u{FE0F}": "Wrench", "\u{1F6E0}": "Wrench",
  "\u{1F4A1}": "Lightbulb",   "\u{1F3C6}": "Trophy",
  "\u{1F680}": "Rocket",      "\u{23F1}": "Clock",
  "\u{1F44B}": "Hand",        "\u{1F393}": "GraduationCap",
  "\u{1F4BC}": "Briefcase",   "\u{1F916}": "Bot",
  "\u{1F41B}": "Bug",         "\u{1F3A8}": "Palette",
  "\u{1F52C}": "Microscope",  "\u{1F30D}": "Globe",
  "\u{2600}\u{FE0F}": "Sun",  "\u{2600}": "Sun",
  "\u{1F319}": "Moon",        "\u{26A1}": "Zap",
  "\u{1F512}": "Lock",        "\u{2696}": "Scale",
  "\u{1F4A0}": "Pill",        "\u{2795}": "Plus",
  "\u{2139}": "Info",         "\u{2298}": "Slash",
  "\u{1F4B0}": "Coins",       "\u{1F44D}": "ThumbsUp",
  "\u{2B50}": "Star",         "\u{1F525}": "Flame",
  "\u{1F389}": "PartyPopper", "\u{1F48E}": "Gem",
  "\u{1F3C1}": "Flag",        "\u{26A0}\u{FE0F}": "AlertTriangle",
  "\u{25B2}": "ChevronUp",    "\u{25BC}": "ChevronDown",
  "\u{21BB}": "RotateCw",     "\u{21BA}": "RotateCcw",
  "\u{1F4BD}": "FloppyDisk",  "\u{1F916}": "Bot",
  "\u{23F3}": "Hourglass",
};

// Process character by character
let result = "";
const usedIcons = new Set();

// First, handle sevIcon specially
const sevIconRegex = /function sevIcon[\s\S]*?\n\}/;
const sevIconMatch = c.match(sevIconRegex);
if (sevIconMatch) {
  usedIcons.add("TriangleAlert");
  usedIcons.add("AlertCircle");
  usedIcons.add("CheckCircle");
  usedIcons.add("Circle");
}

// Process the file
let inString = false;
let stringChar = "";
let i = 0;
while (i < c.length) {
  const ch = c[i];
  
  // Track string boundaries (roughly - won't handle template literals well)
  if (ch === '"' || ch === "'" || ch === "`") {
    if (!inString) {
      inString = true;
      stringChar = ch;
    } else if (ch === stringChar) {
      // Check not escaped
      let backslashes = 0;
      for (let j = i - 1; j >= 0 && c[j] === "\\"; j--) backslashes++;
      if (backslashes % 2 === 0) inString = false;
    }
  }
  
  // Check for emoji at current position (multibyte)
  const cp = c.codePointAt(i);
  if (cp && (
    (cp >= 0x1F300 && cp <= 0x1F9FF) ||
    (cp >= 0x2600 && cp <= 0x26FF) ||
    (cp >= 0x2700 && cp <= 0x27BF) ||
    (cp >= 0x2000 && cp <= 0x2BFF) ||
    cp === 0x2705 || cp === 0x274C || cp === 0x2713 || 
    cp === 0x2716 || cp === 0x2715 || cp === 0x2699 ||
    cp === 0x2696 || cp === 0x26A1 || cp === 0x26AA ||
    cp === 0x26F6 || cp === 0x23F1 || cp === 0x23F3 ||
    cp === 0x25B2 || cp === 0x25BC || cp === 0x21BB ||
    cp === 0x21BA || cp === 0x2139 || cp === 0x2298 ||
    cp === 0x2795 || cp === 0x2B50 || cp === 0x2600
  )) {
    const emoji = String.fromCodePoint(cp);
    const nextIdx = i + (cp > 0xFFFF ? 2 : 1);
    // Check for VS16
    let fullEmoji = emoji;
    let skip = nextIdx;
    if (c.codePointAt(nextIdx) === 0xFE0F) {
      fullEmoji += String.fromCodePoint(0xFE0F);
      skip = nextIdx + 1;
    }
    
    const iconName = map[fullEmoji] || map[emoji];
    if (iconName) {
      if (!inString) {
        usedIcons.add(iconName);
        // In JSX context, wrap with icon component
        result += `<${iconName} size={14} />`;
      } else {
        // Inside a string literal - keep the emoji but note that
        // we should replace icon map strings later
        result += emoji;
      }
    } else {
      result += emoji;
    }
    i = skip;
    continue;
  }
  
  result += ch;
  i++;
}

// Build import line
const iconList = [...usedIcons].sort();
const importLine = `import { ${iconList.join(", ")} } from "lucide-react";\n`;

if (result.includes('from "lucide-react"')) {
  result = result.replace(/import \{ [^}]+ \} from "lucide-react";?\n?/, importLine);
} else {
  result = result.replace(
    /(import .+? from "react";\n)/,
    "$1" + importLine
  );
}

writeFileSync("src/main.tsx", result, "utf8");
console.log(`Done! Icons used: ${iconList.length}`);
