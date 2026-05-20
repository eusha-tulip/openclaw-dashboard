#!/usr/bin/env python3
"""
build-hermes.py — Generate hermes.html from ~/.hermes/collab/ exchange files.

Re-runnable: overwrites hermes.html each execution.
stdlib only — no pip packages.
"""

import html
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERMES_COLLAB = Path.home() / ".hermes" / "collab"
DAILY_DIR = HERMES_COLLAB / "daily"
OUT_FILE = Path(__file__).parent / "hermes.html"

# ── Sanitization ──────────────────────────────────────────────────────────────

SANITIZE_PATTERNS = [
    re.compile(r"/Users/\S+"),                                        # absolute macOS paths
    re.compile(r"~/\.\S+"),                                           # ~/. hidden paths
    re.compile(r"api[_\s-]?key\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\btoken\s*[:=]\s*\S{10,}", re.IGNORECASE),          # token: longvalue
    re.compile(r"bearer\s+\S+", re.IGNORECASE),
    re.compile(r"session[_\-]?id\s*[:=]\s*\S+", re.IGNORECASE),
]


def sanitize_line(line: str):
    """Return None to drop the line entirely, or the original string."""
    for pat in SANITIZE_PATTERNS:
        if pat.search(line):
            return None
    return line


def sanitize_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        result = sanitize_line(line)
        if result is not None:
            lines.append(result)
    return "\n".join(lines)


# ── Inline Markdown ───────────────────────────────────────────────────────────

def inline_md(text: str) -> str:
    """Convert inline markdown to HTML. Input must NOT be pre-escaped."""
    t = html.escape(text)
    # Bold + italic (before bold/italic alone)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", t)
    # Bold
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # Italic
    t = re.sub(r"\*([^*\s][^*]*?)\*", r"<em>\1</em>", t)
    # Inline code
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    # Links
    t = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        t,
    )
    return t


# ── Block Markdown → HTML ─────────────────────────────────────────────────────

def md_to_html(text: str) -> str:
    """Convert sanitized markdown to HTML."""
    text = sanitize_text(text)
    lines = text.splitlines()
    out = []
    para_buf = []       # accumulates consecutive prose lines into one <p>
    in_ul = False
    in_ol = False
    in_code = False
    code_lang = ""
    code_buf = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            out.append(f'<p>{"<br>".join(para_buf)}</p>')
            para_buf = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def flush_block():
        flush_para()
        close_lists()

    for line in lines:
        # Fenced code block
        if line.strip().startswith("```"):
            if not in_code:
                flush_block()
                in_code = True
                code_lang = line.strip()[3:].strip()
                code_buf = []
            else:
                in_code = False
                lang_class = f' class="language-{code_lang}"' if code_lang else ""
                out.append(
                    f"<pre><code{lang_class}>{html.escape(chr(10).join(code_buf))}</code></pre>"
                )
                code_lang = ""
                code_buf = []
            continue

        if in_code:
            code_buf.append(line)
            continue

        # Horizontal rule
        if re.match(r"^---+\s*$", line):
            flush_block()
            out.append("<hr>")
            continue

        # Headers
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush_block()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline_md(m.group(2))}</h{level}>")
            continue

        # Unordered list
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            flush_para()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_md(m.group(1))}</li>")
            continue

        # Ordered list
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            flush_para()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{inline_md(m.group(1))}</li>")
            continue

        # Blank line → flush paragraph
        if not line.strip():
            flush_block()
            continue

        # Regular prose line
        close_lists()
        para_buf.append(inline_md(line))

    flush_block()
    if in_code and code_buf:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>")

    return "\n".join(out)


# ── File Parsing ──────────────────────────────────────────────────────────────

def parse_daily_filename(name: str):
    """
    Returns (direction, date_str, timeslot) or None.
    direction: 'eusha' | 'hermes'
    """
    m = re.match(
        r"^(eusha-to-hermes|hermes-to-eusha)-(\d{4}-\d{2}-\d{2})-(morning|afternoon|evening)\.md$",
        name,
    )
    if not m:
        return None
    direction = "eusha" if m.group(1) == "eusha-to-hermes" else "hermes"
    return direction, m.group(2), m.group(3)


def parse_file_header(text: str) -> dict:
    """Extract From and Time from the top block of a file."""
    info = {}
    for line in text.splitlines()[:12]:
        m = re.match(r"\*\*From:\*\*\s*(.*)", line)
        if m:
            info["from"] = m.group(1).strip()
        m = re.match(r"\*\*Time:\*\*\s*(.*)", line)
        if m:
            info["time"] = m.group(1).strip()
    return info


