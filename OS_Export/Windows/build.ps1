<#
Build the Windows packages: dist\windows\PythonOS-<version>-windows-portable.zip
(and, with Inno Setup installed, PythonOS-<version>-setup.exe).

    $env:VERSION = "1.2.0"; powershell -File OS_Export\Windows\build.ps1

The package bundles its own Python (the official "embeddable" build) with every
dependency installed, so users do not need Python installed. PythonOS.exe is the PythonOS window
(WebView2 + xterm.js + a pseudo console, see build-native.ps1); PythonOS-console.exe is the plain
console launcher (PyInstaller) it falls back to. The OS itself is NOT in the package: on first
start start.py runs bootstrap.py, which downloads the latest core from GitHub releases.
Also built: PythonOS-<version>-web-setup.exe, a 100 KB installer that downloads and checks all of this.
#>
param(
    [string]$PythonVersion = "3.12.8",
    [ValidateSet("x64", "arm64")][string]$Arch = "x64"      # arm64: Windows on ARM (Surface Pro X, Copilot+ PCs, ARM VMs)
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
Copy-Item (Join-Path $Here "start.py") (Join-Path $App "start.py")
# Which package this is, so PythonOS can say when a newer one must be installed by hand
python (Join-Path $Repo "OS_Export\stage.py") --write-export windows (Join-Path $App "export.json")

# 2. An embedded Python runtime
$Runtime = Join-Path $App "python"
$EmbedZip = Join-Path $Out "python-embed.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-" + $(if ($Arch -eq "arm64") { "arm64" } else { "amd64" }) + ".zip"
$Tag = if ($Arch -eq "arm64") { "-arm64" } else { "" }          # file names: ...-windows-arm64-portable.zip, ...-arm64-setup.exe
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
if ($Arch -eq "arm64") {
    # The ARM64 Python cannot run on this (x64) build machine, so its libraries are fetched as ARM64 wheels and unpacked into its
    # site-packages with the build machine's own pip; pip itself goes in too, so `python -m pip` works on the ARM64 PC (the requirement
    # checks use it). Everything PythonOS imports is pure Python or has a win_arm64 wheel.
    $Site = Join-Path $Runtime "Lib\site-packages"
    New-Item -ItemType Directory -Force -Path $Site | Out-Null
    python -m pip install --quiet --target $Site --platform win_arm64 --python-version 3.12 --implementation cp --abi cp312 --only-binary=:all: `
        pip -r (Join-Path $Repo "requirements.txt") -r (Join-Path $Repo "boot-requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "installing the ARM64 dependencies failed" }
} else {
    $GetPip = Join-Path $Out "get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
    & "$Runtime\python.exe" $GetPip --no-warn-script-location --quiet
    if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }
    Remove-Item $GetPip
    & "$Runtime\python.exe" -m pip install --no-warn-script-location --quiet `
        -r (Join-Path $Repo "requirements.txt") -r (Join-Path $Repo "boot-requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "installing dependencies failed" }
}
Get-ChildItem $App -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 4. PythonOS.exe launcher (PyInstaller, running on the build machine's Python)
python -m pip install --quiet pyinstaller pillow
if ($LASTEXITCODE -ne 0) { throw "installing PyInstaller failed" }
$Work = Join-Path $Out "pyinstaller"
# Installer artwork and the icon, drawn by make_art.py
$Art = Join-Path $Out "installer-art"
python (Join-Path $Here "make_art.py") $Art
$IconArgs = @()
$IconFile = Join-Path $Art "PythonOS.ico"
if (Test-Path $IconFile) { $IconArgs = @("--icon", $IconFile) }
if ($Arch -eq "arm64") {
    # PyInstaller makes programs for the machine it runs on (x64 here), so the plain-console fallback is not built for ARM64;
    # PythonOS.exe (the window) is the program on Windows on ARM.
    Write-Host "ARM64: skipping the console launcher."
} else {
    python -m PyInstaller --onefile --console --name PythonOS-console @IconArgs `
        --distpath $App --workpath $Work --specpath $Work (Join-Path $Here "launcher.py")
    if ($LASTEXITCODE -ne 0 -and $IconArgs.Count -gt 0) {
        Write-Host "Icon conversion failed - building the launcher without an icon."
        python -m PyInstaller --onefile --console --name PythonOS-console `
            --distpath $App --workpath $Work --specpath $Work (Join-Path $Here "launcher.py")
    }
    if (-not (Test-Path (Join-Path $App "PythonOS-console.exe"))) { throw "PythonOS-console.exe was not built" }
    Remove-Item $Work -Recurse -Force
}

# 4b. The PythonOS window and the web installer (C#, built with the compiler that ships with Windows)
$Native = Join-Path $Out "native"
$Numeric = if ($Version -match '^(\d+)\.(\d+)\.(\d+)') { "$($Matches[1]).$($Matches[2]).$($Matches[3]).0" } else { "0.0.0.0" }
& (Join-Path $Here "build-native.ps1") -Out $Native -Version $Numeric -IconFile $IconFile -Arch $Arch
if ($LASTEXITCODE -ne 0) { throw "building the native programs failed" }
Copy-Item (Join-Path $Native "PythonOS.exe"), (Join-Path $Native "Microsoft.Web.WebView2.Core.dll"), `
    (Join-Path $Native "Microsoft.Web.WebView2.WinForms.dll"), (Join-Path $Native "WebView2Loader.dll") $App
Copy-Item (Join-Path $Native "web") $App -Recurse
if ($Arch -eq "x64") { Copy-Item (Join-Path $Native "PythonOS-Setup.exe") (Join-Path $Out "PythonOS-$Version-web-setup.exe") }   # one web installer for every architecture
Remove-Item $Native -Recurse -Force

# 5. Portable zip
$Zip = Join-Path $Out "PythonOS-$Version-windows$Tag-portable.zip"
Compress-Archive -Path $App -DestinationPath $Zip
Write-Host "Built $Zip"

# 6. Installer (optional)
$Iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $Candidate = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path $Candidate) { $Iscc = $Candidate }
}
if ($Iscc) {
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$App" "/DOutputDir=$Out" "/DArtDir=$Art" "/DNameTag=$Tag" "/DTargetArch=$Arch" (Join-Path $Here "PythonOS.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    Write-Host "Built installer"
} else {
    Write-Host "Inno Setup not found - skipping the installer (portable zip is ready)."
}
Get-ChildItem $Out
