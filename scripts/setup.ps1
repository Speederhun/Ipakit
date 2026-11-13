$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $PSScriptRoot
$home_   = Join-Path $env:LOCALAPPDATA "Ipakit"
$venv    = Join-Path $home_ "venv"
$binDir  = Join-Path $env:APPDATA "Ipakit\bin"
New-Item -ItemType Directory -Force $home_, $binDir | Out-Null

function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }

# 1) Python
Step "Python"
function Find-Python {
    foreach ($c in @("py -3", "python")) {
        try { $v = & cmd /c "$c --version 2>&1"; if ($v -match "Python 3\.(1[0-9]|[2-9][0-9])") { return $c } } catch {}
    }
    $p = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { return "`"$($p.FullName)`"" }
    return $null
}
$py = Find-Python
if (-not $py) {
    Write-Host "Installing Python 3.12 with winget..."
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    $py = Find-Python
    if (-not $py) { throw "Python install failed. Install Python 3.10+ manually and run this again." }
}
Write-Host "Using: $py"

# 2) Apple USB driver (comes with iTunes)
Step "Apple Mobile Device driver"
if (-not (Get-Service "Apple Mobile Device Service" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing iTunes (for the iPhone USB driver)..."
    winget install -e --id Apple.iTunes --silent --accept-package-agreements --accept-source-agreements
} else { Write-Host "Already installed." }

# 3) Ipakit in its own virtual environment
Step "Ipakit"
if (-not (Test-Path "$venv\Scripts\python.exe")) { & cmd /c "$py -m venv `"$venv`"" }
& "$venv\Scripts\python.exe" -m pip install --upgrade pip
& "$venv\Scripts\python.exe" -m pip install --upgrade "$root"

# 4) zsign
Step "zsign"
if (-not (Test-Path "$binDir\zsign.exe")) {
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/zhlynn/zsign/releases/latest" -Headers @{ "User-Agent" = "ipakit" }
        $asset = $rel.assets | Where-Object { $_.name -match "win" } | Select-Object -First 1
        if ($asset) {
            $zip = Join-Path $env:TEMP "zsign.zip"
            Invoke-WebRequest $asset.browser_download_url -OutFile $zip
            $tmp = Join-Path $env:TEMP "zsign_x"
            Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
            if ($asset.name -match "\.zip$") { Expand-Archive $zip $tmp -Force } else { New-Item -ItemType Directory $tmp | Out-Null; Copy-Item $zip "$tmp\zsign.exe" }
            $exe = Get-ChildItem $tmp -Recurse -Filter "zsign*.exe" | Select-Object -First 1
            if ($exe) { Copy-Item $exe.FullName "$binDir\zsign.exe" -Force }
        }
    } catch { Write-Host "Auto-download failed: $_" -ForegroundColor Yellow }
    if (-not (Test-Path "$binDir\zsign.exe")) {
        Write-Host "Could not fetch zsign automatically. Put zsign.exe into: $binDir" -ForegroundColor Yellow
    }
} else { Write-Host "Already present." }

# 5) Desktop icon
Step "Desktop shortcut"
Copy-Item (Join-Path $root "assets\ipakit.ico") (Join-Path $home_ "ipakit.ico") -Force
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $desktop "Ipakit.lnk"))
$lnk.TargetPath       = "$venv\Scripts\pythonw.exe"
$lnk.Arguments        = "-m ipakit.gui"
$lnk.WorkingDirectory = $home_
$lnk.IconLocation     = (Join-Path $home_ "ipakit.ico")
$lnk.Description      = "Ipakit"
$lnk.Save()

Write-Host "`nDone. Start Ipakit from the desktop icon." -ForegroundColor Green
