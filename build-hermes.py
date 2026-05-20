#!/usr/bin/env python3
"""
build-hermes.py — Generate hermes.html from conversation index files.
Re-runnable: overwrites hermes.html each time.
Usage: python build-hermes.py
"""

import re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

OPENCLAW_ROOT = Path.home() / ".openclaw"
CONV_INDEX_ROOT = OPENCLAW_ROOT / "memory" / "conversation-index"
DASHBOARD_ROOT = Path(__file__).parent
OUTPUT_HTML = DASHBOARD_ROOT / "hermes.html"

SEARCH_DIRS = ["claude", "main"]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_hermes_files():
    found = []
    for dir_name in SEARCH_DIRS:
        d = CONV_INDEX_ROOT / dir_name
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                text = f.read_text(errors="replace")
            except Exception:
                continue
            if "hermes" in text.lower():
                found.append((dir_name, f, text))
    return found


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_meta(text):
    meta = {}
    for key, pattern in [
        ("date_str", r"\*\*Date:\*\*\s*(.+)"),
        ("source",   r"\*\*Source:\*\*\s*(.+)"),
        ("type",     r"\*\*Type:\*\*\s*(.+)"),
        ("model",    r"\*\*Model:\*\*\s*(.+)"),
    ]:
        m = re.search(pattern, text)
        meta[key] = m.group(1).strip() if m else ""

    meta["date"] = None
    for fmt in ("%Y-%m-%d %H:%M UTC", "%Y-%m-%d"):
        try:
            meta["date"] = datetime.strptime(meta["date_str"], fmt).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            pass
    return meta


def extract_uuid(name):
    m = re.match(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})-chunk-\d+", name)
    return m.group(1) if m else name


def get_conv_body(text):
    m = re.search(r"## Conversation\s*\n(.*)", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def get_summary(conv_body, max_len=280):
    """Extract a readable summary from the last Eusha response."""
    # Split on speaker turns
    parts = re.split(r"\n\n(?=\*\*(?:User|Eusha|Justin):\*\*)", conv_body)
    eusha_parts = [p for p in parts if p.lstrip().startswith("**Eusha:**")]

    text = eusha_parts[-1] if eusha_parts else conv_body
    # Strip speaker label
    text = re.sub(r"^\*\*Eusha:\*\*\s*", "", text.lstrip()).strip()
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text).strip()
    # First paragraph
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    summary = paras[0] if paras else text
    # Strip markdown formatting
    summary = re.sub(r"\*\*(.+?)\*\*", r"\1", summary)
    summary = re.sub(r"`[^`]+`", "", summary)
    summary = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) > max_len:
        summary = summary[:max_len].rsplit(" ", 1)[0] + "…"
    return summary or "Conversation content"


# ---------------------------------------------------------------------------
# Markdown → HTML
# ---------------------------------------------------------------------------

