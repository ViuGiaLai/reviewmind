import { readFileSync, writeFileSync } from "fs";

let c = readFileSync("src/main.tsx", "utf8");

// Comprehensive emoji -> icon name mapping (without size, added per context)
const emojiToIcon = {
  // Severity indicators
  "\u{1F534}": "Circle",       // 🔴
  "\u{1F7E1}": "AlertCircle",  // 🟡
  "\u{1F7E2}": "CheckCircle",  // 🟢
  "\u{26AA}": "Circle",        // ⚪
  "\u{1F7E0}": "AlertCircle",  // 🟠
  "\u{274C}": "CircleX",       // ❌
  "\u{2705}": "Check",         // ✅
  "\u{2714}\u{FE0F}": "Check", // ✔️
  "\u{2713}": "Check",         // ✓
  "\u{2716}": "X",             // ✗
  "\u{2715}": "X",             // ✕
  "\u{2712}": "Pencil",        // ✒

  // Navigation & UI
  "\u{1F3E0}": "House",        // 🏠
  "\u{2699}\u{FE0F}": "Settings", // ⚙️
  "\u{2699}": "Settings",      // ⚙
  "\u{1F4CC}": "Pin",          // 📌
  "\u{1F50D}": "Search",       // 🔍
  "\u{1F441}\u{FE0F}": "Eye",  // 👁️
  "\u{1F441}": "Eye",          // 👁
  "\u{26F6}": "Maximize",      // ⛶
  "\u{1F504}": "RefreshCw",    // 🔄
  "\u{1F5D1}\u{FE0F}": "Trash2", // 🗑️
  "\u{1F5D1}": "Trash2",       // 🗑
  "\u{1F4BE}": "FloppyDisk",   // 💾
  "\u{1F4BD}": "FloppyDisk",   // 💽

  // Documents & Files
  "\u{1F4C4}": "FileText",     // 📄
  "\u{1F4DD}": "FilePen",      // 📝
  "\u{1F4CB}": "ClipboardList",// 📋
  "\u{1F4CA}": "BarChart3",    // 📊
  "\u{1F4C8}": "TrendingUp",   // 📈
  "\u{1F4C6}": "Calendar",     // 📅
  "\u{1F4C1}": "Folder",       // 📁
  "\u{1F4D5}": "BookX",        // 📕
  "\u{1F4D8}": "BookOpen",     // 📘
  "\u{1F4D6}": "Book",         // 📖
  "\u{1F4DA}": "BookOpen",     // 📚
  "\u{1F4F0}": "Newspaper",    // 📰
  "\u{1F4DC}": "ScrollText",   // 📜
  "\u{1F4E4}": "Upload",       // 📤
  "\u{1F516}": "BookOpen",     // 🔖
  "\u{1F4E1}": "Radio",        // 📡

  // Objects & Tools
  "\u{1F3AF}": "Target",       // 🎯
  "\u{1F527}": "Wrench",       // 🔧
  "\u{1F6E0}\u{FE0F}": "Wrench", // 🛠️
  "\u{1F6E0}": "Wrench",       // 🛠
  "\u{1F4A1}": "Lightbulb",    // 💡
  "\u{1F3C6}": "Trophy",       // 🏆
  "\u{1F680}": "Rocket",       // 🚀
  "\u{23F1}": "Clock",         // ⏱
  "\u{23F3}": "Clock",         // ⏳
  "\u{1F552}": "Clock",        // 🕒
  "\u{1F4F1}": "Smartphone",   // 📱
  "\u{1F4BB}": "Monitor",      // 💻

  // People & Status
  "\u{1F44B}": "Hand",         // 👋
  "\u{1F393}": "GraduationCap",// 🎓
  "\u{1F4BC}": "Briefcase",    // 💼
  "\u{1F916}": "Bot",          // 🤖
  "\u{1F41B}": "Bug",          // 🐛
  "\u{1F3A8}": "Palette",      // 🎨

  // Science & Nature
  "\u{1F52C}": "Microscope",   // 🔬
  "\u{1F30D}": "Globe",        // 🌍
  "\u{1F30E}": "Globe",        // 🌎
  "\u{2600}\u{FE0F}": "Sun",   // ☀️
  "\u{2600}": "Sun",           // ☀
  "\u{1F319}": "Moon",         // 🌙

  // Symbols
  "\u{26A1}": "Zap",           // ⚡
  "\u{1F512}": "Lock",         // 🔒
  "\u{1F513}": "LockOpen",     // 🔓
  "\u{2696}": "Scale",         // ⚖
  "\u{1F6A9}": "Flag",         // 🚩
  "\u{1F4A0}": "Pill",         // 💊
  "\u{2B50}": "Star",          // ⭐

  // Arrows & Indicators
  "\u{25B2}": "ChevronUp",     // ▲
  "\u{25BC}": "ChevronDown",   // ▼
  "\u{25C0}": "ChevronLeft",   // ◀
  "\u{25B6}": "ChevronRight",  // ▶
  "\u{2B06}\u{FE0F}": "ArrowUp",   // ⬆️
  "\u{2B07}\u{FE0F}": "ArrowDown", // ⬇️
  "\u{21BB}": "RotateCw",      // ↻
  "\u{21BA}": "RotateCcw",     // ↺

  // Misc
  "\u{2139}\u{FE0F}": "Info",   // ℹ️
  "\u{2139}": "Info",           // ℹ
  "\u{2298}": "Slash",          // ⊘
  "\u{2795}": "Plus",           // ➕
  "\u{1F4B0}": "Coins",         // 💰
  "\u{1F6A8}": "BellRing",      // 🚨
  "\u{2757}": "AlertTriangle",  // ❗
  "\u{26A0}\u{FE0F}": "AlertTriangle", // ⚠️
  "\u{1F4CD}": "MapPin",        // 📍
  "\u{1F44D}": "ThumbsUp",      // 👍
  "\u{1F44E}": "ThumbsDown",    // 👎
  "\u{1F525}": "Flame",         // 🔥
  "\u{1F389}": "PartyPopper",   // 🎉
  "\u{1F381}": "Gift",          // 🎁
  "\u{1F48E}": "Gem",           // 💎
};

