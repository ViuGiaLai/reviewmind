import { readFileSync, writeFileSync } from "fs";

const EMOJI_MAP = {
  "🔴": '<TriangleAlert size={14} />',
  "🟡": '<AlertCircle size={14} />',
  "🟢": '<CheckCircle size={14} />',
  "⚪": '<Circle size={14} />',
  "✅": '<Check size={14} />',
  "🔍": '<Search size={14} />',
  "📄": '<FileText size={14} />',
  "📊": '<BarChart3 size={14} />',
  "📝": '<FilePen size={14} />',
  "📌": '<Pin size={14} />',
  "🎯": '<Target size={14} />',
  "⏱": '<Clock size={14} />',
  "🤖": '<Bot size={14} />',
  "🎨": '<Palette size={14} />',
  "📋": '<ClipboardList size={14} />',
  "💡": '<Lightbulb size={14} />',
  "🏆": '<Trophy size={14} />',
  "🎓": '<GraduationCap size={14} />',
  "💼": '<Briefcase size={14} />',
  "📖": '<Book size={14} />',
  "📰": '<Newspaper size={14} />',
  "📁": '<Folder size={14} />',
  "📦": '<Package size={14} />',
  "⚡": '<Zap size={14} />',
  "📘": '<BookOpen size={14} />',
  "📚": '<BookOpen size={14} />',
  "🔬": '<Microscope size={14} />',
  "💻": '<Monitor size={14} />',
  "🌍": '<Globe size={14} />',
  "💊": '<Pill size={14} />',
  "👁️": '<Eye size={14} />',
  "📜": '<ScrollText size={14} />',
  "🔒": '<Lock size={14} />',
  "🎭": '<MaskedIcon size={14} />',
  "✓": '<Check size={12} />',
  "▲": '<ChevronUp size={14} />',
  "▼": '<ChevronDown size={14} />',
  "⬆": '<ArrowUp size={14} />',
  "⬇": '<ArrowDown size={14} />',
  "↺": '<RotateCcw size={14} />',
  "↻": '<RotateCw size={14} />',
  "⛶": '<Maximize size={14} />',
  "ℹ️": '<Info size={14} />',
  "⊘": '<Slash size={14} />',
  "➕": '<Plus size={14} />',
  "✗": '<X size={14} />',
  "✕": '<X size={14} />',
  "☆": '<Star size={14} />',
};

const ICON_IMPORTS = new Set();
for (const [_, replacement] of Object.entries(EMOJI_MAP)) {
  const match = replacement.match(/<(\w+)/);
  if (match) ICON_IMPORTS.add(match[1]);
}

const path = "src/main.tsx";
let content = readFileSync(path, "utf8");

// Build import line
const importNames = [...ICON_IMPORTS].sort();
const importLine = `import { ${importNames.join(", ")} } from "lucide-react";\n`;

// Replace import
content = content.replace(
  /import\s+\{[^}]*\}\s+from\s+"lucide-react";?\s*\n?/,
  importLine
);

// If no lucide-react import exists, add it after the last react import
if (!content.includes('from "lucide-react"')) {
  content = content.replace(
    /(import\s+.*?from\s+"[^"]*";\n)(?!.*import)/,
    (match) => match + importLine
  );
}

// Wrap emoji replacements in <span> for inline display
// Replace emojis - for JSX text content, wrap in span
for (const [emoji, jsx] of Object.entries(EMOJI_MAP)) {
  // Escape special regex chars
  const escaped = emoji.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // In JSX context (inside tags, not inside strings)
  content = content.replace(new RegExp(escaped, "g"), (match, offset) => {
    // Check if we're inside a string or comment
    const before = content.slice(Math.max(0, offset - 20), offset);
    if (before.includes('"') && !before.includes('+')) return match; // skip if inside string
    return `<span className="icon">${jsx}</span>`;
  });
}

