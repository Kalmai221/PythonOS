; Inno Setup script for the PythonOS Windows installer.
; Built by build.ps1 with:  iscc /DAppVersion=1.2.0 /DSourceDir=<staged PythonOS folder> /DOutputDir=<dest> PythonOS.iss
#ifndef AppVersion
  #define AppVersion "1.0"
#endif
#ifndef SourceDir
  #error SourceDir must be defined (the folder produced by build.ps1)
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
AppId={{6B0B3A63-5B6E-4C3E-9C47-7C1D2F6A9E11}
AppName=PythonOS
AppVersion={#AppVersion}
AppPublisher=Kalmai221
AppPublisherURL=https://github.com/Kalmai221/PythonOS
; Installed per-user: PythonOS writes its files and accounts next to itself,
; which would be blocked inside Program Files.
DefaultDirName={localappdata}\PythonOS
DefaultGroupName=PythonOS
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=PythonOS-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=PythonOS

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
; Never overwrite the user's data on upgrade
; The package holds PythonOS.exe, the bundled Python and bootstrap.py. The OS itself is downloaded
; on first run (and updates itself), so an upgrade of this installer never touches it or the user's data.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\PythonOS"; Filename: "{app}\PythonOS.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall PythonOS"; Filename: "{uninstallexe}"
Name: "{userdesktop}\PythonOS"; Filename: "{app}\PythonOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\PythonOS.exe"; Description: "Start PythonOS"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Remove generated files but leave a chance to keep user data: only caches are deleted
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\commands"
Type: filesandordirs; Name: "{app}\core"
Type: filesandordirs; Name: "{app}\programs"
Type: filesandordirs; Name: "{app}\pyos"
