; Villagen installer (Inno Setup 6). Built by tools/package_release.py --installer; by hand:
;   .tools\innosetup\ISCC.exe /DEdition=school /DAppVer=0.11.1 tools\installer\villagen.iss
; Edition "school" packs builds\school (plays on the school server) as Villagen_School_Setup.exe;
; edition "public" packs builds\windows as Villagen_Setup.exe. The two install side by side.
; Installs per user by default (no admin prompt); "모든 사용자용" in the first dialog installs to
; Program Files. Game progress lives on the server, so uninstalling or reinstalling loses nothing.

#ifndef Edition
  #define Edition "school"
#endif
#ifndef AppVer
  #define AppVer "0.0.0"
#endif
#if Edition == "school"
  #define AppGuid "70049920-F304-4EE1-BEAB-B8C12713B216"
  #define SrcDir "..\..\builds\school"
  #define OutName "Villagen_School_Setup"
  #define DirName "Villagen School"
  #define Shortcut "Villagen"
#else
  #define AppGuid "CB337B23-A7AC-4091-A458-1E38422555A6"
  #define SrcDir "..\..\builds\windows"
  #define OutName "Villagen_Setup"
  #define DirName "Villagen"
  #define Shortcut "Villagen"
#endif

[Setup]
AppId={{{#AppGuid}}
AppName=Villagen
AppVersion={#AppVer}
AppVerName=Villagen {#AppVer}
AppPublisher=Villagen Team
AppPublisherURL=https://github.com/NormalMan0228/tripo_s1
VersionInfoVersion={#AppVer}
DefaultDirName={autopf}\{#DirName}
DefaultGroupName=Villagen
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousAppDir=yes
OutputDir=..\..\builds\release
OutputBaseFilename={#OutName}
SetupIconFile=..\..\game\assets\villagen.ico
UninstallDisplayIcon={app}\villagen.ico
UninstallDisplayName=Villagen
WizardStyle=modern
; The game pack is one large file: block LZMA2 at a fast level packs ~1.8 GB in minutes.
Compression=lzma2/fast
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SrcDir}\Villagen.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Villagen.pck"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\game\assets\villagen.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docs\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\..\game\assets\fonts\LICENSES.md"; DestDir: "{app}\licenses"; DestName: "Fonts-LICENSES.md"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#Shortcut}"; Filename: "{app}\Villagen.exe"; WorkingDir: "{app}"; IconFilename: "{app}\villagen.ico"
Name: "{autodesktop}\{#Shortcut}"; Filename: "{app}\Villagen.exe"; WorkingDir: "{app}"; IconFilename: "{app}\villagen.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Villagen.exe"; Description: "{cm:LaunchProgram,Villagen}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
