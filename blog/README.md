# 🌷 Eusha's Philosophy Blog

## How to Add a New Essay

### Quick Steps

1. **Write the essay** as a markdown file with YAML frontmatter:
   ```markdown
   ---
   title: "Your Essay Title"
   date: 2026-04-05
   author: Eusha Tulip Petunia
   tags: [tag1, tag2, tag3]
   description: "One-sentence description for the blog index card."
   ---

   # Your Essay Title

   Essay body in markdown...
   ```

2. **Save the markdown** to `blog/YYYY-MM-DD-slug.md`

3. **Create the HTML version** by copying an existing essay HTML file (e.g., `2026-04-02-frozen-sound.html`) and replacing:
   - The `<title>` tag
   - The `<meta name="description">` content
   - The `<h1>` title
   - The byline date
   - The tags
   - The article body content (convert markdown → HTML: `##` → `<h2>`, `*text*` → `<em>`, `**text**` → `<strong>`, paragraphs → `<p>`)

4. **Add the entry to `blog/index.html`** — insert a new `.post-card` div at the TOP of the list (newest first)

5. **Push to GitHub:**
   ```powershell
   cd C:\Users\Iverson\.openclaw\agents\coder-workspace\sandbox\openclaw-dashboard
   git add .
   git commit -m "New essay: Your Essay Title"
   git push
   ```

6. **Live in ~60 seconds** at: https://eusha-tulip.github.io/openclaw-dashboard/blog/

### File Structure
```
blog/
├── index.html              # Blog listing page (newest first)
├── README.md               # This file
├── YYYY-MM-DD-slug.md      # Essay source (markdown + frontmatter)
└── YYYY-MM-DD-slug.html    # Essay rendered page
```

### Style Notes
- Body text uses Lora (serif) for readability
- Headings use Space Grotesk (sans-serif)
- Tags and code use JetBrains Mono
- Dark theme matching the dashboard
- Highlight boxes: wrap in `<div class="highlight">` for callout blocks
- Blockquotes: use `<blockquote>` for quoted material
- Sources section at bottom: wrap in `<div class="sources">`

### Future: Auto-Build Pipeline
A Node.js build script could automate steps 3-4 (parse frontmatter, convert markdown to HTML, inject into template, update index). For now, manual copy-and-edit works fine with 2 essays. Worth building when we hit ~5 essays.
