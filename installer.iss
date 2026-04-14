; ClipQueue — Inno Setup Script
; Build: pyinstaller build.spec  →  then compile this .iss with Inno Setup 6+

#define AppName "ClipQueue"
#define AppVersion "1.0.0"
#define AppExe "ClipQueue.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ClipQueue
AppPublisherURL=https://github.com/
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputBaseFilename=ClipQueue-Setup-{#AppVersion}
OutputDir=dist
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: desktopicon; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: unchecked
Name: startup;     Description: "Запускать автоматически при входе в Windows"; GroupDescription: "Автозапуск:"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json";     DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExe}"""; \
  Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; \
  Description: "Запустить {#AppName}"; \
  Flags: postinstall shellexec skipifsilent
