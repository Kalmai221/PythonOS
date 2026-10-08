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
; "" for the x64 installer, "-arm64" for Windows on ARM
#ifndef NameTag
  #define NameTag ""
#endif
#ifndef TargetArch
  #define TargetArch "x64"
#endif
; The "What's new" page (RTF made from the CHANGELOG by OS_Export/whatsnew_rtf.py); without it the wizard simply has no such page
#ifndef WhatsNew
  #define WhatsNew ""
#endif
; The optional libraries the wizard offers (one "name|what it adds" line each, made by make_extras_list.py); without it the wizard has no such page
#ifndef ExtrasList
  #define ExtrasList ""
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
OutputBaseFilename=PythonOS-{#AppVersion}{#NameTag}-setup
Compression=lzma2/ultra64
SolidCompression=yes
#if TargetArch == "arm64"
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
#else
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif
UninstallDisplayName=PythonOS
UninstallDisplayIcon={app}\PythonOS.exe

; Look and feel: the modern wizard with PythonOS artwork instead of the plain default
WizardStyle=modern dynamic
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
#if WhatsNew != ""
InfoBeforeFile={#WhatsNew}
#endif

[Messages]
WizardInfoBefore=What's new
InfoBeforeLabel=Here is what changed in this version.
InfoBeforeClickLabel=When you are ready to continue, click Next.
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
#if ExtrasList != ""
Source: "{#ExtrasList}"; DestDir: "{tmp}"; Flags: dontcopy
#endif

[Icons]
Name: "{group}\PythonOS"; Filename: "{app}\PythonOS.exe"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{group}\Uninstall PythonOS"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{userdesktop}\PythonOS"; Filename: "{app}\PythonOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Requirements: the PythonOS system itself and the Python libraries it imports. Anything missing is downloaded now (needs internet);
; PythonOS.exe checks the same things at every start, so a failure here only means it finishes the job on the first start.
Filename: "{app}\python\python.exe"; Parameters: """{app}\bootstrap.py"" --dest ""{app}"""; WorkingDir: "{app}"; StatusMsg: "Downloading the PythonOS system..."; Flags: runhidden waituntilterminated
Filename: "{app}\python\python.exe"; Parameters: "-m pip install --quiet --no-warn-script-location -r ""{app}\requirements.txt"" -r ""{app}\boot-requirements.txt"""; WorkingDir: "{app}"; StatusMsg: "Installing the Python libraries PythonOS needs..."; Check: LibrariesMissing; Flags: runhidden waituntilterminated
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
  FreshInstall: Boolean;
  MemoryPage: TInputOptionWizardPage;
  ExtrasPage: TInputOptionWizardPage;
  ExtraNames: TArrayOfString;

// True when the bundled Python cannot import the libraries PythonOS needs (checked after the system was downloaded)
function LibrariesMissing(): Boolean;
var
  Code: Integer;
begin
  if not Exec(ExpandConstant('{app}\python\python.exe'), '-c "import rich, psutil, requests, yaspin, ping3, prompt_toolkit, pygments"',
              ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, Code) then
    Code := 1;
  Result := Code <> 0;
end;

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
  FreshInstall := Existing = '';
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

// ------------------------------------------------------------ optional libraries
// One tick per library of requirements-extra.txt (all ticked to begin with). The list is made at build time and read from the installer itself.
procedure MakeExtrasPage();
var
  Lines: TArrayOfString;
  I, P, N: Integer;
  Text: String;
begin
#if ExtrasList != ""
  ExtractTemporaryFile('extras.txt');
  if not LoadStringsFromFile(ExpandConstant('{tmp}\extras.txt'), Lines) then
    Exit;
  ExtrasPage := CreateInputOptionPage(MemoryPage.ID, 'Optional libraries', 'Which optional libraries should PythonOS have?',
    'PythonOS works without them. Each adds something; untick the ones you do not want. You can change this later with the command: extras', False, True);
  N := 0;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    P := Pos('|', Lines[I]);
    if P > 1 then
    begin
      SetArrayLength(ExtraNames, N + 1);
      ExtraNames[N] := Copy(Lines[I], 1, P - 1);
      Text := ExtraNames[N];
      if Length(Lines[I]) > P then
        Text := Text + '  -  ' + Copy(Lines[I], P + 1, 90);
      ExtrasPage.Add(Text);
      ExtrasPage.Values[N] := True;
      N := N + 1;
    end;
  end;
#endif
end;

// ------------------------------------------------------------ memory for PythonOS
// PythonOS owns a fixed amount of memory (setting memory_limit_mb). A fresh install asks for it; /MEMORY=2048 (or /MEMORY=all) answers silently.
procedure InitializeWizard();
begin
  MemoryPage := CreateInputOptionPage(wpSelectDir, 'Memory', 'How much memory should PythonOS use?',
    'PythonOS works as a small computer of its own with this much memory. You can change it later with: settings set memory_limit_mb', True, False);
  MemoryPage.Add('512 MB');
  MemoryPage.Add('1 GB (recommended)');
  MemoryPage.Add('2 GB');
  MemoryPage.Add('4 GB');
  MemoryPage.Add('All of the computer''s memory');
  MemoryPage.SelectedValueIndex := 1;
  MakeExtrasPage();
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = MemoryPage.ID) and not FreshInstall;       // an update or repair keeps the settings it has
  if Assigned(ExtrasPage) then
    if PageID = ExtrasPage.ID then
      Result := not FreshInstall;
end;

// The optional libraries as the JSON PythonOS reads (.OSData\extras.json): all of them, none, or the ticked ones. /EXTRAS=all|none|name,name answers silently.
function ChosenExtras(): String;
var
  Given, List: String;
  I, Count: Integer;
begin
  Given := Lowercase(ExpandConstant('{param:extras|}'));
  StringChangeEx(Given, '"', '', True);
  Result := '{"mode": "all", "selected": []}';
  if (Given = 'none') then
    Result := '{"mode": "none", "selected": []}'
  else if (Given <> '') and (Given <> 'all') then
  begin
    StringChangeEx(Given, ',', '", "', True);
    Result := '{"mode": "custom", "selected": ["' + Given + '"]}';
  end
  else if (Given = '') and Assigned(ExtrasPage) then
  begin
    Count := 0;
    List := '';
    for I := 0 to GetArrayLength(ExtraNames) - 1 do
      if ExtrasPage.Values[I] then
      begin
        if List <> '' then List := List + ', ';
        List := List + '"' + ExtraNames[I] + '"';
        Count := Count + 1;
      end;
    if Count = 0 then
      Result := '{"mode": "none", "selected": []}'
    else if Count < GetArrayLength(ExtraNames) then
      Result := '{"mode": "custom", "selected": [' + List + ']}';
  end;
end;

function ChosenMemory(): String;
var
  Given: String;
begin
  Given := Lowercase(ExpandConstant('{param:memory|}'));
  if Given = 'all' then Result := '0'
  else if (Given <> '') and (StrToIntDef(Given, 0) >= 256) then Result := Given
  else
    case MemoryPage.SelectedValueIndex of
      0: Result := '512';
      2: Result := '2048';
      3: Result := '4096';
      4: Result := '0';
    else
      Result := '1024';
    end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Settings, ExtrasFile: String;
begin
  if (CurStep = ssPostInstall) and FreshInstall then
  begin
    Settings := ExpandConstant('{app}\.OSData\settings.json');
    if not FileExists(Settings) then
    begin
      ForceDirectories(ExpandConstant('{app}\.OSData'));
      SaveStringToFile(Settings, '{"memory_limit_mb": ' + ChosenMemory() + '}' + #10, False);
    end;
    ExtrasFile := ExpandConstant('{app}\.OSData\extras.json');
    if not FileExists(ExtrasFile) then
    begin
      ForceDirectories(ExpandConstant('{app}\.OSData'));
      SaveStringToFile(ExtrasFile, ChosenExtras() + #10, False);
    end;
  end;
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
