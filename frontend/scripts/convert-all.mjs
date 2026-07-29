import { readFileSync, writeFileSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, "..", "src");

// Emoji -> Lucide icon name mapping
const EMOJI_MAP = {
  "\u{1F534}": "Circle",         "\u{1F7E1}": "AlertCircle",
  "\u{1F7E2}": "CheckCircle",    "\u{26AA}": "Circle",
  "\u{1F7E0}": "AlertCircle",    "\u{274C}": "CircleX",
  "\u{2705}": "Check",           "\u{2713}": "Check",
  "\u{2716}": "X",               "\u{2715}": "X",
  "\u{1F3E0}": "House",          "\u{2699}\u{FE0F}": "Settings",
  "\u{2699}": "Settings",        "\u{1F4CC}": "Pin",
  "\u{1F50D}": "Search",         "\u{1F441}\u{FE0F}": "Eye",
  "\u{1F441}": "Eye",            "\u{26F6}": "Maximize",
  "\u{1F504}": "RefreshCw",      "\u{1F5D1}\u{FE0F}": "Trash2",
  "\u{1F5D1}": "Trash2",         "\u{1F4C4}": "FileText",
  "\u{1F4DD}": "FilePen",        "\u{1F4CB}": "ClipboardList",
  "\u{1F4CA}": "BarChart3",      "\u{1F4C8}": "TrendingUp",
  "\u{1F4C6}": "Calendar",       "\u{1F4C1}": "Folder",
  "\u{1F4D5}": "BookX",          "\u{1F4D8}": "BookOpen",
  "\u{1F4D6}": "Book",           "\u{1F4DA}": "BookOpen",
  "\u{1F4F0}": "Newspaper",      "\u{1F4DC}": "ScrollText",
  "\u{1F4E4}": "Upload",         "\u{1F4E1}": "Radio",
  "\u{1F3AF}": "Target",         "\u{1F527}": "Wrench",
  "\u{1F6E0}\u{FE0F}": "Wrench", "\u{1F6E0}": "Wrench",
  "\u{1F4A1}": "Lightbulb",      "\u{1F3C6}": "Trophy",
  "\u{1F680}": "Rocket",         "\u{23F1}": "Clock",
  "\u{1F44B}": "Hand",           "\u{1F393}": "GraduationCap",
  "\u{1F4BC}": "Briefcase",      "\u{1F916}": "Bot",
  "\u{1F41B}": "Bug",            "\u{1F3A8}": "Palette",
  "\u{1F52C}": "Microscope",     "\u{1F30D}": "Globe",
  "\u{2600}\u{FE0F}": "Sun",     "\u{2600}": "Sun",
  "\u{1F319}": "Moon",           "\u{26A1}": "Zap",
  "\u{1F512}": "Lock",           "\u{2696}": "Scale",
  "\u{1F4A0}": "Pill",           "\u{2795}": "Plus",
  "\u{2139}": "Info",            "\u{2298}": "Slash",
  "\u{2B50}": "Star",            "\u{1F525}": "Flame",
  "\u{1F389}": "PartyPopper",    "\u{25B2}": "ChevronUp",
  "\u{25BC}": "ChevronDown",     "\u{21BB}": "RotateCw",
  "\u{21BA}": "RotateCcw",       "\u{1F4BD}": "FloppyDisk",
  "\u{23F3}": "Hourglass",       "\u{1F44D}": "ThumbsUp",
  "\u{1F48E}": "Gem",            "\u{1F4B0}": "Coins",
  "\u{1F6A9}": "Flag",           "\u{1F3C1}": "Flag",
  "\u{1F4CD}": "MapPin",         "\u{1F44E}": "ThumbsDown",
  "\u{1F381}": "Gift",           "\u{1F4DB}": "Database",
  "\u{1F3B5}": "Music",          "\u{2191}": "ArrowUp",
  "\u{2193}": "ArrowDown",       "\u{2197}": "ArrowUpRight",
  "\u{2198}": "ArrowDownRight",  "\u{002A}": "Asterisk",
  "\u{1F511}": "Key",            "\u{1F4AD}": "ThoughtBubble",
  "\u{1F4AC}": "MessageCircle",  "\u{1F4E2}": "Bell",
  "\u{2757}": "AlertTriangle",   "\u{26A0}\u{FE0F}": "AlertTriangle",
};

const smileyMap = {
  "\u{1F600}": "Smile", "\u{1F603}": "Smile", "\u{1F604}": "Smile",
  "\u{1F60A}": "Smile", "\u{1F609}": "Wink",  "\u{1F60D}": "Heart",
  "\u{1F618}": "Heart", "\u{1F61C}": "Smile", "\u{1F61E}": "Frown",
  "\u{1F622}": "Frown", "\u{1F62D}": "Frown", "\u{1F631}": "Frown",
};

Object.assign(EMOJI_MAP, smileyMap);

// Build emoji regex
function buildEmojiRegex() {
  const emojis = Object.keys(EMOJI_MAP);
  // Sort by length descending to match longer sequences first
  emojis.sort((a, b) => b.length - a.length);
  const pattern = emojis.map(e => {
    return [...e].map(ch => {
      const cp = ch.codePointAt(0);
      if (cp > 0xFFFF) {
        return `\\u${cp.toString(16).padStart(8, "0")}`;
      }
      return `\\u${cp.toString(16).padStart(4, "0")}`;
    }).join("");
  }).join("|");
  return new RegExp(pattern, "gu");
}

const EMOJI_RE = buildEmojiRegex();

function processFile(filePath) {
  let c = readFileSync(filePath, "utf8");
  const usedIcons = new Set();
  let modified = false;

  // Check if file has any emojis
  if (!EMOJI_RE.test(c)) return { modified: false, usedIcons: [] };
  EMOJI_RE.lastIndex = 0;

  // Replace emojis - simple approach: replace all emojis with icon components
  c = c.replace(EMOJI_RE, (match) => {
    const iconName = EMOJI_MAP[match];
    if (!iconName) return match;
    usedIcons.add(iconName);
    modified = true;
    return `<${iconName} size={14} />`;
  });

  if (!modified) return { modified: false, usedIcons: [] };

  // Add or update lucide-react import
  const iconList = [...usedIcons].sort();
  const importLine = `import { ${iconList.join(", ")} } from "lucide-react";\n`;

  if (c.includes('from "lucide-react"')) {
    c = c.replace(/import \{ [^}]+ \} from "lucide-react";?\n?/, importLine);
  } else {
    // Find the last react import and add after it
    const match = c.match(/^(import .+? from "(?:react|react-dom\/\w+)";\n?)/m);
    if (match) {
      const idx = match.index + match[0].length;
      c = c.slice(0, idx) + "\n" + importLine + c.slice(idx);
    } else {
      // Add at the very top
      c = importLine + c;
    }
  }

  writeFileSync(filePath, c, "utf8");
  return { modified: true, usedIcons: iconList };
}

// Process all TSX files
const files = [
  join(srcDir, "main.tsx"),
  join(srcDir, "components", "QualityInsights.tsx"),
  join(srcDir, "components", "IssueInspector.tsx"),
  join(srcDir, "components", "ReviewTimeline.tsx"),
  join(srcDir, "components", "RuleDistributionChart.tsx"),
  join(srcDir, "components", "DiffViewer.tsx"),
];

for (const file of files) {
  const result = processFile(file);
  if (result.modified) {
    console.log(`✅ ${file.replace(srcDir, "src")}: ${result.usedIcons.length} icons`);
  } else {
    console.log(`➖ ${file.replace(srcDir, "src")}: no changes`);
  }
}
