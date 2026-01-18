Param(
  [int]$Port = 8000,
  [string]$OutDir = '.'
)

$ErrorActionPreference = 'Stop'

function New-InternetShortcut([string]$Path, [string]$Url){
  $content = "[InternetShortcut]`r`nURL=$Url`r`nIconIndex=0`r`n"
  Set-Content -LiteralPath $Path -Value $content -Encoding ASCII -Force
}

if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

# Localhost shortcuts (for the host laptop)
New-InternetShortcut -Path (Join-Path $OutDir 'Open Netplay (Host Local).url') -Url ("http://127.0.0.1:{0}" -f $Port)
New-InternetShortcut -Path (Join-Path $OutDir 'Open Netplay UI (Host Local).url') -Url ("http://127.0.0.1:{0}/static/index.html" -f $Port)
New-InternetShortcut -Path (Join-Path $OutDir 'Bishops - Join Random (Local).url') -Url ("http://127.0.0.1:{0}/static/join_random.html" -f $Port)
New-InternetShortcut -Path (Join-Path $OutDir 'Bishops - Join Chess (Local).url') -Url ("http://127.0.0.1:{0}/static/join_chess.html" -f $Port)
New-InternetShortcut -Path (Join-Path $OutDir 'Bishops - Host Link (Local).url') -Url ("http://127.0.0.1:{0}/static/host_link.html" -f $Port)

# Try to detect LAN IPv4 addresses
try {
  $ips = Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress
  if (-not $ips) { $ips = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress) }
} catch { $ips = @() }

if ($ips) {
  $i = 1
  foreach($ip in $ips) {
    $name = "Open Netplay (LAN #{0}).url" -f $i
    New-InternetShortcut -Path (Join-Path $OutDir $name) -Url ("http://{0}:{1}" -f $ip, $Port)

    $name2 = "Open Netplay UI (LAN #{0}).url" -f $i
    New-InternetShortcut -Path (Join-Path $OutDir $name2) -Url ("http://{0}:{1}/static/index.html" -f $ip, $Port)

    $name3 = "Bishops - Join Random (LAN #{0}).url" -f $i
    New-InternetShortcut -Path (Join-Path $OutDir $name3) -Url ("http://{0}:{1}/static/join_random.html" -f $ip, $Port)

    $name3b = "Bishops - Join Chess (LAN #{0}).url" -f $i
    New-InternetShortcut -Path (Join-Path $OutDir $name3b) -Url ("http://{0}:{1}/static/join_chess.html" -f $ip, $Port)

  $name4 = "Bishops - Host Link (LAN #{0}).url" -f $i
  New-InternetShortcut -Path (Join-Path $OutDir $name4) -Url ("http://{0}:{1}/static/host_link.html" -f $ip, $Port)
    $i++
  }
}

Write-Host "LAN shortcuts written to" (Resolve-Path $OutDir)
