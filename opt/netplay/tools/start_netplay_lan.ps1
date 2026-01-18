Param(
  [int]$Port = 8000
)

# Bishops Netplay - LAN starter (Windows PowerShell)
# - Creates an isolated venv (.lanvenv), installs deps, opens firewall on Private network, and runs the server on 0.0.0.0
# - Usage: Right-click → Run with PowerShell (or run: powershell -ExecutionPolicy Bypass -File tools\start_netplay_lan.ps1)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$msg){ Write-Host $msg -ForegroundColor Cyan }
function Write-Ok([string]$msg){ Write-Host $msg -ForegroundColor Green }
function Write-Warn([string]$msg){ Write-Host $msg -ForegroundColor Yellow }
function Write-Err([string]$msg){ Write-Host $msg -ForegroundColor Red }

$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo

# Pick a Python launcher
$pyLauncher = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $pyLauncher = 'py -3' }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pyLauncher = 'python' }
else { Write-Err 'Python not found. Please install Python 3.10+ from https://www.python.org/downloads/'; exit 1 }

$venvPath = Join-Path $repo '.lanvenv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

Write-Info "Creating/updating virtual environment at: $venvPath"
if (-not (Test-Path $venvPython)) {
  iex "$pyLauncher -m venv `"$venvPath`""
}

Write-Info 'Upgrading pip and installing requirements (netplay/requirements.txt)'
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $repo 'netplay\requirements.txt')

# Try to open firewall (Private profile) for the chosen port
try {
  Write-Info "Opening Windows Firewall for TCP port $Port (Private network)"
  New-NetFirewallRule -DisplayName "Bishops Netplay $Port" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private -ErrorAction SilentlyContinue | Out-Null
} catch { Write-Warn "Couldn't add firewall rule automatically; if clients can't connect, allow port $Port inbound on this PC." }

# Show likely LAN IPs
try {
  $ips = Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress
  if (-not $ips) { $ips = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress) }
} catch { $ips = @() }

Write-Host ''
Write-Ok 'Bishops Netplay server starting...'
if ($ips) {
  Write-Info 'From other devices on Wi-Fi (laptops, iPads), open one of:'
  foreach ($ip in $ips) { Write-Host ("  http://{0}:{1}" -f $ip, $Port) -ForegroundColor White }
} else {
  Write-Warn 'Could not auto-detect LAN IP; run ipconfig and use the IPv4 Address of your active adapter.'
}
Write-Host ''

# Start uvicorn (no auto-reload for stability on LAN)
& $venvPython -m uvicorn netplay.server:app --host 0.0.0.0 --port $Port
