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
; Both shortcuts are offered on the wizard's "Select Additional Tasks" page; the Start menu one is ticked by default.
Name: "startmenuicon"; Description: "Create a &Start menu shortcut"; GroupDescription: "Shortcuts:"
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; Never overwrite the user's data on upgrade
; The package holds PythonOS.exe, the bundled Python and bootstrap.py. The OS itself is downloaded
; on first run (and updates itself), so an upgrade of this installer never touches it or the user's data.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\PythonOS"; Filename: "{app}\PythonOS.exe"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{group}\Uninstall PythonOS"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{userdesktop}\PythonOS"; Filename: "{app}\PythonOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\PythonOS.exe"; Description: "Start PythonOS now"; Flags: postinstall nowait skipifsilent

[InstallDelete]
; Repair: remove the OS files (the app downloads a fresh copy on the next start). Accounts, files and settings are never listed here.
Type: filesandordirs; Name: "{app}\commands"; Check: IsRepair
Type: filesandordirs; Name: "{app}\core"; Check: IsRepair
Type: filesandordirs; Name: "{app}\programs"; Check: IsRepair
Type: filesandordirs; Name: "{app}\pyos"; Check: IsRepair
Type: files; Name: "{app}\main.py"; Check: IsRepair
Type: files; Name: "{app}\shell.py"; Check: IsRepair
Type: files; Name: "{app}\users.py"; Check: IsRepair
Type: files; Name: "{app}\VERSION"; Check: IsRepair

[UninstallDelete]
; Remove generated files but leave a chance to keep user data: only caches are deleted
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\commands"
Type: filesandordirs; Name: "{app}\core"
Type: filesandordirs; Name: "{app}\programs"
Type: filesandordirs; Name: "{app}\pyos"

[Code]
// ---------------------------------------------------------------- already installed?
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6B0B3A63-5B6E-4C3E-9C47-7C1D2F6A9E11}_is1';

function InstalledVersion(): String;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', Result) then
    if not RegQueryStringValue(HKLM, UninstallKey, 'DisplayVersion', Result) then
      Result := '';
end;

var
  RepairMode: Boolean;

function IsRepair(): Boolean;
begin
  Result := RepairMode;
end;

function InitializeSetup(): Boolean;
var
  Existing: String;
  Detail: String;
  Choice: Integer;
begin
  Result := True;
  RepairMode := False;
  Existing := InstalledVersion();
  if (Existing = '') or WizardSilent() then
    Exit;
  Detail := 'PythonOS ' + Existing + ' is already installed on this computer. Your accounts, files and settings are kept either way.' + #13#10#13#10 +
            'Yes: update to version {#AppVersion} (puts the newer program files in place).' + #13#10 +
            'No: repair (puts the program files back and fetches a fresh copy of the PythonOS system on the next start).' + #13#10 +
            'Cancel: change nothing.';
  Choice := MsgBox(Detail, mbConfirmation, MB_YESNOCANCEL);
  Result := Choice <> IDCANCEL;
  RepairMode := Choice = IDNO;
end;

// ------------------------------------------------------------ uninstalling
var
  DeleteUserData: Boolean;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  DeleteUserData := False;                       // a silent uninstall always keeps the data
  if not UninstallSilent() then
    DeleteUserData := MsgBox('PythonOS is about to be removed.' + #13#10#13#10 +
      'Do you also want to delete your PythonOS data (accounts, files, settings and installed apps)?' + #13#10#13#10 +
      'Choose No to keep it: it stays in the PythonOS folder and is used again if you reinstall.',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DeleteUserData then
    DelTree(ExpandConstant('{app}'), True, True, True);
end;
