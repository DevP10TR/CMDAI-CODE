import { CustomCodeEditor } from "/editor.js?v=20261117j";
import { CustomMindMap } from "/map.js?v=20261117j";

const HERO_SLOGANS = [
  "What should we build today?",
  "Ready to architect, code, and verify.",
  "Drop a @file or /command to get started.",
  "What are we debugging or shipping next?",
  "Turn a rough idea into clean, tested code.",
  "Inspect the codebase, plan safely, or build fast.",
  "Which module are we improving today?",
  "Let's trace the bug and fix the root cause.",
  "Start with a question, a diff, or a new feature.",
  "Code with full workspace context and precision.",
  "Ready when you are — what's on the roadmap?",
  "Explore symbols, run checks, and ship faster.",
];

function rotateHeroTitle() {
  const el = document.querySelector(".hero-title");
  if (!el) return;
  const current = el.textContent.trim();
  const pool = HERO_SLOGANS.filter((s) => s !== current);
  el.textContent = pool[Math.floor(Math.random() * pool.length)] || HERO_SLOGANS[0];
}

const NS_SVG = "http://www.w3.org/2000/svg";

// Exact block + bevel glyphs from src/cmdai/core/branding.py
const CMDAI_PARTS = [
  " ██████╗███╗   ███╗██████╗  █████╗ ██╗",
  "██╔════╝████╗ ████║██╔══██╗██╔══██╗██║",
  "██║     ██╔████╔██║██║  ██║███████║██║",
  "██║     ██║╚██╔╝██║██║  ██║██╔══██║██║",
  "╚██████╗██║ ╚═╝ ██║██████╔╝██║  ██║██║",
  " ╚═════╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝",
];

const CODE_PARTS = [
  " ██████╗ ██████╗ ██████╗ ███████╗",
  "██╔════╝██╔═══██╗██╔══██╗██╔════╝",
  "██║     ██║   ██║██║  ██║█████╗  ",
  "██║     ██║   ██║██║  ██║██╔══╝  ",
  "╚██████╗╚██████╔╝██████╔╝███████╗",
  " ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
];

const CC_LEFT = [
  " ██████╗",
  "██╔════╝",
  "██║     ",
  "██║     ",
  "╚██████╗",
  " ╚═════╝",
];

const CC_RIGHT = [
  " ██████╗",
  "██╔════╝",
  "██║     ",
  "██║     ",
  "╚██████╗",
  " ╚═════╝",
];

const THEME_BRAND = {
  light: {
    metaColor: "#f4f5f7",
    ccColor: "#18181b",
    states: [
      { cmdai: "#18181b", code: "#18181b" },
      { cmdai: "#71717a", code: "#18181b" },
      { cmdai: "#18181b", code: "#71717a" },
      { cmdai: "#71717a", code: "#71717a" },
    ],
  },
  dark: {
    metaColor: "#0d1117",
    ccColor: "#ffffff",
    states: [
      { cmdai: "#ffffff", code: "#ffffff" },
      { cmdai: "#888888", code: "#ffffff" },
      { cmdai: "#ffffff", code: "#888888" },
      { cmdai: "#888888", code: "#888888" },
    ],
  },
};

const DEFAULT_VISIBLE_MODELS = [
  "localllmapi:gemma-4-12B-it-Q4_K_M.gguf",
  "openrouter:deepseek/deepseek-r1:free",
  "openrouter:anthropic/claude-3.7-sonnet",
  "openrouter:google/gemini-2.5-pro-preview",
  "openai:gpt-4o",
  "openai:o3-mini",
  "deepseek:deepseek-reasoner",
];

const MODE_ORDER = ["auto", "code", "plan"];

// CLI agent commands only (synced from CMDAI CODE CLI COMMANDS_DOC, excluding modal/exit navigation)
const SLASH_COMMANDS = [
  { cmd: "/summarize", icon: "file-text", desc: "Summarize conversation history into compact context handoff" },
  { cmd: "/plan", icon: "list-check", desc: "Switch to read-only planning mode and create a step-by-step plan" },
  { cmd: "/todo", icon: "checkbox", desc: "Project tasks & TODO checklist manager" },
  { cmd: "/diff", icon: "git-compare", desc: "Review working changes and diff hunks" },
  { cmd: "/commit", icon: "git-commit", desc: "Inspect git changes and draft a clean commit message" },
  { cmd: "/revert", icon: "history", desc: "Revert file modifications from current turn" },
  { cmd: "/map", icon: "sparkles", desc: "Preview the AST Repo Map sent to the model" },
  { cmd: "/ctx", icon: "bulb", desc: "Inspect context token usage and pinned files" },
  { cmd: "/add", icon: "checkup", desc: "Pin files to conversation context (@)" },
  { cmd: "/drop", icon: "eraser", desc: "Remove pinned files from conversation context" },
  { cmd: "/memory", icon: "file-text", desc: "View and manage cross-session persistent memory (.cmdai/memory.md)" },
  { cmd: "/rules", icon: "file-text", desc: "View and edit project instructions (AGENTS.md)" },
  { cmd: "/mode", icon: "tool", desc: "Toggle/cycle agent execution mode (auto / code / plan)" },
  { cmd: "/thinking", icon: "bulb", desc: "Show or set thinking effort level" },
  { cmd: "/system", icon: "sparkles", desc: "Inspect or switch system prompt" },
  { cmd: "/new", icon: "eraser", desc: "Start a fresh conversation" },
];

function getSlashCommandIconHtml(iconKey) {
  const icons = {
    sparkles: `<path d="M12 3l1.8 4.2l4.2 1.8l-4.2 1.8l-1.8 4.2l-1.8 -4.2l-4.2 -1.8l4.2 -1.8z"/><path d="M5 17l.9 2.1l2.1 .9l-2.1 .9l-.9 2.1l-.9 -2.1l-2.1 -.9l2.1 -.9z"/>`,
    "list-check": `<path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/><path d="M11 6l9 0"/><path d="M11 12l9 0"/><path d="M11 18l9 0"/>`,
    "git-compare": `<path d="M6 6m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M18 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M11 6h5a2 2 0 0 1 2 2v8"/><path d="M14 9l-3 -3l3 -3"/><path d="M13 18h-5a2 2 0 0 1 -2 -2v-8"/><path d="M10 15l3 3l-3 3"/>`,
    "git-commit": `<path d="M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M12 3l0 6"/><path d="M12 15l0 6"/>`,
    minimize: `<path d="M15 19v-2a2 2 0 0 1 2 -2h2"/><path d="M15 5v2a2 2 0 0 0 2 2h2"/><path d="M5 15h2a2 2 0 0 1 2 2v2"/><path d="M5 9h2a2 2 0 0 0 2 -2v-2"/>`,
    "file-text": `<path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/><path d="M9 9l1 0"/><path d="M9 13l6 0"/><path d="M9 17l6 0"/>`,
    tool: `<path d="M7 10h3v-3l-3.5 -3.5a6 6 0 0 1 8 8l6 6a2 2 0 0 1 -3 3l-6 -6a6 6 0 0 1 -8 -8l3.5 3.5"/>`,
    bulb: `<path d="M3 12h1m8 -9v1m8 8h1m-15.4 -6.4l.7 .7m12.1 -.7l-.7 .7"/><path d="M9 16a5 5 0 1 1 6 0a3.5 3.5 0 0 0 -1 3a2 2 0 0 1 -4 0a3.5 3.5 0 0 0 -1 -3"/><path d="M9.7 17l4.6 0"/>`,
    checkup: `<path d="M9 5h-2a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-12a2 2 0 0 0 -2 -2h-2"/><path d="M9 3m0 2a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2v0a2 2 0 0 1 -2 2h-2a2 2 0 0 1 -2 -2z"/><path d="M9 14l2 2l4 -4"/>`,
    checkbox: `<path d="M9 11l3 3l8 -8"/><path d="M20 12v6a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h9"/>`,
    history: `<path d="M12 8l0 4l2 2"/><path d="M3.05 11a9 9 0 1 1 .5 4m-.5 5v-5h5"/>`,
    eraser: `<path d="M19 20h-10.5l-4.21 -4.3a1 1 0 0 1 0 -1.41l10 -10a1 1 0 0 1 1.41 0l5 5a1 1 0 0 1 0 1.41l-9.2 9.3"/><path d="M18 13.3l-6.3 -6.3"/>`,
  };
  const body = icons[iconKey] || icons.sparkles;
  return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;color:var(--text-secondary);">${body}</svg>`;
}

const LOCAL_FIRST_IDS = ["local_gguf", "localllmapi", "ollama", "lmstudio", "vllm"];

const FILE_TYPE_META = {
  py: { color: "#2563eb", label: "py", kind: "code" },
  pyw: { color: "#2563eb", label: "py", kind: "code" },
  js: { color: "#d97706", label: "js", kind: "code" },
  mjs: { color: "#d97706", label: "js", kind: "code" },
  ts: { color: "#1d4ed8", label: "ts", kind: "code" },
  tsx: { color: "#1d4ed8", label: "tsx", kind: "code" },
  rs: { color: "#c2410c", label: "rs", kind: "code" },
  css: { color: "#7c3aed", label: "css", kind: "style" },
  scss: { color: "#7c3aed", label: "scss", kind: "style" },
  html: { color: "#ea580c", label: "html", kind: "markup" },
  htm: { color: "#ea580c", label: "html", kind: "markup" },
  json: { color: "#0d9488", label: "json", kind: "config" },
  toml: { color: "#0d9488", label: "toml", kind: "config" },
  yaml: { color: "#0d9488", label: "yml", kind: "config" },
  yml: { color: "#0d9488", label: "yml", kind: "config" },
  md: { color: "#475569", label: "md", kind: "doc" },
  txt: { color: "#64748b", label: "txt", kind: "doc" },
  png: { color: "#16a34a", label: "img", kind: "image" },
  jpg: { color: "#16a34a", label: "img", kind: "image" },
  jpeg: { color: "#16a34a", label: "img", kind: "image" },
  svg: { color: "#16a34a", label: "svg", kind: "image" },
  sh: { color: "#0f766e", label: "sh", kind: "code" },
  ps1: { color: "#2563eb", label: "ps", kind: "code" },
};

function getFileIconHtml(filename) {
  const name = String(filename || "").split(/[\\/]/).pop() || "";
  const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  const spec = FILE_TYPE_META[ext] || { color: "#64748b", label: "file", kind: "doc" };

  if (spec.kind === "image") {
    return `<span class="file-type-ico" style="color:${spec.color};" title="${escapeHtml(ext || "image")}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M15 8h.01"/><path d="M3 6a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v12a3 3 0 0 1 -3 3h-12a3 3 0 0 1 -3 -3v-12z"/><path d="M3 16l5 -5c.928 -.893 2.072 -.893 3 0l5 5"/><path d="M14 14l1 -1c.928 -.893 2.072 -.893 3 0l3 3"/></svg></span>`;
  }
  if (spec.kind === "config" || spec.kind === "style") {
    return `<span class="file-type-ico" style="color:${spec.color};" title="${escapeHtml(ext || "file")}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4a2 2 0 0 0 -2 2v3a2 3 0 0 1 -2 3a2 3 0 0 1 2 3v3a2 2 0 0 0 2 2"/><path d="M17 4a2 2 0 0 1 2 2v3a2 3 0 0 0 2 3a2 3 0 0 0 -2 3v3a2 2 0 0 1 -2 2"/></svg></span>`;
  }
  if (spec.kind === "code" || spec.kind === "markup") {
    return `<span class="file-type-ico" style="color:${spec.color};" title="${escapeHtml(ext || "code")}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/><path d="M10 13l-1.5 2l1.5 2"/><path d="M14 13l1.5 2l-1.5 2"/></svg></span>`;
  }
  return `<span class="file-type-ico" style="color:${spec.color};" title="${escapeHtml(ext || "document")}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/><path d="M9 9h1"/><path d="M9 13h6"/><path d="M9 17h6"/></svg></span>`;
}

window.getCmdaiFileIconHtml = getFileIconHtml;

const state = {
  bootstrap: null,
  theme: "light",
  workdir: "",
  activeSessionId: null,
  openTabs: [{ tabId: "tab-init", sessionId: null, title: "New Chat" }],
  activeTabId: "tab-init",
  pinnedFiles: [],
  treeEntries: [],
  filePaths: [],
  sessions: [],
  workspaces: [],
  expandedWorkspaces: new Set(),
  expandedShowAllWorkspaces: new Set(),
  pinnedSessionIds: new Set(JSON.parse(localStorage.getItem("cmdai_pinned_sessions") || "[]")),
  projectLabels: JSON.parse(localStorage.getItem("cmdai_project_labels") || "{}"),
  recentWorkspaces: JSON.parse(localStorage.getItem("cmdai_recent_workspaces") || "[]"),
  selectedProjectSettingsPath: "",
  skillsCollapsed: false,
  selectedProvider: "localllmapi",
  modalProvider: "localllmapi",
  modelsNav: "show_in_input", // "show_in_input" | "engine" | "provider"
  visibleModels: new Set(JSON.parse(localStorage.getItem("cmdai_visible_models") || JSON.stringify(DEFAULT_VISIBLE_MODELS))),
  activeProvider: "localllmapi",
  activeModel: "",
  mode: "auto",
  modePermissions: JSON.parse(localStorage.getItem("cmdai_mode_permissions") || JSON.stringify({
    auto: { read: "allow", write: "allow", edit: "allow", command: "allow" },
    code: { read: "allow", write: "allow", edit: "allow", command: "ask" },
    plan: { read: "allow", write: "deny", edit: "deny", command: "deny" },
  })),
  reasoningLevel: "medium",
  capabilityCache: new Map(),
  isGenerating: false,
  activeAbortController: null,
  secondaryView: null,
  openSubapps: [],
  acItems: [],
  acIndex: 0,
  acMode: null,
  acTokenStart: -1,
  brandCycleIdx: 0,
};

function dayOfYearCycle() {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const diff = (now - start) + (start.getTimezoneOffset() - now.getTimezoneOffset()) * 60000;
  return Math.floor(diff / 86400000) % 4;
}

function modelKey(providerId, modelId) {
  return `${providerId}:${modelId}`;
}

function formatCapLabel(s) {
  const raw = String(s || "");
  return raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : "";
}

function renderCapabilityIcons(model) {
  let html = "";
  if (model?.thinking) {
    const lvls = Array.isArray(model.levels) && model.levels.length ? ` (${model.levels.join(" / ")})` : "";
    html += `<span class="cap-icon-badge thinking" title="Thinking / Reasoning${escapeHtml(lvls)}">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 -6 6c0 2.15 1.15 4.02 2.85 5.05c.45 .28 .65 .78 .65 1.3v.65h5v-.65c0 -.52 .2 -1.02 .65 -1.3c1.7 -1.03 2.85 -2.9 2.85 -5.05a6 6 0 0 0 -6 -6z"/><path d="M9.5 19h5"/><path d="M10.5 21.5h3"/></svg>
    </span>`;
  }
  if (model?.vision) {
    html += `<span class="cap-icon-badge vision" title="Vision (Images &amp; Screenshots)">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/><path d="M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6"/></svg>
    </span>`;
  }
  return html;
}

function buildBlockWordPaths(lines, colOffset, cellW, cellH) {
  let d = "";
  const sw = Math.max(1.5, cellW * 0.15);
  for (let r = 0; r < lines.length; r++) {
    const line = lines[r];
    for (let c = 0; c < line.length; c++) {
      const ch = line[c];
      if (ch === " ") continue;
      const x = (colOffset + c) * cellW;
      const y = r * cellH;
      const xA = x + cellW * 0.28;
      const xB = x + cellW * 0.64;
      const yA = y + cellH * 0.30;
      const yB = y + cellH * 0.64;

      if (ch === "█") {
        d += `M${(x - 0.25).toFixed(2)},${(y - 0.3).toFixed(2)}h${(cellW + 0.5).toFixed(2)}v${(cellH + 0.6).toFixed(2)}h-${(cellW + 0.5).toFixed(2)}z`;
      } else if (ch === "═") {
        d += `M${(x - 0.2).toFixed(2)},${yA.toFixed(2)}h${(cellW + 0.4).toFixed(2)}v${sw.toFixed(2)}h-${(cellW + 0.4).toFixed(2)}z`;
        d += `M${(x - 0.2).toFixed(2)},${yB.toFixed(2)}h${(cellW + 0.4).toFixed(2)}v${sw.toFixed(2)}h-${(cellW + 0.4).toFixed(2)}z`;
      } else if (ch === "║") {
        d += `M${xA.toFixed(2)},${(y - 0.2).toFixed(2)}h${sw.toFixed(2)}v${(cellH + 0.4).toFixed(2)}h-${sw.toFixed(2)}z`;
        d += `M${xB.toFixed(2)},${(y - 0.2).toFixed(2)}h${sw.toFixed(2)}v${(cellH + 0.4).toFixed(2)}h-${sw.toFixed(2)}z`;
      } else if (ch === "╔") {
        d += `M${xA.toFixed(2)},${yA.toFixed(2)}H${(x + cellW + 0.2).toFixed(2)}v${sw.toFixed(2)}H${(xA + sw).toFixed(2)}V${(y + cellH + 0.2).toFixed(2)}H${xA.toFixed(2)}z`;
        d += `M${xB.toFixed(2)},${yB.toFixed(2)}H${(x + cellW + 0.2).toFixed(2)}v${sw.toFixed(2)}H${(xB + sw).toFixed(2)}V${(y + cellH + 0.2).toFixed(2)}H${xB.toFixed(2)}z`;
      } else if (ch === "╗") {
        d += `M${(x - 0.2).toFixed(2)},${yA.toFixed(2)}H${(xB + sw).toFixed(2)}V${(y + cellH + 0.2).toFixed(2)}h-${sw.toFixed(2)}V${(yA + sw).toFixed(2)}H${(x - 0.2).toFixed(2)}z`;
        d += `M${(x - 0.2).toFixed(2)},${yB.toFixed(2)}H${(xA + sw).toFixed(2)}V${(y + cellH + 0.2).toFixed(2)}h-${sw.toFixed(2)}V${(yB + sw).toFixed(2)}H${(x - 0.2).toFixed(2)}z`;
      } else if (ch === "╚") {
        d += `M${xA.toFixed(2)},${(y - 0.2).toFixed(2)}h${sw.toFixed(2)}V${yB.toFixed(2)}H${(x + cellW + 0.2).toFixed(2)}v${sw.toFixed(2)}H${xA.toFixed(2)}z`;
        d += `M${xB.toFixed(2)},${(y - 0.2).toFixed(2)}h${sw.toFixed(2)}V${yA.toFixed(2)}H${(x + cellW + 0.2).toFixed(2)}v${sw.toFixed(2)}H${xB.toFixed(2)}z`;
      } else if (ch === "╝") {
        d += `M${xB.toFixed(2)},${(y - 0.2).toFixed(2)}h${sw.toFixed(2)}V${(yB + sw).toFixed(2)}H${(x - 0.2).toFixed(2)}v-${sw.toFixed(2)}H${xB.toFixed(2)}z`;
        d += `M${xA.toFixed(2)},${(y - 0.2).toFixed(2)}h${sw.toFixed(2)}V${(yA + sw).toFixed(2)}H${(x - 0.2).toFixed(2)}v-${sw.toFixed(2)}H${xA.toFixed(2)}z`;
      }
    }
  }
  return d;
}

function renderBannerSvgInto(hostEl) {
  if (!hostEl) return null;
  const cw = 10;
  const ch = 23;
  const gap = 3;
  const totalCols = CMDAI_PARTS[0].length + gap + CODE_PARTS[0].length;
  const w = totalCols * cw;
  const h = CMDAI_PARTS.length * ch;

  const svg = document.createElementNS(NS_SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("class", "cmdai-banner-svg");

  const gLeft = document.createElementNS(NS_SVG, "g");
  gLeft.setAttribute("class", "word-cmdai");
  const pLeft = document.createElementNS(NS_SVG, "path");
  pLeft.setAttribute("d", buildBlockWordPaths(CMDAI_PARTS, 0, cw, ch));
  gLeft.appendChild(pLeft);

  const gRight = document.createElementNS(NS_SVG, "g");
  gRight.setAttribute("class", "word-code");
  const pRight = document.createElementNS(NS_SVG, "path");
  pRight.setAttribute("d", buildBlockWordPaths(CODE_PARTS, CMDAI_PARTS[0].length + gap, cw, ch));
  gRight.appendChild(pRight);

  svg.appendChild(gLeft);
  svg.appendChild(gRight);
  hostEl.innerHTML = "";
  hostEl.appendChild(svg);
  return svg;
}

function renderCcSvgInto(hostEl) {
  if (!hostEl) return null;
  return renderBannerSvgInto(hostEl);
}

function applyBrandState(cycleIdx) {
  state.brandCycleIdx = ((cycleIdx % 4) + 4) % 4;
  const palette = THEME_BRAND[state.theme] || THEME_BRAND.light;
  const colors = palette.states[state.brandCycleIdx];
  document.querySelectorAll(".cmdai-banner-svg").forEach((svg) => {
    const l = svg.querySelector(".word-cmdai");
    const r = svg.querySelector(".word-code");
    if (l) l.setAttribute("fill", colors.cmdai);
    if (r) r.setAttribute("fill", colors.code);
  });
}

function applyTheme(themeName) {
  const clean = themeName === "dark" ? "dark" : "light";
  state.theme = clean;
  document.documentElement.setAttribute("data-theme", clean);
  const palette = THEME_BRAND[clean];
  const meta = document.getElementById("meta-theme-color");
  if (meta) meta.setAttribute("content", palette.metaColor);

  document.querySelectorAll(".cc-block-svg").forEach((svg) => {
    svg.setAttribute("fill", palette.ccColor);
  });
  applyBrandState(state.brandCycleIdx);

  document.querySelectorAll(".ag-theme-card").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.themeChoice === clean);
  });
  if (mindMap.loaded) mindMap.draw();
}

function normalizeMode(raw) {
  const m = String(raw || "code").trim().toLowerCase();
  if (MODE_ORDER.includes(m)) return m;
  if (m === "turbo") return "auto";
  return "code";
}

function toast(msg) {
  const host = document.getElementById("toast-container");
  if (!host) return;
  while (host.children.length >= 2) {
    host.firstElementChild?.remove();
  }
  const el = document.createElement("div");
  el.className = "toast-msg";
  el.textContent = msg;
  host.appendChild(el);
  setTimeout(() => el.classList.add("fade-out"), 1350);
  setTimeout(() => el.remove(), 1480);
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function cleanMessageContent(raw) {
  let s = String(raw || "");
  s = s.replace(/^\[Active Mode:[^\]]*\]\s*/i, "");
  s = s.replace(/<tool_result\b[^>]*>[\s\S]*?<\/tool_result>/gi, "");
  s = s.replace(/<\|tool_call>[\s\S]*?(?:<tool_call\|>|<\/\|tool_call>|\/>|$)/gi, " ");
  s = s.replace(/\bcall:[a-zA-Z0-9_]+\{[\s\S]*?(?:\}(?:<tool_call\|>|<\/\|tool_call>)?|$)/gi, " ");
  s = s.replace(/\bcall:[a-zA-Z0-9_]*$/gi, " ");
  s = s.replace(/<\|?tool_call\|?>/gi, " ");
  s = s.replace(/<\|channel>thought[\s\S]*?(?:<\|channel>|$)/gi, "");
  s = s.replace(/<\|channel>[^>\n]*>?/gi, "");
  s = s.replace(/<tool(?::[a-zA-Z0-9_]+|[a-z]+)\b[^>]*>[\s\S]*?(?:<\/tool(?::[a-zA-Z0-9_]+|[a-z]+)>|$)/gi, "");
  s = s.replace(/<tool(?::[a-zA-Z0-9_]+|[a-z]+)\b[\s\S]*$/gi, "");
  s = s.replace(/<\/tool(?::[a-zA-Z0-9_]+|[a-z]+)>/gi, "");
  s = s.replace(/<tool:[^\n>]*\/>/gi, "");
  s = s.replace(/<function_calls>[\s\S]*?(?:<\/function_calls>|$)/gi, "");
  s = s.replace(/<invoke\b[^>]*>[\s\S]*?(?:<\/invoke>|$)/gi, "");
  s = s.replace(/<\|?$/g, "");
  return s.replace(/[ \t]{2,}/g, " ").trim();
}

function formatMd(md) {
  let html = escapeHtml(md);
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
  html = html.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
  html = html.replace(/\n\n+/g, "</p><p>");
  return `<p>${html}</p>`.replace(/<p><ul>/g, "<ul>").replace(/<\/ul><\/p>/g, "</ul>");
}

function normalizePathKey(p) {
  return String(p || "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
}

function projectDisplayName(ws) {
  const key = normalizePathKey(ws.path);
  return state.projectLabels[key] || ws.name || ws.path.split(/[\\/]/).filter(Boolean).pop() || "Project";
}

function getAllProviders() {
  const list = state.bootstrap?.models_state?.providers || [];
  return [...list].sort((a, b) => {
    const ai = LOCAL_FIRST_IDS.indexOf(a.id);
    const bi = LOCAL_FIRST_IDS.indexOf(b.id);
    if (ai !== -1 || bi !== -1) {
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    }
    if (a.has_key !== b.has_key) return a.has_key ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

function findModelMeta(providerId, modelId) {
  const key = `${providerId}:${modelId}`;
  if (state.capabilityCache.has(key)) return state.capabilityCache.get(key);
  const prov = getAllProviders().find((p) => p.id === providerId);
  const found = (prov?.models || []).find((m) => m.id === modelId);
  if (found) return found;
  return {
    id: modelId,
    name: modelId,
    thinking: false,
    vision: false,
    levels: [],
    default_level: "off",
    param_style: "none",
    source: "unknown",
  };
}

async function ensureModelMeta(providerId, modelId) {
  const found = findModelMeta(providerId, modelId);
  if (found && found.source !== "unknown") return found;
  try {
    const resp = await fetch(`/api/capabilities?provider=${encodeURIComponent(providerId)}&model=${encodeURIComponent(modelId)}`);
    if (resp.ok) {
      const cap = await resp.json();
      state.capabilityCache.set(`${providerId}:${modelId}`, cap);
      return cap;
    }
  } catch {
    // non-fatal
  }
  return found;
}

function syncReasoningUI(meta) {
  const m = meta || findModelMeta(state.activeProvider, state.activeModel);
  const thinkBtn = document.getElementById("btn-composer-thinking");
  const thinkLbl = document.getElementById("composer-thinking-label");
  const setReasonSel = document.getElementById("set-reasoning-level");

  const hasThinking = Boolean(m?.thinking && Array.isArray(m.levels) && m.levels.length > 0);
  if (hasThinking) {
    const levels = m.levels;
    if (!levels.includes(state.reasoningLevel)) {
      state.reasoningLevel = levels.includes(m.default_level) ? m.default_level : levels[levels.length - 1];
    }
    if (thinkBtn && thinkLbl) {
      thinkLbl.textContent = formatCapLabel(state.reasoningLevel);
      thinkBtn.classList.remove("hidden");
    }
    if (setReasonSel) {
      setReasonSel.innerHTML = levels.map((lvl) => `<option value="${lvl}">${lvl}</option>`).join("");
      setReasonSel.value = state.reasoningLevel;
    }
  } else {
    if (thinkBtn) thinkBtn.classList.add("hidden");
  }
}

const MODE_ICONS_SVG = {
  auto: `<path d="M13 3l0 7l6 0l-8 11l0 -7l-6 0l8 -11"/>`,
  code: `<path d="M7 8l-4 4l4 4"/><path d="M17 8l4 4l-4 4"/><path d="M14 4l-4 16"/>`,
  plan: `<path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/><path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/><path d="M11 6l9 0"/><path d="M11 12l9 0"/><path d="M11 18l9 0"/>`,
};

function updateModeUI() {
  state.mode = normalizeMode(state.mode);
  const lbl = document.getElementById("composer-mode-label");
  const modePill = document.getElementById("btn-cycle-mode");
  const modeIcon = document.getElementById("composer-mode-icon");
  const selMode = document.getElementById("set-agent-mode");
  if (lbl) lbl.textContent = state.mode;
  if (modePill) modePill.dataset.mode = state.mode;
  if (modeIcon) modeIcon.innerHTML = MODE_ICONS_SVG[state.mode] || MODE_ICONS_SVG.auto;
  if (selMode && ["auto", "code", "plan"].includes(state.mode)) {
    setSegValue("set-agent-mode", state.mode);
  }
  document.querySelectorAll(".perm-option").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.permMode === state.mode);
  });
}

async function saveActiveModelSettings(providerId, modelId) {
  try {
    const resp = await fetch("/api/settings/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: providerId,
        model: modelId,
        mode: state.mode,
        reasoning_level: state.reasoningLevel,
      }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (state.bootstrap && data.models_state) {
        state.bootstrap.models_state = data.models_state;
      }
    }
  } catch {
    // non-fatal
  }
}

const editor = new CustomCodeEditor({
  onToast: toast,
  onOpenSplitDiff: () => openSecondaryPanel("review"),
  onRequestRefreshTree: () => refreshTree(),
});

const mindMap = new CustomMindMap({
  onOpenFileAtLine: async (path, line) => {
    await openSecondaryPanel("files");
    await editor.openFile(path, line || 1);
  },
  onPinContext: (path) => togglePinnedFile(path, true),
});

function closeAllComposerPopovers() {
  ["popover-workdir", "popover-branch", "popover-tasks", "popover-model", "popover-thinking", "popover-permissions"].forEach((id) => {
    document.getElementById(id)?.classList.add("hidden");
  });
  document.getElementById("model-hover-submenu")?.classList.add("hidden");
  document.getElementById("composer-dock")?.classList.remove("ctx-pop-open");
}

function toggleComposerPopover(popoverId, _keepContextStrip = false, forceOpen = null) {
  const el = document.getElementById(popoverId);
  if (!el) return;
  const willOpen = forceOpen !== null ? forceOpen : el.classList.contains("hidden");
  closeAllComposerPopovers();
  if (willOpen) {
    el.classList.remove("hidden");
    if (popoverId === "popover-workdir" || popoverId === "popover-branch" || popoverId === "popover-tasks") {
      document.getElementById("composer-dock")?.classList.add("ctx-pop-open");
    }
  }
}

/* ================= TOPBAR OPEN CHAT TABS ================= */

function getActiveTabObj() {
  return state.openTabs.find((t) => t.tabId === state.activeTabId) || state.openTabs[0];
}

