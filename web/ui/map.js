/**
 * Autorski Desktopowy Silnik /map (Interactive 2D Mind Map & AST Dependency Graph)
 * Zbudowany bezpośrednio na HTML5 Canvas 2D (60 FPS) z animowanymi cząsteczkami przepływu,
 * obsługą Drag & Drop węzłów, Zoomem pod kursorem i Inspektorem Symboli AST.
 * Dopasowany do matowej estetyki Claude Desktop + Antigravity (#191918).
 */

export class CustomMindMap {
  constructor(hooks) {
    this.hooks = hooks; // { onOpenFileAtLine, onPinContext }
    this.canvas = document.getElementById("map-canvas");
    this.ctx = this.canvas.getContext("2d");

    this.nodes = [];
    this.edges = [];
    this.nodeById = new Map();
    this.positions = new Map();
    this.velocities = new Map();

    this.layoutMode = "layered";
    this.importsOnly = false;
    this.filterText = "";
    this.selectedId = null;
    this.hoverId = null;

    this.camX = 0;
    this.camY = 0;
    this.zoom = 1.0;

    this.draggingNodeId = null;
    this.panning = false;
    this.dragMoved = false;
    this.lastMouse = { x: 0, y: 0 };

    this.animFrame = null;
    this.pulsePhase = 0;
    this.loaded = false;

    this.elStats = document.getElementById("map-stats-label");
    this.elSearch = document.getElementById("map-search-input");
    this.elInspTitle = document.getElementById("insp-node-title");
    this.elInspPath = document.getElementById("insp-node-path");
    this.elInspBody = document.getElementById("insp-body");

    this._bindEvents();
  }

