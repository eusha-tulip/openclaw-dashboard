# OpenClaw Dashboard - Deploy to GitHub Pages
# Run this script from the dashboard directory

$ghPath = "C:\Users\Iverson\AppData\Local\Temp\gh-cli\bin\gh.exe"

# Check if already authenticated
$authStatus = & $ghPath auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged into GitHub. Starting login..." -ForegroundColor Yellow
    & $ghPath auth login --hostname github.com --git-protocol https --web
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GitHub login failed. Exiting." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Authenticated with GitHub!" -ForegroundColor Green

# Create the repo
& $ghPath repo create openclaw-dashboard --public --source=. --remote=origin --push
if ($LASTEXITCODE -ne 0) {
    Write-Host "Repo creation failed - it may already exist. Trying to push..." -ForegroundColor Yellow
    git remote add origin "https://github.com/$(& $ghPath api user --jq .login)/openclaw-dashboard.git" 2>$null
    git push -u origin master
}

# Enable GitHub Pages
$owner = & $ghPath api user --jq ".login"
& $ghPath api "repos/$owner/openclaw-dashboard/pages" --method POST --input - 2>$null <<EOF
{"build_type":"legacy","source":{"branch":"master","path":"/"}}
EOF

Write-Host ""
Write-Host "Dashboard deployed! It should be live at:" -ForegroundColor Green
Write-Host "  https://$owner.github.io/openclaw-dashboard/" -ForegroundColor Cyan
Write-Host ""
Write-Host "(It may take 1-2 minutes for GitHub Pages to build)" -ForegroundColor Yellow