function renderTopbarTabs() {
  const host = document.getElementById("topbar-chat-tabs");
  if (!host) return;
  host.innerHTML = "";
  state.openTabs.forEach((tab) => {
    const isAct = tab.tabId === state.activeTabId;
    const isStreaming = Boolean(state.isGenerating && (isAct || (state.activeSessionId && tab.sessionId === state.activeSessionId)));
    const btn = document.createElement("div");
    btn.className = `chat-tab${isAct ? " active" : ""}${isStreaming ? " is-streaming" : ""}`;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", isAct ? "true" : "false");
    btn.title = tab.title || "New Chat";
    btn.innerHTML = `
      <span class="chat-tab-dot"></span>
      <span class="chat-tab-title">${escapeHtml(tab.title || "New Chat")}</span>
      <button class="chat-tab-close" title="Close tab">&times;</button>
    `;

    btn.addEventListener("click", (e) => {
      if (e.target.closest(".chat-tab-close")) return;
      activateChatTab(tab.tabId);
    });

    btn.querySelector(".chat-tab-close").addEventListener("click", (e) => {
      e.stopPropagation();
      closeChatTab(tab.tabId);
    });

    host.appendChild(btn);
  });
}

async function activateChatTab(tabId) {
  closeModelsView();
  const tab = state.openTabs.find((t) => t.tabId === tabId);
  if (!tab) return;
  state.activeTabId = tab.tabId;
  if (tab.sessionId) {
    await loadSession(tab.sessionId);
  } else {
    state.activeSessionId = null;
    const msgs = document.getElementById("chat-messages");
    if (msgs) msgs.innerHTML = "";
    const tl = document.getElementById("timeline-rail");
    if (tl) tl.innerHTML = "";
    document.getElementById("hero-welcome")?.classList.remove("hidden-hero");
    renderWorkspacesSidebar();
    renderTopbarTabs();
    if (!mobileUI.isMobile) document.getElementById("composer-input")?.focus();
  }
}

async function openOrActivateSessionTab(sessionObj) {
  closeModelsView();
  if (sessionObj.directory && normalizePathKey(sessionObj.directory) !== normalizePathKey(state.workdir)) {
    await switchWorkspacePath(sessionObj.directory, false);
  }
  const existing = state.openTabs.find((t) => t.sessionId === sessionObj.id);
  if (existing) {
    state.activeTabId = existing.tabId;
    await loadSession(sessionObj.id);
    return;
  }

  const cur = getActiveTabObj();
  const isBlankUnused = cur && !cur.sessionId && document.querySelectorAll("#chat-messages > *").length === 0;
  if (isBlankUnused) {
    cur.sessionId = sessionObj.id;
    cur.title = sessionObj.title || "Conversation";
    state.activeTabId = cur.tabId;
  } else {
    const newId = `tab-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    state.openTabs.push({ tabId: newId, sessionId: sessionObj.id, title: sessionObj.title || "Conversation" });
    state.activeTabId = newId;
  }
  await loadSession(sessionObj.id);
}

function closeChatTab(tabId) {
  const idx = state.openTabs.findIndex((t) => t.tabId === tabId);
  if (idx === -1) return;
  state.openTabs.splice(idx, 1);
  if (state.openTabs.length === 0) {
    const fresh = { tabId: `tab-${Date.now()}`, sessionId: null, title: "New Chat" };
    state.openTabs.push(fresh);
    state.activeTabId = fresh.tabId;
    activateChatTab(fresh.tabId);
    return;
  }
  if (state.activeTabId === tabId) {
    const next = state.openTabs[Math.min(idx, state.openTabs.length - 1)];
    state.activeTabId = next.tabId;
    activateChatTab(next.tabId);
  } else {
    renderTopbarTabs();
  }
}

function startNewConversation(forceNewTab = true) {
  closeModelsView();
  const cur = getActiveTabObj();
  const isBlankCurrent = cur && !cur.sessionId && document.querySelectorAll("#chat-messages > *").length === 0;
  if (forceNewTab && !isBlankCurrent) {
    const fresh = { tabId: `tab-${Date.now()}-${Math.random().toString(36).slice(2, 5)}`, sessionId: null, title: "New Chat" };
    state.openTabs.push(fresh);
    state.activeTabId = fresh.tabId;
  }
  state.activeSessionId = null;
  const msgs = document.getElementById("chat-messages");
  if (msgs) msgs.innerHTML = "";
  const tlDots = document.getElementById("timeline-dots");
  if (tlDots) tlDots.innerHTML = "";
  document.getElementById("timeline-rail")?.classList.remove("has-items");
  if (typeof hideTimelineTooltip === "function") hideTimelineTooltip();
  if (typeof renderComposerTodoBar === "function") renderComposerTodoBar([]);
  if (typeof clearSessionChanges === "function") clearSessionChanges();
  document.getElementById("hero-welcome")?.classList.remove("hidden-hero");
  rotateHeroTitle();
  renderTopbarTabs();
  renderWorkspacesSidebar();
  if (!mobileUI.isMobile) document.getElementById("composer-input")?.focus();
}

/* ================= BOOTSTRAP & CONTEXT ================= */

async function refreshBootstrap() {
  const resp = await fetch("/api/bootstrap");
  const data = await resp.json();
  state.bootstrap = data;
  state.workdir = data.workdir || "";
  state.sessions = data.sessions || [];
  state.workspaces = data.workspaces || [];
  state.activeProvider = data.models_state?.active_provider || state.activeProvider;
  state.activeModel = data.models_state?.active_model || state.activeModel;
  state.selectedProvider = state.activeProvider;
  if (!state.modalProvider) state.modalProvider = state.activeProvider;
  state.mode = normalizeMode(data.general_settings?.mode || data.models_state?.mode || "code");
  state.reasoningLevel = data.general_settings?.reasoning_level || data.models_state?.reasoning_level || "medium";

  if (Array.isArray(data.general_settings?.visible_models)) {
    state.visibleModels = new Set(data.general_settings.visible_models);
    localStorage.setItem("cmdai_visible_models", JSON.stringify(Array.from(state.visibleModels)));
  }
  if (data.general_settings?.theme) {
    applyTheme(data.general_settings.theme);
  }
  if (state.activeProvider && state.activeModel) {
    state.visibleModels.add(modelKey(state.activeProvider, state.activeModel));
  }

  const activeWsKey = normalizePathKey(state.workdir);
  if (activeWsKey && state.expandedWorkspaces.size === 0) {
    state.expandedWorkspaces.add(activeWsKey);
  }

  const curTab = getActiveTabObj();
  if (curTab && state.activeSessionId) {
    const matched = state.sessions.find((s) => s.id === state.activeSessionId);
    if (matched) {
      curTab.sessionId = matched.id;
      curTab.title = matched.title;
    }
  }

  updateHeaderContext();
  updateModeUI();
  updateModelLabels();
  renderTopbarTabs();
  const meta = await ensureModelMeta(state.activeProvider, state.activeModel);
  syncReasoningUI(meta);
  renderWorkspacesSidebar();
  renderSettingsProjectsNav();
  renderOrbitPanels();
  applyGeneralSettingsToModal(data.general_settings || {});
}

function recordRecentWorkspace(wsPath) {
  const key = normalizePathKey(wsPath);
  if (!key) return;
  const filtered = (state.recentWorkspaces || []).filter((p) => normalizePathKey(p) !== key);
  filtered.unshift(wsPath);
  state.recentWorkspaces = filtered.slice(0, 12);
  localStorage.setItem("cmdai_recent_workspaces", JSON.stringify(state.recentWorkspaces));
}

function updateHeaderContext() {
  const wsName = state.workdir.split("/").filter(Boolean).pop() || state.workdir || "Workspace";
  if (state.workdir) recordRecentWorkspace(state.workdir);
  const gitInfo = state.bootstrap?.git;
  const hasGit = Boolean(gitInfo && gitInfo.is_repo);
  const lbl = document.getElementById("ctx-workdir-label");
  if (lbl) lbl.textContent = wsName;
  const branchWrap = document.getElementById("ctx-branch-wrap");
  if (branchWrap) branchWrap.classList.toggle("hidden", !hasGit);
  const br = document.getElementById("ctx-branch-label");
  if (br && hasGit) br.textContent = gitInfo.branch || "main";
}

function updateModelLabels() {
  const meta = findModelMeta(state.activeProvider, state.activeModel);
  const el = document.getElementById("composer-model-name");
  if (el) el.textContent = meta?.name || state.activeModel || "Select model";
}

function renderWorkspacesSidebar() {
  const pinSection = document.getElementById("pinned-sessions-section");
  const pinList = document.getElementById("pinned-sessions-list");
  const treeHost = document.getElementById("workspaces-tree");
  if (!treeHost) return;

  const pinnedItems = state.sessions.filter((s) => state.pinnedSessionIds.has(s.id));
  if (pinSection && pinList) {
    pinSection.classList.toggle("hidden", pinnedItems.length === 0);
    pinList.innerHTML = "";
    pinnedItems.forEach((s) => pinList.appendChild(createSessionRowEl(s, true)));
  }

  const activeKey = normalizePathKey(state.workdir);
  const grouped = new Map();
  (state.workspaces || []).forEach((w) => {
    grouped.set(normalizePathKey(w.path), { info: w, sessions: [] });
  });
  if (activeKey && !grouped.has(activeKey)) {
    const fallbackName = state.workdir.split("/").filter(Boolean).pop() || "Workspace";
    grouped.set(activeKey, { info: { name: fallbackName, path: state.workdir, active: true }, sessions: [] });
  }

  const scratchSessions = [];
  (state.sessions || []).forEach((s) => {
    if (s.scratch_no_project || s.dir_name === "Without Project" || s.directory === "__scratch__") {
      scratchSessions.push(s);
      return;
    }
    const rawDir = String(s.directory || "").trim();
    const k = normalizePathKey(rawDir);
    if (!k) {
      scratchSessions.push(s);
      return;
    }
    if (!grouped.has(k)) {
      const folderName = String(s.dir_name || rawDir.replace(/\\/g, "/").split("/").filter(Boolean).pop() || "Workspace");
      grouped.set(k, { info: { name: folderName, path: rawDir.replace(/\\/g, "/"), active: k === activeKey }, sessions: [] });
    }
    grouped.get(k).sessions.push(s);
  });

  treeHost.innerHTML = "";

  // Always show "Without Project" cleanly at the top of the left sidebar
  {
    const isScratchActive = Boolean(state.scratchNoProject);
    const isScratchExpanded = state.expandedWorkspaces.has("__scratch__") || (isScratchActive && scratchSessions.length > 0);
    const sGroupEl = document.createElement("div");
    sGroupEl.className = `ws-group${isScratchExpanded ? " expanded" : ""}`;
    const sHeaderRow = document.createElement("div");
    sHeaderRow.className = `ws-folder-row${isScratchActive ? " active-ws" : ""}`;
    sHeaderRow.innerHTML = `
      <div class="ws-folder-left">
        <svg class="ws-chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6l-6 6"/></svg>
        <svg class="ws-folder-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-10z"/><path d="M9 12h6"/></svg>
        <span class="ws-folder-name">Without Project</span>
      </div>
      <button class="ws-add-chat-btn" title="New conversation without project">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5l0 14"/><path d="M5 12l14 0"/></svg>
      </button>
    `;
    sHeaderRow.querySelector(".ws-folder-left").addEventListener("click", () => {
      if (state.expandedWorkspaces.has("__scratch__")) state.expandedWorkspaces.delete("__scratch__");
      else state.expandedWorkspaces.add("__scratch__");
      startScratchWithoutProject();
      renderSessions();
    });
    sHeaderRow.querySelector(".ws-add-chat-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      state.expandedWorkspaces.add("__scratch__");
      startScratchWithoutProject();
      renderSessions();
    });
    sGroupEl.appendChild(sHeaderRow);
    if (scratchSessions.length) {
      const sChildren = document.createElement("div");
      sChildren.className = "ws-sessions-list";
      scratchSessions.slice(0, 8).forEach((s) => sChildren.appendChild(createSessionRowEl(s, false)));
      sGroupEl.appendChild(sChildren);
    }
    treeHost.appendChild(sGroupEl);
  }

  for (const [key, group] of grouped.entries()) {
    const ws = group.info;
    const isActiveWs = !state.scratchNoProject && key === activeKey;
    const list = group.sessions;
    const isExpanded = state.expandedWorkspaces.has(key);
    const showAll = state.expandedShowAllWorkspaces.has(key);
    const visible = showAll ? list : list.slice(0, 5);
    const dispName = projectDisplayName(ws);

    const groupEl = document.createElement("div");
    groupEl.className = `ws-group${isExpanded ? " expanded" : ""}`;

    const headerRow = document.createElement("div");
    headerRow.className = `ws-folder-row${isActiveWs ? " active-ws" : ""}`;
    headerRow.innerHTML = `
      <div class="ws-folder-left">
        <svg class="ws-chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6l-6 6"/></svg>
        <svg class="ws-folder-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2"/></svg>
        <span class="ws-folder-name">${escapeHtml(dispName)}</span>
      </div>
      <button class="ws-add-chat-btn" title="New conversation in ${escapeHtml(dispName)}">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5l0 14"/><path d="M5 12l14 0"/></svg>
      </button>
    `;

    headerRow.querySelector(".ws-folder-left").addEventListener("click", () => {
      const nowExpanded = !state.expandedWorkspaces.has(key);
      if (nowExpanded) state.expandedWorkspaces.add(key);
      else state.expandedWorkspaces.delete(key);
      groupEl.classList.toggle("expanded", nowExpanded);
      if (!isActiveWs) switchWorkspacePath(ws.path);
    });

    headerRow.querySelector(".ws-add-chat-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!isActiveWs) await switchWorkspacePath(ws.path);
      startNewConversation(true);
    });

    const sessionsWrap = document.createElement("div");
    sessionsWrap.className = "ws-sessions-wrap";
    if (!visible.length) {
      sessionsWrap.innerHTML = `<div class="ws-empty-msg">No conversations yet</div>`;
    } else {
      visible.forEach((s) => sessionsWrap.appendChild(createSessionRowEl(s, false)));
      if (list.length > 5) {
        const moreBtn = document.createElement("button");
        moreBtn.className = "ag-see-all-btn";
        moreBtn.textContent = showAll ? "Show less" : `See all (${list.length})`;
        moreBtn.addEventListener("click", () => {
          if (showAll) state.expandedShowAllWorkspaces.delete(key);
          else state.expandedShowAllWorkspaces.add(key);
          renderWorkspacesSidebar();
        });
        sessionsWrap.appendChild(moreBtn);
      }
    }

    groupEl.appendChild(headerRow);
    groupEl.appendChild(sessionsWrap);
    treeHost.appendChild(groupEl);
  }
}

function createSessionRowEl(s, showWsSub = false) {
  const isPinned = state.pinnedSessionIds.has(s.id);
  const isStreaming = Boolean(state.isGenerating && state.activeSessionId === s.id);
  const row = document.createElement("div");
  row.className = `session-item${state.activeSessionId === s.id ? " active" : ""}${isStreaming ? " is-streaming" : ""}`;
  row.innerHTML = `
    <div class="session-main">
      <div class="session-title" style="display:flex;align-items:center;gap:6px;"><span class="s-status-dot"></span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(s.title)}</span></div>
      ${showWsSub && s.dir_name ? `<div class="session-sub">${escapeHtml(s.dir_name)}</div>` : ""}
    </div>
    <div class="session-right">
      <span class="session-time">${escapeHtml(s.updated_at || "")}</span>
      <button class="session-action-btn pin${isPinned ? " pinned" : ""}" title="${isPinned ? "Unpin" : "Pin"}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="${isPinned ? "currentColor" : "none"}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17.75l-6.172 3.245l1.179 -6.873l-5 -4.867l6.9 -1l3.086 -6.253l3.086 6.253l6.9 1l-5 4.867l1.179 6.873z"/></svg>
      </button>
      <button class="session-action-btn del" title="Delete conversation">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7l16 0"/><path d="M10 11l0 6"/><path d="M14 11l0 6"/><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12"/><path d="M9 7v-3a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v3"/></svg>
      </button>
    </div>
  `;

  row.addEventListener("click", (e) => {
    if (e.target.closest(".session-action-btn")) return;
    openOrActivateSessionTab(s);
  });

  row.querySelector(".pin").addEventListener("click", (e) => {
    e.stopPropagation();
    if (state.pinnedSessionIds.has(s.id)) state.pinnedSessionIds.delete(s.id);
    else state.pinnedSessionIds.add(s.id);
    localStorage.setItem("cmdai_pinned_sessions", JSON.stringify(Array.from(state.pinnedSessionIds)));
    renderWorkspacesSidebar();
  });

  row.querySelector(".del").addEventListener("click", async (e) => {
    e.stopPropagation();
    const resp = await fetch(`/api/sessions/${encodeURIComponent(s.id)}`, { method: "DELETE" });
    if (resp.ok) {
      state.sessions = state.sessions.filter((item) => item.id !== s.id);
      state.pinnedSessionIds.delete(s.id);
      const linkedTab = state.openTabs.find((t) => t.sessionId === s.id);
      if (linkedTab) closeChatTab(linkedTab.tabId);
      else renderWorkspacesSidebar();
      toast("Conversation deleted");
    }
  });

  return row;
}

function formatShortTimestamp(raw) {
  if (raw === null || raw === undefined || raw === "") return "";
  const num = Number(raw);
  if (Number.isFinite(num) && num > 1e9) {
    const ms = num < 1e12 ? num * 1000 : num;
    const d = new Date(ms);
    if (!Number.isNaN(d.getTime())) {
      return `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    }
  }
  const s = String(raw).trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    const d = new Date(s);
    if (!Number.isNaN(d.getTime())) {
      return `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    }
  }
  return s;
}

async function loadSession(sessionId) {
  closeModelsView();
  const resp = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
  if (!resp.ok) return toast("Could not load conversation");
  const data = await resp.json();
  state.activeSessionId = sessionId;
  const msgsHost = document.getElementById("chat-messages");
  msgsHost.innerHTML = "";
  const tlDots = document.getElementById("timeline-dots");
  if (tlDots) tlDots.innerHTML = "";
  document.getElementById("timeline-rail")?.classList.remove("has-items");
  hideTimelineTooltip();
  renderComposerTodoBar(Array.isArray(data.todo_list) ? data.todo_list : []);
  clearSessionChanges();
  document.getElementById("hero-welcome")?.classList.add("hidden-hero");

  const transcript = Array.isArray(data.transcript) ? data.transcript : [];
  if (transcript.length > 0) {
    let curCard = null;
    const ensureCard = () => {
      if (!curCard) {
        curCard = createAssistantTurnCard(data.model_id || state.activeModel, data.agent_mode || state.mode, false);
      }
      return curCard;
    };
    for (const ev of transcript) {
      if (!ev || typeof ev !== "object") continue;
      if (ev.kind === "user") {
        curCard = null;
        const txt = cleanMessageContent(String(ev.prompt || ev.content || ev.text || ""));
        const tStr = formatShortTimestamp(ev.time || ev.timestamp || data.updated_at || "");
        if (txt) appendUserBubble(txt, tStr);
      } else if (ev.kind === "thinking") {
        const th = String(ev.text || ev.content || "");
        if (th.trim()) ensureCard().appendThinking(th);
      } else if (ev.kind === "tool" || ev.kind === "tool_result") {
        const c = ensureCard();
        const tId = `cli_${Math.random().toString(36).slice(2, 7)}`;
        const tName = ev.tool || ev.name || "tool";
        const tArgs = ev.target || ev.args || "";
        const resObj = ev.result || {};
        const ok = ev.ok !== false && ev.success !== false && resObj.success !== false;
        const rawOut = String(resObj.content || resObj.output || resObj.error || ev.preview || ev.content || "").trim();
        const firstLine = rawOut ? rawOut.split("\n")[0].slice(0, 140) : "";
        c.startTool({ id: tId, name: tName, args: tArgs, historical: true });
        c.finishTool({
          id: tId,
          name: tName,
          args: tArgs,
          historical: true,
          ok,
          summary: ev.summary || firstLine || (ok ? "Completed" : "Failed"),
          preview: rawOut,
        });
      } else if (ev.kind === "assistant") {
        const txt = cleanMessageContent(String(ev.text || ev.content || ""));
        if (txt) ensureCard().setDone(txt);
      }
    }
  } else {
    for (const m of data.messages || []) {
      const rawContent = String(m.content || "");
      if (m.role === "user") {
        if (/^\s*<tool_result\b/i.test(rawContent)) continue;
        const cleanedUser = cleanMessageContent(rawContent);
        if (cleanedUser) appendUserBubble(cleanedUser);
      } else if (m.role === "assistant") {
        const cleanedAssistant = cleanMessageContent(rawContent);
        if (!cleanedAssistant) continue;
        const card = createAssistantTurnCard(data.model_id || state.activeModel, data.agent_mode || state.mode, false);
        card.setDone(cleanedAssistant);
      }
    }
  }
  renderTopbarTabs();
  renderWorkspacesSidebar();
}

async function switchWorkspacePath(targetPath, createIfMissing = false) {
  const resp = await fetch("/api/workspace/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workdir: targetPath, create_if_missing: createIfMissing }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    toast(err.detail || "Failed to switch project");
    return false;
  }
  const key = normalizePathKey(targetPath);
  if (key) state.expandedWorkspaces.add(key);
  // Reset open editor tabs from previous workspace so stale paths never 404
  if (editor && Array.isArray(editor.tabs)) {
    editor.tabs = [];
    editor.activePath = null;
    editor.renderTabs?.();
  }
  await refreshBootstrap();
  await refreshTree();
  toast(`Project: ${targetPath.split(/[\\/]/).filter(Boolean).pop() || targetPath}`);
  return true;
}

async function refreshTree() {
  try {
    const resp = await fetch("/api/editor/tree?limit=1200");
    if (!resp.ok) return;
    const data = await resp.json();
    state.treeEntries = data.entries || [];
    state.treeWorkdir = state.workdir;
    state.filePaths = state.treeEntries.filter((e) => e.kind === "file").map((e) => e.path);
    editor.renderTree(state.treeEntries);
  } catch {
    // non-fatal
  }
}

function togglePinnedFile(path, forcePin = null) {
  const idx = state.pinnedFiles.indexOf(path);
  const add = forcePin !== null ? forcePin : idx === -1;
  if (add && idx === -1) state.pinnedFiles.push(path);
  else if (!add && idx !== -1) state.pinnedFiles.splice(idx, 1);

  const host = document.getElementById("pinned-chips");
  if (!host) return;
  host.innerHTML = "";
  state.pinnedFiles.forEach((p) => {
    const baseName = p.split("/").pop();
    const chip = document.createElement("span");
    chip.className = "pinned-chip";
    chip.title = p;
    chip.innerHTML = `${getFileIconHtml(baseName)}<span>${escapeHtml(baseName)}</span><button title="Remove">&times;</button>`;
    chip.querySelector("button").addEventListener("click", () => togglePinnedFile(p, false));
    host.appendChild(chip);
  });
}

async function loadCheckpointsOverlay() {
  const countEl = document.getElementById("orbit-cp-count");
  const listEl = document.getElementById("orbit-checkpoints-list");
  if (!listEl) return;
  listEl.innerHTML = `<div class="orbit-card" style="color:var(--text-muted);">Loading checkpoints...</div>`;
  try {
    const resp = await fetch("/api/checkpoints/list");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const cps = data.checkpoints || [];
    if (countEl) countEl.textContent = String(cps.length);
    if (!cps.length) {
      listEl.innerHTML = `<div class="orbit-card" style="color:var(--text-muted);">No workspace checkpoints saved yet. Enter a description above and click "+ Create Checkpoint".</div>`;
      return;
    }
    listEl.innerHTML = "";
    cps.forEach((c) => {
      const fc = Array.isArray(c.files_changed) ? c.files_changed.length : Number(c.files_changed || 0);
      const statsStr = c.stats && typeof c.stats === "object"
        ? `+${c.stats.added || 0}/-${c.stats.removed || 0}`
        : (c.stats ? String(c.stats) : "");
      const row = document.createElement("div");
      row.className = "cp-row";
      row.innerHTML = `
        <div class="cp-meta">
          <div class="cp-title">${escapeHtml(c.prompt || c.id)}</div>
          <div class="cp-sub">${escapeHtml(c.id)} · ${escapeHtml(c.timestamp || "")}${statsStr ? " · " + escapeHtml(statsStr) : ""}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
          <span class="cap-tag">${c.is_active ? "ACTIVE" : `${fc} files`}</span>
          <button class="ed-action-btn compact btn-cp-restore" type="button">Restore Snapshot</button>
        </div>
      `;
      row.querySelector(".btn-cp-restore")?.addEventListener("click", async () => {
        const res = await fetch("/api/checkpoints/restore", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ checkpoint_id: c.id }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          return toast(err.detail || "Restore failed");
        }
        toast(`Restored checkpoint ${c.id}`);
        await loadCheckpointsOverlay();
        await refreshTree();
      });
      listEl.appendChild(row);
    });
  } catch (err) {
    listEl.innerHTML = `<div class="orbit-card" style="color:var(--accent-red);">${escapeHtml(err.message)}</div>`;
  }
}

async function loadCliSyncOverlay() {
  const pathInp = document.getElementById("sync-cli-path-input");
  const sumEl = document.getElementById("sync-summary-row");
  const listEl = document.getElementById("sync-diff-list");
  if (!listEl) return;
  if (pathInp && !pathInp.value.trim() && state.bootstrap?.general_settings?.cli_repo_path) {
    pathInp.value = state.bootstrap.general_settings.cli_repo_path;
  }
  const cliRoot = (pathInp?.value || "").trim();
  if (sumEl) sumEl.textContent = "Scanning shared core modules...";
  listEl.innerHTML = `<div class="orbit-card" style="color:var(--text-muted);">Scanning CLI repository...</div>`;
  try {
    const qs = cliRoot ? `?cli_root=${encodeURIComponent(cliRoot)}` : "";
    const resp = await fetch(`/api/sync/cli_diff${qs}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!data.cli_found) {
      if (sumEl) sumEl.textContent = `CLI repository not found at: ${data.cli_root}`;
      listEl.innerHTML = `<div class="orbit-card" style="color:var(--accent-red);">Directory not found. Set your CMDAI CODE path above and click Scan Diff.</div>`;
      return;
    }
    const diffs = data.modified_files || [];
    if (sumEl) {
      sumEl.textContent = `${data.synced_count || 0}/${data.total_shared_files || 0} shared core files identical · ${diffs.length} pending changes from CLI (${data.cli_root})`;
    }
    if (!diffs.length) {
      listEl.innerHTML = `<div class="orbit-card" style="color:var(--text-secondary);">Desktop core modules match CMDAI CODE CLI (${data.total_shared_files || 0} files synced). Desktop UI stays isolated.</div>`;
      return;
    }
    listEl.innerHTML = "";
    diffs.forEach((item) => {
      const row = document.createElement("div");
      row.className = "sync-row";
      row.innerHTML = `
        <div class="sync-meta">
          <div class="sync-title">${escapeHtml(item.path)}</div>
          <div class="sync-sub">${item.status === "new_from_cli" ? "New module in CLI" : "Modified in CLI"} · ${Number(item.size || 0)} bytes</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
          <span class="sync-badge differs">${escapeHtml(item.status === "new_from_cli" ? "NEW" : "MODIFIED")}</span>
          <button class="ed-action-btn compact" data-sync-path="${escapeHtml(item.path)}">Port to Desktop</button>
        </div>
      `;
      row.querySelector("button").addEventListener("click", async () => {
        const res = await fetch("/api/sync/cli_transfer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cli_root: cliRoot, paths: [item.path] }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          return toast(err.detail || "Transfer failed");
        }
        toast(`Ported ${item.path} to Desktop`);
        await loadCliSyncOverlay();
        await refreshBootstrap();
      });
      listEl.appendChild(row);
    });
  } catch (err) {
    if (sumEl) sumEl.textContent = `Sync scan failed: ${err.message}`;
    listEl.innerHTML = `<div class="orbit-card" style="color:var(--accent-red);">${escapeHtml(err.message)}</div>`;
  }
}

function formatDiffHtml(diffText) {
  if (!diffText || !diffText.trim()) {
    return escapeHtml("Clean working tree (no unstaged or staged diff).");
  }
  return diffText
    .split("\n")
    .map((line) => {
      const esc = escapeHtml(line);
      if (line.startsWith("+") && !line.startsWith("+++")) return `<span class="diff-line-add">${esc}</span>`;
      if (line.startsWith("-") && !line.startsWith("---")) return `<span class="diff-line-del">${esc}</span>`;
      if (line.startsWith("@@") || line.startsWith("diff --git")) return `<span class="diff-line-hunk">${esc}</span>`;
      return esc;
    })
    .join("\n");
}

function clearSessionChanges() {
  if (state.sessionChanges instanceof Map) state.sessionChanges.clear();
  else state.sessionChanges = new Map();
}