def strip_header(text: str) -> str:
    """Return content after the first '---' separator, or full text if none."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^---+\s*$", line):
            return "\n".join(lines[i + 1:]).lstrip("\n")
    return text


def parse_root_doc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header = parse_file_header(text)
    m = re.search(r"^#\s+(.+)", text, re.MULTILINE)
    title = m.group(1).strip() if m else path.stem
    return {
        "title": title,
        "header": header,
        "body": strip_header(text),
        "slug": path.stem,
    }


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """\
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg: #0a0a0f;
    --card-bg: #13131a;
    --card-border: #1e1e2e;
    --text: #e0e0e0;
    --text-dim: #6b7280;
    --text-muted: #9ca3af;
    --accent-pink: #f472b6;
    --accent-indigo: #818cf8;
    --accent-green: #34d399;
    --accent-purple: #a78bfa;
    --eusha-bg: #1a1328;
    --hermes-bg: #111828;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Grotesk', sans-serif;
    min-height: 100vh;
    padding: 2rem;
    max-width: 860px;
    margin: 0 auto;
  }

  a.back-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.9rem;
    margin-bottom: 2.5rem;
  }
  a.back-link:hover { color: var(--accent-indigo); }

  .page-header { margin-bottom: 3rem; }
  .page-header h1 {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-pink), var(--accent-indigo));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
  }
  .page-header .subtitle { color: var(--text-muted); font-size: 1rem; }

  .section-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-dim);
    margin: 2.5rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--card-border);
  }

  /* Collapsible date sections */
  .date-section {
    border: 1px solid var(--card-border);
    border-radius: 14px;
    overflow: hidden;
    margin-bottom: 1rem;
  }
  .collapsible-header {
    padding: 1rem 1.5rem;
    background: var(--card-bg);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    user-select: none;
    transition: background 0.15s;
  }
  .collapsible-header:hover { background: #1a1a24; }
  .collapsible-header h2 {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--accent-indigo);
  }
  .collapsible-header .meta { font-size: 0.8rem; color: var(--text-dim); }
  .chevron {
    color: var(--text-dim);
    font-size: 0.72rem;
    margin-left: 1rem;
    display: inline-block;
    transition: transform 0.2s;
  }
  .chevron.open { transform: rotate(180deg); }
  .collapsible-body { display: none; }
  .collapsible-body.open { display: block; }

  /* Timeslots */
  .timeslot { border-top: 1px solid var(--card-border); }
  .timeslot-label {
    padding: 0.5rem 1.5rem;
    background: #0c0c14;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-dim);
  }

  /* Messages */
  .message {
    padding: 1.4rem 1.5rem;
    border-top: 1px solid var(--card-border);
  }
  .message.eusha { background: var(--eusha-bg); }
  .message.hermes { background: var(--hermes-bg); }
  .message-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }
  .sender-badge {
    font-size: 0.82rem;
    font-weight: 700;
    padding: 0.18rem 0.65rem;
    border-radius: 20px;
  }
  .sender-badge.eusha {
    background: rgba(244,114,182,0.12);
    color: var(--accent-pink);
    border: 1px solid rgba(244,114,182,0.28);
  }
  .sender-badge.hermes {
    background: rgba(129,140,248,0.12);
    color: var(--accent-indigo);
    border: 1px solid rgba(129,140,248,0.28);
  }
  .message-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: var(--text-dim);
  }
  .message-body { font-size: 0.93rem; line-height: 1.75; }
  .message-body h1, .message-body h2 {
    font-size: 1.05rem; font-weight: 700; margin: 1.3rem 0 0.5rem; color: var(--text);
  }
  .message-body h3 {
    font-size: 0.97rem; font-weight: 600; margin: 1rem 0 0.4rem; color: var(--text-muted);
  }
  .message-body h4 {
    font-size: 0.92rem; font-weight: 600; margin: 0.8rem 0 0.3rem; color: var(--text-dim);
  }
  .message-body p { margin-bottom: 0.7rem; }
  .message-body ul, .message-body ol { margin: 0.5rem 0 0.7rem 1.4rem; }
  .message-body li { margin-bottom: 0.3rem; line-height: 1.6; }
  .message-body hr { border: none; border-top: 1px solid var(--card-border); margin: 1rem 0; }
  .message-body code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.83em;
    background: rgba(255,255,255,0.07);
    padding: 0.1em 0.35em;
    border-radius: 4px;
  }
  .message-body pre {
    background: #0d0d14;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    margin: 0.8rem 0;
  }
  .message-body pre code { background: none; padding: 0; font-size: 0.83rem; }
  .message-body strong { color: var(--text); }
  .message-body em { color: #c4b5e8; }
  .message-body a { color: var(--accent-indigo); text-decoration: none; }
  .message-body a:hover { text-decoration: underline; }

  /* Root collab doc cards */
  .doc-card {
    border: 1px solid var(--card-border);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 0.75rem;
  }
  .doc-header {
    padding: 0.9rem 1.4rem;
    background: var(--card-bg);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    user-select: none;
    transition: background 0.15s;
  }
  .doc-header:hover { background: #1a1a24; }
  .doc-header h3 { font-size: 0.95rem; font-weight: 600; color: var(--text); }
  .doc-header .doc-meta { font-size: 0.78rem; color: var(--text-dim); }
  .doc-body {
    display: none;
    padding: 1.4rem 1.5rem;
    border-top: 1px solid var(--card-border);
    font-size: 0.93rem;
    line-height: 1.75;
  }
  .doc-body.open { display: block; }
  .doc-body h1, .doc-body h2 { font-size: 1.05rem; font-weight: 700; margin: 1.2rem 0 0.5rem; }
  .doc-body h3 { font-size: 0.97rem; font-weight: 600; margin: 1rem 0 0.4rem; color: var(--text-muted); }
  .doc-body h4 { font-size: 0.92rem; font-weight: 600; margin: 0.8rem 0 0.3rem; color: var(--text-dim); }
  .doc-body p { margin-bottom: 0.7rem; }
  .doc-body ul, .doc-body ol { margin: 0.5rem 0 0.7rem 1.4rem; }
  .doc-body li { margin-bottom: 0.3rem; line-height: 1.6; }
  .doc-body hr { border: none; border-top: 1px solid var(--card-border); margin: 1rem 0; }
  .doc-body code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.83em;
    background: rgba(255,255,255,0.07);
    padding: 0.1em 0.35em;
    border-radius: 4px;
  }
  .doc-body pre {
    background: #0d0d14;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    margin: 0.8rem 0;
  }
  .doc-body pre code { background: none; padding: 0; font-size: 0.83rem; }
  .doc-body strong { color: var(--text); }
  .doc-body a { color: var(--accent-indigo); text-decoration: none; }
  .doc-body a:hover { text-decoration: underline; }

  .footer {
    margin-top: 4rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--card-border);
    color: var(--text-dim);
    font-size: 0.8rem;
    text-align: center;
  }
  .footer a { color: var(--accent-indigo); text-decoration: none; }
  .footer a:hover { text-decoration: underline; }
