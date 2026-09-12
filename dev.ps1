# Start both halves with auto-reload, in one window.
#
#   .\dev.ps1
#
# Backend  http://127.0.0.1:8000   restarts itself when a .py file changes
# Frontend http://127.0.0.1:5173   hot-reloads on save, no refresh needed
#
# Ctrl+C stops both. Use -BackendOnly or -FrontendOnly to run just one.
param(
  [switch]$BackendOnly,
  [switch]$FrontendOnly,
  [int]$ApiPort = 8000,
  [int]$WebPort = 5173
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "No venv at $py" }

# A port still held by an earlier run is the classic "my change did nothing"
# trap: uvicorn fails to bind, the old process keeps serving the old code, and
# the error scrolls past unread.
function Stop-Port([int]$port, [string]$label) {
  $held = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $held) {
    $owner = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
    if (-not $owner) {
      # Windows can leave a listening socket behind after its process dies. It
      # still answers requests, with whatever code it was running, and there is
      # no process left to kill. Only closing the owning terminal or rebooting
      # clears it -- and a new server bound to the same port loses every race.
      Write-Host "  !! $label port $port is held by a DEAD process (pid $($c.OwningProcess))." -ForegroundColor Red
      Write-Host "     It will keep serving stale code. Close the terminal it" -ForegroundColor Red
      Write-Host "     started in, reboot, or run:  .\dev.ps1 -ApiPort $($port + 1)" -ForegroundColor Red
      continue
    }
    Write-Host "  freeing $label port $port (pid $($c.OwningProcess))" -ForegroundColor DarkYellow
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
  }
  if ($held) { Start-Sleep -Seconds 2 }
}

$jobs = @()
try {
  if (-not $FrontendOnly) {
    Stop-Port $ApiPort 'backend'
    Write-Host "backend  -> http://127.0.0.1:$ApiPort  (reloads on .py change)" -ForegroundColor Cyan
    $jobs += Start-Job -Name api -ScriptBlock {
      param($root, $py, $port)
      Set-Location $root
      & $py -m uvicorn backend.api.app:app --host 127.0.0.1 --port $port --reload --reload-dir backend 2>&1
    } -ArgumentList $root, $py, $ApiPort
  }

  if (-not $BackendOnly) {
    Stop-Port $WebPort 'frontend'
    Write-Host "frontend -> http://127.0.0.1:$WebPort  (hot-reloads on save)" -ForegroundColor Cyan
    $jobs += Start-Job -Name web -ScriptBlock {
      param($root, $port, $api)
      Set-Location (Join-Path $root 'frontend')
      # Without this, -ApiPort moved the backend but the browser kept proxying
      # to 8000 and every call 404'd against whatever was still sitting there.
      $env:VITE_API_TARGET = "http://127.0.0.1:$api"
      & npm run dev -- --port $port 2>&1
    } -ArgumentList $root, $WebPort, $ApiPort
  }

  Write-Host "`nboth running. Ctrl+C to stop.`n" -ForegroundColor Green
  while ($true) {
    foreach ($j in $jobs) { Receive-Job -Job $j | ForEach-Object { Write-Host "[$($j.Name)] $_" } }
    $dead = $jobs | Where-Object { $_.State -eq 'Failed' -or $_.State -eq 'Completed' }
    if ($dead) { Write-Host "`n[$($dead[0].Name)] stopped." -ForegroundColor Red; break }
    Start-Sleep -Milliseconds 400
  }
} finally {
  foreach ($j in $jobs) { Stop-Job -Job $j -ErrorAction SilentlyContinue; Remove-Job -Job $j -Force -ErrorAction SilentlyContinue }
  if (-not $FrontendOnly) { Stop-Port $ApiPort 'backend' }
  if (-not $BackendOnly) { Stop-Port $WebPort 'frontend' }
  Write-Host 'stopped.' -ForegroundColor DarkGray
}