async function loadReviewSubApp(selectedPath = "") {
  const metaEl = document.getElementById("review-git-meta");
  const filesHost = document.getElementById("review-files-list");
  const diffOut = document.getElementById("review-diff-output");
  if (!filesHost || !diffOut) return;
  const sessionList = state.sessionChanges instanceof Map ? Array.from(state.sessionChanges.values()) : [];
  const renderSessionFallback = (reasonMsg) => {
    if (!sessionList.length) {
      if (metaEl) metaEl.textContent = reasonMsg;
      filesHost.innerHTML = `<div style="padding:8px;font-size:12px;color:var(--text-muted);">Use the branch switcher above the chat composer to run git init.</div>`;
      diffOut.textContent = "This workspace does not have a .git repository yet.";
      state.reviewSelectedPath = "";
      return;
    }
    const active = sessionList.find((c) => c.path === selectedPath) || sessionList[0];
    state.reviewSelectedPath = active.path;
    if (metaEl) metaEl.textContent = `Session Changes · ${sessionList.length} file${sessionList.length === 1 ? "" : "s"} modified`;
    filesHost.innerHTML = "";
    sessionList.forEach((ch) => {
      const btn = document.createElement("button");
      btn.className = `review-file-btn${active.path === ch.path ? " active" : ""}`;
      btn.innerHTML = `<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(ch.path)}</span><span class="cap-tag">+${ch.added || 0} -${ch.removed || 0}</span>`;
      btn.addEventListener("click", () => {
        state.reviewSelectedPath = ch.path;
        loadReviewSubApp(ch.path);
      });
      filesHost.appendChild(btn);
    });
    diffOut.innerHTML = formatDiffHtml(active.unified || `--- a/${active.path}\n+++ b/${active.path}\n(Modified in session: +${active.added || 0} / -${active.removed || 0})`);
  };
  try {
    const qs = selectedPath ? `?file_path=${encodeURIComponent(selectedPath)}` : "";
    const resp = await fetch(`/api/git/diff${qs}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (!data.is_repo) {
      renderSessionFallback("No Git repository initialized in this workspace");
      return;
    }
    const changed = data.changed || [];
    if (!changed.length && sessionList.length) {
      renderSessionFallback(`${data.branch || "main"} · Session Changes`);
      return;
    }
    if (metaEl) metaEl.textContent = `${data.branch || "main"} · ${data.commit || "HEAD"} · ${changed.length} changed`;
    filesHost.innerHTML = "";
    if (!changed.length) {
      filesHost.innerHTML = `<div style="padding:8px;font-size:12px;color:var(--text-muted);">Working tree clean</div>`;
    } else {
      changed.forEach((ch) => {
        const btn = document.createElement("button");
        btn.className = `review-file-btn${selectedPath === ch.path ? " active" : ""}`;
        btn.innerHTML = `<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(ch.path)}</span><span class="cap-tag">${escapeHtml(ch.status)}</span>`;
        btn.addEventListener("click", () => {
          state.reviewSelectedPath = ch.path;
          loadReviewSubApp(ch.path);
        });
        filesHost.appendChild(btn);
      });
    }
    diffOut.innerHTML = formatDiffHtml(data.diff || "");
  } catch (err) {
    renderSessionFallback(`Error: ${err.message}`);
  }
}

const ptyTerm = {
  term: null,
  fitAddon: null,
  es: null,
  connected: false,
  fallbackMode: false,
  resizeObserver: null,
  themeObserver: null,
  inputBuf: "",
  inputTimer: null,
  resizeTimer: null,

  getTheme() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    if (isDark) {
      return {
        background: "#0d0e11",
        foreground: "#e4e4e7",
        cursor: "#e4e4e7",
        cursorAccent: "#0d0e11",
        selectionBackground: "rgba(96, 165, 250, 0.28)",
        black: "#18181b",
        red: "#f87171",
        green: "#4ade80",
        yellow: "#facc15",
        blue: "#60a5fa",
        magenta: "#c084fc",
        cyan: "#22d3ee",
        white: "#e4e4e7",
        brightBlack: "#71717a",
        brightRed: "#fca5a5",
        brightGreen: "#86efac",
        brightYellow: "#fde047",
        brightBlue: "#93c5fd",
        brightMagenta: "#d8b4fe",
        brightCyan: "#67e8f9",
        brightWhite: "#fafafa",
      };
    }
    return {
      background: "#f3f3f3",
      foreground: "#1e1e1e",
      cursor: "#18181b",
      cursorAccent: "#f3f3f3",
      selectionBackground: "rgba(37, 99, 235, 0.20)",
      black: "#18181b",
      red: "#c50f1f",
      green: "#13a10e",
      yellow: "#c19c00",
      blue: "#0037da",
      magenta: "#881798",
      cyan: "#3a96dd",
      white: "#52525b",
      brightBlack: "#767676",
      brightRed: "#e74856",
      brightGreen: "#16c60c",
      brightYellow: "#b58900",
      brightBlue: "#3b78ff",
      brightMagenta: "#b4009e",
      brightCyan: "#0891b2",
      brightWhite: "#1e1e1e",
    };
  },

  setStatus(st) {
    const pill = document.getElementById("pty-status-pill");
    const txt = document.getElementById("pty-status-text");
    if (!pill || !txt) return;
    pill.classList.remove("connected", "exited");
    if (st && st.running) {
      pill.classList.add("connected");
      const sh = st.shell || "shell";
      const bk = st.backend ? ` · ${st.backend}` : "";
      txt.textContent = `${sh}${bk}`;
    } else if (st && st.running === false) {
      pill.classList.add("exited");
      txt.textContent = "Exited";
    } else {
      txt.textContent = "Connecting...";
    }
  },

  stripAnsi(s) {
    return String(s || "").replace(/\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, "");
  },

  writeToView(chunk) {
    if (!chunk) return;
    if (this.term && !this.fallbackMode) {
      this.term.write(chunk);
    } else {
      const out = document.getElementById("subapp-terminal-output");
      if (out) {
        out.textContent += this.stripAnsi(chunk);
        if (out.textContent.length > 80000) {
          out.textContent = out.textContent.slice(-60000);
        }
        out.scrollTop = out.scrollHeight;
      }
    }
  },

  queueInput(data) {
    if (!data) return;
    this.inputBuf += data;
    if (this.inputTimer) return;
    this.inputTimer = setTimeout(() => {
      const payload = this.inputBuf;
      this.inputBuf = "";
      this.inputTimer = null;
      this.sendInputNow(payload);
    }, 12);
  },

  async sendInputNow(data) {
    if (!data) return;
    const cols = this.term?.cols || 100;
    const rows = this.term?.rows || 28;
    try {
      await fetch("/api/terminal/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, cols, rows }),
      });
    } catch (_) {}
  },

  fitAndResize() {
    if (!this.term || !this.fitAddon || this.fallbackMode) return;
    const host = document.getElementById("pty-terminal-host");
    if (!host || host.offsetWidth < 40 || host.offsetHeight < 40) return;
    try {
      this.fitAddon.fit();
    } catch (_) {
      return;
    }
    const cols = this.term.cols || 100;
    const rows = this.term.rows || 28;
    clearTimeout(this.resizeTimer);
    this.resizeTimer = setTimeout(() => {
      fetch("/api/terminal/resize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cols, rows }),
      }).catch(() => {});
    }, 90);
  },

  ensureTerminalUI() {
    const host = document.getElementById("pty-terminal-host");
    const fb = document.getElementById("pty-fallback-wrap");
    if (!host) return;

    if (this.term) {
      this.term.options.theme = this.getTheme();
      setTimeout(() => {
        this.fitAndResize();
        this.term?.focus();
      }, 30);
      return;
    }

    const XTermCtor = window.Terminal;
    const FitCtor = window.FitAddon?.FitAddon || window.FitAddon;
    if (typeof XTermCtor === "function") {
      this.fallbackMode = false;
      host.classList.remove("hidden");
      fb?.classList.add("hidden");
      const isMob = document.documentElement.classList.contains("is-mobile");
      this.term = new XTermCtor({
        cursorBlink: true,
        fontFamily: 'ui-monospace, "Cascadia Code", "JetBrains Mono", Consolas, Menlo, monospace',
        fontSize: isMob ? 11.5 : 13,
        lineHeight: 1.32,
        scrollback: 5000,
        convertEol: false,
        theme: this.getTheme(),
      });
      if (typeof FitCtor === "function") {
        this.fitAddon = new FitCtor();
        this.term.loadAddon(this.fitAddon);
      }
      this.term.open(host);
      this.term.onData((data) => this.queueInput(data));

      if (typeof ResizeObserver !== "undefined") {
        this.resizeObserver = new ResizeObserver(() => this.fitAndResize());
        this.resizeObserver.observe(host);
      }
      if (!this.themeObserver) {
        this.themeObserver = new MutationObserver(() => {
          if (this.term) this.term.options.theme = this.getTheme();
        });
        this.themeObserver.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["data-theme"],
        });
      }
      setTimeout(() => {
        this.fitAndResize();
        this.term?.focus();
      }, 40);
    } else {
      // Offline / CDN-blocked fallback: still talks to the real persistent PTY
      this.fallbackMode = true;
      host.classList.add("hidden");
      fb?.classList.remove("hidden");
      setTimeout(() => document.getElementById("subapp-terminal-input")?.focus(), 40);
    }
  },

  connect() {
    this.ensureTerminalUI();
    if (this.es && this.es.readyState !== EventSource.CLOSED) {
      return;
    }
    const cols = this.term?.cols || 100;
    const rows = this.term?.rows || 28;
    const es = new EventSource(`/api/terminal/stream?cols=${cols}&rows=${rows}`);
    this.es = es;

    es.addEventListener("init", (ev) => {
      try {
        const msg = JSON.parse(ev.data || "{}");
        this.connected = true;
        this.setStatus(msg.state);
        if (this.term && !this.fallbackMode) {
          this.term.reset();
        } else {
          const out = document.getElementById("subapp-terminal-output");
          if (out) out.textContent = "";
        }
        if (msg.buffer) {
          this.writeToView(msg.buffer);
        }
        setTimeout(() => {
          this.fitAndResize();
          this.term?.focus();
        }, 40);
      } catch (_) {}
    });

    es.addEventListener("data", (ev) => {
      try {
        const msg = JSON.parse(ev.data || "{}");
        if (msg.chunk) this.writeToView(msg.chunk);
      } catch (_) {}
    });

    es.addEventListener("state", (ev) => {
      try {
        const st = JSON.parse(ev.data || "{}");
        this.setStatus(st);
      } catch (_) {}
    });

    es.onerror = () => {
      this.connected = false;
      this.setStatus(null);
    };
  },

  async restart() {
    const cols = this.term?.cols || 100;
    const rows = this.term?.rows || 28;
    if (this.term && !this.fallbackMode) this.term.reset();
    else {
      const out = document.getElementById("subapp-terminal-output");
      if (out) out.textContent = "";
    }
    try {
      const resp = await fetch("/api/terminal/restart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cols, rows }),
      });
      const st = await resp.json().catch(() => ({}));
      this.setStatus(st);
      if (!this.es || this.es.readyState === EventSource.CLOSED) {
        this.connect();
      }
      this.term?.focus();
    } catch (err) {
      toast(`Restart failed: ${err.message}`);
    }
  },

  clear() {
    if (this.term && !this.fallbackMode) {
      this.term.clear();
      this.sendInputNow("\x0c");
      this.term.focus();
    } else {
      const out = document.getElementById("subapp-terminal-output");
      if (out) out.textContent = "";
    }
  },

  ctrlC() {
    this.sendInputNow("\x03");
    this.term?.focus();
  },
};

const mobileUI = {
  isMobile: false,
  drawerOpen: false,

  detect() {
    const narrow = window.matchMedia("(max-width: 820px)").matches;
    const coarseTouch =
      window.matchMedia("(pointer: coarse)").matches && window.innerWidth <= 920;
    const uaMobile =
      /Android|iPhone|iPad|iPod|Mobile|webOS|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent || ""
      ) && window.innerWidth <= 920;
    const next = Boolean(narrow || coarseTouch || uaMobile);
    const changed = next !== this.isMobile;
    this.isMobile = next;

    const root = document.documentElement;
    root.classList.toggle("is-mobile", next);
    root.setAttribute("data-device", next ? "mobile" : "desktop");

    if (!next && this.drawerOpen) {
      this.closeDrawer();
    }
    if (changed && ptyTerm.term) {
      ptyTerm.term.options.fontSize = next ? 11.5 : 13;
      setTimeout(() => ptyTerm.fitAndResize(), 60);
    }
    return next;
  },

  syncViewport() {
    const vv = window.visualViewport;
    if (!vv) return;
    const h = Math.round(vv.height);
    document.documentElement.style.setProperty("--vv-height", `${h}px`);
    const kbdOpen = this.isMobile && window.innerHeight - vv.height > 140;
    document.documentElement.classList.toggle("keyboard-open", kbdOpen);
    if (state.secondaryView === "terminal") {
      setTimeout(() => ptyTerm.fitAndResize(), 80);
    }
  },

  openDrawer() {
    if (!this.isMobile) return;
    this.drawerOpen = true;
    document.getElementById("left-sidebar")?.classList.add("mobile-open");
    document.getElementById("mobile-sidebar-backdrop")?.classList.add("visible");
  },

  closeDrawer() {
    this.drawerOpen = false;
    document.getElementById("left-sidebar")?.classList.remove("mobile-open");
    document.getElementById("mobile-sidebar-backdrop")?.classList.remove("visible");
  },

  toggleDrawer() {
    if (this.drawerOpen) this.closeDrawer();
    else this.openDrawer();
  },

  syncNav() {
    const nav = document.getElementById("mobile-bottom-nav");
    if (!nav) return;
    const modelsOpen = document.getElementById("view-models")?.classList.contains("active");
    let activeKey = "chat";
    if (modelsOpen) activeKey = "models";
    else if (state.secondaryView) activeKey = state.secondaryView;
    nav.querySelectorAll(".mob-nav-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mobNav === activeKey);
    });
  },

  init() {
    this.detect();
    this.syncViewport();
    this.syncNav();

    window.addEventListener("resize", () => {
      this.detect();
      this.syncViewport();
    });
    window.addEventListener("orientationchange", () => {
      setTimeout(() => {
        this.detect();
        this.syncViewport();
      }, 120);
    });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", () => this.syncViewport());
    }

    document.getElementById("btn-mobile-menu")?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggleDrawer();
    });
    document.getElementById("mobile-sidebar-backdrop")?.addEventListener("click", () => {
      this.closeDrawer();
    });

    // Settings mobile slide-over category drawer
    const closeSettingsDrawer = () => {
      document.getElementById("settings-modal-sidebar")?.classList.remove("mobile-open");
      document.getElementById("settings-mobile-backdrop")?.classList.remove("visible");
    };
    document.getElementById("btn-settings-mobile-menu")?.addEventListener("click", (e) => {
      e.stopPropagation();
      const sb = document.getElementById("settings-modal-sidebar");
      const bd = document.getElementById("settings-mobile-backdrop");
      const open = sb?.classList.toggle("mobile-open");
      bd?.classList.toggle("visible", Boolean(open));
    });
    document.getElementById("settings-mobile-backdrop")?.addEventListener("click", closeSettingsDrawer);
    document.getElementById("settings-modal-sidebar")?.addEventListener("click", (e) => {
      if (!this.isMobile) return;
      if (e.target.closest(".ag-sb-item, .ag-sb-add-proj-btn")) {
        closeSettingsDrawer();
      }
    });
    // Auto-collapse mobile Editor file tree after picking a file so code gets 100% width
    document.getElementById("editor-tree-list")?.addEventListener("click", (e) => {
      if (!this.isMobile) return;
      if (e.target.closest(".tree-file, .outline-item, [data-path]")) {
        document.getElementById("editor-tree-pane")?.classList.add("collapsed");
      }
    });
    document.getElementById("btn-close-settings")?.addEventListener("click", closeSettingsDrawer);
    document.getElementById("btn-settings-cancel")?.addEventListener("click", closeSettingsDrawer);
    // Auto-close drawer on mobile when picking a session, new chat, models, or settings
    document.getElementById("left-sidebar")?.addEventListener("click", (e) => {
      if (!this.isMobile || !this.drawerOpen) return;
      if (
        e.target.closest(
          ".sb-session-item, .sb-new-conv-btn, #btn-nav-models, #btn-sidebar-settings, #btn-toggle-sidebar"
        )
      ) {
        this.closeDrawer();
      }
    });

    // Bottom navigation bar
    document.querySelectorAll("#mobile-bottom-nav .mob-nav-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const target = btn.dataset.mobNav || "chat";
        this.closeDrawer();
        if (target === "chat") {
          closeModelsView();
          closeSecondaryPanel();
        } else if (target === "models") {
          openModelsView();
        } else {
          await openSecondaryPanel(target);
        }
        this.syncNav();
      });
    });

    // Prevent mobile keyboard from popping up when tapping composer toolbar buttons/popovers
    document.addEventListener(
      "pointerdown",
      (e) => {
        if (!this.isMobile) return;
        const btn = e.target.closest(
          ".composer-context-strip button, .composer-footer button, .upward-popover button"
        );
        if (btn && btn.id !== "btn-pin-file") {
          const inp = document.getElementById("composer-input");
          if (inp && document.activeElement === inp) {
            inp.blur();
          }
        }
      },
      true
    );

    // Edge swipe gesture to open/close drawer
    let sx = 0;
    let sy = 0;
    let tracking = false;
    document.addEventListener(
      "touchstart",
      (e) => {
        if (!this.isMobile || e.touches.length !== 1) return;
        const t = e.touches[0];
        sx = t.clientX;
        sy = t.clientY;
        tracking = sx < 26 || this.drawerOpen;
      },
      { passive: true }
    );
    document.addEventListener(
      "touchend",
      (e) => {
        if (!tracking || !this.isMobile || !e.changedTouches.length) return;
        tracking = false;
        const t = e.changedTouches[0];
        const dx = t.clientX - sx;
        const dy = Math.abs(t.clientY - sy);
        if (dy > 70) return;
        if (!this.drawerOpen && sx < 26 && dx > 55) this.openDrawer();
        else if (this.drawerOpen && dx < -55) this.closeDrawer();
      },
      { passive: true }
    );
  },
};

async function runSubappTerminalCommand(cmdRaw) {
  const cmd = String(cmdRaw || "").trim();
  if (!cmd) return;
  ptyTerm.connect();
  await ptyTerm.sendInputNow(cmd + "\r");
}

const SUBAPP_VIEW_MAP = {
  files: { id: "view-editor", label: "Files" },
  review: { id: "view-review", label: "Review" },
  map: { id: "view-map", label: "Mind Map" },
  terminal: { id: "view-terminal", label: "Terminal" },
  checkpoints: { id: "view-checkpoints", label: "Checkpoints" },
  tasks: { id: "view-tasks", label: "Tasks" },
  subagent: { id: "view-subagent", label: "Subagent" },
  browser: { id: "view-browser", label: "Browser" },
};

function renderOpenSubappTabs() {
  const host = document.getElementById("open-subapp-tabs");
  if (!host) return;
  host.innerHTML = "";
  (state.openSubapps || []).forEach((kind) => {
    const info = SUBAPP_VIEW_MAP[kind];
    if (!info) return;
    const isAct = state.secondaryView === kind;
    const pill = document.createElement("div");
    pill.className = `active-panel-pill${isAct ? " active" : ""}`;
    pill.dataset.subappTab = kind;
    pill.innerHTML = `
      <span class="subapp-tab-lbl">${escapeHtml(info.label)}</span>
      <button class="panel-close-x" title="Close ${escapeHtml(info.label)}" type="button">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6l-12 12"/><path d="M6 6l12 12"/></svg>
      </button>
    `;
    pill.addEventListener("click", (e) => {
      if (e.target.closest(".panel-close-x")) return;
      openSecondaryPanel(kind);
    });
    pill.querySelector(".panel-close-x").addEventListener("click", (e) => {
      e.stopPropagation();
      closeSecondaryPanel(kind);
    });
    host.appendChild(pill);
  });
}

async function openSecondaryPanel(kind) {
  closeModelsView();
  const stage = document.getElementById("main-stage");
  document.getElementById("overview-popover")?.classList.add("hidden");
  document.getElementById("btn-overview-menu")?.classList.remove("open");

  const normKind = SUBAPP_VIEW_MAP[kind] ? kind : "files";
  const entry = SUBAPP_VIEW_MAP[normKind];
  if (!state.openSubapps.includes(normKind)) {
    state.openSubapps.push(normKind);
  }
  state.secondaryView = normKind;
  stage?.classList.add("mode-split");
  document.querySelectorAll(".subapp-pane").forEach((p) => p.classList.remove("active"));
  document.getElementById(entry.id)?.classList.add("active");
  renderOpenSubappTabs();
  mobileUI.syncNav();

  if (normKind === "map") {
    await mindMap.ensureLoaded();
    mindMap.resizeCanvas();
  } else if (normKind === "review") {
    await loadReviewSubApp(state.reviewSelectedPath || "");
  } else if (normKind === "browser") {
    await refreshBrowserState();
  } else if (normKind === "terminal") {
    ptyTerm.connect();
    setTimeout(() => {
      ptyTerm.fitAndResize();
      ptyTerm.term?.focus();
    }, 50);
  } else if (normKind === "checkpoints") {
    await loadCheckpointsOverlay();
  } else if (normKind === "tasks") {
    renderOrbitPanels();
  } else {
    await refreshTree();
    editor.renderTree(state.treeEntries);
    editor.setDiffMode(false);
    if (mobileUI.isMobile) {
      document.getElementById("editor-tree-pane")?.classList.add("collapsed");
    }
    if (!editor.activeTab() && state.filePaths.length > 0) {
      await editor.openFile(state.filePaths[0], 1).catch(() => {});
    }
    editor.updateStatusBar();
  }
}

function closeSecondaryPanel(kind = null) {
  const target = kind || state.secondaryView;
  if (target) {
    state.openSubapps = (state.openSubapps || []).filter((k) => k !== target);
  } else {
    state.openSubapps = [];
  }

  if (state.openSubapps.length > 0 && target === state.secondaryView) {
    const nextKind = state.openSubapps[state.openSubapps.length - 1];
    openSecondaryPanel(nextKind);
    return;
  }
  if (!state.openSubapps.length) {
    state.secondaryView = null;
    document.getElementById("main-stage")?.classList.remove("mode-split", "editor-maximized", "subapp-maximized");
    document.querySelectorAll(".subapp-pane").forEach((p) => p.classList.remove("active"));
    renderOpenSubappTabs();
    mobileUI.syncNav();
    return;
  }

  if (state.openSubapps.length === 0) {
    state.secondaryView = null;
    const stage = document.getElementById("main-stage");
    stage?.classList.remove("mode-split", "editor-maximized", "subapp-maximized");
    document.querySelectorAll(".btn-subapp-maximize span").forEach((sp) => {
      sp.textContent = "Full Window";
    });
    document.querySelectorAll(".subapp-pane").forEach((p) => p.classList.remove("active"));
  }
  renderOpenSubappTabs();
}

function getOrCreateTimelineTooltip() {
  let tip = document.getElementById("tl-floating-tooltip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "tl-floating-tooltip";
    tip.className = "tl-tooltip";
    document.body.appendChild(tip);
  }
  return tip;
}

function hideTimelineTooltip() {
  document.getElementById("tl-floating-tooltip")?.classList.remove("visible");
}

function showTimelineTooltip(dotEl, idx, total, preview, timeStr = "") {
  if (!dotEl) return;
  const tip = getOrCreateTimelineTooltip();
  const rect = dotEl.getBoundingClientRect();
  const cleanPreview = String(preview || "(message)").trim();
  const shortLine = cleanPreview.length > 44 ? `${cleanPreview.slice(0, 44)}…` : cleanPreview;
  const tDisp = timeStr || dotEl.dataset.timeStr || "";
  tip.innerHTML = `
    <div class="tl-tooltip-text" style="font-weight:600;color:var(--text-primary);margin-bottom:4px;">${escapeHtml(shortLine)}</div>
    <div class="tl-tooltip-meta" style="display:flex;justify-content:space-between;align-items:center;gap:14px;margin:0;color:var(--text-muted);font-weight:500;">
      <span>${idx + 1} of ${total}</span>
      ${tDisp ? `<span>${escapeHtml(tDisp)}</span>` : ""}
    </div>
  `;
  tip.style.left = `${Math.round(rect.right + 10)}px`;
  tip.style.top = `${Math.max(12, Math.round(rect.top - 8))}px`;
  tip.classList.add("visible");
}

function activateTimelineDot(idx) {
  const dotsHost = document.getElementById("timeline-dots");
  if (!dotsHost) return;
  const dots = Array.from(dotsHost.querySelectorAll(".tl-dot"));
  dots.forEach((d, i) => d.classList.toggle("active", i === idx));
  state.activeTimelineIdx = idx;
}

function scrollToUserTurn(idx) {
  const sc = document.getElementById("chat-scroll");
  const rows = Array.from(document.querySelectorAll("#chat-messages .msg-user-row"));
  const targetRow = rows[idx];
  if (!targetRow) return;
  if (sc) {
    const scRect = sc.getBoundingClientRect();
    const rowRect = targetRow.getBoundingClientRect();
    const targetTop = Math.max(0, sc.scrollTop + (rowRect.top - scRect.top) - 18);
    sc.scrollTo({ top: targetTop, behavior: "smooth" });
  } else {
    targetRow.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function jumpTimelineStep(delta) {
  const dotsHost = document.getElementById("timeline-dots");
  const rows = Array.from(document.querySelectorAll("#chat-messages .msg-user-row"));
  if (!dotsHost || !rows.length) return;
  const dots = Array.from(dotsHost.querySelectorAll(".tl-dot"));
  if (!dots.length) return;
  let cur = typeof state.activeTimelineIdx === "number" ? state.activeTimelineIdx : dots.length - 1;
  if (cur < 0 || cur >= dots.length) cur = dots.length - 1;
  const next = Math.max(0, Math.min(dots.length - 1, cur + delta));
  activateTimelineDot(next);
  scrollToUserTurn(next);
  showTimelineTooltip(dots[next], next, dots.length, dots[next].dataset.preview || "", dots[next].dataset.timeStr || "");
  clearTimeout(state._tlTipTimer);
  state._tlTipTimer = setTimeout(hideTimelineTooltip, 1600);
}

async function revertOrDeleteUserTurn(rowEl, restoreToInput = false) {
  if (state.isGenerating) {
    toast("Stop generation before editing or reverting a turn");
    return;
  }
  const host = document.getElementById("chat-messages");
  if (!host || !rowEl) return;
  const userRows = Array.from(host.querySelectorAll(".msg-user-row"));
  const turnIdx = userRows.indexOf(rowEl);
  if (turnIdx < 0) return;

  const promptText = rowEl.dataset.rawPrompt || "";
  if (state.activeSessionId) {
    try {
      await fetch(`/api/sessions/${encodeURIComponent(state.activeSessionId)}/truncate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ turn_index: turnIdx }),
      });
    } catch {
      // keep UI responsive
    }
  }

  // Remove this user row and everything after it
  const allChildren = Array.from(host.children);
  const startDomIdx = allChildren.indexOf(rowEl);
  if (startDomIdx >= 0) {
    for (let i = allChildren.length - 1; i >= startDomIdx; i--) {
      allChildren[i].remove();
    }
  }

  // Truncate timeline dots
  const dotsHost = document.getElementById("timeline-dots");
  const rail = document.getElementById("timeline-rail");
  if (dotsHost) {
    const dots = Array.from(dotsHost.querySelectorAll(".tl-dot"));
    for (let i = dots.length - 1; i >= turnIdx; i--) {
      dots[i].remove();
    }
    const remDots = dotsHost.querySelectorAll(".tl-dot").length;
    rail?.classList.toggle("has-items", remDots > 1);
    if (remDots > 0) activateTimelineDot(remDots - 1);
  }
  hideTimelineTooltip();

  if (host.children.length === 0) {
    document.getElementById("hero-welcome")?.classList.remove("hidden-hero");
  }

  if (restoreToInput && promptText) {
    const inp = document.getElementById("composer-input");
    if (inp) {
      inp.value = promptText;
      inp.dispatchEvent(new Event("input"));
      inp.focus();
    }
    toast("Turn reverted — prompt restored");
  } else {
    toast("Turn deleted");
  }
}