def md_to_html(text):
    # HTML-escape
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Fenced code blocks
    def code_block(m):
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        cls = f' class="lang-{lang}"' if lang else ""
        return f"<pre><code{cls}>{code}</code></pre>"
    text = re.sub(r"```(\w*)\n?([\s\S]*?)```", code_block, text)

    # Inline code
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)

    # Headers
    text = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$",  r"<h3>\1</h3>",  text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$",   r"<h2>\1</h2>",  text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$",    r"<h1>\1</h1>",  text, flags=re.MULTILINE)

    # Speaker labels (bold colon pattern: **Name:**)
    text = re.sub(
        r"\*\*(User|Eusha|Justin|Hermes|Assistant|Human):\*\*",
        r'<span class="speaker">\1</span>',
        text
    )

    # Bold + italic combo
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic (avoid matching stray asterisks)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)

    # Bullet lists
    def listify(m):
        items = re.findall(r"^[-*] (.+)$", m.group(0), re.MULTILINE)
        lis = "".join(f"<li>{item}</li>" for item in items)
        return f"<ul>{lis}</ul>"
    text = re.sub(r"(?:^[-*] .+\n?)+", listify, text, flags=re.MULTILINE)

    # Horizontal rules (--- separators between chunks)
    text = re.sub(r"^---$", r"<hr>", text, flags=re.MULTILINE)

    # Wrap in paragraphs
    blocks = re.split(r"\n{2,}", text)
    out = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if re.match(r"^<(h[1-4]|ul|pre|hr)", b):
            out.append(b)
        else:
            b = b.replace("\n", "<br>")
            out.append(f"<p>{b}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

BADGE_STYLES = {
    "cron":         ("var(--accent-green)",  "rgba(52,211,153,0.12)"),
    "agent-claude": ("var(--accent-indigo)", "rgba(129,140,248,0.12)"),
    "agent-main":   ("var(--accent-pink)",   "rgba(244,114,182,0.12)"),
    "main":         ("var(--accent-pink)",   "rgba(244,114,182,0.12)"),
    "claude":       ("var(--accent-indigo)", "rgba(129,140,248,0.12)"),
}


def badge_html(label):
    fg, bg = BADGE_STYLES.get(label, ("var(--text-muted)", "rgba(156,163,175,0.1)"))
    return (
        f'<span class="badge" style="color:{fg};background:{bg};'
        f'border-color:{fg}44">{label}</span>'
    )


def build_html(conversations):
    cards = []
    for i, c in enumerate(conversations):
        if c["date"]:
            date_display = c["date"].strftime("%B %d, %Y · %H:%M UTC")
        else:
            date_display = c["date_str"] or "Unknown date"

        src_badge  = badge_html(c["source"])
        type_badge = badge_html(c["type"]) if c["type"] else ""
        chunks_note = (
            f'<span class="chunks">{c["file_count"]} files</span>'
            if c["file_count"] > 1 else ""
        )

        body_html = md_to_html(c["body"])

        cards.append(f"""  <div class="conv-card" id="conv-{i}">
    <button class="conv-header" onclick="toggle({i})" aria-expanded="false">
      <div class="conv-meta">
        <span class="conv-date">{date_display}</span>
        <div class="conv-badges">{src_badge}{type_badge}{chunks_note}</div>
      </div>
      <p class="conv-summary">{c["summary"]}</p>
      <span class="expand-icon" aria-hidden="true">▼</span>
    </button>
    <div class="conv-body" id="body-{i}" hidden>
{body_html}
    </div>
  </div>""")

    cards_html = "\n".join(cards)
    count = len(conversations)
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>✉ Hermes Archive — Eusha Command Center</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  :root {{
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
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Grotesk', sans-serif;
    min-height: 100vh;
    padding: 2rem;
    max-width: 860px;
    margin: 0 auto;
  }}

  .back {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--accent-indigo);
    text-decoration: none;
    font-size: 0.9rem;
    margin-bottom: 2rem;
  }}
  .back:hover {{ text-decoration: underline; }}

  .page-header {{
    margin-bottom: 2.5rem;
  }}
  .page-header h1 {{
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-pink), var(--accent-indigo));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.4rem;
  }}
  .page-header .subtitle {{
    color: var(--text-muted);
    font-size: 1rem;
    margin-bottom: 0.3rem;
  }}
  .page-header .meta {{
    color: var(--text-dim);
    font-size: 0.8rem;
    font-family: 'JetBrains Mono', monospace;
  }}

  .conv-card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    margin-bottom: 1rem;
    overflow: hidden;
    transition: border-color 0.2s;
  }}
  .conv-card:hover {{ border-color: #2a2a3e; }}
  .conv-card.open {{ border-color: var(--accent-indigo); }}

  .conv-header {{
    width: 100%;
    background: none;
    border: none;
    color: var(--text);
    cursor: pointer;
    padding: 1.4rem 1.6rem;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    position: relative;
  }}
  .conv-header:hover {{ background: rgba(255,255,255,0.015); }}

  .conv-meta {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    flex-wrap: wrap;
  }}
  .conv-date {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: var(--text-dim);
  }}
  .conv-badges {{ display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }}
  .badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    padding: 0.18rem 0.5rem;
    border-radius: 4px;
    border: 1px solid transparent;
    letter-spacing: 0.02em;
  }}
  .chunks {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--text-dim);
  }}
  .conv-summary {{
    font-size: 0.88rem;
    color: var(--text-muted);
    line-height: 1.55;
    padding-right: 2rem;
  }}
  .expand-icon {{
    position: absolute;
    right: 1.4rem;
    top: 1.5rem;
    color: var(--text-dim);
    font-size: 0.65rem;
    transition: transform 0.2s;
    pointer-events: none;
  }}
  .conv-card.open .expand-icon {{ transform: rotate(180deg); }}

  .conv-body {{
    padding: 1.2rem 1.6rem 1.4rem;
    border-top: 1px solid var(--card-border);
    font-size: 0.87rem;
    line-height: 1.7;
  }}
  .conv-body p {{ margin: 0.55rem 0; }}
  .conv-body h1, .conv-body h2, .conv-body h3, .conv-body h4 {{
    color: var(--accent-indigo);
    margin: 1.1rem 0 0.35rem;
    font-size: 0.95rem;
  }}
  .conv-body h1 {{ font-size: 1.05rem; }}
  .conv-body code {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.79rem;
    background: #0c0c17;
    padding: 0.1em 0.35em;
    border-radius: 3px;
    color: var(--accent-green);
  }}
  .conv-body pre {{
    background: #080810;
    border: 1px solid var(--card-border);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    overflow-x: auto;
    margin: 0.8rem 0;
  }}
  .conv-body pre code {{
    background: none;
    padding: 0;
    font-size: 0.77rem;
    color: var(--text);
  }}
  .conv-body ul {{ padding-left: 1.4rem; margin: 0.5rem 0; }}
  .conv-body li {{ margin: 0.22rem 0; }}
  .conv-body strong {{ color: var(--text); }}
  .conv-body em {{ color: var(--accent-purple); font-style: italic; }}
  .conv-body hr {{
    border: none;
    border-top: 1px solid var(--card-border);
    margin: 1.2rem 0;
  }}
  .conv-body .speaker {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--accent-pink);
    display: block;
    margin-top: 1.1rem;
    margin-bottom: 0.15rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}

  .footer {{
    margin-top: 3rem;
    color: var(--text-dim);
    font-size: 0.82rem;
    text-align: center;
  }}
  .footer a {{ color: var(--accent-indigo); text-decoration: none; }}
  .footer a:hover {{ text-decoration: underline; }}

  @media (max-width: 600px) {{
    body {{ padding: 1rem; }}
    .conv-header {{ padding: 1rem; }}
    .conv-body {{ padding: 1rem; }}
    .page-header h1 {{ font-size: 1.7rem; }}
  }}
