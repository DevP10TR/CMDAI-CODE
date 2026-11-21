import html
import json
import os
import re
import time
from typing import Any, Dict, List, Optional


HTML_EXPORTER_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CMDAI CODE · {session_title}</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2318181b'/%3E%3Cpath d='M7 9h7v3H10v8h4v3H7V9zm11 0h7v3h-4v8h4v3h-7V9z' fill='%23ffffff'/%3E%3C/svg%3E" />
    <style>
        :root, [data-theme="light"] {{
            --bg-app: #f4f5f7;
            --bg-topbar: #f4f5f7;
            --bg-stage: #ffffff;
            --bg-card: #ffffff;
            --bg-subtle: #f1f3f6;
            --bg-hover: rgba(15, 23, 42, 0.05);
            --border-hairline: #e4e7ec;
            --border-strong: #cfd5e1;
            --text-primary: #111827;
            --text-secondary: #4b5563;
            --text-muted: #6b7280;
            --accent-blue: #2563eb;
            --accent-blue-soft: #eff6ff;
            --accent-green: #15803d;
            --accent-red: #dc2626;
            --brand-fg: #18181b;
            --brand-fg-soft: #71717a;
            --code-bg: #f6f8fa;
            --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
            --font-sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            --font-mono: "JetBrains Mono", "Cascadia Mono", Consolas, monospace;
        }}
        [data-theme="dark"] {{
            --bg-app: #09090b;
            --bg-topbar: #0e0e12;
            --bg-stage: #111115;
            --bg-card: #17171c;
            --bg-subtle: #1f1f27;
            --bg-hover: rgba(255, 255, 255, 0.06);
            --border-hairline: #23232b;
            --border-strong: #32323e;
            --text-primary: #f4f4f5;
            --text-secondary: #a1a1aa;
            --text-muted: #71717a;
            --accent-blue: #3b82f6;
            --accent-blue-soft: rgba(59, 130, 246, 0.14);
            --accent-green: #34d399;
            --accent-red: #f87171;
            --brand-fg: #f4f4f5;
            --brand-fg-soft: #a1a1aa;
            --code-bg: #0c0c0f;
            --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.35);
            color-scheme: dark;
        }}
        ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(15, 23, 42, 0.14); border-radius: 99px; }}
        [data-theme="dark"] ::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.11); }}
        [data-theme="dark"] ::-webkit-scrollbar-thumb:hover {{ background: rgba(255, 255, 255, 0.22); }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{
            height: 100%;
            background: var(--bg-app);
            color: var(--text-primary);
            font-family: var(--font-sans);
            font-size: 14px;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }}
        body {{
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 8px;
            gap: 0;
        }}
        .hidden {{ display: none !important; }}

        /* Main Shell Card (Matching CMDAI CODE Web .main-canvas-card) */
        .app-shell {{
            flex: 1;
            min-height: 0;
            display: flex;
            flex-direction: column;
            background: var(--bg-stage);
            border: 1px solid var(--border-hairline);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow-xs);
        }}

        /* Top Bar (Matching CMDAI CODE Web .stage-topbar) */
        .share-topbar {{
            height: 44px;
            padding: 0 14px;
            background: var(--bg-topbar);
            border-bottom: 1px solid var(--border-hairline);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-shrink: 0;
        }}
        .top-left {{
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 0;
        }}
        .cc-vector-badge {{
            width: 118px;
            height: 20px;
            display: inline-flex;
            align-items: center;
            flex-shrink: 0;
        }}
        .cc-vector-badge svg {{
            width: 100%;
            height: 100%;
            display: block;
            shape-rendering: geometricPrecision;
        }}
        .top-divider {{
            width: 1px;
            height: 16px;
            background: var(--border-strong);
            flex-shrink: 0;
        }}
        .session-tab-pill {{
            height: 28px;
            padding: 0 11px;
            border-radius: 7px;
            background: var(--bg-card);
            border: 1px solid var(--border-hairline);
            box-shadow: var(--shadow-xs);
            display: inline-flex;
            align-items: center;
            gap: 7px;
            min-width: 0;
            max-width: 340px;
        }}
        .session-tab-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--accent-blue);
            flex-shrink: 0;
        }}
        .session-pill {{
            font-size: 12.3px;
            font-weight: 500;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .top-right {{
            display: flex;
            align-items: center;
            gap: 7px;
            flex-shrink: 0;
        }}
        .meta-pill {{
            font-size: 11.5px;
            font-weight: 500;
            padding: 3px 9px;
            border-radius: 999px;
            background: var(--bg-card);
            border: 1px solid var(--border-hairline);
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }}
        .top-btn {{
            height: 28px;
            padding: 0 10px;
            border-radius: 7px;
            border: 1px solid var(--border-hairline);
            background: var(--bg-card);
            color: var(--text-primary);
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 5px;
            box-shadow: var(--shadow-xs);
            transition: border-color 0.12s ease, background 0.12s ease;
        }}
        .top-btn:hover {{ border-color: var(--border-strong); background: var(--bg-hover); }}
        .top-btn.active {{
            border-color: var(--accent-blue);
            background: var(--accent-blue-soft);
            color: var(--accent-blue);
        }}

        /* Chat Layout with Left Turn Timeline Dots */
        .chat-layout {{
            flex: 1;
            min-height: 0;
            display: flex;
            position: relative;
            background: var(--bg-stage);
        }}
        .timeline-rail {{
            width: 44px;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 16px 0;
            user-select: none;
        }}
        .tl-arrow {{
            width: 24px;
            height: 24px;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}
        .tl-arrow:hover {{ background: var(--bg-hover); color: var(--text-primary); }}
        .timeline-dots {{
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            max-height: 62vh;
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-width: none;
            padding: 8px 0;
        }}
        .timeline-dots::-webkit-scrollbar {{ display: none; }}
        .tl-dot {{
            width: 8px;
            height: 8px;
            flex-shrink: 0;
            border-radius: 50%;
            border: none;
            background: var(--border-strong);
            cursor: pointer;
            transition: transform 0.14s ease, background 0.14s ease;
            position: relative;
        }}
        .tl-dot:hover {{ transform: scale(1.35); background: var(--text-secondary); }}
        .tl-dot.active {{
            background: var(--accent-blue);
            transform: scale(1.35);
        }}

        .chat-scroll {{
            flex: 1;
            min-width: 0;
            overflow-y: auto;
            padding: 28px 28px 56px 10px;
            scroll-behavior: smooth;
        }}
        .stage {{
            width: 100%;
            max-width: 780px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}

        /* Messages (Exact CMDAI CODE Web Style: user bubble right, assistant plain text left) */
        .turn-anchor {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .msg-user-wrap {{
            display: flex;
            justify-content: flex-end;
        }}
        .msg-user-bubble {{
            max-width: 82%;
            background: var(--bg-subtle);
            border: 1px solid var(--border-hairline);
            border-radius: 14px;
            padding: 10px 15px;
            font-size: 13.8px;
            color: var(--text-primary);
            word-break: break-word;
        }}
        .msg-assistant-wrap {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .assistant-head {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-muted);
        }}
        .assistant-model {{
            font-weight: 600;
            color: var(--text-secondary);
        }}
        .assistant-body {{
            font-size: 14px;
            line-height: 1.68;
            color: var(--text-primary);
            word-break: break-word;
        }}
        .assistant-body p {{ margin: 0 0 10px 0; }}
        .assistant-body p:last-child {{ margin-bottom: 0; }}
        .assistant-body h1, .assistant-body h2, .assistant-body h3, .assistant-body h4 {{
            font-weight: 650;
            color: var(--text-primary);
            margin: 14px 0 6px 0;
            line-height: 1.35;
        }}
        .assistant-body h1 {{ font-size: 17px; }}
        .assistant-body h2 {{ font-size: 15.5px; }}
        .assistant-body h3 {{ font-size: 14.5px; }}
        .assistant-body h4 {{ font-size: 13.8px; }}
        .assistant-body ul, .assistant-body ol {{
            margin: 6px 0 10px 20px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .assistant-body blockquote {{
            border-left: 3px solid var(--border-strong);
            padding: 4px 12px;
            margin: 8px 0;
            color: var(--text-secondary);
            background: var(--bg-subtle);
            border-radius: 0 6px 6px 0;
        }}
        .assistant-body hr {{
            border: none;
            border-top: 1px solid var(--border-hairline);
            margin: 12px 0;
        }}
        .assistant-body a {{
            color: var(--accent-blue);
            text-decoration: none;
        }}
        .assistant-body a:hover {{ text-decoration: underline; }}
        .assistant-body table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 13px;
        }}
        .assistant-body th, .assistant-body td {{
            border: 1px solid var(--border-hairline);
            padding: 6px 10px;
            text-align: left;
        }}
        .assistant-body th {{
            background: var(--bg-subtle);
            font-weight: 600;
        }}
        .assistant-body code:not(pre code), .msg-user-bubble code:not(pre code) {{
            font-family: var(--font-mono);
            font-size: 12.2px;
            background: var(--bg-subtle);
            padding: 1px 5px;
            border-radius: 5px;
            border: 1px solid var(--border-hairline);
        }}
        .code-wrap {{
            margin: 10px 0;
            border-radius: 10px;
            border: 1px solid var(--border-hairline);
            background: var(--code-bg);
            overflow: hidden;
        }}
        .code-head {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 12px;
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border-hairline);
        }}
        .code-copy {{
            background: transparent;
            border: 1px solid var(--border-hairline);
            color: var(--text-secondary);
            border-radius: 6px;
            padding: 2px 7px;
            font-size: 11px;
            cursor: pointer;
        }}
        .code-copy:hover {{ border-color: var(--border-strong); color: var(--text-primary); }}
        .code-wrap pre {{
            padding: 12px 14px;
            overflow-x: auto;
            font-family: var(--font-mono);
            font-size: 12.2px;
            line-height: 1.5;
        }}

        /* Compact Tool & Thinking Pills (Matching CMDAI CODE Web .cli-tool-block) */
        details.think-block, details.tool-block {{
            border: 1px solid var(--border-hairline);
            border-radius: 10px;
            background: var(--bg-card);
            overflow: hidden;
            box-shadow: var(--shadow-xs);
        }}
        details.think-block summary, details.tool-block summary {{
            cursor: pointer;
            padding: 8px 12px;
            font-size: 12.8px;
            color: var(--text-secondary);
            user-select: none;
            list-style: none;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        details.think-block summary:hover, details.tool-block summary:hover {{
            background: var(--bg-hover);
        }}
        details.think-block summary::-webkit-details-marker,
        details.tool-block summary::-webkit-details-marker {{ display: none; }}
        .tool-ico {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: var(--accent-blue);
            flex-shrink: 0;
        }}
        .tool-ico.write {{ color: var(--accent-red); }}
        .tool-name {{
            font-weight: 600;
            color: var(--text-primary);
            flex-shrink: 0;
        }}
        .tool-arg {{
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-muted);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
            min-width: 0;
        }}
        .tool-chev {{
            color: var(--text-muted);
            font-size: 11px;
            transition: transform 0.14s ease;
            flex-shrink: 0;
        }}
        details[open] > summary .tool-chev {{ transform: rotate(90deg); }}
        .think-content, .tool-content {{
            padding: 10px 13px;
            border-top: 1px solid var(--border-hairline);
            background: var(--code-bg);
            font-family: var(--font-mono);
            font-size: 12px;
            white-space: pre-wrap;
            overflow-x: auto;
            max-height: 420px;
            color: var(--text-secondary);
        }}
        .diff-add {{ color: var(--accent-green); }}
        .diff-del {{ color: var(--accent-red); }}

        /* Raw Markdown View (when Download clicked) */
        .raw-md-wrap {{
            flex: 1;
            min-height: 0;
            overflow-y: auto;
            padding: 20px 24px 40px;
            background: var(--bg-stage);
        }}
        .raw-md-card {{
            max-width: 860px;
            margin: 0 auto;
            background: var(--bg-card);
            border: 1px solid var(--border-hairline);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow-xs);
        }}
        .raw-md-head {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-hairline);
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .raw-md-pre {{
            padding: 16px 18px;
            font-family: var(--font-mono);
            font-size: 12.5px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-word;
            color: var(--text-primary);
            background: var(--code-bg);
        }}

        @media (max-width: 720px) {{
            body {{ padding: 0; }}
            .app-shell {{ border-radius: 0; border: none; }}
            .meta-pill.hide-sm, .top-divider.hide-sm, .session-tab-pill.hide-sm {{ display: none; }}
            .timeline-rail {{ width: 32px; }}
            .chat-scroll {{ padding: 18px 14px 42px 4px; }}
            .msg-user-bubble {{ max-width: 94%; }}
        }}
    </style>
</head>
<body>
    <div class="app-shell">
        <header class="share-topbar">
            <div class="top-left">
                <span id="share-brand-logo" class="cc-vector-badge" aria-label="CMDAI CODE"></span>
                <span class="top-divider hide-sm"></span>
                <div class="session-tab-pill hide-sm" title="{session_title}">
                    <span class="session-tab-dot"></span>
                    <span class="session-pill">{session_title}</span>
                </div>
            </div>
            <div class="top-right">
                <span class="meta-pill hide-sm">{model_id}</span>
                <button id="btn-raw-md" class="top-btn" type="button" title="View / Download Raw Markdown">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span id="btn-raw-md-lbl">Download</span>
                </button>
                <button id="theme-toggle" class="top-btn" type="button">Dark</button>
            </div>
        </header>

        <!-- Chat View (Read-only, with Left Turn Timeline Dots) -->
        <div id="chat-view" class="chat-layout">
            <nav class="timeline-rail" aria-label="Turn Timeline">
                <button id="tl-up" class="tl-arrow" type="button" title="Previous message">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M6 15l6-6 6 6"/></svg>
                </button>
                <div id="timeline-dots" class="timeline-dots">{timeline_dots}</div>
                <button id="tl-down" class="tl-arrow" type="button" title="Next message">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
                </button>
            </nav>

            <main id="chat-scroll" class="chat-scroll">
                <div class="stage">
                    {timeline_cards}
                </div>
            </main>
        </div>

        <!-- Raw Plain Markdown View (toggled via top-right Download button) -->
        <div id="raw-md-view" class="raw-md-wrap hidden">
            <div class="raw-md-card">
                <div class="raw-md-head">
                    <span>{session_id}.md · Raw Markdown</span>
                    <div style="display:flex;gap:6px;">
                        <button id="btn-copy-md" class="top-btn" type="button">Copy MD</button>
                        <button id="btn-save-md" class="top-btn" type="button">Save .md</button>
                    </div>
                </div>
                <pre id="raw-md-content" class="raw-md-pre">{raw_markdown}</pre>
            </div>
        </div>
    </div>

    <script>
        (function() {{
            // Exact CMDAI CODE vector block logo from web/ui/app.js
            const NS_SVG = "http://www.w3.org/2000/svg";
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
            function buildBlockWordPaths(lines, colOffset, cellW, cellH) {{
                let d = "";
                const sw = Math.max(1.5, cellW * 0.15);
                for (let r = 0; r < lines.length; r++) {{
                    const line = lines[r];
                    for (let c = 0; c < line.length; c++) {{
                        const ch = line[c];
                        if (ch === " ") continue;
                        const x = (colOffset + c) * cellW;
                        const y = r * cellH;
                        const xA = x + cellW * 0.28;
                        const xB = x + cellW * 0.64;
                        const yA = y + cellH * 0.30;
                        const yB = y + cellH * 0.64;
                        if (ch === "█") {{
                            d += `M${{(x - 0.25).toFixed(2)}},${{(y - 0.3).toFixed(2)}}h${{(cellW + 0.5).toFixed(2)}}v${{(cellH + 0.6).toFixed(2)}}h-${{(cellW + 0.5).toFixed(2)}}z`;
                        }} else if (ch === "═") {{
                            d += `M${{(x - 0.2).toFixed(2)}},${{yA.toFixed(2)}}h${{(cellW + 0.4).toFixed(2)}}v${{sw.toFixed(2)}}h-${{(cellW + 0.4).toFixed(2)}}z`;
                            d += `M${{(x - 0.2).toFixed(2)}},${{yB.toFixed(2)}}h${{(cellW + 0.4).toFixed(2)}}v${{sw.toFixed(2)}}h-${{(cellW + 0.4).toFixed(2)}}z`;
                        }} else if (ch === "║") {{
                            d += `M${{xA.toFixed(2)}},${{(y - 0.2).toFixed(2)}}h${{sw.toFixed(2)}}v${{(cellH + 0.4).toFixed(2)}}h-${{sw.toFixed(2)}}z`;
                            d += `M${{xB.toFixed(2)}},${{(y - 0.2).toFixed(2)}}h${{sw.toFixed(2)}}v${{(cellH + 0.4).toFixed(2)}}h-${{sw.toFixed(2)}}z`;
                        }} else if (ch === "╔") {{
                            d += `M${{xA.toFixed(2)}},${{yA.toFixed(2)}}H${{(x + cellW + 0.2).toFixed(2)}}v${{sw.toFixed(2)}}H${{(xA + sw).toFixed(2)}}V${{(y + cellH + 0.2).toFixed(2)}}H${{xA.toFixed(2)}}z`;
                            d += `M${{xB.toFixed(2)}},${{yB.toFixed(2)}}H${{(x + cellW + 0.2).toFixed(2)}}v${{sw.toFixed(2)}}H${{(xB + sw).toFixed(2)}}V${{(y + cellH + 0.2).toFixed(2)}}H${{xB.toFixed(2)}}z`;
                        }} else if (ch === "╗") {{
                            d += `M${{(x - 0.2).toFixed(2)}},${{yA.toFixed(2)}}H${{(xB + sw).toFixed(2)}}V${{(y + cellH + 0.2).toFixed(2)}}h-${{sw.toFixed(2)}}V${{(yA + sw).toFixed(2)}}H${{(x - 0.2).toFixed(2)}}z`;
                            d += `M${{(x - 0.2).toFixed(2)}},${{yB.toFixed(2)}}H${{(xA + sw).toFixed(2)}}V${{(y + cellH + 0.2).toFixed(2)}}h-${{sw.toFixed(2)}}V${{(yB + sw).toFixed(2)}}H${{(x - 0.2).toFixed(2)}}z`;
                        }} else if (ch === "╚") {{
                            d += `M${{xA.toFixed(2)}},${{(y - 0.2).toFixed(2)}}h${{sw.toFixed(2)}}V${{yB.toFixed(2)}}H${{(x + cellW + 0.2).toFixed(2)}}v${{sw.toFixed(2)}}H${{xA.toFixed(2)}}z`;
                            d += `M${{xB.toFixed(2)}},${{(y - 0.2).toFixed(2)}}h${{sw.toFixed(2)}}V${{yA.toFixed(2)}}H${{(x + cellW + 0.2).toFixed(2)}}v${{sw.toFixed(2)}}H${{xB.toFixed(2)}}z`;
                        }} else if (ch === "╝") {{
                            d += `M${{xB.toFixed(2)}},${{(y - 0.2).toFixed(2)}}h${{sw.toFixed(2)}}V${{(yB + sw).toFixed(2)}}H${{(x - 0.2).toFixed(2)}}v-${{sw.toFixed(2)}}H${{xB.toFixed(2)}}z`;
                            d += `M${{xA.toFixed(2)}},${{(y - 0.2).toFixed(2)}}h${{sw.toFixed(2)}}V${{(yA + sw).toFixed(2)}}H${{(x - 0.2).toFixed(2)}}v-${{sw.toFixed(2)}}H${{xA.toFixed(2)}}z`;
                        }}
                    }}
                }}
                return d;
            }}
            function renderBrandLogo(host) {{
                if (!host) return;
                const cw = 10, ch = 23, gap = 3;
                const w = (CMDAI_PARTS[0].length + gap + CODE_PARTS[0].length) * cw;
                const h = CMDAI_PARTS.length * ch;
                const svg = document.createElementNS(NS_SVG, "svg");
                svg.setAttribute("viewBox", `0 0 ${{w}} ${{h}}`);
                const gL = document.createElementNS(NS_SVG, "g");
                gL.setAttribute("class", "word-cmdai");
                const pL = document.createElementNS(NS_SVG, "path");
                pL.setAttribute("d", buildBlockWordPaths(CMDAI_PARTS, 0, cw, ch));
                gL.appendChild(pL);
                const gR = document.createElementNS(NS_SVG, "g");
                gR.setAttribute("class", "word-code");
                const pR = document.createElementNS(NS_SVG, "path");
                pR.setAttribute("d", buildBlockWordPaths(CODE_PARTS, CMDAI_PARTS[0].length + gap, cw, ch));
                gR.appendChild(pR);
                svg.appendChild(gL);
                svg.appendChild(gR);
                host.innerHTML = "";
                host.appendChild(svg);
            }}
            renderBrandLogo(document.getElementById("share-brand-logo"));

            const themeBtn = document.getElementById("theme-toggle");
            const applyTheme = (t) => {{
                document.documentElement.setAttribute("data-theme", t);
                if (themeBtn) themeBtn.textContent = t === "dark" ? "Light" : "Dark";
                const fg = t === "dark" ? "#f8fafc" : "#18181b";
                const fgSoft = t === "dark" ? "#94a3b8" : "#71717a";
                const wL = document.querySelector("#share-brand-logo .word-cmdai");
                const wR = document.querySelector("#share-brand-logo .word-code");
                if (wL) wL.setAttribute("fill", fg);
                if (wR) wR.setAttribute("fill", fgSoft);
            }};
            applyTheme(localStorage.getItem("cmdai_share_theme") || "light");
            themeBtn?.addEventListener("click", () => {{
                const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
                localStorage.setItem("cmdai_share_theme", next);
                applyTheme(next);
            }});

            // Toggle Raw Markdown view from top-right Download button
            const rawBtn = document.getElementById("btn-raw-md");
            const rawLbl = document.getElementById("btn-raw-md-lbl");
            const chatView = document.getElementById("chat-view");
            const rawView = document.getElementById("raw-md-view");
            let showingRaw = false;
            rawBtn?.addEventListener("click", () => {{
                showingRaw = !showingRaw;
                chatView?.classList.toggle("hidden", showingRaw);
                rawView?.classList.toggle("hidden", !showingRaw);
                rawBtn.classList.toggle("active", showingRaw);
                if (rawLbl) rawLbl.textContent = showingRaw ? "Back to Chat" : "Download";
            }});

            // Copy & Save .md inside Raw Markdown view
            const mdText = document.getElementById("raw-md-content")?.textContent || "";
            document.getElementById("btn-copy-md")?.addEventListener("click", (e) => {{
                if (navigator.clipboard) {{
                    navigator.clipboard.writeText(mdText);
                    e.currentTarget.textContent = "Copied";
                    setTimeout(() => (e.currentTarget.textContent = "Copy MD"), 1200);
                }}
            }});
            document.getElementById("btn-save-md")?.addEventListener("click", () => {{
                const blob = new Blob([mdText], {{ type: "text/markdown;charset=utf-8" }});
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "{session_filename}.md";
                a.click();
                URL.revokeObjectURL(a.href);
            }});

            // Code block copy buttons
            document.querySelectorAll(".code-copy").forEach((b) => {{
                b.addEventListener("click", () => {{
                    const code = b.closest(".code-wrap")?.querySelector("pre code")?.textContent || "";
                    if (navigator.clipboard) {{
                        navigator.clipboard.writeText(code);
                        b.textContent = "Copied";
                        setTimeout(() => (b.textContent = "Copy"), 1100);
                    }}
                }});
            }});

            // Left Turn Timeline Dots navigation
            const dots = Array.from(document.querySelectorAll(".tl-dot"));
            const turns = Array.from(document.querySelectorAll(".turn-anchor"));
            let activeIdx = 0;
            const setActiveDot = (idx) => {{
                if (!dots.length) return;
                activeIdx = Math.max(0, Math.min(dots.length - 1, idx));
                dots.forEach((d, i) => d.classList.toggle("active", i === activeIdx));
            }};
            const jumpToTurn = (idx) => {{
                if (!turns.length) return;
                setActiveDot(idx);
                turns[activeIdx]?.scrollIntoView({{ behavior: "smooth", block: "start" }});
            }};
            dots.forEach((dot, idx) => dot.addEventListener("click", () => jumpToTurn(idx)));
            document.getElementById("tl-up")?.addEventListener("click", () => jumpToTurn(activeIdx - 1));
            document.getElementById("tl-down")?.addEventListener("click", () => jumpToTurn(activeIdx + 1));

            const scroller = document.getElementById("chat-scroll");
            scroller?.addEventListener("scroll", () => {{
                const top = scroller.getBoundingClientRect().top;
                let best = 0;
                turns.forEach((t, i) => {{
                    if (t.getBoundingClientRect().top - top <= 120) best = i;
                }});
                setActiveDot(best);
            }});
            setActiveDot(0);
        }})();
    </script>
</body>
</html>
"""


_SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "sk-[REDACTED]"),
    (re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b"), "sk-or-v1-[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"), "AIza[REDACTED]"),
    (re.compile(r"\bhf_[A-Za-z0-9]{16,}\b"), "hf_[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "gh_[REDACTED]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._-]{16,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:API_KEY|SECRET_KEY|ACCESS_TOKEN|PASSWORD)\s*[=:]\s*['\"]?)([^\s'\"`]{8,})"), r"\1[REDACTED]"),
]

_TOOL_RESPONSE_FINDALL_RE = re.compile(
    r"<tool_(?:response|result)\b[^>]*name=[\"']?([^\"'\s>]+)[\"']?[^>]*>([\s\S]*?)</tool_(?:response|result)>",
    re.IGNORECASE,
)

# Tight, backreferenced tool-call tag stripping so prose/HTML after a tool call is NEVER swallowed
_STRIP_TOOL_TAGS_RE = re.compile(
    r"(?:<\|tool_call>call:\w+[\s\S]*?<tool_call\|>|"
    r"<\|tool_call>call:\w+[\s\S]*?</\|tool_call>|"
    r"<tool:(\w+)\b[^>]*/>|"
    r"<tool:(\w+)\b[^>]*>[\s\S]*?</(?:tool:)?\2>|"
    r"<tool_call\b[^>]*>[\s\S]*?</tool_call>)",
    re.DOTALL | re.IGNORECASE,
)

_INTERNAL_NOTICE_RE = re.compile(
    r"(?:^\s*\[Active Mode:[^\]]*\]\s*|"
    r"^\s*Pinned context files:[^\n]*\s*|"
    r"\[Proceed with the next step[^\]]*\]\s*|"
    r"\[System:[^\]]*\]\s*)",
    re.IGNORECASE | re.MULTILINE,
)

_TOOL_ICONS = {
    "ls": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2"/></svg>',
    "read": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/></svg>',
    "write": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>',
    "edit": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>',
    "multi_edit": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>',
    "search": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/></svg>',
    "grep": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 10m-7 0a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/></svg>',
    "bash": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7l5 5l-5 5"/><path d="M12 19l7 0"/></svg>',
    "run": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7l5 5l-5 5"/><path d="M12 19l7 0"/></svg>',
    "todo": '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3l8 -8"/><path d="M20 12v6a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h9"/></svg>',
}
_DEFAULT_TOOL_ICON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1 -2.83 2.83l-.06-.06a1.65 1.65 0 0 0 -1.82-.33 1.65 1.65 0 0 0 -1 1.51V21a2 2 0 1 1 -4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0 -1.82.33l-.06.06a2 2 0 1 1 -2.83 -2.83l.06-.06a1.65 1.65 0 0 0 .33 -1.82 1.65 1.65 0 0 0 -1.51 -1H3a2 2 0 1 1 0 -4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0 -.33 -1.82l-.06-.06a2 2 0 1 1 2.83 -2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1 -1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82 -.33l.06 -.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0 -.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0 -1.51 1z"/></svg>'


def redact_secrets(text: str) -> str:
    """Mask common API keys and bearer tokens before sharing a session publicly."""
    if not text:
        return text
    out = text
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def _extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _format_inline_md(escaped_line: str) -> str:
    # Inline code first so formatting inside backticks is untouched
    code_spans: List[str] = []

    def _stash_code(m):
        idx = len(code_spans)
        code_spans.append(f"<code>{m.group(1)}</code>")
        return f"@@ICODE_{idx}@@"

    s = re.sub(r"`([^`]+)`", _stash_code, escaped_line)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
    for idx, span in enumerate(code_spans):
        s = s.replace(f"@@ICODE_{idx}@@", span)
    return s


def _format_markdown_simple(text: str) -> str:
    """Render full, clean Markdown (headings, lists, code blocks, tables, quotes, inline formatting)."""
    if not text:
        return ""
    blocks: List[str] = []

    def _code_block(match):
        lang = html.escape((match.group(1) or "code").strip())
        code_body = html.escape(match.group(2).strip("\r\n"))
        idx = len(blocks)
        blocks.append(
            f'<div class="code-wrap"><div class="code-head"><span>{lang}</span>'
            f'<button type="button" class="code-copy">Copy</button></div>'
            f'<pre><code>{code_body}</code></pre></div>'
        )
        return f"\n@@CODEBLOCK_{idx}@@\n"

    processed = re.sub(r"```([^\n`]*)\r?\n([\s\S]*?)```", _code_block, text)
    lines = processed.splitlines()
    out: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        cb_m = re.match(r"^@@CODEBLOCK_(\d+)@@$", stripped)
        if cb_m:
            out.append(blocks[int(cb_m.group(1))])
            i += 1
            continue

        if re.match(r"^(?:---|\*\*\*|___)\s*$", stripped):
            out.append("<hr>")
            i += 1
            continue

        h_m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if h_m:
            lvl = len(h_m.group(1))
            out.append(f"<h{lvl}>{_format_inline_md(html.escape(h_m.group(2)))}</h{lvl}>")
            i += 1
            continue

        if stripped.startswith("> "):
            q_lines = []
            while i < n and lines[i].strip().startswith(">"):
                q_lines.append(_format_inline_md(html.escape(re.sub(r"^>\s?", "", lines[i].strip()))))
                i += 1
            out.append("<blockquote>" + "<br>".join(q_lines) + "</blockquote>")
            continue

        if re.match(r"^[-*+]\s+", stripped):
            items = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                item_txt = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                items.append(f"<li>{_format_inline_md(html.escape(item_txt))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_txt = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append(f"<li>{_format_inline_md(html.escape(item_txt))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Markdown table detection
        if "|" in stripped and i + 1 < n and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]*$", lines[i + 1]):
            hdr_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows_html = ["<thead><tr>" + "".join(f"<th>{_format_inline_md(html.escape(c))}</th>" for c in hdr_cells) + "</tr></thead>"]
            body_rows = []
            while i < n and "|" in lines[i].strip() and lines[i].strip():
                r_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                body_rows.append("<tr>" + "".join(f"<td>{_format_inline_md(html.escape(c))}</td>" for c in r_cells) + "</tr>")
                i += 1
            if body_rows:
                rows_html.append("<tbody>" + "".join(body_rows) + "</tbody>")
            out.append("<table>" + "".join(rows_html) + "</table>")
            continue

        # Normal paragraph (collect consecutive plain lines)
        p_lines = []
        while i < n:
            cur = lines[i].strip()
            if (
                not cur
                or re.match(r"^@@CODEBLOCK_\d+@@$", cur)
                or re.match(r"^(?:#{1,4}\s+|[-*+]\s+|\d+\.\s+|>\s|---$|\*\*\*$)", cur)
            ):
                break
            p_lines.append(_format_inline_md(html.escape(lines[i])))
            i += 1
        if p_lines:
            out.append("<p>" + "<br>".join(p_lines) + "</p>")

    rendered = "".join(out)
    for idx, blk in enumerate(blocks):
        rendered = rendered.replace(f"@@CODEBLOCK_{idx}@@", blk)
    return rendered


def _format_tool_output_html(text: str) -> str:
    lines = []
    for raw_line in html.escape(text).splitlines():
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            lines.append(f'<span class="diff-add">{raw_line}</span>')
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            lines.append(f'<span class="diff-del">{raw_line}</span>')
        else:
            lines.append(raw_line)
    return "\n".join(lines)


def _extract_tool_target(t_name: str, t_body: str) -> str:
    try:
        parsed = json.loads(t_body)
        if isinstance(parsed, dict):
            return str(parsed.get("path") or parsed.get("cmd") or parsed.get("query") or parsed.get("action") or "")
    except Exception:
        pass
    m_file = re.match(r"^\s*File:\s*([^\r\n]+)", t_body)
    if m_file:
        return m_file.group(1).strip()
    m_found = re.match(r"^\s*(Found\s+\d+\s+[^\r\n:]+)", t_body)
    if m_found:
        return m_found.group(1).strip()
    return ""


def _normalize_turns(messages: List[Dict[str, Any]], redact: bool) -> List[Dict[str, Any]]:
    """Group raw session messages into clean chat turns, attaching <tool_response> blocks as tool cards."""
    def _clean(val: str) -> str:
        return redact_secrets(val) if redact else val

    turns: List[Dict[str, Any]] = []
    current_turn: Optional[Dict[str, Any]] = None

    for msg in messages:
        role = str(msg.get("role") or "user").lower()
        raw_content = _clean(_extract_content_text(msg.get("content")))

        if role in ("user", "tool"):
            found_tools = list(_TOOL_RESPONSE_FINDALL_RE.finditer(raw_content))
            if found_tools:
                if current_turn is None:
                    current_turn = {"user": "", "assistant_parts": []}
                    turns.append(current_turn)
                if not current_turn["assistant_parts"]:
                    current_turn["assistant_parts"].append({"thinking": "", "tools": [], "text": ""})
                for tm in found_tools:
                    t_name = tm.group(1).strip()
                    t_body = tm.group(2).strip()
                    current_turn["assistant_parts"][-1]["tools"].append({
                        "name": t_name,
                        "target": _extract_tool_target(t_name, t_body),
                        "output": t_body[:60000],
                    })
                remainder = _TOOL_RESPONSE_FINDALL_RE.sub("", raw_content)
                remainder = _INTERNAL_NOTICE_RE.sub("", remainder).strip()
                if not remainder:
                    continue
                raw_content = remainder

            if role == "tool":
                continue

            cleaned_user = _INTERNAL_NOTICE_RE.sub("", raw_content).strip()
            if not cleaned_user:
                continue
            current_turn = {"user": cleaned_user, "assistant_parts": []}
            turns.append(current_turn)

        elif role == "assistant":
            thinking = _clean(str(msg.get("thinking") or ""))
            body = raw_content
            if not thinking and "<think>" in body:
                m = re.search(r"<think>([\s\S]*?)</think>", body)
                if m:
                    thinking = m.group(1).strip()
                    body = re.sub(r"<think>[\s\S]*?</think>", "", body)
            body = _STRIP_TOOL_TAGS_RE.sub("", body).strip()

            tools = []
            for t in (msg.get("tools") or []):
                tools.append({
                    "name": str(t.get("name") or "tool"),
                    "target": _clean(str(t.get("target") or "")),
                    "output": _clean(str(t.get("output") or "")),
                })

            if current_turn is None:
                current_turn = {"user": "", "assistant_parts": []}
                turns.append(current_turn)
            current_turn["assistant_parts"].append({
                "thinking": thinking,
                "tools": tools,
                "text": body,
            })

    return turns


def summarize_session_counts(messages: List[Dict[str, Any]]) -> Dict[str, int]:
    """Return real human-visible turn & tool counts (excluding raw <tool_response> system entries)."""
    turns = _normalize_turns(messages, redact=False)
    turn_count = len(turns)
    tool_count = sum(
        len(part.get("tools") or [])
        for t in turns
        for part in (t.get("assistant_parts") or [])
    )
    return {"turns": turn_count, "tools": tool_count}


def build_raw_markdown(
    session_id: str,
    turns: List[Dict[str, Any]],
    model_id: str,
    timestamp: str,
) -> str:
    """Build complete raw Markdown transcript for the Download / Raw MD view."""
    lines = [
        f"# CMDAI CODE — Shared Session ({session_id})",
        f"- Model: `{model_id}`",
        f"- Date: {timestamp}",
        "",
    ]
    for idx, turn in enumerate(turns, 1):
        if turn.get("user"):
            lines.append(f"## User #{idx}")
            lines.append("")
            lines.append(turn["user"])
            lines.append("")
        parts = turn.get("assistant_parts") or []
        if parts:
            lines.append(f"### Assistant ({model_id})")
            lines.append("")
            for part in parts:
                if part.get("text"):
                    lines.append(part["text"])
                    lines.append("")
                for t in (part.get("tools") or []):
                    t_hdr = f"- Tool `{t['name']}`" + (f" (`{t['target']}`)" if t.get("target") else "")
                    lines.append(t_hdr)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_session_html(
    session_id: str,
    messages: List[Dict[str, Any]],
    stats: Dict[str, Any],
    model_id: str,
    workdir: str,
    redact: bool = True,
) -> str:
    """Render a standalone read-only CMDAI CODE Web chat page with authentic logo, Turn Timeline dots & Raw Markdown Download."""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    turns = _normalize_turns(messages, redact=redact)

    session_title = session_id
    for t in turns:
        if t.get("user"):
            first_ln = t["user"].splitlines()[0].strip()
            if first_ln:
                session_title = (first_ln[:54] + "…") if len(first_ln) > 54 else first_ln
                break

    cards: List[str] = []
    dots: List[str] = []

    for idx, turn in enumerate(turns):
        user_txt = turn.get("user") or ""
        tip = (user_txt.splitlines()[0][:60] if user_txt else f"Turn #{idx + 1}")
        dots.append(f'<button type="button" class="tl-dot" title="{html.escape(tip)}" aria-label="Jump to turn {idx + 1}"></button>')

        inner: List[str] = []
        if user_txt:
            inner.append(f'<div class="msg-user-wrap"><div class="msg-user-bubble">{_format_markdown_simple(user_txt)}</div></div>')

        parts = turn.get("assistant_parts") or []
        if parts:
            blocks: List[str] = []
            for part in parts:
                if part.get("thinking"):
                    blocks.append(f"""
                    <details class="think-block">
                        <summary><span class="tool-name">Thought process</span><span class="tool-arg"></span><span class="tool-chev">▸</span></summary>
                        <div class="think-content">{html.escape(part["thinking"])}</div>
                    </details>
                    """)
                if part.get("text"):
                    blocks.append(f'<div class="assistant-body">{_format_markdown_simple(part["text"])}</div>')
                for t in (part.get("tools") or []):
                    raw_tname = str(t.get("name") or "tool").lower()
                    t_name = html.escape(raw_tname.capitalize())
                    t_arg = html.escape(str(t.get("target") or ""))
                    t_out = _format_tool_output_html(str(t.get("output") or ""))
                    ico = _TOOL_ICONS.get(raw_tname, _DEFAULT_TOOL_ICON)
                    ico_cls = "tool-ico write" if raw_tname in ("write", "edit", "multi_edit") else "tool-ico"
                    blocks.append(f"""
                    <details class="tool-block">
                        <summary><span class="{ico_cls}">{ico}</span><span class="tool-name">{t_name}</span><span class="tool-arg">{t_arg}</span><span class="tool-chev">▸</span></summary>
                        <div class="tool-content">{t_out}</div>
                    </details>
                    """)
            inner.append(f"""
            <div class="msg-assistant-wrap">
                <div class="assistant-head">
                    <span class="assistant-model">{html.escape(model_id or "Assistant")}</span>
                </div>
                {"".join(blocks)}
            </div>
            """)

        cards.append(f'<section class="turn-anchor" id="turn-{idx}">{"".join(inner)}</section>')

    raw_md = build_raw_markdown(session_id, turns, model_id or "Assistant", now_str)
    safe_fname = "".join(c for c in session_id if c.isalnum() or c in ("-", "_")) or "cmdai_session"

    return HTML_EXPORTER_TEMPLATE.format(
        session_id=html.escape(session_id),
        session_title=html.escape(session_title),
        session_filename=html.escape(safe_fname),
        model_id=html.escape(model_id or "Assistant"),
        timeline_dots="\n".join(dots),
        timeline_cards="\n".join(cards) if cards else '<div style="color:var(--text-muted);text-align:center;padding:48px;">No messages in session.</div>',
        raw_markdown=html.escape(raw_md),
    )


def export_session_to_html(
    session_id: str,
    messages: List[Dict[str, Any]],
    stats: Dict[str, Any],
    model_id: str,
    workdir: str,
    output_path: Optional[str] = None,
    redact: bool = False,
) -> str:
    if not output_path:
        out_dir = os.path.join(workdir, "exports")
        os.makedirs(out_dir, exist_ok=True)
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_")) or "session"
        output_path = os.path.join(out_dir, f"cmdai_export_{safe_id}_{int(time.time())}.html")
    else:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

    rendered_html = render_session_html(
        session_id=session_id,
        messages=messages,
        stats=stats,
        model_id=model_id,
        workdir=workdir,
        redact=redact,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    return os.path.abspath(output_path)
