param(
    [string]$ServerHost = '127.0.0.1',
    [int]$ServerPort = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

# Resolve repo root (script location) and existing server launcher
$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
Set-Location $scriptDir
$serverScript = Join-Path $scriptDir 'start_netplay.ps1'

if (-not (Test-Path $serverScript)) {
    Write-Error "Could not locate start_netplay.ps1 at $serverScript"
    exit 1
}

# Fire up the server in a separate PowerShell window so it keeps running
$serverArgs = @(
    '-NoExit',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $serverScript
)

$serverProc = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList $serverArgs `
    -WorkingDirectory $scriptDir `
    -WindowStyle Normal `
    -PassThru

if (-not $serverProc) {
    Write-Error 'Failed to launch the netplay server window.'
    exit 1
}

if ($NoBrowser) {
    Write-Host "Server window launched (PID $($serverProc.Id)). Skipping browser auto-open."
    exit 0
}

# Wait briefly for the server to come up before popping the client UI
$baseUrl = "http://$ServerHost`:$ServerPort"
$deadline = (Get-Date).AddSeconds(12)
$ready = $false

while ((Get-Date) -lt $deadline) {
    try {
        Invoke-WebRequest -Uri $baseUrl -UseBasicParsing -TimeoutSec 1 | Out-Null
        $ready = $true
        break
    }
    catch {
        Start-Sleep -Milliseconds 400
    }
}

$clientUrl = "$baseUrl/static/index_v2.html?v=20251102"

if (-not $ready) {
    Write-Warning "Server didn't respond yet; opening client anyway at $clientUrl"
}

Start-Process $clientUrl | Out-Null
Write-Host "Server window launched (PID $($serverProc.Id)). Browser pointed at $clientUrl"