</style>
</head>
<body>

<a href="/openclaw-dashboard/" class="back">← Command Center</a>

<div class="page-header">
  <h1>✉ Hermes Archive</h1>
  <div class="subtitle">Conversations between AI agents</div>
  <div class="meta">{count} conversations · newest first · built {built_at}</div>
</div>

{cards_html}

<div class="footer">
  Built by <a href="https://github.com/eusha-tulip">Eusha Tulip Petunia</a> · Born March 11, 2026
</div>

<script>
function toggle(i) {{
  const card = document.getElementById('conv-' + i);
  const body = document.getElementById('body-' + i);
  const btn  = card.querySelector('.conv-header');
  const isOpen = card.classList.toggle('open');
  btn.setAttribute('aria-expanded', String(isOpen));
  if (isOpen) body.removeAttribute('hidden');
  else body.setAttribute('hidden', '');
}}
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Scanning for Hermes conversation files...")
    raw_files = find_hermes_files()
    print(f"  Found {len(raw_files)} files with Hermes mentions")

    # Group by UUID so multi-chunk conversations merge
    groups = defaultdict(list)
    for dir_name, f, text in raw_files:
        uuid = extract_uuid(f.name)
        groups[uuid].append((dir_name, f, text))

    conversations = []
    for uuid, chunks in groups.items():
        chunks.sort(key=lambda x: x[1].name)

        dir_name, first_f, first_text = chunks[0]
        meta = parse_meta(first_text)

        # Combine conversation bodies; separate chunks with a horizontal rule
        all_bodies = []
        for _, _, text in chunks:
            body = get_conv_body(text)
            if body:
                all_bodies.append(body)
        combined_body = "\n\n---\n\n".join(all_bodies)

        conversations.append({
            "uuid":       uuid,
            "source":     meta.get("source") or dir_name,
            "type":       meta.get("type", ""),
            "date":       meta.get("date"),
            "date_str":   meta.get("date_str", ""),
            "file_count": len(chunks),
            "body":       combined_body,
            "summary":    get_summary(combined_body),
        })

    # Sort newest first; undated entries go to the end
    conversations.sort(
        key=lambda c: c["date"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    print(f"  Grouped into {len(conversations)} conversations")

    html = build_html(conversations)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"  Written: {OUTPUT_HTML}")
    print(f"Done. {len(conversations)} conversations rendered to hermes.html")


if __name__ == "__main__":
    main()