// Collect icon names used
const usedIcons = new Set();

// Replace emojis in JSX/text content
// Strategy: replace ALL emojis with inline Lucide components
// For string literals (icon maps, config arrays), we need special handling

// First, handle specific patterns that use emojis in object literals (icon maps)
// Sidebar navigation items
c = c.replace(
  /\{ id: "([^"]+)", icon: "([^"]+)", label: "([^"]+)"(?:, badge: ([^}]+))? \},?/g,
  (match, id, emojiStr, label, badge) => {
    const iconName = emojiToIcon[emojiStr] || emojiToIcon[emojiStr + "\u{FE0F}"];
    if (!iconName) return match;
    usedIcons.add(iconName);
    if (badge) {
      return `{ id: "${id}", icon: <${iconName} size={16} />, label: "${label}", badge: ${badge} },`;
    }
    return `{ id: "${id}", icon: <${iconName} size={16} />, label: "${label}" },`;
  }
);

// Wizard steps
c = c.replace(
  /\{ id: "([^"]+)" as WizardStep, icon: "([^"]+)", label: "([^"]+)" \},?/g,
  (match, id, emojiStr, label) => {
    const iconName = emojiToIcon[emojiStr] || emojiToIcon[emojiStr + "\u{FE0F}"];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return `{ id: "${id}" as WizardStep, icon: <${iconName} size={16} />, label: "${label}" },`;
  }
);

// Severity icons in dashboard stats
c = c.replace(
  /\{ icon: "([^"]+)", val: (highCount|medCount|lowCount|resolvedCount|openCount|issues\.length), label: "([^"]+)", cls: "([^"]+)" \}/g,
  (match, emojiStr, val, label, cls) => {
    const iconName = emojiToIcon[emojiStr];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return `{ icon: <${iconName} size={16} />, val: ${val}, label: "${label}", cls: "${cls}" }`;
  }
);

// Section titles with span section-icon
c = c.replace(
  /<span className="section-icon">([^<]+)<\/span>/g,
  (match, emojiStr) => {
    const trimmed = emojiStr.trim();
    const iconName = emojiToIcon[trimmed] || emojiToIcon[trimmed + "\u{FE0F}"];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return `<span className="section-icon"><${iconName} size={16} /></span>`;
  }
);

// chart-title headers
c = c.replace(
  /<h3 className="chart-title">([^<]+)<\/h3>/g,
  (match, content) => {
    let newContent = content;
    for (const [emoji, iconName] of Object.entries(emojiToIcon)) {
      if (newContent.includes(emoji)) {
        usedIcons.add(iconName);
        newContent = newContent.replace(emoji, `<${iconName} size={16} /> `);
      }
    }
    if (newContent === content) return match;
    return `<h3 className="chart-title">${newContent}</h3>`;
  }
);

