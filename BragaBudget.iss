[Setup]
AppName=Braga Budget
AppVersion=1.0
DefaultDirName={autopf}\Braga Budget
DefaultGroupName=Braga Budget
OutputDir=installer
OutputBaseFilename=BragaBudget-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName=Braga Budget

[Files]
Source: "dist\BragaBudget\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Braga Budget"; Filename: "{app}\BragaBudget.exe"
Name: "{autodesktop}\Braga Budget"; Filename: "{app}\BragaBudget.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
Filename: "{app}\BragaBudget.exe"; Description: "Abrir Braga Budget"; Flags: nowait postinstall skipifsilent
