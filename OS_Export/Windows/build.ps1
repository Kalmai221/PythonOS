<#
Build the Windows packages: dist\windows\PythonOS-<version>-windows-portable.zip
(and, with Inno Setup installed, PythonOS-<version>-setup.exe).

    $env:VERSION = "1.2.0"; powershell -File OS_Export\Windows\build.ps1

The package bundles its own Python (the official "embeddable" build) with every
dependency installed, so users do not need Python installed. PythonOS.exe is a small
PyInstaller-built launcher that starts it. The OS itself is NOT in the package: on first
start the launcher runs bootstrap.py, which downloads the latest core from GitHub releases.
#>
param(
    [string]$PythonVersion = "3.12.8"
)
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
$Out = Join-Path $Repo "dist\windows"
$Version = (python "$Repo\OS_Export\stage.py" --print-version).Trim()
$App = Join-Path $Out "PythonOS"

if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Path $Out | Out-Null

# 1. Just the bootstrap script - the OS is downloaded on first run
New-Item -ItemType Directory -Path $App | Out-Null
Copy-Item (Join-Path $Repo "OS_Export\bootstrap.py") (Join-Path $App "bootstrap.py")

# 2. An embedded Python runtime
$Runtime = Join-Path $App "python"
$EmbedZip = Join-Path $Out "python-embed.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
Write-Host "Downloading Python $PythonVersion ..."
Invoke-WebRequest -Uri $EmbedUrl -OutFile $EmbedZip
Expand-Archive -Path $EmbedZip -DestinationPath $Runtime
Remove-Item $EmbedZip

# The embeddable build ignores PYTHONPATH and the script folder, so list the search
# path explicitly: the stdlib zip, the runtime itself, the OS root (..) and site-packages.
$Pth = Get-ChildItem $Runtime -Filter "python*._pth" | Select-Object -First 1
$ZipName = ($Pth.BaseName -replace "\._pth$", "") + ".zip"
@($ZipName, ".", "..", "Lib\site-packages", "import site") | Set-Content -Path $Pth.FullName -Encoding ascii

# 3. pip, then the dependencies
$GetPip = Join-Path $Out "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
& "$Runtime\python.exe" $GetPip --no-warn-script-location --quiet
if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }
Remove-Item $GetPip
& "$Runtime\python.exe" -m pip install --no-warn-script-location --quiet `
    -r (Join-Path $Repo "requirements.txt") -r (Join-Path $Repo "boot-requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "installing dependencies failed" }
Get-ChildItem $App -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 4. PythonOS.exe launcher (PyInstaller, running on the build machine's Python)
python -m pip install --quiet pyinstaller pillow
if ($LASTEXITCODE -ne 0) { throw "installing PyInstaller failed" }
$Work = Join-Path $Out "pyinstaller"
$IconArgs = @()
$IconFile = Join-Path $Repo "generated-icon.png"
if (Test-Path $IconFile) { $IconArgs = @("--icon", $IconFile) }
python -m PyInstaller --onefile --console --name PythonOS @IconArgs `
    --distpath $App --workpath $Work --specpath $Work (Join-Path $Here "launcher.py")
if ($LASTEXITCODE -ne 0 -and $IconArgs.Count -gt 0) {
    Write-Host "Icon conversion failed - building the launcher without an icon."
    python -m PyInstaller --onefile --console --name PythonOS `
        --distpath $App --workpath $Work --specpath $Work (Join-Path $Here "launcher.py")
}
if (-not (Test-Path (Join-Path $App "PythonOS.exe"))) { throw "PythonOS.exe was not built" }
Remove-Item $Work -Recurse -Force

# 5. Portable zip
$Zip = Join-Path $Out "PythonOS-$Version-windows-portable.zip"
Compress-Archive -Path $App -DestinationPath $Zip
Write-Host "Built $Zip"

# 6. Installer (optional)
$Iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $Candidate = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $Candidate) { $Iscc = $Candidate }
}
if ($Iscc) {
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$App" "/DOutputDir=$Out" (Join-Path $Here "PythonOS.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    Write-Host "Built installer"
} else {
    Write-Host "Inno Setup not found - skipping the installer (portable zip is ready)."
}
Get-ChildItem $Out
