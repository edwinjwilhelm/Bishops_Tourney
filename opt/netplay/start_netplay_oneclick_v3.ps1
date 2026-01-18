param(
    [string]$ServerHost = '127.0.0.1',
    [int]$ServerPort = 8200,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

# Resolve repo root (script location) and existing server launcher
$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
Set-Location $scriptDir
$serverScript = Join-Path $scriptDir 'start_netplay_v3_server.ps1'

if (-not (Test-Path $serverScript)) {
    Write-Error "Could not locate start_netplay.ps1 at $serverScript"
    exit 1
}

# Detect existing server by listening socket on ServerPort; reuse if present
$existingServer = $null
try {
    $existingServer = Get-NetTCPConnection -State Listen -LocalPort $ServerPort -ErrorAction Stop | Select-Object -First 1
} catch {
    $existingServer = $null
}

$serverProc = $null
if (-not $existingServer) {
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
} else {
    Write-Host "Detected existing server on port $ServerPort; reusing it."
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

$clientUrl = "$baseUrl/static/index_v3.html?v=20251103"

if (-not $ready) {
    $source = "existing server"
    if ($serverProc) { $source = "new server" }
    Write-Warning "Server didn't respond yet (checked $source); opening client anyway at $clientUrl"
}

# Prefer Firefox for the v3 client; fall back to default browser if unavailable
$firefoxCandidates = @(
    "$Env:ProgramFiles\Mozilla Firefox\firefox.exe",
    "$Env:ProgramFiles(x86)\Mozilla Firefox\firefox.exe",
    "firefox"
)
$firefoxPath = $firefoxCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($firefoxPath) {
    try {
        Start-Process -FilePath $firefoxPath -ArgumentList $clientUrl | Out-Null
        if ($serverProc) {
            Write-Host "Server window launched (PID $($serverProc.Id)). Firefox pointed at $clientUrl"
        } else {
            Write-Host "Reused existing server on port $ServerPort. Firefox pointed at $clientUrl"
        }
        return
    } catch {
        Write-Warning "Firefox launch failed ($_). Falling back to default browser."
    }
}

Start-Process $clientUrl | Out-Null
if ($serverProc) {
    Write-Host "Server window launched (PID $($serverProc.Id)). Browser pointed at $clientUrl"
} else {
    Write-Host "Reused existing server on port $ServerPort. Browser pointed at $clientUrl"
}
