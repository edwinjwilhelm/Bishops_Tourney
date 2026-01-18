Param(
  [string]$SourceGlob = 'C:\Bishops_chatGPT\Bishops_Netplay_Engineering_Summary_*.html',
  [string]$OutDir = 'C:\Bishops_chatGPT\backups\chat_exports',
  [string]$UsbDrive = 'D:'
)

$ErrorActionPreference = 'Stop'

function Get-LatestFile([string]$Pattern){
  $files = Get-ChildItem -LiteralPath (Split-Path $Pattern -Parent) -Filter (Split-Path $Pattern -Leaf) -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
  if($files -and $files.Count -gt 0){ return $files[0].FullName }
  return $null
}

function Get-EdgePath(){
  $candidates = @(
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
  )
  foreach($p in $candidates){ if(Test-Path $p){ return $p } }
  return $null
}

function Get-ChromePath(){
  $candidates = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
  )
  foreach($p in $candidates){ if(Test-Path $p){ return $p } }
  return $null
}

function Server-IsUp($url){
  try { $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; return $r.StatusCode -ge 200 -and $r.StatusCode -lt 400 } catch { return $false }
}

if(!(Test-Path $OutDir)){ New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

$src = $null

# Prefer HTTP host page if server is up (avoids file:// restrictions)
if(Server-IsUp 'http://127.0.0.1:8000/static/host_link.html'){
  $src = 'http://127.0.0.1:8000/static/host_link.html'
} else {
  $src = Get-LatestFile -Pattern $SourceGlob
  if(-not $src){
    # Fallback to a simple local page
    $fallback = 'C:\Bishops_chatGPT\netplay\static\host_link.html'
    if(Test-Path $fallback){ $src = $fallback }
  }
}
if(-not $src){ Write-Host 'No source HTML found.'; exit 1 }

$edge = Get-EdgePath
$chrome = Get-ChromePath
if(-not $edge -and -not $chrome){ Write-Host 'No Chromium browser found (Edge/Chrome).'; exit 1 }

$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm'
$outfile = Join-Path $OutDir ("Bishops_Chat_" + $stamp + '.pdf')

# Convert Windows path to file:/// URL
$useUrl = $src
if($src -notmatch '^https?://'){
  $useUrl = 'file:///' + ($src -replace '\\','/')
}

function Try-Pdf($bin, $url, $out){
  if(-not (Test-Path $bin)){ return }
  # Prefer modern headless
  & $bin --headless=new --disable-gpu --allow-file-access-from-files --virtual-time-budget=4000 --run-all-compositor-stages-before-draw --print-to-pdf="$out" "$url" | Out-Null
  Start-Sleep -Milliseconds 600
  if(!(Test-Path $out)){
    # Fallback to legacy headless
    & $bin --headless --disable-gpu --allow-file-access-from-files --virtual-time-budget=4000 --run-all-compositor-stages-before-draw --print-to-pdf="$out" "$url" | Out-Null
    Start-Sleep -Milliseconds 600
  }
}

# Try Edge, then Chrome
if($edge){ Try-Pdf -bin $edge -url $useUrl -out $outfile }
if(!(Test-Path $outfile) -and $chrome){ Try-Pdf -bin $chrome -url $useUrl -out $outfile }

if(!(Test-Path $outfile)){
  Write-Host ('Failed to create PDF: ' + $outfile)
  exit 1
}

Write-Host ('PDF written: ' + $outfile)

# Optional copy to USB drive root
try{
  if($UsbDrive -and (Test-Path ($UsbDrive + '\\'))){
    Copy-Item -LiteralPath $outfile -Destination ($UsbDrive + '\\') -Force
    Write-Host ('Copied to ' + $UsbDrive + '\\')
  }
} catch { Write-Host 'USB copy skipped: ' + $_.Exception.Message }

exit 0
