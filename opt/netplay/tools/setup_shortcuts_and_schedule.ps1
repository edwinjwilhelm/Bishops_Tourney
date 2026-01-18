Param(
  [int]$Port = 8000,
  [string]$Desktop = [Environment]::GetFolderPath('Desktop'),
  [string]$UsbRoot = 'D:',
  [string]$ScheduleTime = '09:00'
)

$ErrorActionPreference = 'Stop'

function Write-Info([string]$m){ Write-Host $m -ForegroundColor Cyan }
function Write-Ok([string]$m){ Write-Host $m -ForegroundColor Green }
function Write-Warn([string]$m){ Write-Host $m -ForegroundColor Yellow }
function Write-Err([string]$m){ Write-Host $m -ForegroundColor Red }

$repo = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $repo 'tools'
$shortDir = Join-Path $tools 'shortcuts'

# 1) Generate fresh LAN shortcuts (includes Local + LAN + Chess)
Write-Info 'Generating LAN shortcuts...'
& powershell -ExecutionPolicy Bypass -File (Join-Path $tools 'generate_lan_shortcuts.ps1') -Port $Port -OutDir $shortDir

# 2) Copy shortcuts to Desktop
if (Test-Path $Desktop) {
  Write-Info "Copying shortcuts to Desktop: $Desktop"
  Get-ChildItem -LiteralPath $shortDir -Filter *.url -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Desktop $_.Name) -Force
  }
} else { Write-Warn "Desktop not found: $Desktop" }

# 3) Copy shortcuts to USB (root) if present
try {
  if ($UsbRoot -and (Test-Path ($UsbRoot + '\\'))) {
    Write-Info "Copying shortcuts to USB: $UsbRoot\\"
    Get-ChildItem -LiteralPath $shortDir -Filter *.url -File | ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination (Join-Path ($UsbRoot + '\\') $_.Name) -Force
    }
  } else {
    Write-Warn 'USB root not available; skipping USB copy.'
  }
} catch { Write-Warn ("USB copy skipped: " + $_.Exception.Message) }

# 4) Ensure backup folder for PDFs exists
$backupDir = Join-Path $repo 'backups\chat_exports'
if (!(Test-Path $backupDir)) { New-Item -ItemType Directory -Force -Path $backupDir | Out-Null }

# 5) Register a Windows Scheduled Task for daily 9:00 AM exports
#    (a) Netplay Host UI to PDF via tools/print_chat_pdf.ps1
#    (b) Rules (from Golden) to docs/rules.pdf via tools/export_rules_scheduled.ps1
$psExe = (Get-Command powershell.exe).Source
$taskName = 'Bishops Daily PDF Export'
$scriptPath = Join-Path $tools 'print_chat_pdf.ps1'
$action = New-ScheduledTaskAction -Execute $psExe -Argument ("-ExecutionPolicy Bypass -File `"$scriptPath`" -OutDir `"$backupDir`" -UsbDrive `"$UsbRoot`"")
# Secondary task: Rules export
$rulesTask = 'Bishops Daily Rules Export'
$rulesScript = Join-Path $tools 'export_rules_scheduled.ps1'
$rulesOut = (Join-Path $repo 'docs')
$rulesAction = New-ScheduledTaskAction -Execute $psExe -Argument ("-ExecutionPolicy Bypass -File `"$rulesScript`" -OutDir `"$rulesOut`"")
# Parse time string HH:mm to build a 24h TimeSpan today. If time passed today, it will still schedule as daily at that time.
try {
  $timeParts = $ScheduleTime.Split(':'); if ($timeParts.Length -lt 2) { throw 'Invalid time' }
  $hour = [int]$timeParts[0]; $min = [int]$timeParts[1]
  $trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours($hour).AddMinutes($min))
} catch {
  Write-Warn 'Invalid ScheduleTime; defaulting to 9:00 AM.'
  $trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours(9))
}

# Run with highest privileges to avoid policy issues when printing

# Attempt Highest privileges first; if Access Denied, fall back to Limited
$principalHigh = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$principalLimited = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Register or update the task
function Register-ExportTask([Microsoft.Management.Infrastructure.CimInstance]$principal){
  if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
  }
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Description 'Exports Bishops Host page to PDF daily at 9am and copies to USB if present.' | Out-Null
  if (Get-ScheduledTask -TaskName $rulesTask -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $rulesTask -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
  }
  Register-ScheduledTask -TaskName $rulesTask -Action $rulesAction -Trigger $trigger -Principal $principal -Description 'Exports Bishops rules (from Golden) to docs/rules.pdf daily at 9am.' | Out-Null
}

try {
  Register-ExportTask -principal $principalHigh
  Write-Ok "Scheduled task registered (Highest): $taskName at $ScheduleTime"
  Write-Ok "Scheduled task registered (Highest): $rulesTask at $ScheduleTime"
} catch {
  Write-Warn ("Highest run-level registration failed: " + $_.Exception.Message)
  try {
    Register-ExportTask -principal $principalLimited
    Write-Ok "Scheduled task registered (Limited): $taskName at $ScheduleTime"
    Write-Ok "Scheduled task registered (Limited): $rulesTask at $ScheduleTime"
  } catch {
    Write-Warn ("Failed to register scheduled task (Limited): " + $_.Exception.Message)
  }
}

Write-Ok 'Shortcuts deployed and schedule setup complete.'
