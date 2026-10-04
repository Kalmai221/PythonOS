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
; The wizard artwork drawn by make_art.py (side panel, header badge, icon)
#ifndef ArtDir
  #error ArtDir must be defined (the folder produced by make_art.py)
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
UninstallDisplayIcon={app}\PythonOS.exe

; Look and feel: the modern wizard with PythonOS artwork instead of the plain default
WizardStyle=modern
WizardSizePercent=110
WizardImageFile={#ArtDir}\wizard-164x314.bmp,{#ArtDir}\wizard-192x386.bmp,{#ArtDir}\wizard-246x459.bmp,{#ArtDir}\wizard-328x628.bmp
WizardSmallImageFile={#ArtDir}\small-55.bmp,{#ArtDir}\small-64.bmp,{#ArtDir}\small-80.bmp,{#ArtDir}\small-110.bmp
SetupIconFile={#ArtDir}\PythonOS.ico
DisableProgramGroupPage=yes
DisableReadyPage=yes
ShowLanguageDialog=no
CloseApplications=yes
AppComments=A tiny operating system that lives in your terminal.
VersionInfoDescription=PythonOS setup

[Messages]
WelcomeLabel1=Welcome to PythonOS
WelcomeLabel2=This installs [name/ver].%n%nA tiny operating system that lives in your terminal, with its own accounts, files, shell and app store.%n%nYou do not need Python: it comes with PythonOS. The system itself downloads on the first start and keeps itself up to date.
SelectDirDesc=Where should PythonOS live?
SelectDirLabel3=PythonOS keeps its accounts and files in this folder, so it goes in your own profile by default. No administrator rights needed.
SelectTasksLabel2=Pick the extras you would like.
InstallingLabel=Putting PythonOS in place. This takes a moment...
FinishedHeadingLabel=PythonOS is ready
FinishedLabel=Start it from the Start menu or your desktop. The first start downloads the system and sets up your account.
FinishedLabelNoIcons=PythonOS is installed. Start it from the Start menu.

[Tasks]
Name: "desktopicon"; Description: "Put a PythonOS shortcut on my &desktop"; GroupDescription: "Extras:"

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
Filename: "{app}\PythonOS.exe"; Description: "Start PythonOS now"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Remove generated files but leave a chance to keep user data: only caches are deleted
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\commands"
Type: filesandordirs; Name: "{app}\core"
Type: filesandordirs; Name: "{app}\programs"
Type: filesandordirs; Name: "{app}\pyos"
