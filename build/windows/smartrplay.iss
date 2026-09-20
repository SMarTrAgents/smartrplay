; Inno-Setup-Skript fuer den SMarTrPlay-Installer.
; SMarTrAgents.ai by AKATONGIE with Fable 5 (Anthropic). MIT license.
; Gebaut im GitHub-Workflow build-windows.yml.

#define MeinName "SMarTrPlay"
#define MeinHersteller "SMarTrAgents"
#define MeineSeite "https://smartragents.ai"
#ifndef MeineVersion
  #define MeineVersion "5.0.0"
#endif

[Setup]
AppId={{9E5B1F42-7C3A-4D18-9A6E-5F2B8C0D1E77}
AppName={#MeinName}
AppVersion={#MeineVersion}
AppPublisher={#MeinHersteller}
AppPublisherURL={#MeineSeite}
AppSupportURL={#MeineSeite}
AppUpdatesURL=https://github.com/SMarTrAgents/smartrplay/releases
DefaultDirName={autopf}\{#MeinName}
DefaultGroupName={#MeinName}
OutputDir=..\..\dist
OutputBaseFilename=SMarTrPlay-Setup-{#MeineVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\LICENSE
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\SMarTrPlay.exe

[Languages]
Name: "deutsch"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\SMarTrPlay.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MeinName}"; Filename: "{app}\SMarTrPlay.exe"
Name: "{group}\SMarTrAgents.ai"; Filename: "{#MeineSeite}"
Name: "{autodesktop}\{#MeinName}"; Filename: "{app}\SMarTrPlay.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SMarTrPlay.exe"; Description: "{cm:LaunchProgram,{#MeinName}}"; Flags: nowait postinstall skipifsilent
Filename: "{#MeineSeite}"; Description: "SMarTrAgents.ai besuchen / visit SMarTrAgents.ai"; Flags: nowait postinstall skipifsilent shellexec unchecked

[Code]
// SMarTrPlay spielt ueber libVLC. Fehlt VLC, wird darauf hingewiesen und der
// Download angeboten, statt den Nutzer spaeter mit einem schwarzen Bild
// stehen zu lassen.
function VlcGefunden(): Boolean;
begin
  Result := RegKeyExists(HKLM, 'SOFTWARE\VideoLAN\VLC')
         or RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\VideoLAN\VLC')
         or RegKeyExists(HKCU, 'SOFTWARE\VideoLAN\VLC')
         or FileExists(ExpandConstant('{autopf}\VideoLAN\VLC\libvlc.dll'))
         or FileExists(ExpandConstant('{autopf32}\VideoLAN\VLC\libvlc.dll'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Fehler: Integer;
begin
  if (CurStep = ssPostInstall) and (not VlcGefunden()) then
  begin
    if MsgBox('SMarTrPlay braucht den VLC media player fuer die Wiedergabe.' #13#10
            + 'SMarTrPlay needs VLC media player for playback.' #13#10 #13#10
            + 'Jetzt die Downloadseite oeffnen? / Open the download page now?',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://www.videolan.org/vlc/', '', '', SW_SHOW, ewNoWait, Fehler);
  end;
end;