// Chip badges (📁, 📦, 📄, 📅, etc.)
c = c.replace(
  /<span className="chip[^"]*">([^<]{1,30})<\/span>/g,
  (match, content) => {
    let newContent = content;
    for (const [emoji, iconName] of Object.entries(emojiToIcon)) {
      if (newContent.includes(emoji)) {
        usedIcons.add(iconName);
        newContent = newContent.replace(emoji, `<${iconName} size={12} /> `);
      }
    }
    if (newContent === content) return match;
    return match.replace(content, newContent);
  }
);

// Empty state / stat icons / nav icons
c = c.replace(
  /className="(empty-icon|stat-icon|nav-icon|dv-icon|meta-icon)">([^<]+)<\/div>/g,
  (match, cls, emojiStr) => {
    const trimmed = emojiStr.trim();
    const iconName = emojiToIcon[trimmed] || emojiToIcon[trimmed + "\u{FE0F}"];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return `className="${cls}"><${iconName} size={20} /></div>`;
  }
);

// Tab buttons with emoji prefix
c = c.replace(
  /<button className={`tab-btn \$\{activeTab === "([^"]+)" \? "active" : ""}`} onClick=\{\(\) => setActiveTab\("([^"]+)"\)}>([^<]+)<\/button>/g,
  (match, tab, setter, label) => {
    let newLabel = label;
    for (const [emoji, iconName] of Object.entries(emojiToIcon)) {
      if (newLabel.startsWith(emoji)) {
        usedIcons.add(iconName);
        newLabel = `<${iconName} size={14} /> ${newLabel.slice(emoji.length).trim()}`;
        break;
      }
    }
    if (newLabel === label) return match;
    return `<button className={\`tab-btn \${activeTab === "${tab}" ? "active" : ""}\`} onClick={() => setActiveTab("${setter}")}>${newLabel}</button>`;
  }
);

// Button with emoji (Jump to Doc, etc.)
c = c.replace(
  /<button[^>]*>([^<]{1,5}) ([^<]+)<\/button>/g,
  (match, emojiStr, text) => {
    const iconName = emojiToIcon[emojiStr] || emojiToIcon[emojiStr + "\u{FE0F}"];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return match.replace(emojiStr + " ", `<${iconName} size={14} /> `);
  }
);

// Simple emoji followed by text (like "⚡ Auto-fix", "✅ Resolve", etc.)
c = c.replace(
  /(\s)>([\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}][\u{FE0F}]?) ([^<"\n]+)/g,
  (match, prefix, emoji, text) => {
    const iconName = emojiToIcon[emoji];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return `${prefix}><${iconName} size={14} /> ${text}`;
  }
);

// Standalone emoji in text (like <h3>🎨 Appearance</h3>)
c = c.replace(
  /([\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}][\u{FE0F}]?)([A-Za-z\s])/g,
  (match, emoji, rest) => {
    const iconName = emojiToIcon[emoji];
    if (!iconName) return match;
    usedIcons.add(iconName);
    return `<${iconName} size={14} />${rest}`;
  }
);

// Remaining standalone emojis
c = c.replace(
  /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/g,
  (emoji) => {
    // Skip if already inside a component (would be after a `<`)
    const iconName = emojiToIcon[emoji];
    if (!iconName) return emoji;
    usedIcons.add(iconName);
    return `<${iconName} size={14} />`;
  }
);

// Update icon names to have properly cased first letters where needed
// Fix any double-wrapping issues

// Remove duplicate icons in sevIcon function
// The sevIcon should return icon components, not strings with JSX
c = c.replace(
  /function sevIcon\(s: string\) \{[\s\S]*?\n\}/,
  `function sevIcon(s: string) {
  const icons: Record<string, React.ReactNode> = { high: <TriangleAlert size={16} />, medium: <AlertCircle size={16} />, low: <CheckCircle size={16} /> };
  return icons[s] ?? <Circle size={16} />;
}`
);
usedIcons.add("TriangleAlert");
usedIcons.add("AlertCircle");
usedIcons.add("CheckCircle");
usedIcons.add("Circle");

// Build import
const iconList = [...usedIcons].sort();
const importLine = `import { ${iconList.join(", ")} } from "lucide-react";\n`;

if (c.includes('from "lucide-react"')) {
  c = c.replace(/import \{ [^}]+ \} from "lucide-react";?\n?/, importLine);
} else {
  c = c.replace(
    /(import .+? from "react";\n)/,
    "$1" + importLine
  );
}

writeFileSync("src/main.tsx", c, "utf8");
console.log(`Done! Replaced emojis with ${iconList.length} Lucide icons.`);
