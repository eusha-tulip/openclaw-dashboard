# update-usage.ps1 — Pull real token usage from OpenClaw sessions into usage-data.json
# Run periodically or before pushing dashboard updates

$ErrorActionPreference = 'Stop'
$dashDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Get session data from openclaw
$raw = openclaw status --json 2>&1 | Out-String
$status = $raw | ConvertFrom-Json
$allSessions = @()

foreach ($byAgent in $status.sessions.byAgent) {
    foreach ($s in $byAgent.recent) {
        $model = 'opus'
        if ($s.model -match 'sonnet') { $model = 'sonnet' }
        elseif ($s.model -match 'haiku') { $model = 'haiku' }

        # Skip duplicates (cron run keys duplicate the cron key)
        if ($s.key -match ':run:') { continue }

        $ts = [DateTimeOffset]::FromUnixTimeMilliseconds($s.updatedAt).ToString('o')
        $inputTok = if ($null -ne $s.inputTokens) { $s.inputTokens } else { 0 }
        $outputTok = if ($null -ne $s.outputTokens) { $s.outputTokens } else { 0 }
        $cachedTok = if ($null -ne $s.cacheRead) { $s.cacheRead } else { 0 }
        $totalTok = if ($null -ne $s.totalTokens) { $s.totalTokens } else { 0 }

        $allSessions += @{
            ts = $ts
            model = $model
            agentId = $s.agentId
            inputTokens = $inputTok
            outputTokens = $outputTok
            cachedTokens = $cachedTok
            totalTokens = $totalTok
            percentUsed = if ($null -ne $s.percentUsed) { $s.percentUsed } else { 0 }
        }
    }
}

# Build daily totals from sessions grouped by date
$dailyMap = @{}
foreach ($s in $allSessions) {
    $date = ([DateTimeOffset]::Parse($s.ts)).ToString('yyyy-MM-dd')
    if (-not $dailyMap.ContainsKey($date)) {
        $dailyMap[$date] = @{
            date = $date
            opus = @{ input = 0; output = 0 }
            sonnet = @{ input = 0; output = 0 }
        }
    }
    $m = $s.model
    if ($m -eq 'opus' -or $m -eq 'sonnet') {
        $dailyMap[$date][$m].input += $s.inputTokens + $s.cachedTokens
        $dailyMap[$date][$m].output += $s.outputTokens
    }
}

$dailyTotals = $dailyMap.Values | Sort-Object { $_.date }

$output = @{
    generatedAt = (Get-Date).ToUniversalTime().ToString('o')
    sessions = $allSessions
    dailyTotals = $dailyTotals
} | ConvertTo-Json -Depth 5

$output | Set-Content -Path (Join-Path $dashDir 'usage-data.json') -Encoding UTF8

Write-Host "Updated usage-data.json with $($allSessions.Count) sessions, $($dailyTotals.Count) daily entries" -ForegroundColor Green
