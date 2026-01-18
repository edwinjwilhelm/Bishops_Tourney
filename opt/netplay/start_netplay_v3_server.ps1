
$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
Set-Location $scriptDir

python -m uvicorn netplay.server_v3:app --reload --host 0.0.0.0 --port 8200

