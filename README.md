# 🌷 Eusha Command Center Dashboard

A dark-mode, vibes-first dashboard with two tabs:

- **🏥 Maternity Ward** — Agent birth countdown tracker (who's born, who's next)
- **📊 Token Usage** — Approximate Claude Max x20 capacity gauge

## Files

| File | Purpose |
|------|---------|
| `index.html` | Combined tabbed dashboard |
| `birth-monitor.html` | Original standalone maternity ward (preserved) |
| `usage-data.json` | Token usage data — agents write here, dashboard reads it |

## How It Works

### Token Tracking

The dashboard reads `usage-data.json` on load and every 30 seconds. Agents (or scripts) append session entries to track usage.

**Data format:**

```json
{
  "sessions": [
    {
      "ts": "2026-03-29T00:00:00Z",
      "model": "opus",
      "inputTokens": 12500,
      "outputTokens": 3200,
      "cachedTokens": 8000,
      "durationMs": 45000
    }
  ],
  "dailyTotals": [
    {
      "date": "2026-03-28",
      "opus": { "input": 150000, "output": 15000 },
      "sonnet": { "input": 0, "output": 0 }
    }
  ]
}
```

- **`sessions`** — Individual API calls/messages. The dashboard counts sessions within the 5-hour window to estimate gauge levels.
- **`dailyTotals`** — Aggregated daily token counts for the weekly bar chart.

### Claude Max x20 Limits (Reference)

| | 5-Hour Rolling Window | 7-Day Rolling Cap |
|---|---|---|
| **Opus** | ~200-350 messages | ~24-40 hours |
| **Sonnet** | ~700-900 messages | ~240-480 hours |

There's no fixed reset time. Capacity restores gradually as your oldest messages age past the 5-hour mark.

### Gauge Colors

- 🟢 **Green** (0-45%) — Plenty of capacity, go wild
- 🟡 **Yellow** (45-75%) — Moderate usage, be mindful
- 🔴 **Red** (75-100%) — Conserve, rate limit may hit soon

## Local Usage

Just open `index.html` in a browser:

```bash
# Windows
start dashboard/index.html

# Mac/Linux
open dashboard/index.html
```

The `usage-data.json` fetch works when served over HTTP. For local file:// usage, some browsers block fetch — use a local server:

```bash
cd dashboard
npx serve .
# or
python -m http.server 8080
```

## Deploy to GitHub Pages

1. **Create a repo** (or use an existing one):
   ```bash
   cd C:\Users\Iverson\.openclaw\dashboard
   git init
   git remote add origin https://github.com/YOUR_USER/eusha-dashboard.git
   ```

2. **Commit and push:**
   ```bash
   git add index.html usage-data.json README.md
   git commit -m "🌷 Eusha Command Center dashboard"
   git branch -M main
   git push -u origin main
   ```

3. **Enable GitHub Pages:**
   - Go to repo **Settings → Pages**
   - Source: **Deploy from a branch**
   - Branch: `main` / `/ (root)`
   - Save

4. **Access at:** `https://YOUR_USER.github.io/eusha-dashboard/`

### Auto-updating usage data on GitHub Pages

For live data on Pages, you'd need a GitHub Action or external script to periodically commit updated `usage-data.json`. For local use, agents write directly to the file.

## Writing Usage Data (for Agents)

Agents can append to `usage-data.json` after API calls. Example PowerShell snippet:

```powershell
$data = Get-Content "C:\Users\Iverson\.openclaw\dashboard\usage-data.json" | ConvertFrom-Json
$data.sessions += @{
    ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    model = "opus"
    inputTokens = 12500
    outputTokens = 3200
    cachedTokens = 8000
    durationMs = 45000
}
$data | ConvertTo-Json -Depth 5 | Set-Content "C:\Users\Iverson\.openclaw\dashboard\usage-data.json"
```

---

*Built for vibes, not spreadsheets.* 🌊
