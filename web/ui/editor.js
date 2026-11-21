/**
 * Autorski Desktopowy Edytor Kodu (bez Monaco / VS Code)
 * Wykorzystuje natywny skaner plików w Rust oraz diagnostics.py / format.py / ast_indexer.py z Pythona.
 */

export class CustomCodeEditor {
  constructor(hooks) {
    this.hooks = hooks; // { onToast, onOpenSplitDiff, onRequestRefreshTree }
    this.tabs = [];
    this.activePath = null;
    this.highlightedLine = null;
    this.diffMode = false;
    this.currentDiff = null;
    this.termHistory = [];
    this.termHistIdx = -1;

    this.elTabsList = document.getElementById("editor-tabs-list");
    this.elTreePane = document.getElementById("editor-tree-pane");
    this.elTreeList = document.getElementById("editor-tree-list");
    this.elBreadcrumb = document.getElementById("ed-breadcrumb");
    this.elStats = document.getElementById("ed-file-stats");
    this.elTreeFilter = document.getElementById("editor-tree-filter");
    this.elBtnNewFile = document.getElementById("btn-editor-new-file");
    this.elCursorStatus = document.getElementById("ed-cursor-status");
    this.elLangStatus = document.getElementById("ed-lang-status");
    this.elLintStatus = document.getElementById("ed-lint-status");
    this._allTreeEntries = [];
    this.treeFilterQuery = "";
    this.elSymbolJump = document.getElementById("ed-symbol-jump");
    this.elGutter = document.getElementById("editor-gutter");
    this.elHighlight = document.getElementById("editor-highlight-layer");
    this.elTextarea = document.getElementById("editor-textarea");
    this.elOutline = document.getElementById("editor-outline-list");

    this.elCodeContainer = document.getElementById("editor-code-container");
    this.elDiffContainer = document.getElementById("editor-diff-container");
    this.elDiffHunks = document.getElementById("editor-diff-hunks");
    this.elDiffSummary = document.getElementById("diff-summary-text");

    this.elTermOut = document.getElementById("terminal-output");
    this.elTermIn = document.getElementById("terminal-input");
    this.elProblemsList = document.getElementById("problems-list");
    this.elProblemsCount = document.getElementById("dock-problems-count");
    this.elSearchInput = document.getElementById("search-files-input");
    this.elSearchResults = document.getElementById("search-files-results");

    this._bindEvents();
    this._bootTerminalBanner();
    if (this.elTextarea) {
      this.elTextarea.addEventListener("input", () => this.updateStatusBar());
    }
    if (typeof MutationObserver !== "undefined") {
      const obs = new MutationObserver(() => this.updateStatusBar());
      if (this.elBreadcrumb) obs.observe(this.elBreadcrumb, { childList: true, characterData: true, subtree: true });
      if (this.elProblemsCount) obs.observe(this.elProblemsCount, { childList: true, characterData: true, subtree: true });
    }
    this.updateStatusBar();
  }

