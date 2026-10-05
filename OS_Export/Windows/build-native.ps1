<#
Build the native Windows programs with the C# compiler that ships with Windows (no Visual Studio, no SDK):

  PythonOS.exe        the PythonOS window (host/): WebView2 + xterm.js + a pseudo console
  PythonOS-Setup.exe  the small installer that downloads PythonOS from GitHub (setup/)

    powershell -File OS_Export\Windows\build-native.ps1 -Out dist\windows\native

Downloads once (cached in dist\native-deps): the Microsoft.Web.WebView2 NuGet package, xterm.js and its fit addon.
The Python-side files (start.py, bootstrap.py) and the embedded Python are put in place by build.ps1.
#>
param(
    [string]$Out = "",
    [string]$Version = "0.0.0",
    [string]$IconFile = ""
)
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = (Resolve-Path (Join-Path $Here "..\..")).Path
if (-not $Out) { $Out = Join-Path $Repo "dist\windows\native" }
$Deps = Join-Path $Repo "dist\native-deps"
$WebView2Version = "1.0.2739.15"
$Xterm = "5.5.0"
$FitAddon = "0.10.0"
$Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $Csc)) { throw "The .NET Framework C# compiler was not found: $Csc" }

New-Item -ItemType Directory -Force -Path $Deps, $Out | Out-Null

function Get-Package($Name, $Url, $Check) {
    if (Test-Path (Join-Path $Deps $Check)) { return }
    Write-Host "Downloading $Name ..."
    $Zip = Join-Path $Deps "$Name.pkg"
    Invoke-WebRequest -Uri $Url -OutFile $Zip
    $Target = Join-Path $Deps $Name
    if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }
    New-Item -ItemType Directory -Path $Target | Out-Null
    tar -xf $Zip -C $Target
    if ($LASTEXITCODE -ne 0) { throw "could not unpack $Name" }
    Remove-Item $Zip
}

Get-Package "webview2" "https://www.nuget.org/api/v2/package/Microsoft.Web.WebView2/$WebView2Version" "webview2\lib\net462\Microsoft.Web.WebView2.Core.dll"
Get-Package "xterm" "https://registry.npmjs.org/@xterm/xterm/-/xterm-$Xterm.tgz" "xterm\package\lib\xterm.js"
Get-Package "addon-fit" "https://registry.npmjs.org/@xterm/addon-fit/-/addon-fit-$FitAddon.tgz" "addon-fit\package\lib\addon-fit.js"

$Wv = Join-Path $Deps "webview2"
$Common = @("/nologo", "/optimize+", "/codepage:65001", "/platform:x64", "/r:System.dll", "/r:System.Core.dll", "/r:System.Drawing.dll", "/r:System.Windows.Forms.dll")
$IconArgs = @()
if ($IconFile -and (Test-Path $IconFile)) { $IconArgs = @("/win32icon:$IconFile") }
$VersionFile = Join-Path $Out "AssemblyInfo.cs"
@"
using System.Reflection;
[assembly: AssemblyTitle("PythonOS")]
[assembly: AssemblyProduct("PythonOS")]
[assembly: AssemblyVersion("$Version")]
[assembly: AssemblyFileVersion("$Version")]
"@ | Set-Content -Path $VersionFile -Encoding ascii

# 1. The window
Write-Host "Compiling PythonOS.exe ..."
& $Csc @Common /target:winexe @IconArgs "/out:$Out\PythonOS.exe" `
    "/r:$Wv\lib\net462\Microsoft.Web.WebView2.Core.dll" "/r:$Wv\lib\net462\Microsoft.Web.WebView2.WinForms.dll" `
    (Join-Path $Here "native\host\ConPty.cs") (Join-Path $Here "native\host\Host.cs") $VersionFile
if ($LASTEXITCODE -ne 0) { throw "compiling PythonOS.exe failed" }
Copy-Item "$Wv\lib\net462\Microsoft.Web.WebView2.Core.dll", "$Wv\lib\net462\Microsoft.Web.WebView2.WinForms.dll", "$Wv\runtimes\win-x64\native\WebView2Loader.dll" $Out
$Web = Join-Path $Out "web"
New-Item -ItemType Directory -Force -Path $Web | Out-Null
Copy-Item (Join-Path $Here "native\host\web\terminal.html") $Web
Copy-Item (Join-Path $Deps "xterm\package\lib\xterm.js"), (Join-Path $Deps "xterm\package\css\xterm.css"), (Join-Path $Deps "addon-fit\package\lib\addon-fit.js") $Web

# 2. The installer (when its sources exist)
$Setup = Join-Path $Here "native\setup"
if (Test-Path (Join-Path $Setup "Setup.cs")) {
    Write-Host "Compiling PythonOS-Setup.exe ..."
    $Sources = Get-ChildItem $Setup -Filter *.cs | ForEach-Object { $_.FullName }
    & $Csc @Common /target:winexe @IconArgs "/r:System.IO.Compression.dll" "/r:System.IO.Compression.FileSystem.dll" "/r:System.Web.Extensions.dll" "/out:$Out\PythonOS-Setup.exe" `
        $Sources $VersionFile
    if ($LASTEXITCODE -ne 0) { throw "compiling PythonOS-Setup.exe failed" }
}
Remove-Item $VersionFile
Write-Host "Native programs are in $Out"