function appendUserBubble(text, timeStr = "") {
  const host = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = "msg-user-row";
  row.dataset.rawPrompt = text;
  row.innerHTML = `
    <div class="msg-user-wrap">
      <div class="msg-user-bubble">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
      <div class="msg-user-actions">
        <button type="button" class="msg-u-act" data-uact="copy" title="Copy prompt">Copy</button>
        <button type="button" class="msg-u-act" data-uact="revert" title="Undo turn & edit prompt">Undo & Edit</button>
        <button type="button" class="msg-u-act danger" data-uact="delete" title="Delete turn">Delete</button>
      </div>
    </div>
  `;
  row.querySelector('[data-uact="copy"]')?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast("Prompt copied");
    } catch {
      toast("Copy failed");
    }
  });
  row.querySelector('[data-uact="revert"]')?.addEventListener("click", () => revertOrDeleteUserTurn(row, true));
  row.querySelector('[data-uact="delete"]')?.addEventListener("click", () => revertOrDeleteUserTurn(row, false));
  host.appendChild(row);

  const now = new Date();
  const defaultStamp = `${now.toLocaleDateString([], { month: "short", day: "numeric" })} ${now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  const finalTime = String(timeStr || "").trim() || defaultStamp;

  const rail = document.getElementById("timeline-rail");
  const dotsHost = document.getElementById("timeline-dots") || rail;
  if (dotsHost) {
    const dot = document.createElement("span");
    dot.className = "tl-dot";
    dot.dataset.preview = text.slice(0, 120);
    dot.dataset.timeStr = finalTime;
    dot.addEventListener("mouseenter", () => {
      const allDots = Array.from(dotsHost.querySelectorAll(".tl-dot"));
      const idx = allDots.indexOf(dot);
      showTimelineTooltip(dot, Math.max(0, idx), allDots.length, dot.dataset.preview || "", dot.dataset.timeStr || "");
    });
    dot.addEventListener("mouseleave", hideTimelineTooltip);
    dot.addEventListener("click", () => {
      const allDots = Array.from(dotsHost.querySelectorAll(".tl-dot"));
      const idx = allDots.indexOf(dot);
      const safeIdx = Math.max(0, idx);
      activateTimelineDot(safeIdx);
      scrollToUserTurn(safeIdx);
    });
    dotsHost.appendChild(dot);
    const totalDots = dotsHost.querySelectorAll(".tl-dot").length;
    rail?.classList.toggle("has-items", totalDots > 1);
    activateTimelineDot(totalDots - 1);
  }
  row.scrollIntoView({ behavior: "smooth", block: "end" });
}

function formatCliToolTitle(name = "") {
  const n = String(name || "").toLowerCase();
  if (n.includes("read")) return "Read";
  if (n.includes("write") || n.includes("create")) return "Write";
  if (n.includes("edit") || n.includes("patch") || n.includes("replace")) return "Edit";
  if (n.includes("run") || n.includes("shell") || n.includes("exec") || n.includes("term") || n.includes("cmd")) return "Run";
  if (n.includes("search") || n.includes("grep") || n.includes("find")) return "Search";
  if (n.includes("list") || n.includes("dir") || n.includes("tree")) return "List";
  return String(name || "Tool")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatToolArgsText(args) {
  if (!args) return "";
  if (typeof args === "string") {
    const s = args.trim();
    if (s === "{}" || s === "None" || s === "null") return "";
    if (/(?:old|new|content|code)=/i.test(s)) {
      const pm = s.match(/(?:path|file_path|target_file|file)=([^,\r\n]+)/i);
      if (pm && pm[1]) return pm[1].trim().replace(/^['"]|['"]$/g, "");
    }
    return s;
  }
  if (typeof args === "object") {
    const pVal = args.path || args.file_path || args.target_file || args.file;
    if (pVal && ("content" in args || "old" in args || "new" in args || "code" in args)) {
      return String(pVal);
    }
    return Object.entries(args)
      .filter(([k, v]) => v !== undefined && v !== null && String(v) !== "" && !["content", "code", "old", "new", "old_str", "new_str"].includes(String(k).toLowerCase()))
      .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
      .join(", ");
  }
  return String(args);
}

function getToolIconSvg(name = "") {
  const n = String(name || "").toLowerCase();
  let d = `<path d="M7 10h3v-3l-3.5 -3.5a6 6 0 0 1 8 8l6 6a2 2 0 0 1 -3 3l-6 -6a6 6 0 0 1 -8 -8l3.5 3.5"/>`;
  if (n.includes("read")) d = `<path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/><path d="M9 9l1 0"/><path d="M9 13l6 0"/><path d="M9 17l6 0"/>`;
  else if (n.includes("write") || n.includes("edit") || n.includes("patch")) d = `<path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/>`;
  else if (n.includes("run") || n.includes("command") || n.includes("shell") || n.includes("cmd")) d = `<path d="M8 9l3 3l-3 3"/><path d="M13 15l3 0"/><path d="M3 4m0 2a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2z"/>`;
  else if (n.includes("search") || n.includes("grep") || n.includes("glob") || n.includes("find")) d = `<path d="M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/>`;
  else if (n.includes("ls") || n.includes("list") || n.includes("dir")) d = `<path d="M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2"/>`;
  else if (n.includes("web")) d = `<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/><path d="M3.6 9h16.8"/><path d="M3.6 15h16.8"/>`;
  else if (n.includes("todo") || n.includes("scratch")) d = `<path d="M9 11l3 3l8 -8"/><path d="M20 12v6a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h9"/>`;
  return `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
}

const CLI_NON_EXPANDABLE_TOOLS = new Set([
  "read", "file_read", "ls", "list", "dir", "scratch", "todo", "tasks",
  "glob", "search", "grep", "search_code", "find_files",
  "web", "webfetch", "fetch", "search_web", "web_search", "websearch", "searchweb",
  "google_search", "brave_search", "duckduckgo_search",
  "memory", "agent_note", "note", "ask",
]);

const CLI_TIMED_TOOLS = new Set([
  "write", "file_write", "edit", "file_edit", "patch",
  "terminal", "command", "shell", "bash", "sh", "cmd", "run_command", "exec",
  "powershell", "pwsh", "execute_command", "run_shell_command", "shell_command",
  "subagent", "task", "summarizing", "summarize", "compact", "context_compact",
]);

function normalizeToolKey(name = "") {
  let tl = String(name || "").toLowerCase().trim();
  if (tl.startsWith("tool:")) tl = tl.slice(5).trim();
  return tl;
}

function isTimedTool(name = "") {
  const tl = normalizeToolKey(name);
  return CLI_TIMED_TOOLS.has(tl);
}

function isToolExpandable(name = "", preview = "") {
  const tl = normalizeToolKey(name);
  const tlClean = tl.replace(/[-_\s]/g, "");
  if (CLI_NON_EXPANDABLE_TOOLS.has(tl) || CLI_NON_EXPANDABLE_TOOLS.has(tlClean)) {
    return false;
  }
  return Boolean(preview && String(preview).trim().length > 0 && String(preview).trim() !== "(No output)");
}

function renderFilesChangedCard(hostEl, filesMap) {
  if (!hostEl || !filesMap || filesMap.size === 0) return;
  const items = Array.from(filesMap.values());
  const totalAdd = items.reduce((s, f) => s + (f.added || 0), 0);
  const totalDel = items.reduce((s, f) => s + (f.removed || 0), 0);
  const card = document.createElement("div");
  card.className = "files-changed-card";
  card.innerHTML = `
    <div class="files-changed-head">
      <button type="button" class="files-changed-toggle">
        <span>${items.length} file${items.length === 1 ? "" : "s"} changed</span>
        <span class="fc-stats"><span class="fc-add">+${totalAdd}</span><span class="fc-del">-${totalDel}</span></span>
        <span class="thinking-chev">&#9662;</span>
      </button>
      <button type="button" class="ed-action-btn compact btn-fc-review">Review</button>
    </div>
    <div class="files-changed-list">
      ${items
        .map((f) => {
          const parts = String(f.path || "").split("/");
          const fname = parts.pop() || f.path;
          const dir = parts.join("/");
          return `
            <div class="fc-row">
              <div class="fc-left">
                ${getFileIconHtml(fname)}
                <span class="fc-name">${escapeHtml(fname)}</span>
                ${dir ? `<span class="fc-dir">${escapeHtml(dir)}</span>` : ""}
              </div>
              <span class="fc-stats"><span class="fc-add">+${f.added || 0}</span><span class="fc-del">-${f.removed || 0}</span></span>
            </div>`;
        })
        .join("")}
    </div>
  `;
  card.querySelector(".files-changed-toggle")?.addEventListener("click", () => {
    const col = card.classList.toggle("collapsed");
    const ch = card.querySelector(".thinking-chev");
    if (ch) ch.innerHTML = col ? "&#9656;" : "&#9662;";
  });
  card.querySelector(".btn-fc-review")?.addEventListener("click", () => openSecondaryPanel("review"));
  hostEl.innerHTML = "";
  hostEl.appendChild(card);
}

function createAssistantTurnCard(modelId, mode, supportsThinking = false) {
  const host = document.getElementById("chat-messages");
  const card = document.createElement("div");
  card.className = "msg-assistant-turn";
  card.innerHTML = `
    <div class="turn-head">
      <div class="turn-head-left">
        <span>${escapeHtml(modelId)}</span>
        <span class="turn-badge">${escapeHtml(mode)}</span>
      </div>
    </div>
    <div class="cli-loading-block">
      <span class="cli-loading-icon"></span>
      <span class="cli-loading-text">Generating...</span>
    </div>
    <div class="turn-flow"></div>
    <div class="diff-slot"></div>
    <div class="files-changed-slot"></div>
  `;
  const loadingEl = card.querySelector(".cli-loading-block");
  const hideLoading = () => loadingEl?.classList.add("hidden");
  const turnFlow = card.querySelector(".turn-flow");
  const diffSlot = card.querySelector(".diff-slot");
  const fcSlot = card.querySelector(".files-changed-slot");
  const pendingTools = [];
  const changedFilesMap = new Map();

  let curSegType = null; // "thinking" | "tools" | "md"
  let curThinkBody = null;
  let curRawThink = "";
  let curToolsStack = null;
  let curMdEl = null;
  let curRawMd = "";

  const ensureThinkingSeg = () => {
    if (curSegType === "thinking" && curThinkBody) return curThinkBody;
    const tb = document.createElement("div");
    tb.className = "thinking-block cli-tool-block";
    tb.innerHTML = `
      <button class="thinking-toggle thinking-head" type="button" aria-expanded="true">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 -6 6c0 2.15 1.15 4.02 2.85 5.05c.45 .28 .65 .78 .65 1.3v.65h5v-.65c0 -.52 .2 -1.02 .65 -1.3c1.7 -1.03 2.85 -2.9 2.85 -5.05a6 6 0 0 0 -6 -6z"/><path d="M9.5 19h5"/></svg>
        <span style="flex:1;text-align:left;">Thinking</span>
        <span class="thinking-chev">&#9662;</span>
      </button>
      <div class="thinking-body"></div>
    `;
    const toggle = tb.querySelector(".thinking-toggle");
    const chev = tb.querySelector(".thinking-chev");
    toggle.addEventListener("click", () => {
      const isCollapsed = tb.classList.toggle("collapsed");
      toggle.setAttribute("aria-expanded", String(!isCollapsed));
      if (chev) chev.innerHTML = isCollapsed ? "&#9656;" : "&#9662;";
    });
    turnFlow.appendChild(tb);
    curSegType = "thinking";
    curThinkBody = tb.querySelector(".thinking-body");
    curRawThink = "";
    curToolsStack = null;
    curMdEl = null;
    curRawMd = "";
    return curThinkBody;
  };

  const ensureToolsSeg = () => {
    if (curSegType === "tools" && curToolsStack) return curToolsStack;
    const st = document.createElement("div");
    st.className = "tools-stack";
    turnFlow.appendChild(st);
    curSegType = "tools";
    curToolsStack = st;
    curThinkBody = null;
    curRawThink = "";
    curMdEl = null;
    curRawMd = "";
    return st;
  };

  const ensureMdSeg = () => {
    if (curSegType === "md" && curMdEl) return curMdEl;
    const md = document.createElement("div");
    md.className = "assistant-md";
    turnFlow.appendChild(md);
    curSegType = "md";
    curMdEl = md;
    curRawMd = "";
    curThinkBody = null;
    curRawThink = "";
    curToolsStack = null;
    return md;
  };

  host.appendChild(card);

  return {
    el: card,
    appendThinking(chunk) {
      if (!chunk) return;
      if (!curRawThink && !String(chunk).trim()) return;
      hideLoading();
      const body = ensureThinkingSeg();
      curRawThink += chunk;
      body.textContent = curRawThink;
    },
    streamTool(ev) {
      hideLoading();
      const toolsStack = ensureToolsSeg();
      let el = toolsStack.querySelector(".cli-tool-block.live-stream-tool");
      const targetTxt = String(ev.args || "").trim();
      const lineTxt = ev.lines > 0 ? `generating · ${ev.lines} lines...` : "generating tool...";
      if (!el) {
        el = document.createElement("div");
        el.className = "cli-tool-block live-stream-tool expandable open";
        el.innerHTML = `
          <button class="cli-tool-head" type="button">
            <span class="cli-tool-ico">${getToolIconSvg(ev.name)}</span>
            <span class="cli-tool-name">${escapeHtml(formatCliToolTitle(ev.name))}</span>
            <span class="cli-tool-arg">${escapeHtml(targetTxt)}</span>
            <span class="cli-tool-time" style="color:var(--accent-blue)">${escapeHtml(lineTxt)}</span>
          </button>
          <div class="cli-tool-body" style="display:block;max-height:220px;overflow:auto;"><pre class="cli-tool-stream-pre" style="margin:0;padding:8px 10px;font-family:var(--font-mono);font-size:11.5px;white-space:pre-wrap;color:var(--text-secondary);"></pre></div>
        `;
        toolsStack.appendChild(el);
      } else {
        const nameEl = el.querySelector(".cli-tool-name");
        const argEl = el.querySelector(".cli-tool-arg");
        const timeEl = el.querySelector(".cli-tool-time");
        if (nameEl) nameEl.textContent = formatCliToolTitle(ev.name);
        if (argEl && targetTxt) argEl.textContent = targetTxt;
        if (timeEl) timeEl.textContent = lineTxt;
      }
      const pre = el.querySelector(".cli-tool-stream-pre");
      if (pre && ev.preview) {
        pre.textContent = ev.preview;
        const body = el.querySelector(".cli-tool-body");
        if (body) body.scrollTop = body.scrollHeight;
      }
      const cs = document.getElementById("chat-scroll");
      if (cs && cs.scrollHeight - cs.scrollTop - cs.clientHeight < 260) cs.scrollTop = cs.scrollHeight;
    },
    upsertSubagent(ev) {
      hideLoading();
      const toolsStack = ensureToolsSeg();
      toolsStack.querySelectorAll(".cli-tool-block.live-stream-tool").forEach((n) => n.remove());
      const sid = String(ev.id || ev.name || "subagent");
      let el = toolsStack.querySelector(`.cli-tool-block[data-subagent-id="${CSS.escape(sid)}"]`);
      const role = String(ev.role || ev.name || "Subagent");
      const status = String(ev.status || "running").toLowerCase();
      const isDone = status === "finished" || status === "completed";
      const isErr = status === "failed" || status === "error" || status === "cancelled";
      const statusColor = isErr ? "var(--accent-red)" : (isDone ? "var(--accent-green)" : "var(--accent-blue)");
      const subText = ev.tool ? `${ev.tool} ${ev.arg || ""}`.trim() : String(ev.summary || ev.goal || status);
      const subIco = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M12 7.5v4.5m0 0l-4.5 3.8m4.5 -3.8l4.5 3.8"/></svg>`;
      if (!el) {
        el = document.createElement("div");
        el.className = "cli-tool-block subagent-card expandable";
        el.dataset.subagentId = sid;
        el.innerHTML = `
          <button class="cli-tool-head" type="button" title="Open Subagent Inspector">
            <span class="cli-tool-ico" style="color:${statusColor}">${subIco}</span>
            <span class="cli-tool-name">Subagent · ${escapeHtml(role)}</span>
            <span class="cli-tool-arg">${escapeHtml(subText)}</span>
            <span class="cli-tool-time" style="color:${statusColor}">${escapeHtml(status)}</span>
            <span class="cli-tool-chev">↗</span>
          </button>
        `;
        el.querySelector(".cli-tool-head")?.addEventListener("click", () => openSubagentInspector(sid));
        toolsStack.appendChild(el);
      } else {
        const icoEl = el.querySelector(".cli-tool-ico");
        const argEl = el.querySelector(".cli-tool-arg");
        const timeEl = el.querySelector(".cli-tool-time");
        if (icoEl) icoEl.style.color = statusColor;
        if (argEl) argEl.textContent = subText;
        if (timeEl) { timeEl.textContent = status; timeEl.style.color = statusColor; }
      }
      const cs = document.getElementById("chat-scroll");
      if (cs && cs.scrollHeight - cs.scrollTop - cs.clientHeight < 260) cs.scrollTop = cs.scrollHeight;
    },
    startTool(ev) {
      hideLoading();
      const toolsStack = ensureToolsSeg();
      toolsStack.querySelectorAll(".cli-tool-block.live-stream-tool").forEach((n) => n.remove());
      const argsText = formatToolArgsText(ev.args);
      const isHist = Boolean(ev.historical);
      const el = document.createElement("div");
      el.className = "cli-tool-block";
      el.innerHTML = `
        <button class="cli-tool-head" type="button">
          <span class="cli-tool-ico">${getToolIconSvg(ev.name)}</span>
          <span class="cli-tool-name">${escapeHtml(formatCliToolTitle(ev.name))}</span>
          <span class="cli-tool-arg">${escapeHtml(argsText)}</span>
          <span class="cli-tool-time">${isHist ? "" : "running..."}</span>
          <span class="cli-tool-chev">&#9656;</span>
        </button>
        <div class="cli-tool-body"></div>
      `;
      el.querySelector(".cli-tool-head").addEventListener("click", () => {
        if (!el.classList.contains("expandable")) return;
        el.classList.toggle("expanded");
      });
      toolsStack.appendChild(el);
      pendingTools.push({ id: ev.id || "", name: ev.name || "", argsText, el, startedAt: performance.now(), done: false, historical: isHist });
    },
    finishTool(ev) {
      let rec = null;
      if (ev.id) {
        rec = pendingTools.find((r) => r.id === ev.id && !r.done);
      }
      if (!rec) {
        rec = pendingTools.find((r) => r.name === (ev.name || "") && !r.done) || pendingTools.find((r) => !r.done);
      }
      if (!rec) return;
      rec.done = true;
      const { el, startedAt, argsText, historical } = rec;
      const ok = ev.ok !== false && ev.result?.success !== false;
      const ico = el.querySelector(".cli-tool-ico");
      if (ico && !ok) ico.classList.add("error");
      const timeEl = el.querySelector(".cli-tool-time");
      if (timeEl) {
        if (!isTimedTool(ev.name)) {
          timeEl.textContent = "";
        } else if (ev.duration_ms) {
          const sec = Number(ev.duration_ms) / 1000;
          timeEl.textContent = sec >= 0.05 ? `${sec.toFixed(1)}s` : "";
        } else if (!historical && !ev.historical) {
          const sec = (performance.now() - startedAt) / 1000;
          timeEl.textContent = sec >= 0.05 ? `${sec.toFixed(1)}s` : "";
        } else {
          timeEl.textContent = "";
        }
      }
      const preview = String(ev.diff?.unified || ev.preview || ev.result?.content || ev.result?.output || ev.result?.error || "").trim();
      const bodyEl = el.querySelector(".cli-tool-body");
      const canExpand = isToolExpandable(ev.name, preview);
      el.classList.toggle("expandable", canExpand);
      if (bodyEl && canExpand) {
        const lines = [];
        if (argsText) lines.push(`> ${formatCliToolTitle(ev.name)} ${argsText}`);
        if (preview) lines.push(preview);
        bodyEl.textContent = lines.join("\n");
      }
      const tLow = String(ev.name || "").toLowerCase();
      if (ok && (tLow === "write" || tLow === "edit" || tLow === "patch" || ev.diff)) {
        const fPath = String(ev.diff?.path || "").trim() || (() => {
          const pMatch = argsText.match(/path=([^,]+)/i);
          return (pMatch ? pMatch[1] : argsText).trim().replace(/^['"]|['"]$/g, "");
        })();
        if (fPath) {
          const entry = {
            path: fPath,
            added: Number(ev.diff?.added ?? 1),
            removed: Number(ev.diff?.removed ?? (tLow === "edit" ? 1 : 0)),
            unified: String(ev.diff?.unified || preview || ""),
          };
          changedFilesMap.set(fPath, entry);
          if (!(state.sessionChanges instanceof Map)) state.sessionChanges = new Map();
          state.sessionChanges.set(fPath, entry);
        }
      }
    },
    showDiff(diff) {
      hideLoading();
      if (!diff || !diff.path) return;
      changedFilesMap.set(diff.path, {
        path: diff.path,
        added: Number(diff.added || 0),
        removed: Number(diff.removed || 0),
      });
      diffSlot.innerHTML = `
        <div class="diff-preview-card">
          <div class="diff-preview-head">
            <span style="font-family:var(--font-mono);font-size:11.5px;">Diff: ${escapeHtml(diff.path)} (+${diff.added || 0} / -${diff.removed || 0})</span>
            <button class="ed-action-btn compact">Open in Files</button>
          </div>
          <pre class="diff-code">${escapeHtml((diff.unified || "").split("\n").slice(0, 12).join("\n"))}</pre>
        </div>
      `;
      diffSlot.querySelector("button").addEventListener("click", async () => {
        await openSecondaryPanel("files");
        await editor.openFile(diff.path, 1);
      });
    },
    appendToken(tok) {
      hideLoading();
      const nextRaw = (curSegType === "md" ? curRawMd : "") + tok;
      const cleaned = cleanMessageContent(nextRaw);
      if (curSegType !== "md" && !cleaned) return;
      const md = ensureMdSeg();
      curRawMd = nextRaw;
      md.innerHTML = cleaned ? formatMd(cleaned) : "";
      const sc = document.getElementById("chat-scroll");
      if (sc) sc.scrollTop = sc.scrollHeight;
    },
    setDone(finalText = null) {
      hideLoading();
      if (finalText !== null) {
        const cleanedFinal = cleanMessageContent(finalText);
        if (cleanedFinal) {
          if (curSegType === "md" && curMdEl && curRawMd.trim()) {
            const cleanedCur = cleanMessageContent(curRawMd);
            curMdEl.innerHTML = cleanedCur ? formatMd(cleanedCur) : formatMd(cleanedFinal);
          } else {
            const md = ensureMdSeg();
            curRawMd = finalText;
            md.innerHTML = formatMd(cleanedFinal);
          }
        }
      } else if (curSegType === "md" && curMdEl && curRawMd) {
        const cleanedCur = cleanMessageContent(curRawMd);
        curMdEl.innerHTML = cleanedCur ? formatMd(cleanedCur) : "";
      }
      renderFilesChangedCard(fcSlot, changedFilesMap);
    },
    setError(msg) {
      hideLoading();
      const md = ensureMdSeg();
      md.innerHTML = `<p style="color:var(--accent-red);">${escapeHtml(msg)}</p>`;
    },
  };
}

function syncChatBottomPadding() {
  const msgs = document.getElementById("chat-messages");
  const wrap = document.getElementById("composer-wrap");
  if (!msgs || !wrap) return;
  const h = wrap.offsetHeight || 140;
  msgs.style.paddingBottom = `${Math.max(190, h + 32)}px`;
}

function renderComposerTodoBar(todos) {
  const wrap = document.getElementById("ctx-tasks-wrap");
  const lbl = document.getElementById("ctx-tasks-label");
  const cnt = document.getElementById("tasks-pop-count");
  const listEl = document.getElementById("tasks-pop-list");
  const drawer = document.getElementById("composer-tasks-drawer");
  const pill = document.getElementById("btn-ctx-tasks");
  if (!wrap || !listEl || !drawer) return;
  const list = Array.isArray(todos) ? todos : [];
  if (!list.length) {
    wrap.classList.add("hidden");
    drawer.classList.add("hidden");
    pill?.classList.remove("open");
    listEl.innerHTML = "";
    syncChatBottomPadding();
    return;
  }
  const doneCount = list.filter((t) => typeof t === "object" && Boolean(t.done || t.completed)).length;
  wrap.classList.remove("hidden");
  if (lbl) lbl.textContent = `Tasks (${doneCount}/${list.length})`;
  if (cnt) cnt.textContent = `${doneCount}/${list.length}`;
  listEl.innerHTML = list
    .map((t) => {
      const text = typeof t === "string" ? t : (t.text || t.title || JSON.stringify(t));
      const isDone = typeof t === "object" && Boolean(t.done || t.completed);
      return `<div class="todo-bar-row${isDone ? " done" : ""}"><span>${isDone ? "✓" : "○"}</span><span>${escapeHtml(text)}</span></div>`;
    })
    .join("");
  syncChatBottomPadding();
}

function showApprovalBar(ev) {
  const bar = document.getElementById("composer-approval-bar");
  const shellFrame = document.querySelector(".composer-shell-frame");
  if (!bar || !ev?.id) return;
  const det = ev.details || {};
  const action = String(det.action || "ask");
  const isAsk = action === "ask";
  const target = String(det.target || det.path || det.file_path || "").trim();
  const title = isAsk
    ? (det.question || "Agent Question")
    : (target && target.toLowerCase() !== action.toLowerCase()
        ? `Approve ${action}: ${target}`
        : `Approve ${action}`);
  let detailTxt = isAsk ? "" : String(det.diff_info || det.cmd || det.path || "").trim();
  if (detailTxt === "+0 lines" || detailTxt === "+0 / -0 lines") detailTxt = "";
  const options = isAsk && Array.isArray(det.options) && det.options.length
    ? det.options
    : ["Allow", "Deny"];

  const cleanup = () => {
    bar.classList.add("hidden");
    bar.innerHTML = "";
    if (shellFrame) shellFrame.classList.remove("hidden");
    document.removeEventListener("keydown", onAprKey);
    syncChatBottomPadding();
  };

  const sendDecision = async (val) => {
    cleanup();
    const decision = isAsk ? val : (val === "Allow" ? "allow" : "deny");
    await fetch("/api/agent/respond", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: ev.id, decision }),
    }).catch(() => {});
  };

  const onAprKey = (ke) => {
    if (bar.classList.contains("hidden")) return;
    if (document.activeElement?.id === "approval-custom-input") return;
    if (ke.key === "Enter" || ke.key === "1") { ke.preventDefault(); sendDecision(options[0]); }
    else if (ke.key === "Escape" || ke.key === "2") { ke.preventDefault(); sendDecision(options[1] || "Deny"); }
  };
  document.addEventListener("keydown", onAprKey);

  // Replace entire composer shell cleanly while awaiting approval (no empty strip underneath!)
  if (shellFrame) shellFrame.classList.add("hidden");
  bar.classList.remove("hidden");
  bar.innerHTML = `
    <div class="approval-title">${escapeHtml(title)}</div>
    ${detailTxt ? `<div class="approval-detail">${escapeHtml(detailTxt)}</div>` : ""}
    <div class="approval-actions">
      ${options
        .map((opt, idx) => `<button type="button" class="ed-action-btn small${idx === 0 ? " primary" : ""}" data-apr-val="${escapeHtml(opt)}">${escapeHtml(opt)}</button>`)
        .join("")}
      ${!isAsk ? `<span style="font-size:11px;color:var(--text-muted);margin-left:auto;">Enter: Allow · Esc: Deny</span>` : ""}
    </div>
    ${isAsk ? `
    <div style="display:flex;gap:6px;margin-top:8px;">
      <input type="text" id="approval-custom-input" class="glass-input" style="flex:1;padding:5px 9px;font-size:12px;" placeholder="Or type a custom answer..." />
      <button type="button" id="approval-custom-send" class="ed-action-btn small primary">Reply</button>
    </div>` : ""}
  `;
  syncChatBottomPadding();
  const cs = document.getElementById("chat-scroll");
  if (cs) cs.scrollTop = cs.scrollHeight;
  bar.querySelectorAll("[data-apr-val]").forEach((btn) => {
    btn.addEventListener("click", () => sendDecision(btn.dataset.aprVal));
  });
  const custIn = document.getElementById("approval-custom-input");
  const custBtn = document.getElementById("approval-custom-send");
  if (custIn && custBtn) {
    const sendCustom = () => {
      const v = custIn.value.trim();
      if (v) sendDecision(v);
    };
    custBtn.addEventListener("click", sendCustom);
    custIn.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendCustom();
      }
    });
  }
  syncChatBottomPadding();
}

function setGeneratingUI(isGen) {
  state.isGenerating = Boolean(isGen);
  const btn = document.getElementById("btn-send-prompt");
  if (btn) {
    btn.classList.toggle("is-stopping", state.isGenerating);
    if (state.isGenerating) {
      btn.title = "Stop generating (Esc)";
      btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`;
    } else {
      btn.title = "Send (Enter)";
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5l0 14"/><path d="M18 11l-6 -6"/><path d="M6 11l6 -6"/></svg>`;
    }
  }
  renderWorkspacesSidebar();
  renderTopbarTabs();
}

function stopActiveGeneration() {
  if (state.activeStreamReader) {
    try { state.activeStreamReader.cancel(); } catch (_) {}
    state.activeStreamReader = null;
  }
  if (state.activeAbortController) {
    try {
      state.activeAbortController.abort();
    } catch {
      // ignore
    }
    state.activeAbortController = null;
  }
  if (state.activeTurnCard) {
    try { state.activeTurnCard.setDone(null); } catch (_) {}
    state.activeTurnCard = null;
  }
  setGeneratingUI(false);
  renderWorkspacesSidebar();
  toast("Generation stopped");
}

async function dispatchAgentPrompt(promptText) {
  if (!promptText || state.isGenerating) return;
  closeModelsView();
  document.getElementById("hero-welcome")?.classList.add("hidden-hero");
  appendUserBubble(promptText);

  const curTab = getActiveTabObj();
  if (curTab && !curTab.sessionId) {
    curTab.title = promptText.slice(0, 32) + (promptText.length > 32 ? "..." : "");
    renderTopbarTabs();
  }

  setGeneratingUI(true);
  const ctrl = new AbortController();
  state.activeAbortController = ctrl;
  renderWorkspacesSidebar();
  const activeMeta = findModelMeta(state.activeProvider, state.activeModel);
  const supportsThinking = Boolean(activeMeta?.thinking && Array.isArray(activeMeta.levels) && activeMeta.levels.length > 0);
  const card = createAssistantTurnCard(activeMeta?.name || state.activeModel, state.mode, supportsThinking);
  state.activeTurnCard = card;

  let receivedAnyEvent = false;
  try {
    const reqBody = JSON.stringify({
      prompt: promptText,
      session_id: state.activeSessionId,
      workdir: state.workdir,
      provider: state.activeProvider,
      model: state.activeModel,
      mode: state.mode,
      thinking_level: state.reasoningLevel,
      pinned_files: state.pinnedFiles,
      use_live: true,
    });
    let resp = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        resp = await fetch("/api/agent/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: ctrl.signal,
          body: reqBody,
        });
        break;
      } catch (fetchErr) {
        if (fetchErr?.name === "AbortError" || attempt >= 1) throw fetchErr;
        await new Promise((r) => setTimeout(r, 450));
      }
    }
    if (!resp || !resp.ok || !resp.body) {
      throw new Error(`HTTP ${resp ? resp.status : "network"} error`);
    }
    const reader = resp.body.getReader();
    state.activeStreamReader = reader;
    const dec = new TextDecoder();
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const rawEv of parts) {
        if (!rawEv.startsWith("data: ")) continue;
        receivedAnyEvent = true;
        const ev = JSON.parse(rawEv.slice(6));
        if (ev.type === "meta" && ev.session_id) {
          state.activeSessionId = ev.session_id;
          if (curTab) curTab.sessionId = ev.session_id;
          renderWorkspacesSidebar();
        }
        else if (ev.type === "thinking") card.appendThinking(ev.text || "");
        else if (ev.type === "tool_streaming") card.streamTool(ev);
        else if (ev.type === "browser_event") {
          if (ev.running && state.secondaryView !== "browser") {
            openSecondaryPanel("browser");
          }
          applyBrowserState(ev);
        }
        else if (ev.type === "subagent_event") {
          card.upsertSubagent(ev);
          if (state.bootstrap) {
            const list = Array.isArray(state.bootstrap.subagents) ? state.bootstrap.subagents : (state.bootstrap.subagents = []);
            const idxS = list.findIndex((x) => String(x.id || "") === String(ev.id || ""));
            if (idxS >= 0) {
              const prev = list[idxS];
              list[idxS] = {
                ...prev,
                ...ev,
                goal: ev.goal || prev.goal || "",
                output: ev.output || prev.output || "",
                events: (Array.isArray(ev.events) && ev.events.length) ? ev.events : (prev.events || []),
              };
            } else {
              list.unshift(ev);
            }
            renderOrbitPanels();
            if (state.secondaryView === "subagent" && String(state.activeSubagentId || "") === String(ev.id || "")) {
              renderSubagentInspector();
            }
          }
        }
        else if (ev.type === "tool_start") card.startTool(ev);
        else if (ev.type === "tool_finish") { card.finishTool(ev); const cs = document.getElementById("chat-scroll"); if (cs) cs.scrollTop = cs.scrollHeight; }
        else if (ev.type === "todo_update") renderComposerTodoBar(ev.todos || []);
        else if (ev.type === "approval_request") showApprovalBar(ev);
        else if (ev.type === "diff_proposal") card.showDiff(ev.diff);
        else if (ev.type === "token") {
          card.appendToken(ev.text || "");
          const cs = document.getElementById("chat-scroll");
          if (cs && cs.scrollHeight - cs.scrollTop - cs.clientHeight < 220) cs.scrollTop = cs.scrollHeight;
        }
        else if (ev.type === "done") {
          card.setDone(ev.text || null);
          document.getElementById("composer-approval-bar")?.classList.add("hidden");
          document.querySelector(".composer-shell-frame")?.classList.remove("hidden");
          const cs = document.getElementById("chat-scroll");
          if (cs) cs.scrollTop = cs.scrollHeight;
          if (ev.session_id) {
            state.activeSessionId = ev.session_id;
            if (curTab) curTab.sessionId = ev.session_id;
          }
        } else if (ev.type === "error") {
          card.setError(ev.message || "Stream error");
          document.getElementById("composer-approval-bar")?.classList.add("hidden");
          document.querySelector(".composer-shell-frame")?.classList.remove("hidden");
        }
      }
    }
    await refreshBootstrap().catch(() => {});
  } catch (err) {
    if (err?.name === "AbortError") {
      card.setDone(null);
      toast("Generation stopped");
    } else if (/failed to fetch|networkerror|load failed/i.test(String(err?.message || ""))) {
      if (receivedAnyEvent) {
        card.setDone(null);
        toast("Stream interrupted by bridge");
      } else {
        card.setError("Connection to Desktop bridge failed (Failed to fetch). Ensure CMDAI Desktop is running and retry.");
      }
    } else {
      card.setError(err.message);
    }
  } finally {
    state.activeAbortController = null;
    state.activeStreamReader = null;
    state.activeTurnCard = null;
    setGeneratingUI(false);
    renderWorkspacesSidebar();
  }
}

async function sendPrompt() {
  const inp = document.getElementById("composer-input");
  const raw = (inp?.value || "").trim();
  if (!raw || state.isGenerating) return;

  if (raw.startsWith("/")) {
    const handled = await runSlashCommand(raw);
    if (handled) {
      inp.value = "";
      autoResizeComposer();
      return;
    }
  }

  inp.value = "";
  autoResizeComposer();
  await dispatchAgentPrompt(raw);
}

