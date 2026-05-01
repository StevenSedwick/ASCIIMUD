# ASCIIMUD Twitch extension submission packager.
# Produces dist/asciimud-twitch-ext.zip with only the runtime assets that
# Twitch reviewers expect (no node_modules, no dotfiles, all paths relative).

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$dist = Join-Path $here "dist"
$staging = Join-Path $dist "_stage"
$zipPath = Join-Path $dist "asciimud-twitch-ext.zip"

if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Path $staging | Out-Null

$files = @(
  "viewer.html", "viewer.js", "viewer.css",
  "config.html", "config.js", "config.css",
  "app.js", "icons.js", "style.css"
)

foreach ($f in $files) {
  if (-not (Test-Path $f)) {
    Write-Error "missing required file: $f"
  }
  Copy-Item $f -Destination $staging
}

if (Test-Path "assets") {
  Copy-Item -Recurse "assets" -Destination $staging
}

Push-Location $staging
try {
  $items = Get-ChildItem -Force | ForEach-Object { $_.Name }
  Compress-Archive -Path $items -DestinationPath $zipPath -Force
} finally {
  Pop-Location
}
Remove-Item -Recurse -Force $staging

Write-Host "Built $zipPath" -ForegroundColor Green
Write-Host ("  size: {0:N1} KB" -f ((Get-Item $zipPath).Length / 1KB))