  _bindEvents() {
    this.elTextarea.addEventListener("input", () => {
      const tab = this.activeTab();
      if (tab) {
        tab.content = this.elTextarea.value;
        tab.dirty = tab.content !== tab.savedContent;
        this.renderTabs();
      }
      this.highlightedLine = null;
      this.renderCodeView();
    });

    this.elTextarea.addEventListener("scroll", () => {
      this.elHighlight.scrollTop = this.elTextarea.scrollTop;
      this.elHighlight.scrollLeft = this.elTextarea.scrollLeft;
      this.elGutter.scrollTop = this.elTextarea.scrollTop;
    });

    this.elTextarea.addEventListener("click", () => {
      this.updateActiveLineGutter();
      this.updateStatusBar();
    });
    this.elTextarea.addEventListener("keyup", () => {
      this.updateActiveLineGutter();
      this.updateStatusBar();
    });

    this.elTextarea.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = this.elTextarea.selectionStart;
        const end = this.elTextarea.selectionEnd;
        const val = this.elTextarea.value;
        this.elTextarea.value = val.slice(0, start) + "    " + val.slice(end);
        this.elTextarea.selectionStart = this.elTextarea.selectionEnd = start + 4;
        this.elTextarea.dispatchEvent(new Event("input"));
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        this.saveActiveFile();
      }
    });

    if (this.elSymbolJump) {
      this.elSymbolJump.addEventListener("change", () => {
        const ln = parseInt(this.elSymbolJump.value, 10);
        if (ln > 0) {
          this.jumpToLine(ln);
        }
      });
    }

    document.getElementById("btn-editor-save")?.addEventListener("click", () => this.saveActiveFile());
    document.getElementById("btn-editor-format")?.addEventListener("click", () => this.formatActiveFile());
    document.getElementById("btn-editor-diff-toggle")?.addEventListener("click", () => this.toggleDiffView());
    if (this.elTreeFilter) {
      this.elTreeFilter.addEventListener("input", () => {
        this.treeFilterQuery = (this.elTreeFilter.value || "").trim().toLowerCase();
        this.renderTree(this._allTreeEntries);
      });
    }
    if (this.elBtnNewFile) {
      this.elBtnNewFile.addEventListener("click", () => this.promptNewFileInline());
    }
    document.getElementById("btn-editor-toggle-tree")?.addEventListener("click", () => {
      this.elTreePane?.classList.toggle("collapsed");
    });
    document.getElementById("btn-diff-close").addEventListener("click", () => this.setDiffMode(false));
    document.getElementById("btn-diff-demo").addEventListener("click", () => this.previewSampleDiff());

    // Bottom Dock Tabs
    document.querySelectorAll(".dock-tab").forEach((btn) => {
      btn.addEventListener("click", () => this.switchDockTab(btn.dataset.dock));
    });

    document.getElementById("btn-terminal-run").addEventListener("click", () => this.runTerminalCommand());
    this.elTermIn.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.runTerminalCommand();
      } else if (e.key === "ArrowUp") {
        if (this.termHistory.length && this.termHistIdx < this.termHistory.length - 1) {
          this.termHistIdx += 1;
          this.elTermIn.value = this.termHistory[this.termHistory.length - 1 - this.termHistIdx];
        }
      } else if (e.key === "ArrowDown") {
        if (this.termHistIdx > 0) {
          this.termHistIdx -= 1;
          this.elTermIn.value = this.termHistory[this.termHistory.length - 1 - this.termHistIdx];
        } else {
          this.termHistIdx = -1;
          this.elTermIn.value = "";
        }
      }
    });

    document.getElementById("btn-scan-problems").addEventListener("click", () => this.scanProblems());
    document.getElementById("btn-search-files-run").addEventListener("click", () => this.searchInFiles());
    this.elSearchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.searchInFiles();
    });
  }

  _bootTerminalBanner() {
    this.appendTerminalLog(
      "CMDAI CODE Cross-Platform Shell Ready (Windows PowerShell / Linux Bash)\n" +
      "Type a command below (e.g. `git status`, `python --version`) and press Enter.\n",
      "muted"
    );
  }

  switchDockTab(target = "terminal") {
    document.querySelectorAll(".dock-tab").forEach((b) => b.classList.toggle("active", b.dataset.dock === target));
    document.querySelectorAll(".dock-pane").forEach((p) => {
      p.classList.toggle("active", p.id === `dock-pane-${target}`);
    });
    if (target === "terminal" && this.elTermIn) {
      setTimeout(() => this.elTermIn.focus(), 40);
    }
  }

  setShellLabel(shellName) {
    const labelEl = document.getElementById("dock-shell-name");
    const promptEl = document.getElementById("term-prompt-label");
    if (labelEl) labelEl.textContent = shellName || "Shell";
    if (promptEl) promptEl.textContent = (shellName || "").toLowerCase().includes("bash") ? "$ " : "PS> ";
  }

  applyPreferences({ fontSize = 13, tabSize = 4 } = {}) {
    const fs = `${Math.max(10, Math.min(24, Number(fontSize) || 13))}px`;
    if (this.elTextarea) {
      this.elTextarea.style.fontSize = fs;
      this.elTextarea.style.tabSize = String(tabSize || 4);
    }
    if (this.elHighlight) {
      this.elHighlight.style.fontSize = fs;
      this.elHighlight.style.tabSize = String(tabSize || 4);
    }
    if (this.elGutter) {
      this.elGutter.style.fontSize = fs;
    }
  }

  activeTab() {
    return this.tabs.find((t) => t.path === this.activePath) || null;
  }

  async openFile(path, line = null) {
    if (!path) return;
    const existing = this.tabs.find((t) => t.path === path);
    if (existing) {
      this.activePath = path;
      this.setDiffMode(false);
      this.renderTabs();
      this.loadTabIntoEditor(existing, line);
      return;
    }

    try {
      const resp = await fetch(`/api/editor/file?path=${encodeURIComponent(path)}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const tab = {
        path: data.path,
        name: data.name,
        content: data.content,
        savedContent: data.content,
        dirty: false,
        diagnostics: data.diagnostics || [],
        symbols: data.symbols || [],
        diff: data.diff || { hunks: [], added: 0, removed: 0 },
      };
      this.tabs.push(tab);
      this.activePath = tab.path;
      this.setDiffMode(false);
      this.renderTabs();
      this.loadTabIntoEditor(tab, line);
    } catch (err) {
      this.hooks.onToast?.(`Failed to open ${path}: ${err.message}`);
    }
  }

  loadTabIntoEditor(tab, targetLine = null) {
    this.elTextarea.value = tab.content;
    this.elBreadcrumb.textContent = tab.path;
    this.highlightedLine = targetLine;
    this.currentDiff = tab.diff;
    this.renderSymbols(tab.symbols);
    this.renderCodeView();
    if (targetLine && targetLine > 0) {
      setTimeout(() => this.jumpToLine(targetLine), 30);
    }
  }

  closeTab(path) {
    const idx = this.tabs.findIndex((t) => t.path === path);
    if (idx === -1) return;
    this.tabs.splice(idx, 1);
    if (this.activePath === path) {
      const next = this.tabs[Math.min(idx, this.tabs.length - 1)] || null;
      this.activePath = next ? next.path : null;
      if (next) {
        this.loadTabIntoEditor(next);
      } else {
        this.elTextarea.value = "";
        this.elBreadcrumb.textContent = "No file open";
        this.renderCodeView();
      }
    }
    this.renderTabs();
  }

  renderTabs() {
    this.elTabsList.innerHTML = "";
    for (const tab of this.tabs) {
      const el = document.createElement("div");
      el.className = `ed-tab ${tab.path === this.activePath ? "active" : ""}`;
      const diagCount = (tab.diagnostics || []).length;
      const diagHtml = diagCount > 0 ? `<span style="color:var(--accent-blue);font-size:10px;">●${diagCount}</span>` : "";
      const iconHtml = window.getCmdaiFileIconHtml ? window.getCmdaiFileIconHtml(tab.name) : "";
      el.innerHTML = `
        ${iconHtml}
        <span>${this._escapeHtml(tab.name)}</span>
        ${tab.dirty ? '<span style="color:var(--accent-blue);">●</span>' : ""}
        ${diagHtml}
        <span class="ed-tab-close" title="Close tab">×</span>
      `;
      el.addEventListener("click", (e) => {
        if (e.target.classList.contains("ed-tab-close")) {
          this.closeTab(tab.path);
        } else {
          this.activePath = tab.path;
          this.setDiffMode(false);
          this.renderTabs();
          this.loadTabIntoEditor(tab);
        }
      });
      this.elTabsList.appendChild(el);
    }
    this._syncTreeActive();
  }

  detectLanguage(filePath = "") {
    const ext = String(filePath).split(".").pop().toLowerCase();
    const map = {
      py: "Python",
      js: "JavaScript",
      mjs: "JavaScript",
      ts: "TypeScript",
      tsx: "TypeScript JSX",
      jsx: "JavaScript JSX",
      rs: "Rust",
      html: "HTML",
      css: "CSS",
      json: "JSON",
      md: "Markdown",
      toml: "TOML",
      yaml: "YAML",
      yml: "YAML",
      sh: "Shell",
      ps1: "PowerShell",
      sql: "SQL",
    };
    return map[ext] || (ext ? ext.toUpperCase() : "Plain Text");
  }

  updateStatusBar() {
    const ta = this.elTextarea;
    if (this.elCursorStatus && ta) {
      const pos = ta.selectionStart || 0;
      const before = (ta.value || "").slice(0, pos);
      const lines = before.split("\n");
      const ln = lines.length;
      const col = lines[lines.length - 1].length + 1;
      this.elCursorStatus.textContent = `Ln ${ln}, Col ${col}`;
    }
    if (this.elLangStatus) {
      this.elLangStatus.textContent = this.detectLanguage(this.activePath || "");
    }
    if (this.elLintStatus) {
      const diagLen = Array.isArray(this.diagnostics)
        ? this.diagnostics.length
        : (this.elProblemsCount ? parseInt(this.elProblemsCount.textContent || "0", 10) || 0 : 0);
      this.elLintStatus.textContent = `${diagLen} issues`;
    }
  }

  promptNewFileInline() {
    if (!this.elTreePane) return;
    let bar = this.elTreePane.querySelector(".editor-new-file-row");
    if (bar) {
      const inp = bar.querySelector("input");
      if (inp) inp.focus();
      return;
    }
    bar = document.createElement("div");
    bar.className = "editor-new-file-row";
    bar.style.cssText = "display:flex;gap:4px;padding:6px 8px;border-bottom:1px solid var(--border-hairline);";
    bar.innerHTML = `<input type="text" placeholder="path/new_file.py" style="flex:1;min-width:0;height:26px;padding:0 7px;border-radius:6px;border:1px solid var(--accent-blue);background:var(--bg-card);color:var(--text-primary);font-size:11.5px;outline:none;" />`;
    const controls = this.elTreePane.querySelector(".editor-tree-controls");
    if (controls && controls.nextSibling) {
      this.elTreePane.insertBefore(bar, controls.nextSibling);
    } else {
      this.elTreePane.prepend(bar);
    }
    const input = bar.querySelector("input");
    input.focus();
    const closeBar = () => bar.remove();
    input.addEventListener("keydown", async (e) => {
      if (e.key === "Escape") {
        closeBar();
      } else if (e.key === "Enter") {
        e.preventDefault();
        const rel = (input.value || "").trim().replace(/^[/\\]+/, "");
        closeBar();
        if (!rel) return;
        try {
          const resp = await fetch("/api/editor/file", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: rel, content: "" }),
          });
          if (resp.ok) {
            if (typeof this.loadTree === "function") await this.loadTree();
            await this.openFile(rel);
            this.updateStatusBar();
            return;
          }
        } catch (_) {}
        if (typeof this.openVirtualFile === "function") {
          this.openVirtualFile(rel, "");
        } else {
          if (this.tabs && !this.tabs.has(rel)) {
            this.tabs.set(rel, { path: rel, content: "", originalContent: "", dirty: true });
          }
          this.activePath = rel;
          if (this.elTextarea) this.elTextarea.value = "";
          if (this.elBreadcrumb) this.elBreadcrumb.textContent = rel;
          this.renderTabs();
          this.updateStatusBar();
        }
      }
    });
    input.addEventListener("blur", () => {
      setTimeout(() => { if (!input.value.trim()) closeBar(); }, 160);
    });
  }

  renderTree(entries = null) {
    if (Array.isArray(entries)) {
      this._allTreeEntries = entries.slice();
    }
    const sourceEntries = Array.isArray(this._allTreeEntries) ? this._allTreeEntries : [];
    const query = (this.treeFilterQuery || "").toLowerCase();
    const filtered = query
      ? sourceEntries.filter((e) => String(e.path || e.name || "").toLowerCase().includes(query))
      : sourceEntries;
    if (!this.elTreeList) return;
    this.renderTreeFiltered(filtered);
  }

  renderTreeFiltered(entries = []) {
    if (!this.elTreeList) return;
    this.elTreeList.innerHTML = "";
    const files = entries.filter((e) => e.kind === "file").slice(0, 200);
    if (!files.length) {
      this.elTreeList.innerHTML = `<div style="padding:8px;color:var(--text-muted);font-size:11.5px;">No files indexed</div>`;
      return;
    }
    for (const f of files) {
      const btn = document.createElement("button");
      btn.className = `tree-file-row${f.path === this.activePath ? " active" : ""}`;
      btn.dataset.treePath = f.path;
      btn.title = f.path;
      const base = f.path.split("/").pop();
      const ico = window.getCmdaiFileIconHtml ? window.getCmdaiFileIconHtml(base) : "";
      btn.innerHTML = `${ico}<span class="tree-file-label">${this._escapeHtml(f.path)}</span>`;
      btn.addEventListener("click", () => this.openFile(f.path, 1));
      this.elTreeList.appendChild(btn);
    }
  }

  _syncTreeActive() {
    if (!this.elTreeList) return;
    this.elTreeList.querySelectorAll(".tree-file-row").forEach((row) => {
      row.classList.toggle("active", row.dataset.treePath === this.activePath);
    });
  }

  renderSymbols(symbols) {
    if (!this.elSymbolJump && !this.elOutline) return;
    if (this.elSymbolJump) this.elSymbolJump.innerHTML = `<option value="">◆ AST Symbols (${symbols.length})</option>`;
    if (this.elOutline) this.elOutline.innerHTML = "";
    if (!symbols.length) {
      if (this.elOutline) this.elOutline.innerHTML = `<div style="padding:8px;color:var(--text-muted);font-size:11.5px;">No AST symbols</div>`;
      return;
    }
    for (const sym of symbols) {
      if (this.elSymbolJump) {
        const opt = document.createElement("option");
        opt.value = sym.start_line;
        opt.textContent = `${sym.type === "class" ? "◆" : "ƒ"} ${sym.name} (L${sym.start_line})`;
        this.elSymbolJump.appendChild(opt);
      }
      if (this.elOutline) {
        const item = document.createElement("div");
        item.className = "outline-item";
        item.innerHTML = `
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            <span style="color:${sym.type === "class" ? "#38bdf8" : "#60a5fa"};">${sym.type === "class" ? "◆" : "ƒ"}</span>
            ${this._escapeHtml(sym.name)}
          </span>
          <span class="outline-badge">L${sym.start_line}</span>
        `;
        item.addEventListener("click", () => this.jumpToLine(sym.start_line));
        this.elOutline.appendChild(item);
      }
    }
  }

  jumpToLine(lineNum) {
    this.setDiffMode(false);
    this.highlightedLine = lineNum;
    this.renderCodeView();
    const targetTop = Math.max(0, (lineNum - 5) * 20);
    this.elTextarea.scrollTop = targetTop;
    this.elHighlight.scrollTop = targetTop;
    this.elGutter.scrollTop = targetTop;
  }

  getCursorLine() {
    const pos = this.elTextarea.selectionStart || 0;
    return this.elTextarea.value.slice(0, pos).split("\n").length;
  }

  updateActiveLineGutter() {
    const curLine = this.getCursorLine();
    const nodes = this.elGutter.children;
    for (let i = 0; i < nodes.length; i++) {
      nodes[i].classList.toggle("active-line", i + 1 === curLine);
    }
  }

  renderCodeView() {
    const text = this.elTextarea.value || "";
    const lines = text.split("\n");
    const tab = this.activeTab();
    const diags = tab ? tab.diagnostics || [] : [];
    const diagByLine = new Map();
    for (const d of diags) {
      diagByLine.set(d.row, d);
    }

    const curLine = this.getCursorLine();
    this.elStats.textContent = `${lines.length} lines • ${diags.length} diag • UTF-8`;

    let gutterHtml = "";
    for (let i = 1; i <= lines.length; i++) {
      const diag = diagByLine.get(i);
      const dot = diag
        ? `<span class="gutter-diag-dot ${diag.severity}" title="${this._escapeHtml(diag.code + ": " + diag.message)}"></span>`
        : "";
      const activeCls = i === curLine || i === this.highlightedLine ? "active-line" : "";
      gutterHtml += `<div class="gutter-line ${activeCls}">${dot}<span>${i}</span></div>`;
    }
    this.elGutter.innerHTML = gutterHtml;

    const ext = (this.activePath || "").split(".").pop().toLowerCase();
    const renderedLines = lines.map((line, idx) => {
      const hl = this._highlightLine(line, ext);
      if (this.highlightedLine && idx + 1 === this.highlightedLine) {
        return `<span class="hl-line-flash">${hl || " "}</span>`;
      }
      return hl;
    });
    this.elHighlight.innerHTML = renderedLines.join("\n") + "\n";
  }

  _highlightLine(rawLine, ext) {
    let s = this._escapeHtml(rawLine);
    if (!s) return "";

    const trimmed = rawLine.trimStart();
    if ((ext === "py" || ext === "pyw" || ext === "sh" || ext === "toml" || ext === "yaml") && trimmed.startsWith("#")) {
      return `<span class="tok-com">${s}</span>`;
    }
    if ((ext === "rs" || ext === "js" || ext === "ts" || ext === "css") && trimmed.startsWith("//")) {
      return `<span class="tok-com">${s}</span>`;
    }

    const placeholders = [];
    const stash = (cls, match) => {
      const id = `\x00TOK${placeholders.length}\x00`;
      placeholders.push(`<span class="${cls}">${match}</span>`);
      return id;
    };

    s = s.replace(/(&quot;.*?&quot;|&#39;.*?&#39;)/g, (m) => stash("tok-str", m));
    s = s.replace(/(^|\s)(@[A-Za-z_][A-Za-z0-9_.]*)/g, (_, p1, p2) => p1 + stash("tok-dec", p2));
    s = s.replace(/\b(\d+(?:\.\d+)?)\b/g, (m) => stash("tok-num", m));
    const kwRegex = /\b(def|async|await|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|yield|lambda|pass|break|continue|True|False|None|fn|let|mut|pub|struct|enum|impl|use|mod|match|crate|const|function|export|default|interface|type)\b/g;
    s = s.replace(kwRegex, (m) => stash("tok-kw", m));
    s = s.replace(/\b([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()/g, (m) => stash("tok-fn", m));

    return s.replace(/\x00TOK(\d+)\x00/g, (_, idx) => placeholders[Number(idx)]);
  }

  async saveActiveFile() {
    const tab = this.activeTab();
    if (!tab) return;
    try {
      const resp = await fetch("/api/editor/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: tab.path, content: tab.content }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Save failed");
      tab.savedContent = tab.content;
      tab.dirty = false;
      tab.diagnostics = data.diagnostics || [];
      tab.symbols = data.symbols || [];
      this.renderTabs();
      this.renderSymbols(tab.symbols);
      this.renderCodeView();
      this.hooks.onToast?.(`Saved ${tab.path}`);
    } catch (err) {
      this.hooks.onToast?.(`Save error: ${err.message}`);
    }
  }

  async formatActiveFile() {
    const tab = this.activeTab();
    if (!tab) return;
    try {
      const resp = await fetch("/api/editor/format", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: tab.path, content: tab.content }),
      });
      const data = await resp.json();
      if (data.text && data.changed) {
        tab.content = data.text;
        tab.dirty = tab.content !== tab.savedContent;
        this.elTextarea.value = tab.content;
        this.renderTabs();
        this.renderCodeView();
        this.hooks.onToast?.(`Formatted with ${data.tool || "formatter"}`);
      } else {
        this.hooks.onToast?.(data.error || "Code already formatted");
      }
    } catch (err) {
      this.hooks.onToast?.(`Format error: ${err.message}`);
    }
  }

  setDiffMode(enabled, customDiff = null) {
    this.diffMode = enabled;
    this.elCodeContainer.classList.toggle("hidden", enabled);
    this.elDiffContainer.classList.toggle("hidden", !enabled);
    if (enabled) {
      const diffObj = customDiff || this.currentDiff || { path: this.activePath || "", hunks: [], added: 0, removed: 0 };
      this.renderDiffHunks(diffObj);
    }
  }

  toggleDiffView() {
    this.setDiffMode(!this.diffMode);
  }

  async previewSampleDiff() {
    const tab = this.activeTab();
    if (!tab) return;
    const lines = tab.content.split("\n");
    const modified = [...lines];
    if (modified.length > 2) {
      modified.splice(1, 0, "# [CMDAI Desktop Review] Verified AST signature & cross-platform safety");
    } else {
      modified.push("# [CMDAI Desktop Review]");
    }
    const resp = await fetch("/api/editor/diff_preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: tab.path,
        old_content: tab.content,
        new_content: modified.join("\n"),
      }),
    });
    const diffObj = await resp.json();
    this.setDiffMode(true, diffObj);
  }

  renderDiffHunks(diffObj) {
    const hunks = diffObj.hunks || [];
    this.elDiffSummary.innerHTML = `
      <strong>${this._escapeHtml(diffObj.path || "No file")}</strong>
      <span style="color:#7ee787;margin-left:10px;">+${diffObj.added || 0}</span>
      <span style="color:#f87171;margin-left:6px;">-${diffObj.removed || 0}</span>
      <span style="color:var(--text-muted);margin-left:8px;">(${hunks.length} hunk(s))</span>
    `;
    this.elDiffHunks.innerHTML = "";
    if (!hunks.length) {
      this.elDiffHunks.innerHTML = `
        <div class="hunk-card" style="padding:18px;text-align:center;color:var(--text-secondary);">
          Brak różnic względem HEAD dla <code>${this._escapeHtml(diffObj.path || "")}</code>.
          Kliknij <strong>Preview Proposed Change</strong> aby zasymulować recenzję zmian Hunk Accept/Reject.
        </div>
      `;
      return;
    }

    for (const h of hunks) {
      const card = document.createElement("div");
      card.className = "hunk-card";
      const rowsHtml = (h.rows || [])
        .map((r) => {
          if (r.type === "context") {
            return `<tr><td class="hunk-ln">${r.old_line ?? ""}</td><td class="hunk-ln">${r.new_line ?? ""}</td><td>  ${this._escapeHtml(r.old_text ?? "")}</td></tr>`;
          }
          if (r.type === "remove") {
            return `<tr class="hunk-row-rem"><td class="hunk-ln">${r.old_line ?? ""}</td><td class="hunk-ln"></td><td>- ${this._escapeHtml(r.old_text ?? "")}</td></tr>`;
          }
          if (r.type === "add") {
            return `<tr class="hunk-row-add"><td class="hunk-ln"></td><td class="hunk-ln">${r.new_line ?? ""}</td><td>+ ${this._escapeHtml(r.new_text ?? "")}</td></tr>`;
          }
          return `
            <tr class="hunk-row-mod-old"><td class="hunk-ln">${r.old_line ?? ""}</td><td class="hunk-ln"></td><td>- ${this._escapeHtml(r.old_text ?? "")}</td></tr>
            <tr class="hunk-row-mod-new"><td class="hunk-ln"></td><td class="hunk-ln">${r.new_line ?? ""}</td><td>+ ${this._escapeHtml(r.new_text ?? "")}</td></tr>
          `;
        })
        .join("");

      card.innerHTML = `
        <div class="hunk-header">
          <span>@@ -${h.old_start},${h.old_count} +${h.new_start},${h.new_count} @@</span>
          <div class="hunk-actions">
            <button class="ed-action-btn primary small btn-accept-hunk">✓ Accept Hunk</button>
            <button class="ed-action-btn small btn-reject-hunk">✕ Reject</button>
          </div>
        </div>
        <table class="hunk-table"><tbody>${rowsHtml}</tbody></table>
      `;
      card.querySelector(".btn-accept-hunk").addEventListener("click", async () => {
        try {
          const resp = await fetch("/api/editor/apply_hunk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              path: diffObj.path,
              old_start: h.old_start,
              old_count: h.old_count,
              new_lines: h.new_lines || [],
            }),
          });
          if (resp.ok) {
            this.hooks.onToast?.(`Applied hunk to ${diffObj.path}`);
            card.style.borderColor = "#3fb950";
            card.querySelector(".hunk-actions").innerHTML = `<span style="color:#7ee787;">✓ Applied</span>`;
            await this.openFile(diffObj.path, h.new_start);
          }
        } catch (err) {
          this.hooks.onToast?.(`Failed to apply hunk: ${err.message}`);
        }
      });
      card.querySelector(".btn-reject-hunk").addEventListener("click", () => {
        card.remove();
        this.hooks.onToast?.("Hunk rejected");
      });
      this.elDiffHunks.appendChild(card);
    }
  }

  async runTerminalCommand(explicitCmd = null) {
    const cmd = (explicitCmd ?? this.elTermIn.value).trim();
    if (!cmd) return;
    if (!explicitCmd) {
      this.termHistory.push(cmd);
      this.termHistIdx = -1;
      this.elTermIn.value = "";
    }
    this.appendTerminalLog(`$ ${cmd}\n`, "cmd");
    try {
      const resp = await fetch("/api/terminal/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd }),
      });
      const data = await resp.json();
      if (data.stdout) this.appendTerminalLog(data.stdout, "out");
      if (data.stderr) this.appendTerminalLog(data.stderr, "err");
      this.appendTerminalLog(`[exit ${data.returncode} in ${data.duration_ms}ms]\n`, "muted");
    } catch (err) {
      this.appendTerminalLog(`Error: ${err.message}\n`, "err");
    }
  }

  appendTerminalLog(text, kind = "out") {
    const span = document.createElement("span");
    if (kind === "cmd") span.style.color = "#60a5fa";
    else if (kind === "err") span.style.color = "#f87171";
    else if (kind === "muted") span.style.color = "#7c8ba1";
    span.textContent = text;
    this.elTermOut.appendChild(span);
    this.elTermOut.scrollTop = this.elTermOut.scrollHeight;
  }

  async scanProblems() {
    this.elProblemsList.innerHTML = `<div style="padding:10px;color:var(--text-secondary);">Scanning project with Tree-Sitter + Ruff...</div>`;
    try {
      const resp = await fetch("/api/editor/problems");
      const data = await resp.json();
      const diags = data.diagnostics || [];
      this.elProblemsCount.textContent = String(diags.length);
      this.elProblemsList.innerHTML = "";
      if (!diags.length) {
        this.elProblemsList.innerHTML = `<div style="padding:10px;color:#7ee787;">✓ Zero syntax/lint problems found across ${data.checked} scanned files.</div>`;
        return;
      }
      for (const d of diags) {
        const row = document.createElement("div");
        row.className = "problem-row";
        row.innerHTML = `
          <span>
            <strong style="color:${d.severity === "error" ? "#f87171" : "#38bdf8"};">[${this._escapeHtml(d.code)}]</strong>
            ${this._escapeHtml(d.message)}
          </span>
          <span style="font-family:var(--font-mono);color:var(--text-muted);">${this._escapeHtml(d.path)}:${d.row}</span>
        `;
        row.addEventListener("click", () => this.openFile(d.path, d.row));
        this.elProblemsList.appendChild(row);
      }
    } catch (err) {
      this.elProblemsList.innerHTML = `<div style="padding:10px;color:#f87171;">Scan failed: ${err.message}</div>`;
    }
  }

  async searchInFiles() {
    const q = this.elSearchInput.value.trim();
    if (!q) return;
    this.elSearchResults.innerHTML = `<div style="padding:8px;color:var(--text-secondary);">Searching with Rust fs_engine...</div>`;
    try {
      const resp = await fetch(`/api/editor/search?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      const hits = data.hits || [];
      this.elSearchResults.innerHTML = "";
      if (!hits.length) {
        this.elSearchResults.innerHTML = `<div style="padding:8px;color:var(--text-muted);">No matches for "${this._escapeHtml(q)}"</div>`;
        return;
      }
      for (const h of hits) {
        const row = document.createElement("div");
        row.className = "search-hit-row";
        row.innerHTML = `
          <span style="font-family:var(--font-mono);color:#e2e8f0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            ${this._escapeHtml(h.preview)}
          </span>
          <span style="font-family:var(--font-mono);color:var(--text-muted);flex-shrink:0;">
            ${this._escapeHtml(h.path)}:${h.line}
          </span>
        `;
        row.addEventListener("click", () => this.openFile(h.path, h.line));
        this.elSearchResults.appendChild(row);
      }
    } catch (err) {
      this.elSearchResults.innerHTML = `<div style="padding:8px;color:#f87171;">Search error: ${err.message}</div>`;
    }
  }

  _escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
}