/* ================= SETTINGS & PROJECT PANES ================= */

function openSettingsAtTab(tabId) {
  renderSettingsProjectsNav();
  document.getElementById("settings-overlay")?.classList.remove("hidden");
  document.querySelectorAll(".settings-tab, #settings-projects-nav .ag-sb-item").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".settings-pane").forEach((p) => p.classList.remove("active"));
  document.querySelector(`.settings-tab[data-stab="${tabId}"]`)?.classList.add("active");
  document.getElementById(`stab-${tabId}`)?.classList.add("active");
}

function openRulesModal() {
  document.getElementById("settings-overlay")?.classList.add("hidden");
  document.getElementById("rules-overlay")?.classList.remove("hidden");
  return loadRulesStudio();
}

function closeRulesModal() {
  document.getElementById("rules-overlay")?.classList.add("hidden");
}

const rulesStudioState = {
  data: null,
  dirty: false,
};

const _RULES_SNIPPETS = {
  build: "\n## Build & Test Commands\n- Run tests: `pytest`\n- Build: ``\n",
  style: "\n## Code Style & Conventions\n- Keep functions concise and single-purpose.\n- Reuse existing helpers instead of duplicating logic.\n",
  safety: "\n## Safety & Constraints\n- Never commit secrets, `.env` files, or API keys.\n- Ask before destructive changes or deleting user data.\n",
  language: "\n## Language & Communication\n- Respond in Polish; write code, symbols, and commit messages in English.\n",
};

function _estimateRuleTokens(text) {
  const cleaned = String(text || "").trim();
  if (!cleaned) return 0;
  return Math.max(1, Math.floor(cleaned.length / 4));
}

function updateRulesTokenBadge() {
  const badge = document.getElementById("rules-token-badge");
  if (!badge) return;
  const ta = document.getElementById("rules-editor-textarea");
  const val = ta ? ta.value : "";
  const tok = _estimateRuleTokens(val);
  badge.textContent = `~${tok} tok · ${val.length} chars`;
  badge.classList.toggle("warn", tok > 2000);
}

async function loadRulesStudio() {
  const statusEl = document.getElementById("rules-save-status");
  const pathEl = document.getElementById("rules-file-path");
  const ta = document.getElementById("rules-editor-textarea");
  try {
    const resp = await fetch("/api/rules");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    rulesStudioState.data = data;
    rulesStudioState.dirty = false;
    if (pathEl) {
      const rawP = data.path || "AGENTS.md";
      pathEl.textContent = data.exists ? rawP : `${rawP} (not created yet)`;
      pathEl.title = rawP;
    }
    if (ta) {
      ta.value = data.content || "";
      ta.focus();
    }
    if (statusEl) statusEl.textContent = "";
    updateRulesTokenBadge();
  } catch (err) {
    if (statusEl) statusEl.textContent = `Could not load AGENTS.md: ${err?.message || err}`;
  }
}

async function saveRulesStudio() {
  const ta = document.getElementById("rules-editor-textarea");
  const pathEl = document.getElementById("rules-file-path");
  const content = ta ? ta.value : "";
  const statusEl = document.getElementById("rules-save-status");
  if (statusEl) statusEl.textContent = "Saving...";
  try {
    const resp = await fetch("/api/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    rulesStudioState.data = data;
    rulesStudioState.dirty = false;
    if (pathEl) {
      const rawP = data.path || "AGENTS.md";
      pathEl.textContent = data.exists ? rawP : `${rawP} (not created yet)`;
      pathEl.title = rawP;
    }
    updateRulesTokenBadge();
    if (statusEl) statusEl.textContent = "Saved AGENTS.md — applies on next message.";
    toast("AGENTS.md saved");
  } catch (err) {
    if (statusEl) statusEl.textContent = `Save failed: ${err?.message || err}`;
  }
}

function insertRulesSnippet(kind) {
  const snippet = _RULES_SNIPPETS[kind];
  const ta = document.getElementById("rules-editor-textarea");
  if (!snippet || !ta) return;
  const cur = ta.value;
  const sep = cur.length > 0 && !cur.endsWith("\n") ? "\n" : "";
  ta.value = cur + sep + snippet.replace(/^\n/, "");
  rulesStudioState.dirty = true;
  updateRulesTokenBadge();
  ta.focus();
}

function openNewProjectPane() {
  document.getElementById("settings-overlay")?.classList.remove("hidden");
  document.querySelectorAll(".settings-tab, #settings-projects-nav .ag-sb-item").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".settings-pane").forEach((p) => p.classList.remove("active"));
  document.getElementById("stab-new-project")?.classList.add("active");

  const nameInp = document.getElementById("new-proj-name-input");
  const pathInp = document.getElementById("new-proj-path-input");
  if (nameInp) nameInp.value = "";
  if (pathInp) {
    pathInp.value = "";
    if (!mobileUI.isMobile) setTimeout(() => pathInp.focus(), 40);
  }

  const candHost = document.getElementById("new-proj-candidates-list");
  if (candHost) {
    const activeKey = normalizePathKey(state.workdir);
    const others = (state.workspaces || []).filter((w) => normalizePathKey(w.path) !== activeKey);
    if (!others.length) {
      candHost.innerHTML = `<div class="ag-card-row"><div class="ag-row-desc">No other workspaces indexed yet — enter a path above to create or open a project.</div></div>`;
    } else {
      candHost.innerHTML = "";
      others.forEach((w) => {
        const row = document.createElement("div");
        row.className = "ag-card-row";
        row.innerHTML = `
          <div>
            <div class="ag-row-title">${escapeHtml(projectDisplayName(w))}</div>
            <div class="ag-row-desc" style="font-family:var(--font-mono);">${escapeHtml(w.path)}</div>
          </div>
          <button class="ed-action-btn compact">Open Project</button>
        `;
        row.querySelector("button").addEventListener("click", async () => {
          if (await switchWorkspacePath(w.path, false)) {
            openProjectSettings(w.path);
          }
        });
        candHost.appendChild(row);
      });
    }
  }
}