  _bindEvents() {
    window.addEventListener("resize", () => this.resizeCanvas());

    this.elSearch.addEventListener("input", () => {
      this.filterText = this.elSearch.value.trim().toLowerCase();
    });

    document.querySelectorAll(".map-layout-btns .map-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".map-layout-btns .map-btn").forEach((b) => b.classList.toggle("active", b === btn));
        this.layoutMode = btn.dataset.layout;
        this.computeLayout();
      });
    });

    const impBtn = document.getElementById("btn-map-imports-only");
    impBtn.addEventListener("click", () => {
      this.importsOnly = !this.importsOnly;
      impBtn.classList.toggle("active", this.importsOnly);
    });

    document.getElementById("btn-map-zoom-in").addEventListener("click", () => this.setZoom(this.zoom * 1.18));
    document.getElementById("btn-map-zoom-out").addEventListener("click", () => this.setZoom(this.zoom / 1.18));
    document.getElementById("btn-map-fit").addEventListener("click", () => this.fitView());

    document.getElementById("btn-insp-open-editor").addEventListener("click", () => {
      const node = this.nodeById.get(this.selectedId);
      if (node && node.kind === "file") {
        this.hooks.onOpenFileAtLine?.(node.path, 1);
      }
    });

    document.getElementById("btn-insp-pin-context").addEventListener("click", () => {
      const node = this.nodeById.get(this.selectedId);
      if (node && node.kind === "file") {
        this.hooks.onPinContext?.(node.path);
      }
    });

    // Canvas Mouse Events
    this.canvas.addEventListener("mousedown", (e) => {
      const pt = this._mousePoint(e);
      this.lastMouse = pt;
      this.dragMoved = false;
      const hit = this._hitTest(pt.x, pt.y);
      if (hit) {
        this.draggingNodeId = hit.id;
      } else {
        this.panning = true;
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (!this.loaded) return;
      const rect = this.canvas.getBoundingClientRect();
      if (rect.width === 0) return;
      const pt = { x: e.clientX - rect.left, y: e.clientY - rect.top };

      if (this.draggingNodeId) {
        const dx = (pt.x - this.lastMouse.x) / this.zoom;
        const dy = (pt.y - this.lastMouse.y) / this.zoom;
        if (Math.abs(dx) > 0.2 || Math.abs(dy) > 0.2) this.dragMoved = true;
        const pos = this.positions.get(this.draggingNodeId);
        if (pos) {
          pos.x += dx;
          pos.y += dy;
          pos.tx = pos.x;
          pos.ty = pos.y;
        }
        this.lastMouse = pt;
      } else if (this.panning) {
        const dx = pt.x - this.lastMouse.x;
        const dy = pt.y - this.lastMouse.y;
        if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) this.dragMoved = true;
        this.camX += dx;
        this.camY += dy;
        this.lastMouse = pt;
      } else if (e.target === this.canvas) {
        const hit = this._hitTest(pt.x, pt.y);
        this.hoverId = hit ? hit.id : null;
        this.canvas.style.cursor = hit ? "pointer" : "grab";
      }
    });

    window.addEventListener("mouseup", () => {
      if (this.draggingNodeId && !this.dragMoved) {
        this.selectNode(this.draggingNodeId);
      }
      this.draggingNodeId = null;
      this.panning = false;
    });

    this.canvas.addEventListener("dblclick", (e) => {
      const pt = this._mousePoint(e);
      const hit = this._hitTest(pt.x, pt.y);
      if (hit && hit.kind === "file") {
        this.hooks.onOpenFileAtLine?.(hit.path, 1);
      }
    });

    this.canvas.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const pt = this._mousePoint(e);
        const factor = e.deltaY < 0 ? 1.12 : 0.89;
        const nextZoom = Math.max(0.25, Math.min(2.6, this.zoom * factor));
        const worldX = (pt.x - this.camX) / this.zoom;
        const worldY = (pt.y - this.camY) / this.zoom;
        this.zoom = nextZoom;
        this.camX = pt.x - worldX * this.zoom;
        this.camY = pt.y - worldY * this.zoom;
      },
      { passive: false }
    );
  }

  async ensureLoaded() {
    if (!this.loaded) {
      await this.loadGraph();
    }
    this.resizeCanvas();
    this.startLoop();
  }

  async loadGraph() {
    try {
      const resp = await fetch("/api/map/graph?max_files=65");
      const data = await resp.json();
      this.nodes = data.nodes || [];
      this.edges = data.edges || [];
      this.nodeById.clear();
      for (const n of this.nodes) {
        this.nodeById.set(n.id, n);
      }
      const stats = data.stats || {};
      this.elStats.textContent = `${stats.nodes || this.nodes.length} nodes • ${stats.edges || this.edges.length} edges (${stats.imports || 0} imports)`;
      this.computeLayout(true);
      this.loaded = true;

      const preferred =
        this.nodes.find((n) => n.kind === "file" && (n.ast_symbols || []).length > 0) ||
        this.nodes[0];
      if (preferred) {
        this.selectNode(preferred.id, false);
      }
      this.fitView();
    } catch (err) {
      this.elStats.textContent = `Graph load error: ${err.message}`;
    }
  }

  computeLayout(snap = false) {
    if (!this.nodes.length) return;
    const targets = new Map();

    const dirs = this.nodes.filter((n) => n.kind === "dir");
    const files = this.nodes.filter((n) => n.kind === "file");
    const parentOf = new Map();
    for (const e of this.edges) {
      if (e.kind === "contains") parentOf.set(e.target, e.source);
    }

    if (this.layoutMode === "layered") {
      // Clean left-to-right architectural tree with grouped folder lanes and zero overlap
      const byDir = new Map();
      dirs.forEach((d) => byDir.set(d.id, []));
      files.forEach((f) => {
        const pid = parentOf.get(f.id) || "root";
        if (!byDir.has(pid)) byDir.set(pid, []);
        byDir.get(pid).push(f);
      });

      const ROW_GAP = 48;
      const GROUP_GAP = 32;
      const COL_W = 220;
      const orderedGroups = [];
      for (const d of dirs) {
        orderedGroups.push({ id: d.id, files: byDir.get(d.id) || [] });
      }
      if ((byDir.get("root") || []).length) {
        orderedGroups.unshift({ id: "root", files: byDir.get("root") });
      }

      let cursorY = 0;
      const groupCenters = new Map();
      for (const grp of orderedGroups) {
        const rows = Math.max(1, Math.ceil(grp.files.length / 2));
        const groupH = rows * ROW_GAP;
        const startY = cursorY;
        const centerY = startY + (groupH - ROW_GAP) / 2;
        groupCenters.set(grp.id, centerY);

        grp.files.forEach((f, idx) => {
          const col = idx % 2;
          const row = Math.floor(idx / 2);
          targets.set(f.id, {
            x: 240 + col * COL_W,
            y: startY + row * ROW_GAP,
          });
        });
        cursorY += groupH + GROUP_GAP;
      }

      const midY = Math.max(0, (cursorY - GROUP_GAP) / 2);
      targets.set("root", { x: -340, y: midY });
      dirs.forEach((d) => {
        targets.set(d.id, { x: -60, y: groupCenters.get(d.id) ?? midY });
      });
    } else {
      targets.set("root", { x: 0, y: 0 });
      const dirCount = Math.max(1, dirs.length);
      const startAng = dirCount === 2 ? 0 : (dirCount === 3 ? -Math.PI / 6 : -Math.PI / 2);
      dirs.forEach((d, idx) => {
        const ang = (2 * Math.PI * idx) / dirCount + startAng;
        targets.set(d.id, { x: Math.cos(ang) * 240, y: Math.sin(ang) * 170 });
      });

      const byParent = new Map();
      files.forEach((f) => {
        const pid = parentOf.get(f.id) || "root";
        if (!byParent.has(pid)) byParent.set(pid, []);
        byParent.get(pid).push(f);
      });

      for (const [pid, flist] of byParent.entries()) {
        const pPos = targets.get(pid) || { x: 0, y: 0 };
        const baseAng = pid === "root" ? -Math.PI / 2 : Math.atan2(pPos.y, pPos.x);
        const spread = pid === "root" ? Math.PI * 1.4 : Math.min(1.5, 0.32 * flist.length);
        flist.forEach((f, i) => {
          const frac = flist.length === 1 ? 0 : i / (flist.length - 1) - 0.5;
          const ang = baseAng + frac * spread;
          const ring = 220 + (i % 3) * 115;
          targets.set(f.id, {
            x: pPos.x + Math.cos(ang) * ring,
            y: pPos.y + Math.sin(ang) * ring,
          });
        });
      }

      const ids = this.nodes.map((n) => n.id);
      for (let iter = 0; iter < 55; iter++) {
        for (let i = 0; i < ids.length; i++) {
          for (let j = i + 1; j < ids.length; j++) {
            const a = targets.get(ids[i]);
            const b = targets.get(ids[j]);
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const minW = 165;
            const minH = 56;
            if (Math.abs(dx) < minW && Math.abs(dy) < minH) {
              const pushX = (minW - Math.abs(dx)) * 0.28 * (dx >= 0 ? 1 : -1);
              const pushY = (minH - Math.abs(dy)) * 0.35 * (dy >= 0 ? 1 : -1);
              if (ids[i] !== "root") {
                a.x -= pushX;
                a.y -= pushY;
              }
              if (ids[j] !== "root") {
                b.x += pushX;
                b.y += pushY;
              }
            }
          }
        }
      }
    }

    for (const n of this.nodes) {
      const t = targets.get(n.id) || { x: 0, y: 0 };
      const cur = this.positions.get(n.id);
      if (snap || !cur) {
        this.positions.set(n.id, { x: t.x, y: t.y, tx: t.x, ty: t.y });
      } else {
        cur.tx = t.x;
        cur.ty = t.y;
      }
      this.velocities.set(n.id, { vx: 0, vy: 0 });
    }
  }

  fitView() {
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;
    for (const pos of this.positions.values()) {
      minX = Math.min(minX, pos.tx);
      maxX = Math.max(maxX, pos.tx);
      minY = Math.min(minY, pos.ty);
      maxY = Math.max(maxY, pos.ty);
    }
    if (!Number.isFinite(minX)) return;
    const spanW = Math.max(300, maxX - minX + 260);
    const spanH = Math.max(240, maxY - minY + 180);
    this.zoom = Math.max(0.32, Math.min(1.15, Math.min(rect.width / spanW, rect.height / spanH)));
    const midX = (minX + maxX) / 2;
    const midY = (minY + maxY) / 2;
    this.camX = rect.width / 2 - midX * this.zoom;
    this.camY = rect.height / 2 - midY * this.zoom;
  }

  setZoom(val) {
    const rect = this.canvas.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const next = Math.max(0.25, Math.min(2.6, val));
    const wx = (cx - this.camX) / this.zoom;
    const wy = (cy - this.camY) / this.zoom;
    this.zoom = next;
    this.camX = cx - wx * this.zoom;
    this.camY = cy - wy * this.zoom;
  }

  centerOnNode(nodeId) {
    const pos = this.positions.get(nodeId);
    const rect = this.canvas.getBoundingClientRect();
    if (!pos || !rect.width) return;
    this.camX = rect.width / 2 - pos.x * this.zoom;
    this.camY = rect.height / 2 - pos.y * this.zoom;
  }

  selectNode(nodeId, center = false) {
    this.selectedId = nodeId;
    if (center) this.centerOnNode(nodeId);
    const node = this.nodeById.get(nodeId);
    if (!node) return;

    this.elInspTitle.textContent = node.label;
    this.elInspPath.textContent = `${node.kind.toUpperCase()} • ${node.path}${node.line_count ? ` • ${node.line_count} lines` : ""}`;

    const outImps = this.edges.filter((e) => e.source === nodeId && e.kind === "import").map((e) => e.target);
    const inImps = this.edges.filter((e) => e.target === nodeId && e.kind === "import").map((e) => e.source);
    const syms = node.ast_symbols || [];

    let html = "";
    if (outImps.length) {
      html += `<div><div class="insp-section-title" style="color:#60a5fa;">Imports (${outImps.length})</div><div class="insp-list">`;
      for (const id of outImps) {
        const target = this.nodeById.get(id);
        html += `<button class="insp-chip-btn" data-jump-node="${id}"><span>→ ${this._esc(target ? target.path : id)}</span><span>Focus</span></button>`;
      }
      html += `</div></div>`;
    }
    if (inImps.length) {
      html += `<div><div class="insp-section-title" style="color:#a78bfa;">Imported By (${inImps.length})</div><div class="insp-list">`;
      for (const id of inImps) {
        const src = this.nodeById.get(id);
        html += `<button class="insp-chip-btn" data-jump-node="${id}"><span>← ${this._esc(src ? src.path : id)}</span><span>Focus</span></button>`;
      }
      html += `</div></div>`;
    }
    if (syms.length) {
      html += `<div><div class="insp-section-title" style="color:#34d399;">AST Symbols (${syms.length})</div><div class="insp-list">`;
      for (const s of syms) {
        const icon = s.type === "class" ? "◆" : "ƒ";
        html += `<button class="insp-chip-btn" data-open-line="${s.start_line}"><span>${icon} ${this._esc(s.name)}</span><span style="color:#60a5fa;">L${s.start_line}</span></button>`;
      }
      html += `</div></div>`;
    }
    if (!outImps.length && !inImps.length && !syms.length) {
      html = `<div style="color:var(--text-muted);font-size:12px;">Click a file node with Python/JS AST symbols to inspect imports and jump straight to symbol definitions.</div>`;
    }

    this.elInspBody.innerHTML = html;
    this.elInspBody.querySelectorAll("[data-jump-node]").forEach((btn) => {
      btn.addEventListener("click", () => this.selectNode(btn.dataset.jumpNode, true));
    });
    this.elInspBody.querySelectorAll("[data-open-line]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (node.kind === "file") {
          this.hooks.onOpenFileAtLine?.(node.path, parseInt(btn.dataset.openLine, 10));
        }
      });
    });
  }

  resizeCanvas() {
    const rect = this.canvas.parentElement?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(rect.width * dpr);
    this.canvas.height = Math.floor(rect.height * dpr);
  }

  startLoop() {
    if (this.animFrame) return;
    const tick = () => {
      this.stepSimulation();
      this.draw();
      this.animFrame = requestAnimationFrame(tick);
    };
    this.animFrame = requestAnimationFrame(tick);
  }

  stepSimulation() {
    this.pulsePhase = (this.pulsePhase + 0.012) % 1;
    if (this.layoutMode === "force") {
      const ids = this.nodes.map((n) => n.id);
      for (let i = 0; i < ids.length; i++) {
        const idA = ids[i];
        const posA = this.positions.get(idA);
        const velA = this.velocities.get(idA);
        if (!posA || !velA || idA === this.draggingNodeId) continue;

        for (let j = i + 1; j < ids.length; j++) {
          const idB = ids[j];
          const posB = this.positions.get(idB);
          const velB = this.velocities.get(idB);
          if (!posB || !velB) continue;
          const dx = posB.x - posA.x;
          const dy = posB.y - posA.y;
          const distSq = Math.max(600, dx * dx + dy * dy);
          if (distSq < 68000) {
            const force = 1900 / distSq;
            const d = Math.sqrt(distSq);
            const fx = (dx / d) * force;
            const fy = (dy / d) * force;
            velA.vx -= fx;
            velA.vy -= fy;
            velB.vx += fx;
            velB.vy += fy;
          }
        }
      }

      for (const e of this.edges) {
        const p1 = this.positions.get(e.source);
        const p2 = this.positions.get(e.target);
        const v1 = this.velocities.get(e.source);
        const v2 = this.velocities.get(e.target);
        if (!p1 || !p2 || !v1 || !v2) continue;
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const dist = Math.hypot(dx, dy) || 1;
        const ideal = e.kind === "contains" ? 175 : 230;
        const f = (dist - ideal) * 0.008;
        v1.vx += (dx / dist) * f;
        v1.vy += (dy / dist) * f;
        v2.vx -= (dx / dist) * f;
        v2.vy -= (dy / dist) * f;
      }

      for (const id of ids) {
        if (id === "root" || id === this.draggingNodeId) continue;
        const p = this.positions.get(id);
        const v = this.velocities.get(id);
        v.vx *= 0.84;
        v.vy *= 0.84;
        p.x += v.vx;
        p.y += v.vy;
        p.tx = p.x;
        p.ty = p.y;
      }
    } else {
      for (const [id, p] of this.positions.entries()) {
        if (id === this.draggingNodeId) continue;
        p.x += (p.tx - p.x) * 0.14;
        p.y += (p.ty - p.y) * 0.14;
      }
    }
  }

  draw() {
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.width / dpr;
    const h = this.canvas.height / dpr;
    if (w <= 0 || h <= 0) return;

    const isDark = document.documentElement.getAttribute("data-theme") === "dark";

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Subtle spatial dot grid matching active theme
    const gridStep = 36 * this.zoom;
    if (gridStep > 10) {
      ctx.fillStyle = isDark ? "rgba(240, 239, 234, 0.05)" : "rgba(15, 23, 42, 0.08)";
      const offX = ((this.camX % gridStep) + gridStep) % gridStep;
      const offY = ((this.camY % gridStep) + gridStep) % gridStep;
      for (let gx = offX; gx < w; gx += gridStep) {
        for (let gy = offY; gy < h; gy += gridStep) {
          ctx.fillRect(gx, gy, 1.2, 1.2);
        }
      }
    }

    ctx.translate(this.camX, this.camY);
    ctx.scale(this.zoom, this.zoom);

    const activeEdges = [];
    for (const e of this.edges) {
      if (this.importsOnly && e.kind !== "import") continue;
      if (e.source === this.selectedId || e.target === this.selectedId) {
        activeEdges.push(e);
        continue;
      }
      this._drawEdge(ctx, e, false, isDark);
    }
    for (const e of activeEdges) {
      this._drawEdge(ctx, e, true, isDark);
    }

    for (const n of this.nodes) {
      this._drawNodeCard(ctx, n, isDark);
    }

    ctx.restore();
  }

  _drawEdge(ctx, e, isActive, isDark = false) {
    const p1 = this.positions.get(e.source);
    const p2 = this.positions.get(e.target);
    if (!p1 || !p2) return;

    const isImport = e.kind === "import";
    let color = isImport
      ? (isDark ? "rgba(59, 130, 246, 0.36)" : "rgba(37, 99, 235, 0.35)")
      : (isDark ? "rgba(148, 163, 184, 0.16)" : "rgba(148, 163, 184, 0.38)");
    if (isActive) {
      if (isImport) {
        color = e.source === this.selectedId ? "#2563eb" : "#7c3aed";
      } else {
        color = "#3b82f6";
      }
    }

    const sNode = this.nodeById.get(e.source);
    const tNode = this.nodeById.get(e.target);
    const sHalfW = sNode ? this._nodeSize(sNode).w / 2 : 0;
    const tHalfW = tNode ? this._nodeSize(tNode).w / 2 : 0;

    ctx.beginPath();
    if (this.layoutMode === "layered" && p2.x > p1.x + 20) {
      const x1 = p1.x + sHalfW;
      const y1 = p1.y;
      const x2 = p2.x - tHalfW;
      const y2 = p2.y;
      const midX = (x1 + x2) / 2;
      ctx.moveTo(x1, y1);
      ctx.bezierCurveTo(midX, y1, midX, y2, x2, y2);
    } else {
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const cx1 = p1.x + dx * 0.45 - dy * 0.1;
      const cy1 = p1.y + dy * 0.45 + dx * 0.1;
      ctx.moveTo(p1.x, p1.y);
      ctx.quadraticCurveTo(cx1, cy1, p2.x, p2.y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = isActive ? 2.0 : isImport ? 1.25 : 1.0;
    ctx.stroke();
  }

  _nodeSize(n) {
    const labelLen = Math.min(20, (n.label || "").length);
    const w = n.kind === "root" ? 158 : Math.max(114, 52 + labelLen * 6.8);
    const h = n.kind === "root" ? 42 : 34;
    return { w, h };
  }

  _drawNodeCard(ctx, n, isDark = false) {
    const pos = this.positions.get(n.id);
    if (!pos) return;
    const { w, h } = this._nodeSize(n);
    const x = pos.x - w / 2;
    const y = pos.y - h / 2;

    const isSel = n.id === this.selectedId;
    const isHov = n.id === this.hoverId;
    const matchesSearch = !this.filterText || n.label.toLowerCase().includes(this.filterText) || n.path.toLowerCase().includes(this.filterText);

    const accent =
      isSel ? "#16a34a" :
      n.kind === "root" ? (isDark ? "#e2e8f0" : "#18181b") :
      n.kind === "dir" ? "#2563eb" : "#0284c7";

    ctx.save();
    ctx.globalAlpha = matchesSearch ? 1.0 : 0.22;

    if (isSel || isHov) {
      ctx.shadowColor = isDark ? accent : "rgba(37, 99, 235, 0.22)";
      ctx.shadowBlur = isSel ? 14 : 8;
    }

    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 9);
    ctx.fillStyle = isDark
      ? (isSel ? "#172b28" : "#18202c")
      : (isSel ? "#f0fdf4" : "#ffffff");
    ctx.fill();
    ctx.lineWidth = isSel ? 1.8 : 1.0;
    ctx.strokeStyle = isSel
      ? "#16a34a"
      : isHov
      ? accent
      : (isDark ? "#293548" : "#d0d7de");
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.beginPath();
    ctx.arc(x + 14, pos.y, 4.0, 0, Math.PI * 2);
    ctx.fillStyle = accent;
    ctx.fill();

    ctx.font = n.kind === "root" ? "600 12.5px Inter, Segoe UI, sans-serif" : "600 11.5px JetBrains Mono, Consolas, monospace";
    ctx.fillStyle = isDark ? "#f1f5f9" : "#111827";
    ctx.textBaseline = "middle";
    const textLabel = n.label.length > 18 ? n.label.slice(0, 17) + "…" : n.label;
    ctx.fillText(textLabel, x + 25, pos.y);

    const symCount = (n.ast_symbols || []).length;
    if (symCount > 0) {
      const badge = `${symCount}`;
      ctx.font = "700 9.5px JetBrains Mono, monospace";
      const bw = ctx.measureText(badge).width + 8;
      ctx.fillStyle = isDark ? "rgba(59, 130, 246, 0.22)" : "#eff6ff";
      ctx.beginPath();
      ctx.roundRect(x + w - bw - 6, pos.y - 8, bw, 16, 6);
      ctx.fill();
      ctx.fillStyle = isDark ? "#93c5fd" : "#1d4ed8";
      ctx.fillText(badge, x + w - bw - 2, pos.y);
    }

    ctx.restore();
  }

  _mousePoint(e) {
    const rect = this.canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  _hitTest(sx, sy) {
    const wx = (sx - this.camX) / this.zoom;
    const wy = (sy - this.camY) / this.zoom;
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      const pos = this.positions.get(n.id);
      if (!pos) continue;
      const { w, h } = this._nodeSize(n);
      if (wx >= pos.x - w / 2 && wx <= pos.x + w / 2 && wy >= pos.y - h / 2 && wy <= pos.y + h / 2) {
        return n;
      }
    }
    return null;
  }

  _esc(str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}