// Special handling for sevIcon function - return components instead of strings
content = content.replace(
  'function sevIcon(s: string) { return { high: "🔴", medium: "🟡", low: "🟢" }[s] ?? "⚪"; }',
  `function sevIcon(s: string) {
  const icons: Record<string, React.ReactNode> = { high: <TriangleAlert size={16} />, medium: <AlertCircle size={16} />, low: <CheckCircle size={16} /> };
  return icons[s] ?? <Circle size={16} />;
}`
);

// Handle emojis in string concatenations
// Replace in icon maps
content = content.replace(
  /const icons: Record<string, string> = \{ academic: "🎓", business: "💼", sop: "📋", thesis: "📖", journal: "📰" \};/,
  `const icons: Record<string, React.ReactNode> = { academic: <GraduationCap size={18} />, business: <Briefcase size={18} />, sop: <ClipboardList size={18} />, thesis: <Book size={18} />, journal: <Newspaper size={18} /> };`
);

content = content.replace(
  'const icon = icons[profile.id] || "📁";',
  `const icon = icons[profile.id] || <Folder size={18} />;`
);

content = content.replace(
  /const icons: Record<string, string> = \{ ieee: "⚡", apa: "📘", acm: "💻", nature: "🔬", springer: "📚", elsevier: "📖", iso9001: "✅", fda: "💊", who: "🌍" \};/,
  `const icons: Record<string, React.ReactNode> = { ieee: <Zap size={18} />, apa: <BookOpen size={18} />, acm: <Monitor size={18} />, nature: <Microscope size={18} />, springer: <BookOpen size={18} />, elsevier: <Book size={18} />, iso9001: <Check size={18} />, fda: <Pill size={18} />, who: <Globe size={18} /> };`
);

content = content.replace(
  '<div className="pack-card-icon">{icons[pack.id] || "📦"}</div>',
  `<div className="pack-card-icon">{icons[pack.id] || <Package size={18} />}</div>`
);

// Pipeline icons
content = content.replace(
  `{ id: "parsing", label: "Parsing", icon: "📄", desc: "Reading document content" },`,
  `{ id: "parsing", label: "Parsing", icon: <FileText size={16} />, desc: "Reading document content" },`
);
content = content.replace(
  `{ id: "rules", label: "Rules Engine", icon: "🔍", desc: \`Running \${categories?.length || 0} rule categories\` },`,
  `{ id: "rules", label: "Rules Engine", icon: <Search size={16} />, desc: \`Running \${categories?.length || 0} rule categories\` },`
);
content = content.replace(
  `{ id: "scoring", label: "Scoring", icon: "📊", desc: "Calculating quality score" },`,
  `{ id: "scoring", label: "Scoring", icon: <BarChart3 size={16} />, desc: "Calculating quality score" },`
);
content = content.replace(
  `{ id: "report", label: "Report", icon: "📝", desc: "Generating review report" },`,
  `{ id: "report", label: "Report", icon: <FilePen size={16} />, desc: "Generating review report" },`
);

// Update pipeline icon rendering
content = content.replace(
  `<div className="pipeline-icon">{isPast ? "✓" : s.icon}</div>`,
  `<div className="pipeline-icon">{isPast ? <Check size={14} /> : s.icon}</div>`
);

// Profile estimate clock
content = content.replace(
  '{showEstimate && <small style={{ color: "var(--text3)", fontSize: ".7rem" }}>⏱ {estimates[profile.id] || "~3 min"}</small>}',
  `{showEstimate && <small style={{ color: "var(--text3)", fontSize: ".7rem" }}><Clock size={10} /> {estimates[profile.id] || "~3 min"}</small>}`
);

// Profile check mark
content = content.replace(
  '{selected && <div className="profile-check">✓</div>}',
  `{selected && <div className="profile-check"><Check size={14} /></div>}`
);

// Fix badge
content = content.replace(
  '{issue.autofix_allowed === 1 && <span className="fix-badge">⚡ Auto-fix</span>}',
  `{issue.autofix_allowed === 1 && <span className="fix-badge"><Zap size={12} /> Auto-fix</span>}`
);

writeFileSync(path, content, "utf8");
console.log("Done! Emojis replaced with Lucide icons.");