async function openProjectSettings(wsPath = null, opts = {}) {
  const target = wsPath || state.workdir || state.workspaces[0]?.path || "";
  state.selectedProjectSettingsPath = target;
  renderSettingsProjectsNav();
  document.getElementById("settings-overlay")?.classList.remove("hidden");
  document.querySelectorAll(".settings-tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".settings-pane").forEach((p) => p.classList.remove("active"));
  document.getElementById("stab-project")?.classList.add("active");
  await renderProjectSettingsPane(target, opts);
}

function renderSettingsProjectsNav() {
  const nav = document.getElementById("settings-projects-nav");
  if (!nav) return;
  nav.innerHTML = "";
  const selKey = normalizePathKey(state.selectedProjectSettingsPath || state.workdir);
  (state.workspaces || []).forEach((w) => {
    const k = normalizePathKey(w.path);
    const btn = document.createElement("button");
    btn.className = `ag-sb-item${k === selKey && document.getElementById("stab-project")?.classList.contains("active") ? " active" : ""}`;
    btn.dataset.projPath = w.path;
    btn.textContent = projectDisplayName(w);
    btn.addEventListener("click", () => openProjectSettings(w.path));
    nav.appendChild(btn);
  });
}

async function renderProjectSettingsPane(wsPath, opts = {}) {
  const ws = (state.workspaces || []).find((w) => normalizePathKey(w.path) === normalizePathKey(wsPath)) || {
    name: wsPath.split(/[\\/]/).filter(Boolean).pop() || "Project",
    path: wsPath,
  };
  const titleEl = document.getElementById("proj-settings-title");
  if (titleEl) titleEl.textContent = projectDisplayName(ws);

  const foldersHost = document.getElementById("proj-folders-list");
  if (foldersHost) {
    const isAct = normalizePathKey(ws.path) === normalizePathKey(state.workdir);
    const shortSeg = ws.path.split(/[\\/]/).filter(Boolean).pop() || ws.path;
    foldersHost.innerHTML = `
      <div class="proj-folder-item">
        <div class="proj-folder-left">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2"/></svg>
          <strong>${escapeHtml(shortSeg)}/</strong>
          <span class="proj-folder-path">${escapeHtml(ws.path)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          ${
            isAct
              ? `<span class="cap-tag" style="color:var(--accent-blue);background:var(--accent-blue-soft);border-color:var(--accent-blue-border);">Active</span>`
              : `<button class="ed-action-btn compact btn-switch-proj-here">Open Workspace</button>`
          }
        </div>
      </div>
    `;
    foldersHost.querySelector(".btn-switch-proj-here")?.addEventListener("click", async () => {
      if (await switchWorkspacePath(ws.path)) {
        await renderProjectSettingsPane(ws.path);
      }
    });
  }

  const addForm = document.getElementById("proj-add-folder-form");
  if (addForm) {
    addForm.classList.toggle("hidden", !opts.expandAddFolder);
  }

  const custStatus = document.getElementById("proj-customizations-status");
  const custList = document.getElementById("proj-customizations-list");
  const countEl = document.getElementById("proj-skills-count");
  const skillsList = document.getElementById("proj-skills-list");

  try {
    const resp = await fetch(`/api/project/details?path=${encodeURIComponent(ws.path)}`);
    const det = await resp.json();
    const realCustoms = det.customizations || [];
    const realSkills = det.skills || [];

    if (custStatus) {
      custStatus.textContent = realCustoms.length
        ? `${realCustoms.length} project rule/command customization file(s) found.`
        : "There are no workspace rule or command customizations in this folder.";
    }
    if (custList) {
      custList.innerHTML = "";
      realCustoms.forEach((c) => {
        const row = document.createElement("div");
        row.className = "proj-custom-row clickable";
        row.title = `Click to read ${c.path}`;
        row.innerHTML = `
          <div><strong>${escapeHtml(c.name)}</strong> <span class="ag-skill-badge">${escapeHtml(c.kind)}</span></div>
          <span style="font-family:var(--font-mono);color:var(--text-muted);">${escapeHtml(c.path)}</span>
        `;
        row.addEventListener("click", () => {
          const pNorm = String(c.path || "").replace(/\\/g, "/");
          if (pNorm === "AGENTS.md") {
            openRulesModal();
          } else {
            openCustomizationReader(c.name, c.path);
          }
        });
        custList.appendChild(row);
      });
    }

    if (countEl) countEl.textContent = String(realSkills.length);
    if (skillsList) {
      skillsList.classList.toggle("hidden", state.skillsCollapsed);
      if (!realSkills.length) {
        skillsList.innerHTML = `
          <div class="ag-card-row">
            <div>
              <div class="ag-row-title">No workspace skills defined</div>
              <div class="ag-row-desc">Add markdown skills inside <code>.cmdai/skills/</code> in this repository to enable project-specific skills.</div>
            </div>
          </div>`;
      } else {
        skillsList.innerHTML = realSkills
          .map(
            (sk) => `
            <div class="ag-card-row">
              <div>
                <div class="ag-row-title">${escapeHtml(sk.name)}<span class="ag-skill-badge">${escapeHtml(sk.scope)}</span></div>
                <div class="ag-row-desc">${escapeHtml(sk.desc)}</div>
              </div>
            </div>`
          )
          .join("");
      }
    }
  } catch {
    if (custStatus) custStatus.textContent = "Could not inspect project customizations.";
    if (countEl) countEl.textContent = "0";
    if (skillsList) skillsList.innerHTML = "";
  }
}

async function runSlashCommand(rawInput) {
  const tokens = rawInput.trim().split(/\s+/);
  const cmd = (tokens[0] || "").toLowerCase();
  const arg = tokens.slice(1).join(" ").trim();

  switch (cmd) {
    case "/new":
      startNewConversation(true);
      return true;
    case "/files":
    case "/editor":
      await openSecondaryPanel("files");
      return true;
    case "/diff":
    case "/review":
    case "/revert":
      await openSecondaryPanel("review");
      return true;
    case "/map":
      await openSecondaryPanel("map");
      return true;
    case "/terminal":
      await openSecondaryPanel("terminal");
      return true;
    case "/models":
      openModelsView("show_in_input");
      return true;
    case "/modelinfo": {
      const m = await ensureModelMeta(state.activeProvider, state.activeModel);
      toast(`${m?.name || state.activeModel} · thinking=${m?.thinking ? state.reasoningLevel : "no"} · source=${m?.source || "catalog"}`);
      return true;
    }
    case "/mode":
      await cycleAgentMode();
      return true;
    case "/thinking":
      await cycleThinkingLevel();
      return true;
    case "/settings":
    case "/params":
      openSettingsAtTab("agent");
      return true;
    case "/rules":
    case "/agents":
      await openRulesModal();
      return true;
    case "/loader":
    case "/updatesettings":
      openModelsView("engine");
      return true;
    case "/bg":
      await openSecondaryPanel("tasks");
      return true;
    case "/mcp":
      await openSecondaryPanel("mcp");
      return true;
    case "/checkpoints":
      await openSecondaryPanel("checkpoints");
      return true;
    case "/sync":
      await openSecondaryPanel("sync");
      return true;
    case "/help":
      openSettingsAtTab("shortcuts");
      return true;
    case "/sessions":
      document.getElementById("left-sidebar")?.classList.remove("collapsed");
      document.getElementById("btn-expand-sidebar")?.classList.add("hidden");
      toast(`${state.sessions.length} conversations across ${state.workspaces.length} projects`);
      return true;
    case "/branch":
    case "/git":
      await populateBranchPopover();
      toggleComposerPopover("popover-branch", true, true);
      return true;
    case "/cd":
      if (arg) await switchWorkspacePath(arg);
      else openNewProjectPane();
      return true;
    case "/add":
      if (arg && state.filePaths.includes(arg)) {
        togglePinnedFile(arg, true);
      } else {
        const inp = document.getElementById("composer-input");
        if (inp) {
          inp.value = "@";
          inp.focus();
          updateAutocomplete();
        }
      }
      return true;
    case "/drop":
      state.pinnedFiles = [];
      togglePinnedFile("", false);
      toast("Cleared attached file chips");
      return true;
    case "/ctx":
      toast(`Project: ${state.workdir} · Attached files: ${state.pinnedFiles.length}`);
      return true;
    case "/stats": {
      const turns = document.querySelectorAll(".msg-assistant-turn").length;
      toast(`Session stats: ${turns} turns · Model: ${state.activeModel} · Mode: ${state.mode}`);
      return true;
    }
    case "/memory":
      await openSecondaryPanel("files");
      await editor.openFile(".cmdai/memory.md", 1).catch(() => toast("No .cmdai/memory.md yet"));
      return true;
    case "/custom":
    case "/plugins":
      openProjectSettings(state.workdir);
      return true;
    case "/new":
      startNewConversation(true);
      toast("Started new conversation");
      return true;
    case "/summarize":
      await dispatchAgentPrompt("Summarize the key decisions, files changed, and next steps from this conversation into a concise handoff.");
      return true;
    case "/plan":
      state.mode = "plan";
      updateModeUI();
      if (arg) await dispatchAgentPrompt(arg);
      else toast("Switched to plan mode — describe the task to plan");
      return true;
    case "/todo":
      await dispatchAgentPrompt("Scan workspace TODOs and list prioritized action items.");
      return true;
    case "/commit":
      await dispatchAgentPrompt("Inspect git status and git diff, then propose a concise conventional commit message.");
      return true;
    case "/revert":
      await openSecondaryPanel("checkpoints");
      toast("Checkpoints opened — select a snapshot to revert");
      return true;
    case "/system":
      await dispatchAgentPrompt("Describe the active CMDAI CODE agent rules, tools, and modes.");
      return true;
    case "/exit":
      closeSecondaryPanel();
      closeModelsView();
      closeAllComposerPopovers();
      toast("Closed panels");
      return true;
    default:
      return false;
  }
}

async function cycleAgentMode() {
  const idx = MODE_ORDER.indexOf(state.mode);
  state.mode = MODE_ORDER[(idx + 1) % MODE_ORDER.length];
  updateModeUI();
  await saveActiveModelSettings(state.activeProvider, state.activeModel);
  toast(`Agent mode: ${state.mode}`);
}

async function cycleThinkingLevel() {
  const meta = await ensureModelMeta(state.activeProvider, state.activeModel);
  if (!meta?.thinking || !meta.levels?.length) {
    toast(`${meta?.name || state.activeModel} does not support thinking`);
    return;
  }
  const idx = meta.levels.indexOf(state.reasoningLevel);
  state.reasoningLevel = meta.levels[(idx + 1) % meta.levels.length];
  await saveActiveModelSettings(state.activeProvider, state.activeModel);
  syncReasoningUI(meta);
  toast(`Thinking effort: ${state.reasoningLevel}`);
}

function populateWorkdirPopover() {
  const list = document.getElementById("workdir-options-list");
  const secLbl = document.getElementById("wd-pop-section-label");
  const searchInp = document.getElementById("workdir-search-input");
  if (!list) return;
  const q = (searchInp?.value || "").trim().toLowerCase();
  const allWs = state.workspaces || [];
  const activeKey = normalizePathKey(state.workdir);

  let items = [];
  if (q) {
    if (secLbl) secLbl.textContent = "Matching Projects";
    items = allWs.filter((w) => {
      const disp = projectDisplayName(w).toLowerCase();
      const pth = String(w.path || "").toLowerCase();
      return disp.includes(q) || pth.includes(q);
    });
  } else {
    if (secLbl) secLbl.textContent = "Recent";
    const byKey = new Map(allWs.map((w) => [normalizePathKey(w.path), w]));
    const ordered = [];
    const seen = new Set();
    for (const rp of state.recentWorkspaces || []) {
      const k = normalizePathKey(rp);
      if (k && byKey.has(k) && !seen.has(k)) {
        seen.add(k);
        ordered.push(byKey.get(k));
      }
    }
    for (const w of allWs) {
      const k = normalizePathKey(w.path);
      if (k && !seen.has(k)) {
        seen.add(k);
        ordered.push(w);
      }
    }
    items = ordered.slice(0, 5);
  }

  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = `<div class="ws-empty-msg">No matching projects</div>`;
    return;
  }

  items.forEach((w) => {
    const active = normalizePathKey(w.path) === activeKey;
    const row = document.createElement("div");
    row.className = "wd-row";
    row.title = w.path;
    row.innerHTML = `
      <div class="wd-row-left">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2"/></svg>
        <span>${escapeHtml(projectDisplayName(w))}</span>
      </div>
      <div class="wd-row-actions">
        ${active ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-primary)" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10 -10"/></svg>` : ""}
        <button class="wd-gear-btn" type="button" title="Project Settings">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.325 4.317c.426 -1.756 2.924 -1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543 -.94 3.31 .826 2.37 2.37a1.724 1.724 0 0 0 1.065 2.572c1.756 .426 1.756 2.924 0 3.35a1.724 1.724 0 0 0 -1.066 2.573c.94 1.543 -.826 3.31 -2.37 2.37a1.724 1.724 0 0 0 -2.572 1.065c-.426 1.756 -2.924 1.756 -3.35 0a1.724 1.724 0 0 0 -2.573 -1.066c-1.543 .94 -3.31 -.826 -2.37 -2.37a1.724 1.724 0 0 0 -1.065 -2.572c-1.756 -.426 -1.756 -2.924 0 -3.35a1.724 1.724 0 0 0 1.066 -2.573c-.94 -1.543 .826 -3.31 2.37 -2.37c1 .608 2.296 .07 2.572 -1.065z"/><path d="M9 12a3 3 0 1 0 6 0a3 3 0 0 0 -6 0"/></svg>
        </button>
      </div>
    `;
    row.querySelector(".wd-gear-btn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      closeAllComposerPopovers();
      openProjectSettings(w.path);
    });
    row.addEventListener("click", async (e) => {
      e.stopPropagation();
      closeAllComposerPopovers();
      await switchWorkspacePath(w.path);
    });
    list.appendChild(row);
  });
}

async function populateBranchPopover() {
  const list = document.getElementById("branch-options-list");
  const changed = document.getElementById("branch-changed-files");
  const commitLbl = document.getElementById("branch-pop-commit");
  if (!list) return;
  const resp = await fetch("/api/git/info");
  const git = await resp.json();
  if (!git.is_repo) {
    if (commitLbl) commitLbl.textContent = "no git";
    list.innerHTML = `
      <div class="git-init-box">
        <div>No Git repository in this workspace folder.</div>
        <button id="btn-pop-git-init" class="ed-action-btn primary small" type="button">Initialize Git Repository (git init)</button>
      </div>
    `;
    if (changed) changed.innerHTML = "";
    list.querySelector("#btn-pop-git-init")?.addEventListener("click", async (e) => {
      e.stopPropagation();
      const res = await fetch("/api/git/init", { method: "POST" });
      if (res.ok) {
        await refreshBootstrap();
        await populateBranchPopover();
        toast("Initialized Git repository");
      } else {
        const er = await res.json().catch(() => ({}));
        toast(er.detail || "git init failed");
      }
    });
    return;
  }

  if (commitLbl) commitLbl.textContent = `HEAD ${git.commit || ""}`;
  list.innerHTML = "";
  (git.branches || ["main"]).forEach((br) => {
    const btn = document.createElement("button");
    btn.className = `pop-opt-row${br === git.branch ? " active" : ""}`;
    btn.innerHTML = `<span>${escapeHtml(br)}</span><span>${br === git.branch ? "active" : ""}</span>`;
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const res = await fetch("/api/git/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ branch: br }),
      });
      if (res.ok) {
        await refreshBootstrap();
        closeAllComposerPopovers();
        toast(`Switched branch to ${br}`);
      } else {
        const er = await res.json().catch(() => ({}));
        toast(er.detail || "Checkout failed");
      }
    });
    list.appendChild(btn);
  });

  const newBrForm = document.createElement("div");
  newBrForm.className = "pop-inline-form";
  newBrForm.innerHTML = `<input type="text" placeholder="New branch name..." /><button class="ed-action-btn compact" type="button">Create</button>`;
  const nbInp = newBrForm.querySelector("input");
  const nbBtn = newBrForm.querySelector("button");
  const createBranch = async (e) => {
    e?.stopPropagation();
    const bName = (nbInp?.value || "").trim();
    if (!bName) return;
    const res = await fetch("/api/git/create_branch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ branch: bName }),
    });
    if (res.ok) {
      await refreshBootstrap();
      await populateBranchPopover();
      toast(`Created branch ${bName}`);
    } else {
      const er = await res.json().catch(() => ({}));
      toast(er.detail || "Branch creation failed");
    }
  };
  nbBtn?.addEventListener("click", createBranch);
  nbInp?.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key === "Enter") createBranch(e);
  });
  nbInp?.addEventListener("click", (e) => e.stopPropagation());
  list.appendChild(newBrForm);
}

async function selectActiveModel(providerId, modelId, explicitReasoning = null) {
  state.activeProvider = providerId;
  state.activeModel = modelId;
  state.selectedProvider = providerId;
  if (explicitReasoning) state.reasoningLevel = explicitReasoning;
  state.visibleModels.add(modelKey(providerId, modelId));
  localStorage.setItem("cmdai_visible_models", JSON.stringify(Array.from(state.visibleModels)));

  const freshMeta = await ensureModelMeta(providerId, modelId);
  syncReasoningUI(freshMeta);
  updateModelLabels();
  await saveActiveModelSettings(providerId, modelId);
  toast(`Model: ${freshMeta?.name || modelId}${explicitReasoning ? ` (${explicitReasoning})` : ""}`);
}

async function persistVisibleModels() {
  const arr = Array.from(state.visibleModels);
  localStorage.setItem("cmdai_visible_models", JSON.stringify(arr));
  try {
    await fetch("/api/settings/general", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visible_models: arr }),
    });
  } catch {
    // non-fatal
  }
}

async function toggleModelVisibility(providerId, modelId, forceVisible = null) {
  const k = modelKey(providerId, modelId);
  const next = forceVisible !== null ? forceVisible : !state.visibleModels.has(k);
  if (next) state.visibleModels.add(k);
  else state.visibleModels.delete(k);
  await persistVisibleModels();
  const vc = document.getElementById("models-visible-count");
  if (vc) vc.textContent = String(state.visibleModels.size);
}

/* Antigravity-Style Model Picker Directly Above Model Button with Hover Submenu */
async function populateModelPopover() {
  const listHost = document.getElementById("pop-models-list");
  const submenu = document.getElementById("model-hover-submenu");
  const providers = getAllProviders();
  if (!listHost) return;

  if (submenu) submenu.classList.add("hidden");
  listHost.innerHTML = "";
  const activeKey = modelKey(state.activeProvider, state.activeModel);

  const allPairs = providers.flatMap((p) =>
    (p.models || [])
      .filter((m) => !m.is_placeholder)
      .map((m) => ({ provider: p, model: m, key: modelKey(p.id, m.id) }))
  );

  const candidates = allPairs.filter(({ key }) => state.visibleModels.has(key) || key === activeKey);
  if (candidates.length === 0 && state.activeModel) {
    const prov = providers.find((p) => p.id === state.activeProvider) || { id: state.activeProvider, name: state.activeProvider };
    candidates.push({ provider: prov, model: findModelMeta(state.activeProvider, state.activeModel), key: activeKey });
  }

  candidates.forEach(({ provider, model }) => {
    const isActive = provider.id === state.activeProvider && model.id === state.activeModel;
    const hasThinking = Boolean(model.thinking && Array.isArray(model.levels) && model.levels.length > 0);
    const curEff = isActive ? state.reasoningLevel : (model.default_level || "medium");

    const row = document.createElement("button");
    row.className = `model-opt-row${isActive ? " active" : ""}`;
    row.innerHTML = `
      <div class="model-opt-main">
        <span class="model-opt-title">${escapeHtml(model.name || model.id)}</span>
        ${hasThinking ? `<span class="model-opt-effort">${escapeHtml(formatCapLabel(curEff))}</span>` : ""}
      </div>
      <div class="model-opt-caps">
        ${renderCapabilityIcons(model)}
        ${isActive ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10 -10"/></svg>` : ""}
        ${hasThinking ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6l-6 6"/></svg>` : ""}
      </div>
    `;

    let hoverHideTimer = null;
    const cancelHide = () => {
      if (hoverHideTimer) {
        clearTimeout(hoverHideTimer);
        hoverHideTimer = null;
      }
    };
    if (submenu && !submenu.dataset.hoverBound) {
      submenu.dataset.hoverBound = "1";
      submenu.addEventListener("mouseenter", cancelHide);
      submenu.addEventListener("mouseleave", () => {
        hoverHideTimer = setTimeout(() => submenu.classList.add("hidden"), 110);
      });
    }

    row.addEventListener("mouseenter", () => {
      cancelHide();
      listHost.querySelectorAll(".model-opt-row").forEach((r) => r.classList.remove("hovered"));
      row.classList.add("hovered");
      if (!submenu) return;
      if (!hasThinking) {
        hoverHideTimer = setTimeout(() => submenu.classList.add("hidden"), 80);
        return;
      }
      submenu.innerHTML = "";
      model.levels.forEach((lvl) => {
        const subRow = document.createElement("button");
        const isSubAct = isActive && state.reasoningLevel === lvl;
        subRow.className = `flyout-row${isSubAct ? " active" : ""}`;
        subRow.innerHTML = `
          <span>${escapeHtml(formatCapLabel(lvl))}</span>
          ${isSubAct ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10 -10"/></svg>` : ""}
        `;
        subRow.addEventListener("click", async (e) => {
          e.stopPropagation();
          await selectActiveModel(provider.id, model.id, lvl);
          closeAllComposerPopovers();
        });
        submenu.appendChild(subRow);
      });
      const relTop = Math.max(4, row.offsetTop - listHost.scrollTop + listHost.offsetTop);
      submenu.style.top = `${relTop}px`;
      submenu.classList.remove("hidden");
      const popBox = document.getElementById("popover-model");
      if (popBox) {
        const popRect = popBox.getBoundingClientRect();
        const subH = submenu.offsetHeight || 160;
        const maxTop = Math.max(4, popBox.clientHeight - subH - 6);
        const clampedTop = Math.min(relTop, maxTop);
        const overflowBottom = popRect.top + clampedTop + subH - (window.innerHeight - 10);
        submenu.style.top = `${Math.max(-40, Math.round(clampedTop - Math.max(0, overflowBottom)))}px`;
      }
    });

    row.addEventListener("click", async (e) => {
      e.stopPropagation();
      await selectActiveModel(provider.id, model.id);
      closeAllComposerPopovers();
    });

    listHost.appendChild(row);
  });
}

function populateThinkingPopover() {
  const host = document.getElementById("pop-thinking-options");
  if (!host) return;
  const meta = findModelMeta(state.activeProvider, state.activeModel);
  const levels = meta?.levels?.length ? meta.levels : ["low", "medium", "high"];
  host.innerHTML = "";
  levels.forEach((lvl) => {
    const btn = document.createElement("button");
    const isAct = state.reasoningLevel === lvl;
    btn.className = `flyout-row${isAct ? " active" : ""}`;
    btn.innerHTML = `
      <span>${escapeHtml(formatCapLabel(lvl))}</span>
      ${isAct ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10 -10"/></svg>` : ""}
    `;
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      state.reasoningLevel = lvl;
      syncReasoningUI(meta);
      closeAllComposerPopovers();
      await saveActiveModelSettings(state.activeProvider, state.activeModel);
      toast(`Thinking: ${formatCapLabel(lvl)}`);
    });
    host.appendChild(btn);
  });
}

/* ================= FULL-STAGE MODELS & ENGINE (Dedicated Tabs: Show in Input, Engine, Providers) ================= */

function openModelsView(navTab = null) {
  closeAllComposerPopovers();
  closeSecondaryPanel();
  document.getElementById("settings-overlay")?.classList.add("hidden");
  document.getElementById("view-chat")?.classList.remove("active");
  document.getElementById("view-models")?.classList.add("active");
  document.getElementById("btn-nav-models")?.classList.add("active");
  if (navTab) state.modelsNav = navTab;
  if (!state.modalProvider) state.modalProvider = state.activeProvider || getAllProviders()[0]?.id || "openrouter";
  renderModelsView();
  mobileUI.syncNav();
}

function closeModelsView() {
  document.getElementById("view-models")?.classList.remove("active");
  document.getElementById("btn-nav-models")?.classList.remove("active");
  document.getElementById("view-chat")?.classList.add("active");
  mobileUI.syncNav();
}

function renderModelCardElement(provObj, model, onSelectRefresh) {
  const isActive = provObj.id === state.activeProvider && model.id === state.activeModel;
  const isVisible = state.visibleModels.has(modelKey(provObj.id, model.id));
  const card = document.createElement("div");
  card.className = `ag-model-card${isActive ? " active" : ""}`;

  const ctxBadge = model.context_limit > 0 ? `<span class="cap-tag">${Math.round(model.context_limit / 1024)}k</span>` : "";
  const activeBadge = isActive ? `<span class="cap-tag" style="background:var(--accent-blue);color:#fff;border-color:var(--accent-blue);">Active</span>` : "";

  card.innerHTML = `
    <button class="ag-model-select-zone" title="Activate ${escapeHtml(model.name || model.id)}">
      <div style="min-width:0;">
        <div class="model-opt-title">${escapeHtml(model.name || model.id)}</div>
        <div class="model-opt-sub">${escapeHtml(provObj.name)} · ${escapeHtml(model.id)}</div>
      </div>
      <div class="model-opt-caps">
        ${renderCapabilityIcons(model)}
        ${ctxBadge}
        ${activeBadge}
      </div>
    </button>
    ${
      model.is_placeholder
        ? ""
        : `<label class="vis-switch-wrap" title="Show in chat input quick-picker">
            <span class="vis-switch-lbl">Show in Input</span>
            <input type="checkbox" class="vis-switch" ${isVisible ? "checked" : ""} />
          </label>`
    }
  `;

  card.querySelector(".ag-model-select-zone").addEventListener("click", async () => {
    if (model.is_placeholder) return;
    await selectActiveModel(provObj.id, model.id);
    onSelectRefresh();
  });

  const sw = card.querySelector(".vis-switch");
  sw?.addEventListener("change", async (e) => {
    e.stopPropagation();
    await toggleModelVisibility(provObj.id, model.id, sw.checked);
    toast(`${model.name || model.id}: ${sw.checked ? "shown in input" : "hidden from input"}`);
  });

  return card;
}

function renderModelsView() {
  const nav = document.getElementById("models-prov-nav");
  const pq = (document.getElementById("models-prov-search")?.value || "").trim().toLowerCase();
  const providers = getAllProviders();
  if (!nav) return;

  const visCountEl = document.getElementById("models-visible-count");
  if (visCountEl) visCountEl.textContent = String(state.visibleModels.size);

  document.getElementById("btn-mnav-input")?.classList.toggle("active", state.modelsNav === "show_in_input");
  document.getElementById("btn-mnav-engine")?.classList.toggle("active", state.modelsNav === "engine");
  document.getElementById("btn-mnav-add-provider")?.classList.toggle("active", state.modelsNav === "add_provider");

  document.getElementById("mpane-show-in-input")?.classList.toggle("active", state.modelsNav === "show_in_input");
  document.getElementById("mpane-engine")?.classList.toggle("active", state.modelsNav === "engine");
  document.getElementById("mpane-voice")?.classList.toggle("active", state.modelsNav === "voice");
  document.getElementById("mpane-hf")?.classList.toggle("active", state.modelsNav === "hf");
  document.getElementById("mpane-add-provider")?.classList.toggle("active", state.modelsNav === "add_provider");
  document.getElementById("mpane-provider")?.classList.toggle("active", state.modelsNav === "provider");
  document.getElementById("btn-mnav-voice")?.classList.toggle("active", state.modelsNav === "voice");
  document.getElementById("btn-mnav-hf")?.classList.toggle("active", state.modelsNav === "hf");

  nav.innerHTML = "";
  providers
    .filter((p) => !pq || p.name.toLowerCase().includes(pq) || p.id.toLowerCase().includes(pq))
    .forEach((p) => {
      const btn = document.createElement("button");
      const isSel = state.modelsNav === "provider" && p.id === state.modalProvider;
      const isAct = p.id === state.activeProvider;
      const isReady = LOCAL_FIRST_IDS.includes(p.id) || p.has_key || (p.models || []).some((m) => !m.is_placeholder);
      btn.className = `ag-sb-item${isSel ? " active" : ""}`;
      btn.innerHTML = `
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(p.name)}</span>
        <span class="ag-prov-dot${isAct ? " active-prov" : isReady ? " ready" : ""}"></span>
      `;
      btn.addEventListener("click", async () => {
        state.modalProvider = p.id;
        state.modelsNav = "provider";
        renderModelsView();
        if (!p._remoteFetched) {
          p._remoteFetched = true;
          try {
            const resp = await fetch(`/api/providers/${encodeURIComponent(p.id)}/models`);
            if (resp.ok) {
              const data = await resp.json();
              if (Array.isArray(data.models) && data.models.length > 0) {
                p.models = data.models;
                renderModelsView();
              }
            }
          } catch {
            // non-fatal
          }
        }
      });
      nav.appendChild(btn);
    });

  if (state.modelsNav === "show_in_input") {
    const host = document.getElementById("models-show-in-input-list");
    const iq = (document.getElementById("models-input-search")?.value || "").trim().toLowerCase();
    if (host) {
      host.innerHTML = "";
      const allModels = providers.flatMap((p) =>
        (p.models || [])
          .filter((m) => !m.is_placeholder)
          .map((m) => ({ provObj: p, model: m, visible: state.visibleModels.has(modelKey(p.id, m.id)) }))
      );
      allModels.sort((a, b) => Number(b.visible) - Number(a.visible));
      const filtered = allModels.filter(
        ({ provObj, model }) =>
          !iq ||
          model.id.toLowerCase().includes(iq) ||
          model.name.toLowerCase().includes(iq) ||
          provObj.name.toLowerCase().includes(iq)
      );
      filtered.slice(0, 120).forEach(({ provObj, model }) => {
        host.appendChild(renderModelCardElement(provObj, model, renderModelsView));
      });
    }
    return;
  }

  if (state.modelsNav === "engine") {
    const loaderSel = document.getElementById("engine-loader-select");
    const portInp = document.getElementById("engine-port-input");
    const gs = state.bootstrap?.general_settings || {};
    if (loaderSel && gs.active_loader) loaderSel.value = gs.active_loader;
    if (portInp && gs.server_port) portInp.value = String(gs.server_port);

    const engList = document.getElementById("engine-local-models-list");
    if (engList) {
      engList.innerHTML = "";
      const localProvs = providers.filter((p) => LOCAL_FIRST_IDS.includes(p.id));
      localProvs.forEach((p) => {
        const models = (p.models || []).filter((m) => !m.is_placeholder);
        if (!models.length) {
          const card = document.createElement("div");
          card.className = "ag-model-card";
          card.innerHTML = `
            <div style="min-width:0;">
              <div class="model-opt-title">${escapeHtml(p.name)}</div>
              <div class="model-opt-sub">${escapeHtml(p.base_url || "Local runtime")} · no models currently running</div>
            </div>
            <span class="cap-tag">STANDBY</span>
          `;
          engList.appendChild(card);
        } else {
          models.forEach((m) => engList.appendChild(renderModelCardElement(p, m, renderModelsView)));
        }
      });
    }
    return;
  }

  if (state.modelsNav === "add_provider") {
    return;
  }

  // Provider view
  const prov = providers.find((p) => p.id === state.modalProvider) || providers[0];
  if (!prov) return;

  document.getElementById("models-pane-title").textContent = prov.name;
  document.getElementById("models-pane-sub").textContent = `Provider ID: ${prov.id} · ${(prov.models || []).length} models cataloged`;
  document.getElementById("models-provider-type-badge").textContent = String(prov.provider_type || "API").toUpperCase();
  document.getElementById("models-key-status").textContent = prov.has_key ? `Configured (${prov.masked_key})` : "Not configured (optional for local/free)";
  const keyInp = document.getElementById("models-api-key-input");
  const urlInp = document.getElementById("models-base-url-input");
  if (keyInp) keyInp.value = "";
  if (urlInp) urlInp.value = prov.base_url || "";

  const listHost = document.getElementById("models-pane-list");
  const mq = (document.getElementById("models-list-search")?.value || "").trim().toLowerCase();
  listHost.innerHTML = "";
  (prov.models || [])
    .filter((m) => !mq || m.id.toLowerCase().includes(mq) || m.name.toLowerCase().includes(mq))
    .forEach((model) => {
      listHost.appendChild(renderModelCardElement(prov, model, renderModelsView));
    });
}

/* ================= INLINE SLASH & FILE AUTOCOMPLETE ================= */

function updateAutocomplete() {
  const inp = document.getElementById("composer-input");
  const pop = document.getElementById("composer-autocomplete");
  const list = document.getElementById("autocomplete-list");
  const title = document.getElementById("autocomplete-title");
  if (!inp || !pop || !list) return;

  const val = inp.value;
  const pos = inp.selectionStart ?? val.length;
  const before = val.slice(0, pos);

  if (before.startsWith("/") && !before.includes("\n") && !before.includes(" ")) {
    state.acMode = "slash";
    state.acTokenStart = 0;
    const query = before.toLowerCase();
    state.acItems = SLASH_COMMANDS.filter((c) => c.cmd.includes(query) || c.desc.toLowerCase().includes(query.slice(1)));
    title.textContent = `Commands (${state.acItems.length})`;
  } else {
    const atMatch = before.match(/(^|\s)@([^\s]*)$/);
    if (atMatch) {
      state.acMode = "mention";
      state.acTokenStart = before.length - atMatch[2].length - 1;
      const q = atMatch[2].toLowerCase();
      state.acItems = state.filePaths
        .filter((p) => !/(?:^|\/)(?:node_modules[^/]*|\.git|\.venv|venv|__pycache__|target|dist|build)(?:\/|$)/i.test(p))
        .filter((p) => !q || p.toLowerCase().includes(q))
        .slice(0, 50)
        .map((p) => ({ cmd: p, label: p.split("/").pop(), desc: p }));
      title.textContent = "Attach Workspace File";
    } else {
      state.acMode = null;
      state.acItems = [];
    }
  }

  if (!state.acItems.length) {
    pop.classList.add("hidden");
    return;
  }

  state.acIndex = 0;
  list.innerHTML = "";
  state.acItems.forEach((it, idx) => {
    const row = document.createElement("button");
    row.className = `ac-row${idx === state.acIndex ? " selected" : ""}`;
    if (state.acMode === "mention") {
      row.innerHTML = `<span class="ac-file-left">${getFileIconHtml(it.label)}<span>${escapeHtml(it.label)}</span></span><span class="ac-desc">${escapeHtml(it.desc)}</span>`;
    } else {
      const bareName = String(it.cmd || "").replace(/^\//, "");
      row.innerHTML = `<span class="ac-cmd-left">${getSlashCommandIconHtml(it.icon)}<span>${escapeHtml(bareName)}</span></span><span class="ac-desc">${escapeHtml(it.desc)}</span>`;
    }
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      applyAutocompleteItem(it);
    });
    list.appendChild(row);
  });
  pop.classList.remove("hidden");
  list.scrollTop = 0;
}

function updateAutocompleteSelection() {
  const list = document.getElementById("autocomplete-list");
  if (!list) return;
  const rows = list.querySelectorAll(".ac-row");
  rows.forEach((row, idx) => {
    const isSel = idx === state.acIndex;
    row.classList.toggle("selected", isSel);
    if (isSel) {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  });
}

function applyAutocompleteItem(it) {
  const inp = document.getElementById("composer-input");
  const pop = document.getElementById("composer-autocomplete");
  pop?.classList.add("hidden");
  if (state.acMode === "slash") {
    inp.value = it.cmd;
    state.acMode = null;
    runSlashCommand(it.cmd);
    inp.value = "";
  } else if (state.acMode === "mention") {
    const val = inp.value;
    const pos = inp.selectionStart ?? val.length;
    const head = val.slice(0, state.acTokenStart);
    const tail = val.slice(pos);
    inp.value = (head + tail).replace(/  +/g, " ").trimStart();
    togglePinnedFile(it.cmd, true);
    state.acMode = null;
    inp.focus();
  }
  autoResizeComposer();
}

function autoResizeComposer() {
  const inp = document.getElementById("composer-input");
  if (!inp) return;
  inp.style.height = "auto";
  inp.style.height = Math.min(150, Math.max(24, inp.scrollHeight)) + "px";
  document.getElementById("composer-dock")?.classList.toggle("has-text", Boolean(inp.value.trim()));
}

async function submitAddMcpServer(nameInp, cmdInp, argsInp) {
  const name = (nameInp?.value || "").trim();
  const command = (cmdInp?.value || "").trim();
  const args = (argsInp?.value || "").trim();
  if (!name || !command) return toast("Server name and command/URL are required");
  const resp = await fetch("/api/mcp/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, command, args }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    return toast(err.detail || "Failed to add MCP server");
  }
  const data = await resp.json();
  if (state.bootstrap && Array.isArray(data.mcp_servers)) {
    state.bootstrap.mcp_servers = data.mcp_servers;
  }
  if (nameInp) nameInp.value = "";
  if (cmdInp) cmdInp.value = "";
  if (argsInp) argsInp.value = "";
  renderOrbitPanels();
  toast(`Added MCP server: ${name}`);
}

function openSubagentInspector(subagentId) {
  state.activeSubagentId = String(subagentId || "");
  const subs = state.bootstrap?.subagents || [];
  const item = subs.find((s) => String(s.id || "") === state.activeSubagentId) || subs[0];
  if (item) {
    state.activeSubagentId = String(item.id || "");
    SUBAPP_VIEW_MAP.subagent.label = `Subagent: ${item.role || item.name || "Agent"}`;
  } else {
    SUBAPP_VIEW_MAP.subagent.label = "Subagent";
  }
  openSecondaryPanel("subagent");
  renderSubagentInspector();
}

function renderSubagentInspector() {
  const subs = state.bootstrap?.subagents || [];
  const item = subs.find((s) => String(s.id || "") === String(state.activeSubagentId || "")) || subs[0];
  const titleEl = document.getElementById("subagent-pane-title");
  const statusEl = document.getElementById("subagent-pane-status");
  const elapsedEl = document.getElementById("subagent-pane-elapsed");
  const stopBtn = document.getElementById("btn-subagent-pane-stop");
  const bodyEl = document.getElementById("subagent-pane-body");
  if (!bodyEl) return;

  if (!item) {
    if (titleEl) titleEl.textContent = "Subagent";
    if (statusEl) statusEl.textContent = "idle";
    elapsedEl?.classList.add("hidden");
    stopBtn?.classList.add("hidden");
    bodyEl.innerHTML = `<div class="orbit-card" style="color:var(--text-muted);">Select a subagent from the chat or Background Tasks to inspect its tool calls and report.</div>`;
    return;
  }

  const role = String(item.role || item.name || "Subagent");
  const st = String(item.status || "running").toLowerCase();
  const isDone = st === "finished" || st === "completed";
  const isErr = st === "failed" || st === "error" || st === "cancelled";
  const stColor = isErr ? "var(--accent-red)" : (isDone ? "var(--accent-green)" : "var(--accent-blue)");
  if (titleEl) titleEl.textContent = role;
  if (statusEl) {
    statusEl.textContent = st;
    statusEl.style.color = stColor;
  }
  if (elapsedEl) {
    const secs = Number(item.elapsed || 0);
    if (secs > 0.05) {
      elapsedEl.textContent = `${secs.toFixed(1)}s`;
      elapsedEl.classList.remove("hidden");
    } else {
      elapsedEl.classList.add("hidden");
    }
  }
  if (stopBtn) {
    const canStop = st === "running" || st === "pending";
    stopBtn.classList.toggle("hidden", !canStop);
    stopBtn.onclick = async () => {
      const res = await fetch("/api/subagents/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id }),
      });
      if (res.ok) {
        const data = await res.json();
        if (state.bootstrap && Array.isArray(data.subagents)) state.bootstrap.subagents = data.subagents;
        renderOrbitPanels();
        renderSubagentInspector();
        toast("Subagent stopped");
      }
    };
  }

  const parts = [];
  if (item.goal) {
    parts.push(`
      <div class="orbit-card">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:var(--text-muted);margin-bottom:4px;">Goal</div>
        <div style="font-size:13px;color:var(--text-primary);line-height:1.5;">${escapeHtml(item.goal)}</div>
      </div>
    `);
  }

  const rawEvents = Array.isArray(item.events) ? item.events : [];
  const toolEvents = rawEvents.filter((e) => e && e.tool && e.type !== "text" && e.type !== "thinking");
  if (toolEvents.length) {
    const toolRows = toolEvents.map((te) => {
      const tName = String(te.tool || "tool");
      const tArg = String(te.arg || "");
      const tOut = String(te.output || "");
      const icoCls = te.success === false ? "cli-tool-ico error" : "cli-tool-ico";
      return `
        <details class="cli-tool-block" style="border:1px solid var(--border-hairline);border-radius:9px;background:var(--bg-card);overflow:hidden;">
          <summary class="cli-tool-head" style="padding:7px 10px;list-style:none;">
            <span class="${icoCls}">${getToolIconSvg(tName)}</span>
            <span class="cli-tool-name">${escapeHtml(formatCliToolTitle(tName))}</span>
            <span class="cli-tool-arg">${escapeHtml(tArg)}</span>
            <span class="cli-tool-chev">▸</span>
          </summary>
          <div style="border-top:1px solid var(--border-hairline);background:var(--bg-app);max-height:260px;overflow:auto;">
            <pre style="margin:0;padding:8px 10px;font-family:var(--font-mono);font-size:11.5px;white-space:pre-wrap;color:var(--text-secondary);">${escapeHtml(tOut || "(no output)")}</pre>
          </div>
        </details>
      `;
    }).join("");
    parts.push(`
      <div style="display:flex;flex-direction:column;gap:7px;">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:var(--text-muted);">Tools Executed (${toolEvents.length})</div>
        ${toolRows}
      </div>
    `);
  } else if (item.tool) {
    parts.push(`
      <div class="orbit-card" style="display:flex;align-items:center;gap:8px;">
        <span class="cli-tool-ico">${getToolIconSvg(item.tool)}</span>
        <strong>${escapeHtml(formatCliToolTitle(item.tool))}</strong>
        <span style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted);">${escapeHtml(item.arg || "")}</span>
      </div>
    `);
  }

  const reportTxt = String(item.output || item.summary || "").trim();
  if (reportTxt) {
    const renderedReport = typeof renderMarkdown === "function" ? renderMarkdown(reportTxt) : `<pre style="white-space:pre-wrap;">${escapeHtml(reportTxt)}</pre>`;
    parts.push(`
      <div class="orbit-card">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:var(--text-muted);margin-bottom:6px;">Subagent Report</div>
        <div class="assistant-md" style="font-size:13.2px;line-height:1.6;">${renderedReport}</div>
      </div>
    `);
  }

  bodyEl.innerHTML = parts.join("");
  bodyEl.querySelectorAll(".subagent-ev-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.closest(".cli-tool-block")?.classList.toggle("open");
    });
  });
}

function renderOrbitPanels() {
  const subs = state.bootstrap?.subagents || [];
  const mcps = state.bootstrap?.mcp_servers || [];
  const cps = state.bootstrap?.checkpoints || [];

  const subHtml = subs.length
    ? subs.map((s) => {
        const st = String(s.status || "running").toLowerCase();
        const canCancel = st === "running" || st === "pending";
        const toolCnt = Array.isArray(s.events) ? s.events.filter((e) => e && e.tool && e.type !== "text" && e.type !== "thinking").length : 0;
        return `<div class="orbit-card sub-orbit-open" data-sub-open="${escapeHtml(s.id || "")}" style="cursor:pointer;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <div><strong>${escapeHtml(s.name || s.role || "Subagent")}</strong> <span class="cap-tag">${escapeHtml(st)}</span>${toolCnt ? ` <span class="cap-tag">${toolCnt} tools</span>` : ""}</div>
            <div style="display:flex;align-items:center;gap:6px;">
              ${canCancel ? `<button class="ed-action-btn compact btn-sub-cancel" data-sub-id="${escapeHtml(s.id || "")}" type="button">Stop</button>` : ""}
              <span style="font-size:11.5px;color:var(--text-muted);">Inspect ↗</span>
            </div>
          </div>
          <div style="font-size:11.5px;color:var(--text-secondary);margin-top:4px;">${escapeHtml(s.summary || s.goal || "")}</div>
        </div>`;
      }).join("")
    : `<div class="orbit-card" style="color:var(--text-muted);">No active background tasks or subagents running.</div>`;

  const mcpHtml = mcps.length
    ? mcps
        .map(
          (m) => `
          <div class="cp-row">
            <div class="cp-meta">
              <div class="cp-title">${escapeHtml(m.name)} <span class="cap-tag">${escapeHtml(m.type)}</span></div>
              <div class="cp-sub">${escapeHtml(m.target)}</div>
            </div>
            <button class="ed-action-btn compact btn-mcp-del" data-mcp-del="${escapeHtml(m.name)}" type="button">Remove</button>
          </div>`
        )
        .join("")
    : `<div class="orbit-card" style="color:var(--text-muted);">No MCP servers configured in mcp_config.json</div>`;

  const cpHtml = cps.length
    ? cps.map((c) => `<div class="orbit-card"><strong>${escapeHtml(c.prompt || c.id)}</strong> <span class="cap-tag">${escapeHtml(c.timestamp)}</span></div>`).join("")
    : `<div class="orbit-card" style="color:var(--text-muted);">No workspace checkpoints saved yet</div>`;

  [["orbit-subagent-count", subs.length], ["orbit-mcp-count", mcps.length], ["orbit-cp-count", cps.length],
   ["set-orbit-sub-count", subs.length], ["set-orbit-mcp-count", mcps.length], ["set-orbit-cp-count", cps.length]]
    .forEach(([id, v]) => { const el = document.getElementById(id); if (el) el.textContent = String(v); });

  [["orbit-subagents-list", subHtml], ["set-orbit-sub-list", subHtml],
   ["orbit-mcp-list", mcpHtml], ["set-orbit-mcp-list", mcpHtml],
   ["orbit-checkpoints-list", cpHtml], ["set-orbit-cp-list", cpHtml]]
    .forEach(([id, h]) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = h;
      if (id === "orbit-subagents-list" || id === "set-orbit-sub-list") {
        el.querySelectorAll(".sub-orbit-open").forEach((cardEl) => {
          cardEl.addEventListener("click", (ev) => {
            if (ev.target.closest(".btn-sub-cancel")) return;
            const sid = cardEl.dataset.subOpen || "";
            if (sid) openSubagentInspector(sid);
          });
        });
        el.querySelectorAll(".btn-sub-cancel").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const sid = btn.dataset.subId || "";
            if (!sid) return;
            const res = await fetch("/api/subagents/cancel", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ id: sid }),
            });
            if (res.ok) {
              const data = await res.json();
              if (state.bootstrap && Array.isArray(data.subagents)) {
                state.bootstrap.subagents = data.subagents;
              }
              renderOrbitPanels();
              toast("Subagent stopped");
            }
          });
        });
      }
      if (id === "orbit-mcp-list" || id === "set-orbit-mcp-list") {
        el.querySelectorAll(".btn-mcp-del").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const targetName = btn.dataset.mcpDel || "";
            if (!targetName) return;
            const res = await fetch(`/api/mcp/remove?name=${encodeURIComponent(targetName)}`, { method: "DELETE" });
            if (res.ok) {
              const data = await res.json();
              if (state.bootstrap && Array.isArray(data.mcp_servers)) {
                state.bootstrap.mcp_servers = data.mcp_servers;
              }
              renderOrbitPanels();
              toast(`Removed MCP: ${targetName}`);
            }
          });
        });
      }
    });
}

async function openCustomizationReader(title, relPath) {
  const modal = document.getElementById("customization-reader-modal");
  const tEl = document.getElementById("reader-title");
  const pEl = document.getElementById("reader-path");
  const bEl = document.getElementById("reader-body");
  if (!modal || !bEl) return;
  if (tEl) tEl.textContent = title || relPath;
  if (pEl) pEl.textContent = relPath;
  bEl.textContent = "Loading...";
  modal.classList.remove("hidden");
  try {
    const resp = await fetch(`/api/editor/file?path=${encodeURIComponent(relPath)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    bEl.textContent = data.content || "(empty file)";
  } catch (err) {
    bEl.textContent = `Could not read ${relPath}: ${err.message}`;
  }
}

function setSegValue(inputId, val) {
  const inp = document.getElementById(inputId);
  if (inp && val !== undefined) inp.value = String(val);
  const wrap = document.querySelector(`.seg-switch[data-seg-input="${inputId}"]`);
  if (wrap) {
    wrap.querySelectorAll(".seg-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.segVal === String(val));
    });
  }
}

function applyModePermissionsToUI(modeVal) {
  const m = normalizeMode(modeVal);
  const perms = state.modePermissions?.[m] || { read: "allow", write: "ask", edit: "ask", command: "ask" };
  setSegValue("set-perm-read", perms.read || "allow");
  setSegValue("set-perm-write", perms.write || "ask");
  setSegValue("set-perm-edit", perms.edit || "ask");
  setSegValue("set-perm-command", perms.command || "ask");
}

function startScratchWithoutProject() {
  state.scratchNoProject = true;
  startNewConversation(true);
  const lbl = document.getElementById("ctx-workdir-label");
  if (lbl) lbl.textContent = "Without Project";
  document.getElementById("ctx-branch-wrap")?.classList.add("hidden");
  renderSessions();
  toast("Started conversation without project");
}

function applyGeneralSettingsToModal(gs) {
  const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = String(val); };
  const setChk = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.checked = Boolean(val); };

  setSegValue("set-agent-mode", normalizeMode(gs.mode));
  setVal("set-temperature", gs.temperature ?? 0.2);
  setVal("set-top-p", gs.top_p ?? 0.95);
  setVal("set-rep-penalty", gs.repetition_penalty ?? 1.1);
  setVal("set-subagent-model", gs.subagent_model ?? "");
  setChk("set-auto-repomap", gs.auto_repo_map !== false);
  setChk("set-browser-enabled", Boolean(gs.browser_enabled));

  setSegValue("set-perm-read", gs.perm_read || "allow");
  setSegValue("set-perm-write", gs.perm_write || "ask");
  setSegValue("set-perm-edit", gs.perm_edit || "ask");
  setSegValue("set-perm-command", gs.perm_command || "ask");
  setChk("set-auto-approve-readonly", gs.auto_approve_readonly !== false);

  setChk("set-enable-anim", gs.enable_thinking_animation !== false);
  setChk("set-hide-ctx-type", gs.hide_context_on_type !== false);
  document.body.classList.toggle("no-anim", gs.enable_thinking_animation === false);
  document.getElementById("composer-dock")?.classList.toggle("no-hide-ctx", gs.hide_context_on_type === false);

  setVal("set-editor-fontsize", gs.font_size ?? 13);
  setVal("set-editor-tabsize", gs.tab_size ?? 4);
  setChk("set-format-onsave", gs.format_on_save !== false);
  setVal("set-terminal-shell", gs.shell || "powershell.exe");

  editor.applyPreferences({ fontSize: gs.font_size || 13, tabSize: gs.tab_size || 4 });
  if (gs.shell) editor.setShellLabel(gs.shell);
}

