Param(
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$m){ Write-Host $m -ForegroundColor Cyan }
function Write-Ok([string]$m){ Write-Host $m -ForegroundColor Green }
function Write-Warn([string]$m){ Write-Host $m -ForegroundColor Yellow }
function Write-Err([string]$m){ Write-Host $m -ForegroundColor Red }

$repo = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $repo 'tools'
$script = Join-Path $tools 'export_rules.py'
if (!(Test-Path $script)) { Write-Err "export_rules.py not found: $script"; exit 2 }

# Determine Python
$py = $null
$venvPy = Join-Path $repo '.venv\Scripts\python.exe'
if (Test-Path $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = 'py' }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = 'python' }
else { Write-Warn 'Python not found on PATH; attempting "python" anyway.'; $py = 'python' }

if (-not $OutDir) { $OutDir = (Join-Path $repo 'docs') }
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

Write-Info "Exporting rules to $OutDir ..."
try {
  & $py $script --out $OutDir | Write-Output
  Write-Ok 'Rules export complete.'
} catch {
  Write-Err ("Rules export failed: " + $_.Exception.Message)
  exit 2
}