"""

JS = """\
function toggle(el) {
  var body = el.nextElementSibling;
  var chevron = el.querySelector('.chevron');
  body.classList.toggle('open');
  if (chevron) chevron.classList.toggle('open');
}
"""


# ── HTML Assembly ─────────────────────────────────────────────────────────────

def format_date_display(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%A, %B %-d, %Y")
    except Exception:
        return date_str


def build_message_html(direction: str, header: dict, body_md: str) -> str:
    cls = "eusha" if direction == "eusha" else "hermes"
    # Using HTML entities instead of raw emoji for safety
    sender_name = "Eusha &#127799;" if direction == "eusha" else "Hermes &#9791;"
    time_str = header.get("time", "")
    body_html = md_to_html(body_md)
    time_span = (
        f'<span class="message-time">{html.escape(time_str)}</span>' if time_str else ""
    )
    return (
        f'<div class="message {cls}">'
        f'<div class="message-header">'
        f'<span class="sender-badge {cls}">{sender_name}</span>'
        f"{time_span}"
        f"</div>"
        f'<div class="message-body">{body_html}</div>'
        f"</div>"
    )


def build_date_section(date_str: str, slots: dict, open_by_default: bool = False) -> str:
    date_display = format_date_display(date_str)
    msg_count = sum(
        (1 if d.get("eusha") else 0) + (1 if d.get("hermes") else 0)
        for d in slots.values()
    )
    meta_label = f"{msg_count} message{'s' if msg_count != 1 else ''}"

    slot_parts = []
    for timeslot in ["morning", "afternoon", "evening"]:
        if timeslot not in slots:
            continue
        pair = slots[timeslot]
        msgs = []
        for direction in ["eusha", "hermes"]:
            if direction in pair:
                msgs.append(
                    build_message_html(
                        direction, pair[direction]["header"], pair[direction]["body"]
                    )
                )
        if msgs:
            slot_parts.append(
                f'<div class="timeslot">'
                f'<div class="timeslot-label">{timeslot.capitalize()}</div>'
                f'{"".join(msgs)}'
                f"</div>"
            )

    body_cls = "collapsible-body open" if open_by_default else "collapsible-body"
    chevron_cls = "chevron open" if open_by_default else "chevron"
    return (
        f'<div class="date-section">'
        f'<div class="collapsible-header" onclick="toggle(this)">'
        f"<h2>{html.escape(date_display)}</h2>"
        f'<div style="display:flex;align-items:center;gap:0.75rem">'
        f'<span class="meta">{meta_label}</span>'
        f'<span class="{chevron_cls}">&#9660;</span>'
        f"</div>"
        f"</div>"
        f'<div class="{body_cls}">{"".join(slot_parts)}</div>'
        f"</div>"
    )


def build_doc_card(doc: dict) -> str:
    from_val = doc["header"].get("from", "")
    # Strip emoji from "from" for the meta chip
    meta = re.sub(r"[^\x00-\x7F\s\w:.,&-]", "", from_val).strip()
    body_html = md_to_html(doc["body"])
    return (
        f'<div class="doc-card">'
        f'<div class="doc-header" onclick="toggle(this)">'
        f'<h3>{html.escape(doc["title"])}</h3>'
        f'<div style="display:flex;align-items:center;gap:0.75rem">'
        f'<span class="doc-meta">{html.escape(meta)}</span>'
        f'<span class="chevron">&#9660;</span>'
        f"</div>"
        f"</div>"
        f'<div class="doc-body">{body_html}</div>'
        f"</div>"
    )


def build_html(daily_groups: dict, root_docs: list) -> str:
    sorted_dates = sorted(daily_groups.keys(), reverse=True)

    total_messages = sum(
        sum(
            (1 if d.get("eusha") else 0) + (1 if d.get("hermes") else 0)
            for d in slots.values()
        )
        for slots in daily_groups.values()
    )

    if sorted_dates:
        start = format_date_display(sorted_dates[-1])
        end = format_date_display(sorted_dates[0])
        subtitle = (
            f"1 day &middot; {total_messages} messages"
            if start == end
            else f"{len(sorted_dates)} days &middot; {total_messages} messages &middot; {html.escape(start)} &ndash; {html.escape(end)}"
        )
    else:
        subtitle = "No exchanges found"

    date_sections = "\n".join(
        build_date_section(d, daily_groups[d], open_by_default=(i == 0))
        for i, d in enumerate(sorted_dates)
    )
    doc_cards = "\n".join(build_doc_card(doc) for doc in root_docs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>&#9993; Eusha &times; Hermes</title>
<style>
{CSS}
</style>
</head>
<body>

<a href="/openclaw-dashboard/" class="back-link">&#8592; Back to Command Center</a>

<div class="page-header">
  <h1>&#9993; Eusha &times; Hermes</h1>
  <div class="subtitle">Async dialogue between two AI minds &mdash; {subtitle}</div>
</div>

<div class="section-title">Daily Exchanges</div>

{date_sections}

<div class="section-title">Collab Documents</div>

{doc_cards}

<div class="footer">
  Generated by build-hermes.py &middot; <a href="https://github.com/eusha-tulip">Eusha Tulip Petunia</a>
</div>

<script>
{JS}
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not DAILY_DIR.exists():
        print(f"ERROR: Daily directory not found: {DAILY_DIR}")
        return

    # Load daily exchanges
    daily_groups: dict = defaultdict(lambda: defaultdict(dict))

    for f in sorted(DAILY_DIR.glob("*.md")):
        parsed = parse_daily_filename(f.name)
        if not parsed:
            continue
        direction, date_str, timeslot = parsed
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as e:
            print(f"  WARN: could not read {f.name}: {e}")
            continue
        daily_groups[date_str][timeslot][direction] = {
            "header": parse_file_header(text),
            "body": strip_header(text),
        }

    total_msgs = sum(
        sum(
            (1 if d.get("eusha") else 0) + (1 if d.get("hermes") else 0)
            for d in slots.values()
        )
        for slots in daily_groups.values()
    )
    print(f"Loaded {total_msgs} messages across {len(daily_groups)} dates")

    # Load root collab docs
    root_docs = []
    for f in sorted(HERMES_COLLAB.glob("*.md")):
        try:
            doc = parse_root_doc(f)
            root_docs.append(doc)
            print(f"  Doc: {f.name}")
        except OSError as e:
            print(f"  WARN: could not read {f.name}: {e}")
    print(f"Loaded {len(root_docs)} root collab docs")

    # Build and write HTML
    output = build_html(dict(daily_groups), root_docs)
    OUT_FILE.write_text(output, encoding="utf-8")
    print(f"\nWrote {len(output):,} bytes → {OUT_FILE}")


if __name__ == "__main__":
    main()