function bindEvents() {
  document.querySelectorAll(".seg-switch .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const wrap = btn.closest(".seg-switch");
      const targetId = wrap?.dataset.segInput;
      if (!targetId) return;
      const val = btn.dataset.segVal;
      setSegValue(targetId, val);
      if (targetId === "set-agent-mode") {
        applyModePermissionsToUI(val);
      } else if (["set-perm-read", "set-perm-write", "set-perm-edit", "set-perm-command"].includes(targetId)) {
        const activeMode = normalizeMode(document.getElementById("set-agent-mode")?.value || state.mode);
        const field = targetId.replace("set-perm-", "");
        if (!state.modePermissions[activeMode]) {
          state.modePermissions[activeMode] = { read: "allow", write: "ask", edit: "ask", command: "ask" };
        }
        state.modePermissions[activeMode][field] = val;
        localStorage.setItem("cmdai_mode_permissions", JSON.stringify(state.modePermissions));
      }
    });
  });

  document.getElementById("btn-close-reader")?.addEventListener("click", () => {
    document.getElementById("customization-reader-modal")?.classList.add("hidden");
  });
  document.getElementById("customization-reader-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "customization-reader-modal") {
      e.target.classList.add("hidden");
    }
  });

  document.getElementById("hero-banner-host")?.addEventListener("click", () => {
    applyBrandState(state.brandCycleIdx + 1);
  });

  ["popover-model", "popover-thinking", "popover-permissions", "popover-workdir", "popover-branch", "popover-tasks", "composer-autocomplete"].forEach((id) => {
    document.getElementById(id)?.addEventListener("click", (e) => e.stopPropagation());
  });

  document.getElementById("btn-toggle-sidebar")?.addEventListener("click", () => {
    document.getElementById("left-sidebar")?.classList.add("collapsed");
    document.getElementById("btn-expand-sidebar")?.classList.remove("hidden");
  });
  document.getElementById("btn-expand-sidebar")?.addEventListener("click", () => {
    document.getElementById("left-sidebar")?.classList.remove("collapsed");
    document.getElementById("btn-expand-sidebar")?.classList.add("hidden");
  });

  document.getElementById("btn-new-thread")?.addEventListener("click", () => startNewConversation(true));
  document.getElementById("btn-topbar-new-tab")?.addEventListener("click", () => startNewConversation(true));
  document.getElementById("btn-nav-models")?.addEventListener("click", () => openModelsView("show_in_input"));
  document.getElementById("btn-add-workspace")?.addEventListener("click", (e) => {
    e.stopPropagation();
    document.getElementById("sb-plus-menu")?.classList.toggle("hidden");
  });
  document.getElementById("btn-plus-with-project")?.addEventListener("click", () => {
    document.getElementById("sb-plus-menu")?.classList.add("hidden");
    openNewProjectPane();
  });
  document.getElementById("btn-plus-without-project")?.addEventListener("click", () => {
    document.getElementById("sb-plus-menu")?.classList.add("hidden");
    startScratchWithoutProject();
  });
  document.getElementById("btn-pop-without-project")?.addEventListener("click", () => {
    closeAllComposerPopovers();
    startScratchWithoutProject();
  });
  document.addEventListener("click", () => {
    document.getElementById("sb-plus-menu")?.classList.add("hidden");
  });
  document.getElementById("btn-settings-add-project")?.addEventListener("click", openNewProjectPane);

  // Add New Project Pane handlers
  document.getElementById("btn-create-new-proj")?.addEventListener("click", async () => {
    const pathInp = document.getElementById("new-proj-path-input");
    const nameInp = document.getElementById("new-proj-name-input");
    const targetPath = pathInp?.value.trim();
    const customLabel = nameInp?.value.trim();
    if (!targetPath) {
      toast("Enter a local folder path for the new project.");
      pathInp?.focus();
      return;
    }
    if (await switchWorkspacePath(targetPath, true)) {
      if (customLabel) {
        state.projectLabels[normalizePathKey(targetPath)] = customLabel;
        localStorage.setItem("cmdai_project_labels", JSON.stringify(state.projectLabels));
        renderWorkspacesSidebar();
      }
      await openProjectSettings(targetPath);
    }
  });
  document.getElementById("new-proj-path-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("btn-create-new-proj")?.click();
  });

  // Project Details inline folder & rename interactions
  document.getElementById("btn-proj-add-folder")?.addEventListener("click", () => {
    const form = document.getElementById("proj-add-folder-form");
    form?.classList.toggle("hidden");
    if (!form?.classList.contains("hidden")) {
      document.getElementById("proj-folder-path-input")?.focus();
    }
  });
  document.getElementById("btn-proj-folder-add-go")?.addEventListener("click", async () => {
    const inp = document.getElementById("proj-folder-path-input");
    const val = inp?.value.trim();
    if (!val) return;
    if (await switchWorkspacePath(val, true)) {
      inp.value = "";
      await openProjectSettings(val);
    }
  });
  document.getElementById("proj-folder-path-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("btn-proj-folder-add-go")?.click();
  });
  document.getElementById("btn-toggle-proj-skills")?.addEventListener("click", () => {
    state.skillsCollapsed = !state.skillsCollapsed;
    document.getElementById("proj-skills-list")?.classList.toggle("hidden", state.skillsCollapsed);
  });
  document.getElementById("btn-proj-rename")?.addEventListener("click", () => {
    const titleEl = document.getElementById("proj-settings-title");
    if (!titleEl) return;
    const key = normalizePathKey(state.selectedProjectSettingsPath || state.workdir);
    const parent = titleEl.parentElement;
    if (parent.querySelector(".proj-inline-rename")) return;
    const inp = document.createElement("input");
    inp.className = "glass-input proj-inline-rename";
    inp.value = titleEl.textContent;
    titleEl.classList.add("hidden");
    parent.insertBefore(inp, titleEl);
    inp.focus();
    const commit = () => {
      const nv = inp.value.trim();
      if (nv && key) {
        state.projectLabels[key] = nv;
        localStorage.setItem("cmdai_project_labels", JSON.stringify(state.projectLabels));
        titleEl.textContent = nv;
        renderWorkspacesSidebar();
        renderSettingsProjectsNav();
      }
      inp.remove();
      titleEl.classList.remove("hidden");
    };
    inp.addEventListener("blur", commit);
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") commit();
      if (e.key === "Escape") { inp.remove(); titleEl.classList.remove("hidden"); }
    });
  });

  // Top-right Overview dropdown
  const ovBtn = document.getElementById("btn-overview-menu");
  const ovPop = document.getElementById("overview-popover");
  ovBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    const isHidden = ovPop.classList.contains("hidden");
    ovPop.classList.toggle("hidden", !isHidden);
    ovBtn.classList.toggle("open", isHidden);
  });
  document.querySelectorAll(".ov-item").forEach((b) => {
    b.addEventListener("click", () => openSecondaryPanel(b.dataset.ovAction));
  });
  document.getElementById("btn-close-secondary")?.addEventListener("click", closeSecondaryPanel);

  // Composer strip & footer popovers anchored directly above each button
  document.getElementById("btn-ctx-workdir")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const searchInp = document.getElementById("workdir-search-input");
    if (searchInp) searchInp.value = "";
    populateWorkdirPopover();
    toggleComposerPopover("popover-workdir", true);
    if (!mobileUI.isMobile) setTimeout(() => searchInp?.focus(), 20);
  });
  document.getElementById("workdir-search-input")?.addEventListener("input", () => populateWorkdirPopover());
  document.getElementById("workdir-search-input")?.addEventListener("click", (e) => e.stopPropagation());
  document.getElementById("btn-pop-new-project")?.addEventListener("click", (e) => {
    e.stopPropagation();
    closeAllComposerPopovers();
    openNewProjectPane();
  });
  document.getElementById("btn-ctx-branch")?.addEventListener("click", async (e) => {
    e.stopPropagation();
    await populateBranchPopover();
    toggleComposerPopover("popover-branch", true);
  });

  document.getElementById("btn-composer-model")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const wasHidden = document.getElementById("popover-model")?.classList.contains("hidden");
    toggleComposerPopover("popover-model", false, wasHidden);
    if (wasHidden) populateModelPopover();
  });
  document.getElementById("btn-open-models-window")?.addEventListener("click", () => {
    closeAllComposerPopovers();
    openModelsView("show_in_input");
  });

  document.getElementById("btn-composer-thinking")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const wasHidden = document.getElementById("popover-thinking")?.classList.contains("hidden");
    toggleComposerPopover("popover-thinking", false, wasHidden);
    if (wasHidden) populateThinkingPopover();
  });

  document.getElementById("btn-cycle-mode")?.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleComposerPopover("popover-permissions");
  });
  document.querySelectorAll(".perm-option").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      state.mode = normalizeMode(btn.dataset.permMode);
      updateModeUI();
      closeAllComposerPopovers();
      await saveActiveModelSettings(state.activeProvider, state.activeModel);
      toast(`Mode: ${state.mode}`);
    });
  });

  document.getElementById("btn-pin-file")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const inp = document.getElementById("composer-input");
    if (!inp) return;
    inp.value = inp.value ? `${inp.value.trimEnd()} @` : "@";
    inp.focus();
    updateAutocomplete();
  });

  document.getElementById("btn-send-prompt")?.addEventListener("click", () => {
    if (state.isGenerating) stopActiveGeneration();
    else sendPrompt();
  });

  const compInp = document.getElementById("composer-input");
  compInp?.addEventListener("input", () => {
    autoResizeComposer();
    updateAutocomplete();
  });
  compInp?.addEventListener("keydown", (e) => {
    const acOpen = state.acItems.length > 0 && !document.getElementById("composer-autocomplete")?.classList.contains("hidden");
    if (acOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        state.acIndex = (state.acIndex + 1) % state.acItems.length;
        updateAutocompleteSelection();
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        state.acIndex = (state.acIndex - 1 + state.acItems.length) % state.acItems.length;
        updateAutocompleteSelection();
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
        e.preventDefault();
        applyAutocompleteItem(state.acItems[state.acIndex]);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        document.getElementById("composer-autocomplete")?.classList.add("hidden");
        return;
      }
    }
    if (e.key === "Tab" && e.shiftKey) {
      e.preventDefault();
      cycleAgentMode();
      return;
    }
    if (e.key === "t" && e.ctrlKey) {
      e.preventDefault();
      cycleThinkingLevel();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  });

  // Full-Stage Models & Engine Navigation Tabs
  document.getElementById("btn-mnav-input")?.addEventListener("click", () => {
    state.modelsNav = "show_in_input";
    renderModelsView();
  });
  document.getElementById("btn-mnav-engine")?.addEventListener("click", () => {
    state.modelsNav = "engine";
    renderModelsView();
  });
  document.getElementById("btn-mnav-add-provider")?.addEventListener("click", () => {
    state.modelsNav = "add_provider";
    renderModelsView();
  });

  document.getElementById("tl-arrow-up")?.addEventListener("click", () => jumpTimelineStep(-1));
  document.getElementById("tl-arrow-down")?.addEventListener("click", () => jumpTimelineStep(1));

  document.getElementById("btn-ctx-quick-files")?.addEventListener("click", () => openSecondaryPanel("files"));
  document.getElementById("btn-ctx-quick-cp")?.addEventListener("click", () => openSecondaryPanel("checkpoints"));
  document.getElementById("btn-ctx-tasks")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const drawer = document.getElementById("composer-tasks-drawer");
    const pill = document.getElementById("btn-ctx-tasks");
    if (!drawer) return;
    const isHidden = drawer.classList.toggle("hidden");
    pill?.classList.toggle("open", !isHidden);
    syncChatBottomPadding();
  });

  document.querySelectorAll(".btn-subapp-maximize").forEach((btn) => {
    btn.addEventListener("click", () => {
      const stage = document.getElementById("main-stage");
      if (!stage) return;
      const isMax = !stage.classList.contains("subapp-maximized");
      stage.classList.toggle("subapp-maximized", isMax);
      stage.classList.toggle("editor-maximized", isMax);
      document.querySelectorAll(".btn-subapp-maximize span").forEach((sp) => {
        sp.textContent = isMax ? "Split View" : "Full Window";
      });
      if (state.secondaryView === "map") mindMap.resizeCanvas();
      else editor.updateStatusBar();
    });
  });

  document.querySelectorAll(".btn-subapp-close").forEach((btn) => {
    btn.addEventListener("click", () => closeSecondaryPanel());
  });

  // Dedicated Sub-App Actions: Review, Terminal, Checkpoints, Tasks, MCP, CLI Sync, Add Provider
  document.getElementById("btn-review-refresh")?.addEventListener("click", () => {
    loadReviewSubApp(state.reviewSelectedPath || "");
  });
  document.getElementById("btn-review-stage")?.addEventListener("click", async () => {
    const fp = state.reviewSelectedPath || "";
    try {
      const resp = await fetch("/api/git/stage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: fp }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) return toast(data.detail || "Stage failed");
      toast(fp ? `Staged ${fp}` : "Staged all changes");
      await loadReviewSubApp(fp);
    } catch (err) {
      toast(`Stage failed: ${err.message}`);
    }
  });
  document.getElementById("btn-review-discard")?.addEventListener("click", async () => {
    const fp = state.reviewSelectedPath || "";
    if (!fp) return toast("Select a modified file to discard first");
    if (!window.confirm(`Discard all uncommitted changes in "${fp}"?`)) return;
    try {
      const resp = await fetch("/api/git/discard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: fp }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) return toast(data.detail || "Discard failed");
      toast(`Reverted ${fp}`);
      state.reviewSelectedPath = "";
      await loadReviewSubApp("");
      await refreshTree();
    } catch (err) {
      toast(`Discard failed: ${err.message}`);
    }
  });
  const doReviewCommit = async () => {
    const inp = document.getElementById("review-commit-msg");
    const msg = (inp?.value || "").trim();
    if (!msg) return toast("Enter a commit message first");
    try {
      const resp = await fetch("/api/git/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, stage_all: true }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) return toast(data.detail || "Commit failed");
      if (inp) inp.value = "";
      toast(`Committed: ${msg.slice(0, 48)}`);
      state.reviewSelectedPath = "";
      await loadReviewSubApp("");
      await refreshBootstrap();
    } catch (err) {
      toast(`Commit failed: ${err.message}`);
    }
  };
  document.getElementById("btn-review-commit")?.addEventListener("click", doReviewCommit);
  document.getElementById("review-commit-msg")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      doReviewCommit();
    }
  });
  document.getElementById("btn-review-open-editor")?.addEventListener("click", async () => {
    const p = state.reviewSelectedPath || state.filePaths[0];
    await openSecondaryPanel("files");
    if (p) await editor.openFile(p, 1).catch(() => {});
  });

  document.querySelectorAll(".term-quick-cmd").forEach((btn) => {
    btn.addEventListener("click", () => runSubappTerminalCommand(btn.dataset.cmd || ""));
  });
  document.getElementById("btn-subapp-terminal-run")?.addEventListener("click", async () => {
    const inp = document.getElementById("subapp-terminal-input");
    const cmd = inp?.value.trim();
    if (!cmd) return;
    inp.value = "";
    await runSubappTerminalCommand(cmd);
  });
  document.getElementById("subapp-terminal-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      document.getElementById("btn-subapp-terminal-run")?.click();
    }
  });
  document.getElementById("btn-subapp-terminal-clear")?.addEventListener("click", () => {
    ptyTerm.clear();
  });
  document.getElementById("btn-pty-ctrlc")?.addEventListener("click", () => {
    ptyTerm.ctrlC();
  });
  document.getElementById("btn-pty-restart")?.addEventListener("click", () => {
    ptyTerm.restart();
  });

  // Draggable split divider between Chat and active Sub-App (Terminal / Files / Browser / Review / Mind Map)
  (() => {
    const resizer = document.getElementById("split-resizer");
    const stage = document.getElementById("main-stage");
    if (!resizer || !stage) return;

    const applyPct = (pct, persist = false) => {
      const clamped = Math.max(22, Math.min(76, pct));
      stage.style.setProperty("--split-chat-pct", `${clamped.toFixed(2)}%`);
      if (persist) {
        try { localStorage.setItem("cmdai_split_chat_pct", clamped.toFixed(2)); } catch (_) {}
      }
      if (state.secondaryView === "terminal") ptyTerm.fitAndResize();
      else if (state.secondaryView === "map") mindMap?.resizeCanvas?.();
    };

    try {
      const saved = parseFloat(localStorage.getItem("cmdai_split_chat_pct") || "");
      if (Number.isFinite(saved) && saved >= 22 && saved <= 76) {
        stage.style.setProperty("--split-chat-pct", `${saved.toFixed(2)}%`);
      }
    } catch (_) {}

    let dragging = false;
    let lastPct = 42;

    resizer.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 && e.pointerType === "mouse") return;
      e.preventDefault();
      dragging = true;
      resizer.classList.add("dragging");
      document.body.classList.add("is-resizing-split");
      try { resizer.setPointerCapture(e.pointerId); } catch (_) {}
    });

    resizer.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const rect = stage.getBoundingClientRect();
      if (rect.width <= 0) return;
      lastPct = ((e.clientX - rect.left) / rect.width) * 100;
      applyPct(lastPct, false);
    });

    const endDrag = (e) => {
      if (!dragging) return;
      dragging = false;
      resizer.classList.remove("dragging");
      document.body.classList.remove("is-resizing-split");
      try { resizer.releasePointerCapture(e.pointerId); } catch (_) {}
      applyPct(lastPct, true);
    };

    resizer.addEventListener("pointerup", endDrag);
    resizer.addEventListener("pointercancel", endDrag);
    resizer.addEventListener("dblclick", () => applyPct(42, true));
  })();

  document.getElementById("btn-cp-create")?.addEventListener("click", async () => {
    const inp = document.getElementById("cp-prompt-input");
    const promptVal = (inp?.value || "").trim() || "Manual Desktop Snapshot";
    const resp = await fetch("/api/checkpoints/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptVal }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      return toast(err.detail || "Failed to create checkpoint");
    }
    if (inp) inp.value = "";
    await loadCheckpointsOverlay();
    await refreshBootstrap();
    toast("Checkpoint created");
  });

  document.getElementById("btn-task-run")?.addEventListener("click", async () => {
    const inp = document.getElementById("task-cmd-input");
    const cmd = (inp?.value || "").trim();
    if (!cmd) return toast("Enter a command to run as a workspace task");
    inp.value = "";
    const resp = await fetch("/api/terminal/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: cmd }),
    });
    const data = await resp.json().catch(() => ({}));
    if (state.bootstrap) {
      state.bootstrap.subagents = [
        {
          id: `task_${Date.now()}`,
          name: cmd,
          status: data.returncode === 0 ? "done" : `exit ${data.returncode ?? 1}`,
          summary: String(data.output || data.stdout || data.stderr || "Completed").slice(0, 260),
        },
        ...(state.bootstrap.subagents || []),
      ];
    }
    renderOrbitPanels();
    toast(`Task finished (exit ${data.returncode ?? 0})`);
  });

  document.getElementById("btn-mcp-add")?.addEventListener("click", () =>
    submitAddMcpServer(
      document.getElementById("mcp-name-input"),
      document.getElementById("mcp-cmd-input"),
      document.getElementById("mcp-args-input")
    )
  );
  document.getElementById("btn-set-mcp-add")?.addEventListener("click", () =>
    submitAddMcpServer(
      document.getElementById("set-mcp-name"),
      document.getElementById("set-mcp-cmd"),
      document.getElementById("set-mcp-args")
    )
  );

  document.getElementById("btn-sync-scan")?.addEventListener("click", () => loadCliSyncOverlay());
  document.getElementById("btn-sync-transfer-all")?.addEventListener("click", async () => {
    const cliRoot = (document.getElementById("sync-cli-path-input")?.value || "").trim();
    const resp = await fetch("/api/sync/cli_transfer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cli_root: cliRoot }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      return toast(err.detail || "CLI transfer failed");
    }
    const data = await resp.json();
    await loadCliSyncOverlay();
    await refreshBootstrap();
    toast(`Transferred ${(data.copied || []).length} file(s) from CLI`);
  });

  document.getElementById("btn-save-custom-provider")?.addEventListener("click", async () => {
    const nameEl = document.getElementById("custom-prov-name");
    const idEl = document.getElementById("custom-prov-id");
    const urlEl = document.getElementById("custom-prov-url");
    const keyEl = document.getElementById("custom-prov-key");
    const modelsEl = document.getElementById("custom-prov-models");
    const name = (nameEl?.value || "").trim();
    const base_url = (urlEl?.value || "").trim();
    if (!name || !base_url) return toast("Provider name and Base URL are required");
    const resp = await fetch("/api/providers/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        provider_id: (idEl?.value || "").trim(),
        base_url,
        api_key: (keyEl?.value || "").trim(),
        models: (modelsEl?.value || "").trim(),
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      return toast(err.detail || "Failed to add custom provider");
    }
    const data = await resp.json();
    if (nameEl) nameEl.value = "";
    if (idEl) idEl.value = "";
    if (urlEl) urlEl.value = "";
    if (keyEl) keyEl.value = "";
    if (modelsEl) modelsEl.value = "";
    await refreshBootstrap();
    if (data.provider_id) {
      state.modalProvider = data.provider_id;
      state.modelsNav = "provider";
    }
    renderModelsView();
    toast(`Added provider: ${name}`);
  });
  document.getElementById("models-prov-search")?.addEventListener("input", renderModelsView);
  document.getElementById("models-input-search")?.addEventListener("input", renderModelsView);
  document.getElementById("models-list-search")?.addEventListener("input", renderModelsView);

  document.getElementById("btn-engine-save")?.addEventListener("click", async () => {
    const loader = document.getElementById("engine-loader-select")?.value || "vulkan";
    const port = Number(document.getElementById("engine-port-input")?.value || 8080);
    const resp = await fetch("/api/settings/general", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_loader: loader, server_port: port }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (state.bootstrap) state.bootstrap.general_settings = data.general_settings;
      applyGeneralSettingsToModal(data.general_settings || {});
      toast(`Engine saved (${loader.toUpperCase()}, port ${port})`);
    }
  });

  document.getElementById("btn-models-save-provider")?.addEventListener("click", async () => {
    const resp = await fetch("/api/settings/general", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: state.modalProvider,
        api_key: document.getElementById("models-api-key-input")?.value || "",
        base_url: document.getElementById("models-base-url-input")?.value || "",
      }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (state.bootstrap && data.models_state) state.bootstrap.models_state = data.models_state;
      renderModelsView();
      toast(`Saved credentials for ${state.modalProvider}`);
    }
  });

  // Settings Split Modal Events
  document.getElementById("btn-sidebar-settings")?.addEventListener("click", () => openSettingsAtTab("agent"));
  ["btn-close-settings", "btn-settings-cancel"].forEach((id) => {
    document.getElementById(id)?.addEventListener("click", () => {
      document.getElementById("settings-overlay")?.classList.add("hidden");
    });
  });
  document.querySelectorAll(".settings-tab").forEach((tab) => {
    tab.addEventListener("click", () => openSettingsAtTab(tab.dataset.stab));
  });
  document.querySelectorAll("#rules-snippets-bar .rules-chip").forEach((chip) => {
    chip.addEventListener("click", () => insertRulesSnippet(chip.dataset.snippet));
  });
  document.getElementById("btn-rules-save")?.addEventListener("click", saveRulesStudio);
  document.getElementById("rules-editor-textarea")?.addEventListener("input", () => {
    rulesStudioState.dirty = true;
    updateRulesTokenBadge();
  });
  document.getElementById("rules-editor-textarea")?.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      e.stopPropagation();
      saveRulesStudio();
    }
  });
  document.querySelectorAll(".ag-theme-card").forEach((card) => {
    card.addEventListener("click", async () => {
      const choice = card.dataset.themeChoice || "light";
      applyTheme(choice);
      await fetch("/api/settings/general", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme: choice }),
      }).catch(() => {});
      toast(`Theme: ${choice === "dark" ? "Matte Dark Slate" : "Clear Light"}`);
    });
  });

  document.getElementById("btn-settings-save")?.addEventListener("click", async () => {
    const payload = {
      mode: document.getElementById("set-agent-mode")?.value,
      temperature: Number(document.getElementById("set-temperature")?.value || 0.2),
      top_p: Number(document.getElementById("set-top-p")?.value || 0.95),
      repetition_penalty: Number(document.getElementById("set-rep-penalty")?.value || 1.1),
      subagent_model: document.getElementById("set-subagent-model")?.value || "",
      auto_repo_map: Boolean(document.getElementById("set-auto-repomap")?.checked),
      browser_enabled: Boolean(document.getElementById("set-browser-enabled")?.checked),
      perm_read: document.getElementById("set-perm-read")?.value || "allow",
      perm_write: document.getElementById("set-perm-write")?.value || "ask",
      perm_edit: document.getElementById("set-perm-edit")?.value || "ask",
      perm_command: document.getElementById("set-perm-command")?.value || "ask",
      auto_approve_readonly: Boolean(document.getElementById("set-auto-approve-readonly")?.checked),
      enable_thinking_animation: Boolean(document.getElementById("set-enable-anim")?.checked),
      hide_context_on_type: Boolean(document.getElementById("set-hide-ctx-type")?.checked),
      theme: state.theme,
      font_size: Number(document.getElementById("set-editor-fontsize")?.value || 13),
      tab_size: Number(document.getElementById("set-editor-tabsize")?.value || 4),
      format_on_save: Boolean(document.getElementById("set-format-onsave")?.checked),
      shell: document.getElementById("set-terminal-shell")?.value || "powershell.exe",
    };
    const resp = await fetch("/api/settings/general", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (state.bootstrap) state.bootstrap.general_settings = data.general_settings;
      state.mode = normalizeMode(data.general_settings?.mode);
      state.reasoningLevel = data.general_settings?.reasoning_level || state.reasoningLevel;
      if (state.bootstrap && data.models_state) state.bootstrap.models_state = data.models_state;
      updateModeUI();
      syncReasoningUI(findModelMeta(state.activeProvider, state.activeModel));
      applyGeneralSettingsToModal(data.general_settings || {});
      document.getElementById("settings-save-status").textContent = "Saved to config.json";
      toast("Settings saved");
    }
  });

  document.getElementById("btn-editor-quick-open")?.addEventListener("click", () => {
    renderQuickOpen("");
    document.getElementById("quick-open-overlay")?.classList.remove("hidden");
    if (!mobileUI.isMobile) document.getElementById("qo-search-input")?.focus();
  });
  document.getElementById("qo-search-input")?.addEventListener("input", (e) => renderQuickOpen(e.target.value));
  document.getElementById("qo-search-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.getElementById("quick-open-overlay")?.classList.add("hidden");
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".overview-anchor")) {
      ovPop?.classList.add("hidden");
      ovBtn?.classList.remove("open");
    }
    if (!e.target.closest("#composer-dock")) {
      closeAllComposerPopovers();
      document.getElementById("composer-autocomplete")?.classList.add("hidden");
    }
  });

  document.getElementById("btn-close-rules")?.addEventListener("click", closeRulesModal);
  ["settings-overlay", "quick-open-overlay", "rules-overlay"].forEach((id) => {
    document.getElementById(id)?.addEventListener("click", (e) => {
      if (e.target.id === id) e.target.classList.add("hidden");
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const rulesOv = document.getElementById("rules-overlay");
    if (rulesOv && !rulesOv.classList.contains("hidden")) {
      closeRulesModal();
      return;
    }
    const settingsOv = document.getElementById("settings-overlay");
    if (settingsOv && !settingsOv.classList.contains("hidden")) {
      settingsOv.classList.add("hidden");
      return;
    }
    const qoOv = document.getElementById("quick-open-overlay");
    if (qoOv && !qoOv.classList.contains("hidden")) {
      qoOv.classList.add("hidden");
      return;
    }
    if (!document.getElementById("overview-popover")?.classList.contains("hidden")) {
      ovPop?.classList.add("hidden");
      ovBtn?.classList.remove("open");
      return;
    }
    closeAllComposerPopovers();
    document.getElementById("composer-autocomplete")?.classList.add("hidden");
  });
}

function renderQuickOpen(query) {
  const list = document.getElementById("qo-results-list");
  if (!list) return;
  const q = (query || "").trim().toLowerCase();
  list.innerHTML = "";
  state.filePaths
    .filter((p) => !q || p.toLowerCase().includes(q))
    .slice(0, 24)
    .forEach((p) => {
      const btn = document.createElement("button");
      const base = p.split("/").pop();
      btn.className = "ac-row";
      btn.innerHTML = `<span class="ac-file-left">${getFileIconHtml(base)}<span>${escapeHtml(p)}</span></span><span class="ac-desc">Open</span>`;
      btn.addEventListener("click", async () => {
        document.getElementById("quick-open-overlay")?.classList.add("hidden");
        await openSecondaryPanel("files");
        await editor.openFile(p, 1);
      });
      list.appendChild(btn);
    });
}

let _spectateLastSig = "";
let _spectateEventSource = null;
let _spectatePollTimer = null;
let _spectateInFlight = false;

function _markSpectateEnded() {
  const bar = document.getElementById("spectate-composer-bar");
  const txt = document.getElementById("spectate-composer-text");
  const frame = document.querySelector(".composer-shell-frame");
  bar?.classList.remove("is-active");
  frame?.classList.remove("spectate-active");
  if (txt) txt.textContent = "Live stream ended";
  if (_spectateEventSource) {
    try { _spectateEventSource.close(); } catch {}
    _spectateEventSource = null;
  }
  if (_spectatePollTimer) {
    clearInterval(_spectatePollTimer);
    _spectatePollTimer = null;
  }
}

function _formatSpectateStatus(isGen, phase, detail) {
  if (!isGen) return "Live Spectate · Read-Only — waiting for next prompt";
  if (phase === "thinking") return "Agent is thinking...";
  if (phase === "tool") return detail ? `Running ${detail}...` : "Agent is running a tool...";
  if (phase === "writing") return "Agent is writing live...";
  return "Agent is preparing response...";
}

function renderSpectatePayload(data) {
  if (!data || typeof data !== "object") return;
  const isGen = Boolean(data.is_generating);
  const livePhase = String(data.live_phase || (isGen ? "loading" : "idle"));
  const liveDetail = String(data.live_detail || "");
  const modelId = String(data.model_id || state.activeModel || "cmdai-code");
  const mode = String(data.mode || state.mode || "auto");

  const wdEl = document.getElementById("ctx-workdir-label");
  if (wdEl && data.workdir) {
    const shortWd = String(data.workdir).split(/[\\/]/).filter(Boolean).pop() || String(data.workdir);
    wdEl.textContent = shortWd;
  }

  const compBar = document.getElementById("spectate-composer-bar");
  const compTxt = document.getElementById("spectate-composer-text");
  const compModel = document.getElementById("spectate-composer-model");
  const compMode = document.getElementById("spectate-composer-mode");
  const shellFrame = document.querySelector(".composer-shell-frame");
  compBar?.classList.toggle("is-active", isGen);
  shellFrame?.classList.toggle("spectate-active", isGen);
  if (compTxt) compTxt.textContent = _formatSpectateStatus(isGen, livePhase, liveDetail);
  if (compModel) {
    compModel.textContent = modelId;
    compModel.classList.toggle("hidden", !String(data.model_id || "").trim());
  }
  if (compMode) compMode.textContent = mode;

  const sig = JSON.stringify({
    t: data.transcript || [],
    m: data.messages || [],
    s: data.streaming_text || "",
    g: isGen,
    p: livePhase,
    d: liveDetail,
  });
  if (sig === _spectateLastSig) return;
  _spectateLastSig = sig;

  const sc = document.getElementById("chat-scroll");
  const nearBottom = !sc || (sc.scrollHeight - sc.scrollTop - sc.clientHeight < 240) || sc.scrollTop === 0;

  const msgsHost = document.getElementById("chat-messages");
  if (!msgsHost) return;
  msgsHost.innerHTML = "";
  const tlDots = document.getElementById("timeline-dots");
  if (tlDots) tlDots.innerHTML = "";
  document.getElementById("timeline-rail")?.classList.remove("has-items");
  hideTimelineTooltip();

  const transcript = Array.isArray(data.transcript) ? data.transcript : [];
  const messages = Array.isArray(data.messages) ? data.messages : [];
  const streamingText = String(data.streaming_text || "");

  let curCard = null;
  let lastAssistantRendered = "";
  let lastAssistantStreaming = false;
  const ensureCard = () => {
    if (!curCard) {
      curCard = createAssistantTurnCard(modelId, mode, false);
    }
    return curCard;
  };

  if (transcript.length > 0) {
    for (const ev of transcript) {
      if (!ev || typeof ev !== "object") continue;
      if (ev.kind === "user") {
        curCard = null;
        lastAssistantRendered = "";
        lastAssistantStreaming = false;
        const txt = cleanMessageContent(String(ev.prompt || ev.content || ev.text || ""));
        const tStr = formatShortTimestamp(ev.time || ev.timestamp || "");
        if (txt) appendUserBubble(txt, tStr);
      } else if (ev.kind === "loading") {
        const c = ensureCard();
        const lt = c.el?.querySelector(".cli-loading-text");
        if (lt) lt.textContent = String(ev.text || "Thinking...");
      } else if (ev.kind === "thinking") {
        const th = String(ev.text || ev.content || "");
        if (th.trim()) ensureCard().appendThinking(th);
      } else if (ev.kind === "tool" || ev.kind === "tool_result") {
        const c = ensureCard();
        const tId = `spec_${Math.random().toString(36).slice(2, 7)}`;
        const tName = ev.tool || ev.name || "tool";
        const tArgs = ev.target || ev.args || "";
        const isRunning = Boolean(ev.running);
        c.startTool({ id: tId, name: tName, args: tArgs, historical: !isRunning });
        if (!isRunning) {
          const resObj = ev.result || {};
          const ok = ev.ok !== false && ev.success !== false && resObj.success !== false;
          const rawOut = String(resObj.content || resObj.output || resObj.error || ev.preview || ev.content || "").trim();
          const firstLine = rawOut ? rawOut.split("\n")[0].slice(0, 140) : "";
          c.finishTool({
            id: tId,
            name: tName,
            args: tArgs,
            historical: true,
            ok,
            summary: ev.summary || firstLine || (ok ? "Completed" : "Failed"),
            preview: rawOut,
          });
        }
      } else if (ev.kind === "assistant") {
        const txt = cleanMessageContent(String(ev.text || ev.content || ""));
        if (txt) {
          lastAssistantRendered = txt;
          lastAssistantStreaming = Boolean(ev.streaming);
          ensureCard().setDone(txt);
        }
      }
    }
    const cleanStream = cleanMessageContent(streamingText);
    if (cleanStream && cleanStream !== lastAssistantRendered) {
      lastAssistantStreaming = isGen;
      ensureCard().setDone(cleanStream);
    }
  } else {
    for (const m of messages) {
      if (!m || typeof m !== "object") continue;
      const rawContent = String(m.content || "");
      if (m.role === "user") {
        curCard = null;
        if (/^\s*<tool_result\b/i.test(rawContent)) continue;
        const cleanedUser = cleanMessageContent(rawContent);
        if (cleanedUser) appendUserBubble(cleanedUser);
      } else if (m.role === "assistant") {
        curCard = null;
        const cleanedAssistant = cleanMessageContent(rawContent);
        if (!cleanedAssistant) continue;
        const card = createAssistantTurnCard(m.model || modelId, mode, false);
        card.setDone(cleanedAssistant);
      }
    }
    if (isGen || streamingText.trim()) {
      const card = ensureCard();
      const cleanStream = cleanMessageContent(streamingText);
      if (cleanStream) {
        lastAssistantStreaming = isGen;
        card.setDone(cleanStream);
      }
    }
  }

  if (isGen && curCard?.el) {
    curCard.el.classList.add("is-live-streaming");
    if (livePhase === "writing" || lastAssistantStreaming) {
      const mdSegs = curCard.el.querySelectorAll(".turn-flow .turn-md-seg");
      const lastMd = mdSegs.length ? mdSegs[mdSegs.length - 1] : null;
      if (lastMd) lastMd.classList.add("streaming-cursor");
    }
  }

  const hasAny = transcript.length > 0 || messages.length > 0 || Boolean(streamingText.trim()) || isGen;
  document.getElementById("hero-welcome")?.classList.toggle("hidden-hero", hasAny);
  syncChatBottomPadding();

  if (sc && nearBottom) {
    sc.scrollTop = sc.scrollHeight;
  }
}

async function initSpectateMode() {
  document.body.classList.add("spectate-readonly");
  document.getElementById("spectate-banner")?.classList.remove("hidden");
  document.getElementById("spectate-composer-bar")?.classList.remove("hidden");
  document.getElementById("btn-expand-sidebar")?.classList.remove("hidden");

  const themeBtn = document.getElementById("btn-spectate-theme");
  const syncThemeBtnLabel = () => {
    if (themeBtn) themeBtn.textContent = state.theme === "dark" ? "Light Theme" : "Dark Theme";
  };
  syncThemeBtnLabel();
  themeBtn?.addEventListener("click", () => {
    const next = state.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    syncThemeBtnLabel();
  });

  const fetchLiveOnce = async () => {
    if (_spectateInFlight) return;
    _spectateInFlight = true;
    try {
      const resp = await fetch("/api/live/state", { cache: "no-store" });
      if (resp.status === 401 || resp.status === 403) {
        _markSpectateEnded();
        return;
      }
      if (resp.ok) {
        renderSpectatePayload(await resp.json());
      }
    } catch {
      // keep retry active
    } finally {
      _spectateInFlight = false;
    }
  };

  await fetchLiveOnce();

  if (typeof EventSource !== "undefined") {
    try {
      _spectateEventSource = new EventSource("/api/live/events");
      _spectateEventSource.onmessage = (ev) => {
        try {
          renderSpectatePayload(JSON.parse(ev.data));
        } catch {
          // ignore malformed chunk
        }
      };
      _spectateEventSource.onerror = () => {
        fetchLiveOnce();
      };
    } catch {
      // fallback polling handles updates
    }
  }

  _spectatePollTimer = setInterval(fetchLiveOnce, 350);
}

async function boot() {
  renderBannerSvgInto(document.getElementById("splash-banner-host"));
  renderBannerSvgInto(document.getElementById("hero-banner-host"));
  renderCcSvgInto(document.getElementById("sidebar-cc-host"));
  renderCcSvgInto(document.getElementById("expand-cc-host"));
  rotateHeroTitle();

  applyTheme(state.theme);
  applyBrandState(dayOfYearCycle());
  renderTopbarTabs();
  bindEvents();
  mobileUI.init();

  const webMode = window.location.pathname.startsWith("/l/")
    ? { spectate: true, readonly: true }
    : await fetch("/api/web/mode").then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (webMode && webMode.spectate) {
    await initSpectateMode();
    setTimeout(() => {
      document.getElementById("startup-splash")?.classList.add("fade-out");
    }, 350);
    return;
  }

  try {
    await refreshBootstrap();
    await refreshTree();
  } catch (err) {
    toast("Bridge warning: " + err.message);
  }

  const params = new URLSearchParams(window.location.search);
  const holdSplash = params.get("splash") === "hold";
  setTimeout(() => {
    if (!holdSplash) {
      document.getElementById("startup-splash")?.classList.add("fade-out");
    }
  }, holdSplash ? 900 : 750);
}

boot();


// ============================================================================
// CMDAI CODE CLI PARITY EXTENSIONS (Voice Dictation, HF GGUF Hub, CLI Settings)
// ============================================================================
(function initCmdaiCliParity() {
  const $ = (id) => document.getElementById(id);

  // 1. Horizontal mouse-wheel scroll on Editor Open Tabs Strip (no vertical slider)
  const tabsList = $("editor-tabs-list");
  if (tabsList) {
    tabsList.addEventListener("wheel", (e) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        tabsList.scrollLeft += e.deltaY;
      }
    }, { passive: false });
  }

  // 2. Models & Engine extra tabs: Voice Dictation & HF GGUF Hub
  function activateExtraModelsPane(paneId, btnId) {
    document.querySelectorAll(".models-tab-pane").forEach((p) => p.classList.remove("active"));
    document.querySelectorAll("#view-models .ag-sb-item").forEach((b) => b.classList.remove("active"));
    $(paneId)?.classList.add("active");
    $(btnId)?.classList.add("active");
  }

  async function refreshVoiceStatus() {
    try {
      const r = await fetch("/api/voice/status");
      if (!r.ok) return;
      const d = await r.json();
      const tag = $("voice-status-tag");
      const detail = $("voice-status-detail");
      if (tag) tag.textContent = d.ready ? "READY (OFFLINE)" : "NOT INSTALLED";
      if (detail) detail.textContent = d.detail || (d.ready ? "Whisper model ready." : "Install via /voicemodel in CLI.");
      if ($("voice-model-select") && d.model) $("voice-model-select").value = d.model;
      if ($("voice-lang-select") && d.language) $("voice-lang-select").value = d.language;
    } catch (_) {}
  }

  async function refreshCliSettings() {
    try {
      const r = await fetch("/api/settings/cli");
      if (!r.ok) return;
      const d = await r.json();
      if ($("engine-flash-attn")) $("engine-flash-attn").checked = Boolean(d.flash_attn);
      if ($("engine-kv-cache") && d.kv_cache_type) $("engine-kv-cache").value = d.kv_cache_type;
      if ($("engine-keyring")) $("engine-keyring").checked = Boolean(d.use_system_keyring);
      if ($("set-cli-flash-attn")) $("set-cli-flash-attn").checked = Boolean(d.flash_attn);
      if ($("set-cli-kv-cache") && d.kv_cache_type) $("set-cli-kv-cache").value = d.kv_cache_type;
      if ($("set-cli-keyring")) $("set-cli-keyring").checked = Boolean(d.use_system_keyring);
    } catch (_) {}
  }

  async function saveCliPatch(patch) {
    try {
      await fetch("/api/settings/cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      await refreshCliSettings();
    } catch (_) {}
  }

  $("btn-mnav-voice")?.addEventListener("click", () => {
    activateExtraModelsPane("mpane-voice", "btn-mnav-voice");
    refreshVoiceStatus();
  });

  $("btn-voice-save")?.addEventListener("click", async () => {
    const model = $("voice-model-select")?.value || "large-v3-turbo";
    const language = $("voice-lang-select")?.value || "auto";
    await fetch("/api/voice/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice_model: model, voice_language: language }),
    });
    await refreshVoiceStatus();
  });

  async function runHfSearch() {
    const q = ($("hf-search-input")?.value || "qwen coder").trim();
    const list = $("hf-results-list");
    if (!list) return;
    list.innerHTML = `<div style="padding:14px;color:var(--text-muted)">Searching Hugging Face for "${q}"...</div>`;
    try {
      const r = await fetch(`/api/hf/search?q=${encodeURIComponent(q)}`);
      const d = await r.json();
      if (d.ok === false && d.error) {
        list.innerHTML = `<div style="padding:14px;color:var(--accent-red)">Hugging Face error: ${d.error}</div>`;
        return;
      }
      const items = d.items || [];
      if (!items.length) {
        list.innerHTML = `<div style="padding:14px;color:var(--text-muted)">No GGUF models found.</div>`;
        return;
      }
      list.innerHTML = items.map((it) => {
        const repo = it.repo_id || it.id || it.name || "";
        const dl = it.downloads ? `${Number(it.downloads).toLocaleString()} downloads` : "";
        const likes = it.likes ? `★ ${it.likes}` : "";
        return `<div class="ag-card-row" style="border:1px solid var(--border-hairline);border-radius:10px;padding:11px 13px;background:var(--bg-card);">
          <div>
            <div class="ag-row-title" style="font-family:var(--font-mono);font-size:12.5px;">${repo}</div>
            <div class="ag-row-desc">${[dl, likes].filter(Boolean).join(" · ") || "Hugging Face GGUF Repository"}</div>
          </div>
          <a class="ed-action-btn small" href="https://huggingface.co/${repo}" target="_blank" rel="noopener">Open HF ↗</a>
        </div>`;
      }).join("");
    } catch (err) {
      list.innerHTML = `<div style="padding:14px;color:var(--accent-red)">Search error: ${err.message}</div>`;
    }
  }

  $("btn-mnav-hf")?.addEventListener("click", () => {
    activateExtraModelsPane("mpane-hf", "btn-mnav-hf");
    runHfSearch();
  });
  $("btn-hf-search")?.addEventListener("click", runHfSearch);
  $("hf-search-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runHfSearch();
  });

  // Sync Flash Attn / KV Cache / Keyring toggles in both Engine & Settings
  $("engine-flash-attn")?.addEventListener("change", (e) => saveCliPatch({ flash_attn: e.target.checked }));
  $("engine-kv-cache")?.addEventListener("change", (e) => saveCliPatch({ kv_cache_type: e.target.value }));
  $("engine-keyring")?.addEventListener("change", (e) => saveCliPatch({ use_system_keyring: e.target.checked }));
  $("set-cli-flash-attn")?.addEventListener("change", (e) => saveCliPatch({ flash_attn: e.target.checked }));
  $("set-cli-kv-cache")?.addEventListener("change", (e) => saveCliPatch({ kv_cache_type: e.target.value }));
  $("set-cli-keyring")?.addEventListener("change", (e) => saveCliPatch({ use_system_keyring: e.target.checked }));

  $("btn-nav-models")?.addEventListener("click", refreshCliSettings);
  $("btn-sidebar-settings")?.addEventListener("click", refreshCliSettings);
  refreshCliSettings();

  // 3. Real-Time Word-by-Word Live Voice Dictation (Instant Web Speech interim + Local PC Whisper finish)
  let vRec = false, vCtx = null, vStream = null, vProc = null, vChunks = [], vTimer = null, vSnapTimer = null, vSpeechRec = null;
  let vPrefixText = "", vDirtyAudio = false, vSnapshotBusy = false, vSilenceSec = 0.0, vLiveHadSpeechApi = false;
  function encodeWav16k(chunks, sr) {
    const total = chunks.reduce((a, c) => a + c.length, 0);
    const merged = new Float32Array(total);
    let off = 0;
    for (const c of chunks) { merged.set(c, off); off += c.length; }
    const ratio = sr / 16000;
    const outLen = Math.max(1, Math.floor(merged.length / ratio));
    const pcm = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const s = Math.max(-1, Math.min(1, merged[Math.floor(i * ratio)] || 0));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const buf = new ArrayBuffer(44 + pcm.length * 2);
    const v = new DataView(buf);
    const ws = (o, str) => { for (let i = 0; i < str.length; i++) v.setUint8(o + i, str.charCodeAt(i)); };
    ws(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); ws(8, "WAVE"); ws(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, 16000, true); v.setUint32(28, 32000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    ws(36, "data"); v.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) v.setInt16(44 + i * 2, pcm[i], true);
    const bytes = new Uint8Array(buf);
    let bin = "";
    for (let i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return btoa(bin);
  }

  function applyVoiceText(inp, text) {
    if (!inp || !text) return;
    const clean = text.trim();
    if (!clean) return;
    const sep = vPrefixText && !/\s$/.test(vPrefixText) ? " " : "";
    const combined = `${vPrefixText}${sep}${clean}`;
    inp.value = combined;
    inp.dispatchEvent(new Event("input"));
    try {
      inp.selectionStart = inp.selectionEnd = combined.length;
    } catch (_) {}
  }

  async function stopVoiceRecording() {
    if (!vRec) return;
    const btn = $("btn-composer-voice");
    const waveCanvas = $("composer-voice-wave");
    const lbl = $("composer-voice-lbl");
    const inp = $("composer-input");
    const footer = btn?.closest(".composer-footer");

    vRec = false;
    clearInterval(vTimer);
    clearInterval(vSnapTimer);
    try { vSpeechRec?.stop(); } catch (_) {}
    vSpeechRec = null;
    btn?.classList.remove("recording");
    btn?.classList.add("transcribing");
    footer?.classList.add("voice-active");
    waveCanvas?.classList.add("hidden");
    if (lbl) {
      lbl.textContent = "transcribing...";
      lbl.classList.remove("hidden");
    }
    const sr = vCtx ? vCtx.sampleRate : 44100;
    const finalChunks = vChunks.slice();
    try {
      vProc?.disconnect();
      await vCtx?.close();
      vStream?.getTracks().forEach((t) => t.stop());
    } catch (_) {}

    // Final finishing pass over complete audio on PC Whisper model
    if (finalChunks.length >= 1) {
      try {
        const b64 = encodeWav16k(finalChunks, sr);
        const r = await fetch("/api/voice/transcribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ audio_wav_base64: b64 }),
        });
        const d = await r.json().catch(() => ({}));
        if (r.ok && d.ok && d.text) {
          applyVoiceText(inp, d.text);
          if (!mobileUI.isMobile) inp?.focus();
        } else if (!r.ok || d.error) {
          toast("Voice error: " + (d.error || `HTTP ${r.status}`));
        }
      } catch (err) {
        toast("Voice error: " + (err?.message || "network failed"));
      }
    }
    btn?.classList.remove("transcribing");
    footer?.classList.remove("voice-active");
    lbl?.classList.add("hidden");
  }

  $("btn-composer-voice")?.addEventListener("click", async () => {
    const btn = $("btn-composer-voice");
    const waveCanvas = $("composer-voice-wave");
    const lbl = $("composer-voice-lbl");
    const inp = $("composer-input");
    const footer = btn?.closest(".composer-footer");
    if (!vRec) {
      if (!navigator.mediaDevices?.getUserMedia) {
        toast("Microphone requires localhost or HTTPS (Cloudflare Tunnel).");
        return;
      }
      try {
        vStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        const AC = window.AudioContext || window.webkitAudioContext;
        vCtx = new AC();
        if (vCtx.state === "suspended") {
          await vCtx.resume();
        }
        const src = vCtx.createMediaStreamSource(vStream);
        vProc = vCtx.createScriptProcessor(4096, 1, 1);
        const silentGain = vCtx.createGain();
        silentGain.gain.value = 0;

        vChunks = [];
        vPrefixText = inp?.value || "";
        vDirtyAudio = false;
        vSnapshotBusy = false;
        vSilenceSec = 0.0;
        let lvl = 0;
        let phase = 0;
        let hadAnySpeech = false;
        let lastSentChunks = 0;

        vProc.onaudioprocess = (ev) => {
          const ch = ev.inputBuffer.getChannelData(0);
          vChunks.push(new Float32Array(ch));
          let sum = 0;
          for (let i = 0; i < ch.length; i += 16) sum += Math.abs(ch[i]);
          lvl = Math.min(1, (sum / (ch.length / 16)) * 10.0);
          if (lvl >= 0.005) {
            vDirtyAudio = true;
            hadAnySpeech = true;
            vSilenceSec = 0.0;
          }
        };
        src.connect(vProc);
        vProc.connect(silentGain);
        silentGain.connect(vCtx.destination);
        vRec = true;
        btn.classList.add("recording");
        btn.classList.remove("transcribing");
        footer?.classList.add("voice-active");
        if (lbl) {
          lbl.textContent = "listening...";
          lbl.classList.remove("hidden");
        }
        waveCanvas?.classList.remove("hidden");

        // Live Dot-Matrix Sine Waveform Renderer + 5s silence auto-stop
        const drawWave = () => {
          if (!vRec || !waveCanvas) return;
          if (hadAnySpeech && !vSnapshotBusy && lvl < 0.006) {
            vSilenceSec += 0.045;
            if (vSilenceSec >= 5.0) {
              stopVoiceRecording();
              return;
            }
          }
          const ctx = waveCanvas.getContext("2d");
          const W = waveCanvas.width, H = waveCanvas.height;
          ctx.clearRect(0, 0, W, H);
          const isDark = document.documentElement.getAttribute("data-theme") === "dark";
          const cols = 19, rows = 5;
          const stepX = W / (cols + 1), stepY = H / (rows + 1);
          phase += 0.24;
          const amp = 0.22 + lvl * 1.9;
          for (let c = 0; c < cols; c++) {
            const normX = c / (cols - 1);
            const env = Math.sin(normX * Math.PI);
            const waveY = (rows - 1) / 2 + Math.sin(normX * 7.5 - phase) * amp * env * ((rows - 1) / 2);
            for (let r = 0; r < rows; r++) {
              const dist = Math.abs(r - waveY);
              const alpha = dist < 0.7 ? 0.95 : dist < 1.35 ? 0.35 : 0.12;
              ctx.fillStyle = isDark ? `rgba(241,245,249,${alpha})` : `rgba(17,24,39,${alpha})`;
              ctx.beginPath();
              ctx.arc((c + 1) * stepX, (r + 1) * stepY, dist < 0.7 ? 1.45 : 1.05, 0, Math.PI * 2);
              ctx.fill();
            }
          }
        };
        vTimer = setInterval(drawWave, 45);

        // Live Whisper transcription snapshots directly on PC (/api/voice/transcribe) every 1.1s
        // Appends continuously to any pre-existing text in #composer-input while you speak!
        vLiveHadSpeechApi = false;
        vSnapTimer = setInterval(async () => {
          if (!vRec || vSnapshotBusy || vChunks.length < 3) return;
          if (!vDirtyAudio && vChunks.length <= lastSentChunks + 2) return;
          vSnapshotBusy = true;
          vDirtyAudio = false;
          lastSentChunks = vChunks.length;
          if (lbl && vRec) lbl.textContent = "transcribing...";
          try {
            const sr = vCtx ? vCtx.sampleRate : 44100;
            const b64 = encodeWav16k(vChunks.slice(), sr);
            const r = await fetch("/api/voice/transcribe", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ audio_wav_base64: b64 }),
            });
            const d = await r.json().catch(() => ({}));
            if (vRec && r.ok && d.ok && d.text) {
              applyVoiceText(inp, d.text);
            }
          } catch (_) {
          } finally {
            vSnapshotBusy = false;
            if (lbl && vRec) lbl.textContent = "listening...";
          }
        }, 1100);
      } catch (err) {
        footer?.classList.remove("voice-active");
        toast("Mic error: " + (err?.message || "permission denied"));
      }
    } else {
      await stopVoiceRecording();
    }
  });
})();


// ==========================================================================
// HEADLESS BROWSER CONTROL PANEL (1:1 Rounded Cursor + Frosted Whisper + Tap Burst)
// ==========================================================================
const _browserUiState = {
  lastFrameSeq: -1,
  lastClickSeq: 0,
  width: 1280,
  height: 800,
  takeControl: false,
  lastCursor: { x: 640, y: 400, state: "idle", label: "" },
};

function _positionBrowserCursor() {
  const imgEl = document.getElementById("browser-frame-img");
  const cursorEl = document.getElementById("browser-ai-cursor");
  const whisperEl = document.getElementById("browser-whisper-pill");
  if (!imgEl || !cursorEl) return;
  const rect = imgEl.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const cur = _browserUiState.lastCursor || {};
  const px = Math.round((Number(cur.x || 0) / _browserUiState.width) * rect.width);
  const py = Math.round((Number(cur.y || 0) / _browserUiState.height) * rect.height);
  cursorEl.style.transform = `translate3d(${px}px, ${py}px, 0)`;
  cursorEl.style.opacity = _browserUiState.takeControl ? "0.25" : "1";
  if (whisperEl) {
    const flipLim = Math.min(240, Math.round(rect.width * 0.48));
    whisperEl.classList.toggle("flip-left", px > rect.width - flipLim);
    whisperEl.classList.toggle("flip-top", py > rect.height - 64);
  }
}

async function refreshBrowserState() {
  try {
    const res = await fetch("/api/browser/state");
    if (!res.ok) return;
    const data = await res.json();
    applyBrowserState(data);
  } catch (_) {}
}

function applyBrowserState(st) {
  if (!st) return;
  _browserUiState.width = Number(st.width || 1280);
  _browserUiState.height = Number(st.height || 800);
  _browserUiState.takeControl = Boolean(st.take_control);

  const urlInp = document.getElementById("browser-url-input");
  const emptyEl = document.getElementById("browser-empty-state");
  const stageEl = document.getElementById("browser-frame-stage");
  const imgEl = document.getElementById("browser-frame-img");
  const cursorEl = document.getElementById("browser-ai-cursor");
  const whisperEl = document.getElementById("browser-whisper-pill");
  const whisperTxt = document.getElementById("browser-whisper-text");
  const tapEl = document.getElementById("browser-tap-burst");
  const takeBtn = document.getElementById("btn-browser-take-control");
  const consBadge = document.getElementById("browser-console-badge");
  const consList = document.getElementById("browser-console-list");

  if (urlInp && st.url && document.activeElement !== urlInp) {
    urlInp.value = st.url;
  }
  if (takeBtn) {
    takeBtn.textContent = _browserUiState.takeControl ? "Release Control" : "Take Control";
    takeBtn.style.borderColor = _browserUiState.takeControl ? "var(--accent-blue)" : "";
    takeBtn.style.color = _browserUiState.takeControl ? "var(--accent-blue)" : "";
  }
  if (stageEl) {
    const bw = _browserUiState.width;
    const bh = _browserUiState.height;
    const dev = st.device || (bw < bh ? (bw <= 480 ? "mobile" : "tablet") : "desktop");
    stageEl.style.aspectRatio = `${bw} / ${bh}`;
    stageEl.classList.toggle("device-mobile", dev === "mobile");
    stageEl.classList.toggle("device-tablet", dev === "tablet");
    stageEl.classList.toggle("user-control", _browserUiState.takeControl);
  }

  const isRunning = Boolean(st.running && st.has_frame);
  const sumObj = !isRunning && st.last_session && st.last_session.summary ? st.last_session : null;
  emptyEl?.classList.toggle("hidden", isRunning || Boolean(sumObj));
  stageEl?.classList.toggle("hidden", !isRunning);
  stageEl?.classList.toggle("agent-active", isRunning && !_browserUiState.takeControl);

  const favEl = document.getElementById("browser-omnibox-fav");
  const globeEl = document.getElementById("browser-omnibox-globe");
  const favUrl = String(st.favicon || (sumObj && sumObj.favicon) || "");
  if (favEl && globeEl && favUrl !== _browserUiState.lastFav) {
    _browserUiState.lastFav = favUrl;
    if (!favUrl) {
      favEl.classList.add("hidden");
      globeEl.classList.remove("hidden");
    } else {
      favEl.onload = () => { favEl.classList.remove("hidden"); globeEl.classList.add("hidden"); };
      favEl.onerror = () => { favEl.classList.add("hidden"); globeEl.classList.remove("hidden"); };
      favEl.src = favUrl;
    }
  }

  const sumCard = document.getElementById("browser-summary-card");
  if (sumCard) {
    sumCard.classList.toggle("hidden", !sumObj);
    if (sumObj) {
      const stepsHtml = (sumObj.steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
      sumCard.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
          <strong style="font-size:14px;color:var(--text-primary);">${escapeHtml(sumObj.title || sumObj.url || "Browser Session Complete")}</strong>
          <button id="btn-browser-sum-reopen" class="ed-action-btn compact" type="button">Reopen URL</button>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;">
          <span class="cap-tag">${escapeHtml(sumObj.model || "Browser Agent")}</span>
          <span class="cap-tag">${Number(sumObj.steps_count || 0)} steps</span>
          <span class="cap-tag">${Number(sumObj.elapsed || 0)}s</span>
          <span class="cap-tag">${Number(sumObj.console_errors || 0)} errors</span>
        </div>
        <div style="font-size:13px;line-height:1.6;color:var(--text-primary);white-space:pre-wrap;">${escapeHtml(sumObj.summary || "")}</div>
        ${stepsHtml ? `<details style="border:1px solid var(--border-hairline);border-radius:8px;padding:6px 10px;background:var(--bg-app);"><summary style="cursor:pointer;font-size:12px;color:var(--text-secondary);">Steps Performed (${(sumObj.steps || []).length})</summary><ol style="margin:6px 0 2px 18px;font-family:var(--font-mono);font-size:11.3px;color:var(--text-secondary);">${stepsHtml}</ol></details>` : ""}
      `;
      document.getElementById("btn-browser-sum-reopen")?.addEventListener("click", () => {
        if (urlInp && sumObj.url) urlInp.value = sumObj.url;
        document.getElementById("btn-browser-go")?.click();
      });
    }
  }

  const stPill = document.getElementById("browser-status-pill");
  const stLbl = document.getElementById("browser-status-lbl");
  if (stPill && stLbl) {
    stPill.classList.toggle("live", isRunning && !_browserUiState.takeControl);
    stPill.classList.toggle("user", isRunning && _browserUiState.takeControl);
    stLbl.textContent = !isRunning ? "Idle" : (_browserUiState.takeControl ? "You" : "Agent");
  }

  if (isRunning && imgEl && Number(st.frame_seq || 0) !== _browserUiState.lastFrameSeq) {
    _browserUiState.lastFrameSeq = Number(st.frame_seq || 0);
    imgEl.src = `/api/browser/frame?seq=${_browserUiState.lastFrameSeq}&t=${Date.now()}`;
  }

  // Smooth virtual cursor positioning + Frosted Whisper pill + Tap Burst
  const cur = st.cursor || {};
  _browserUiState.lastCursor = cur;
  if (cursorEl && imgEl && isRunning) {
    _positionBrowserCursor();
    const rect = imgEl.getBoundingClientRect();
    const px = rect.width ? Math.round((Number(cur.x || 0) / _browserUiState.width) * rect.width) : 0;
    const py = rect.height ? Math.round((Number(cur.y || 0) / _browserUiState.height) * rect.height) : 0;

    const lbl = String(cur.label || "").trim();
    const cState = String(cur.state || "idle").toLowerCase();
    if (whisperEl && whisperTxt) {
      const showPill = Boolean(lbl) && cState !== "idle" && !_browserUiState.takeControl;
      whisperEl.classList.toggle("hidden", !showPill);
      if (showPill) whisperTxt.textContent = lbl;
    }

    const clickSeq = Number(cur.click_seq || 0);
    if (clickSeq > _browserUiState.lastClickSeq) {
      _browserUiState.lastClickSeq = clickSeq;
      cursorEl.classList.add("pressing");
      setTimeout(() => cursorEl.classList.remove("pressing"), 180);
      if (tapEl) {
        tapEl.style.left = `${px}px`;
        tapEl.style.top = `${py}px`;
        tapEl.classList.remove("active");
        void tapEl.offsetWidth;
        tapEl.classList.add("active");
      }
    }
  }

  if (consBadge) {
    const errs = Number(st.console_errors || 0);
    consBadge.textContent = errs === 1 ? "1 error" : `${errs} errors`;
    consBadge.style.color = errs > 0 ? "var(--accent-red)" : "";
  }
  if (consList && Array.isArray(st.console_logs)) {
    consList.innerHTML = st.console_logs.length
      ? st.console_logs.map((l) => {
          const isErr = l.level === "error" || l.level === "exception";
          const col = isErr ? "var(--accent-red)" : "var(--text-secondary)";
          return `<div style="color:${col};">[${escapeHtml(l.level || "log")}] ${escapeHtml(l.text || "")}</div>`;
        }).join("")
      : `<div style="color:var(--text-muted);">No console output yet.</div>`;
  }
}

(function initBrowserPanelEvents() {
  const urlInp = document.getElementById("browser-url-input");
  const goBtn = document.getElementById("btn-browser-go");
  const takeBtn = document.getElementById("btn-browser-take-control");
  const stopBtn = document.getElementById("btn-browser-stop");
  const imgEl = document.getElementById("browser-frame-img");

  const doOpen = async () => {
    const url = (urlInp?.value || "").trim();
    if (!url) return;
    if (goBtn) goBtn.textContent = "...";
    try {
      const res = await fetch("/api/browser/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (data.state) applyBrowserState(data.state);
      if (!data.ok && data.error) toast(data.error);
    } catch (e) {
      toast("Browser open failed");
    } finally {
      if (goBtn) goBtn.textContent = "Go";
    }
  };

  goBtn?.addEventListener("click", doOpen);
  document.getElementById("btn-browser-reload")?.addEventListener("click", doOpen);
  document.querySelectorAll(".browser-chip[data-quick-url]").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (urlInp) urlInp.value = chip.dataset.quickUrl || "";
      doOpen();
    });
  });
  urlInp?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      doOpen();
    }
  });

  takeBtn?.addEventListener("click", async () => {
    const next = !_browserUiState.takeControl;
    const res = await fetch("/api/browser/take-control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: next }),
    });
    if (res.ok) applyBrowserState(await res.json());
  });

  stopBtn?.addEventListener("click", async () => {
    const res = await fetch("/api/browser/close", { method: "POST" });
    if (res.ok) {
      _browserUiState.lastFrameSeq = -1;
      applyBrowserState({ running: false, has_frame: false, console_logs: [], console_errors: 0 });
      toast("Headless browser closed");
    }
  });

  imgEl?.addEventListener("load", _positionBrowserCursor);
  window.addEventListener("resize", _positionBrowserCursor);

  imgEl?.addEventListener("click", async (e) => {
    if (!_browserUiState.takeControl) return;
    const rect = imgEl.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const bx = Math.round(((e.clientX - rect.left) / rect.width) * _browserUiState.width);
    const by = Math.round(((e.clientY - rect.top) / rect.height) * _browserUiState.height);
    const res = await fetch("/api/browser/interact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "click", x: bx, y: by }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.state) applyBrowserState(data.state);
    }
  });

  let _browserWheelBusy = false;
  imgEl?.addEventListener("wheel", async (e) => {
    if (!_browserUiState.takeControl) return;
    e.preventDefault();
    if (_browserWheelBusy) return;
    _browserWheelBusy = true;
    try {
      const dir = e.deltaY < 0 ? "up" : "down";
      const amt = Math.min(800, Math.max(220, Math.abs(Math.round(e.deltaY * 2.5))));
      const res = await fetch("/api/browser/interact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "scroll", direction: dir, amount: amt }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.state) applyBrowserState(data.state);
      }
    } finally {
      setTimeout(() => { _browserWheelBusy = false; }, 160);
    }
  }, { passive: false });
})();
