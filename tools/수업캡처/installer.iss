; 수업캡처 설치 파일 (Inno Setup 6)
; build_installer.bat가 PyInstaller 결과(dist\LectureCapture)를 묶어 Output\LectureCapture-Setup.exe를 만든다
; 관리자 권한 없이 사용자 폴더(%LOCALAPPDATA%\Programs\LectureCapture)에 설치된다
; 노트북에 아무것도 없어도 되게: 앱 + lctool.exe(Python 대용) + 작업 폴더 틀(workspace_template)을 같이 넣고,
; 원하면 Claude Code(+ Git for Windows)도 설치한다

#define AppName "수업캡처"
#define AppVersion "1.0.0"
#define AppExe "LectureCapture.exe"

[Setup]
AppId={{7C3B9E1A-4F2D-4C8B-9A61-5E0D2B7F3C41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Ben Lee
DefaultDirName={localappdata}\Programs\LectureCapture
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=LectureCapture-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "바로가기:"
Name: "startup"; Description: "Windows 시작할 때 자동 실행"; GroupDescription: "자동 실행:"; Flags: unchecked
Name: "claudecode"; Description: "Claude Code 설치 (AI 정리에 필요, 인터넷 필요. 이미 있으면 건너뜀)"; GroupDescription: "필요한 프로그램:"

[Files]
Source: "dist\LectureCapture\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; 작업 폴더 틀: 처음 실행 때 "새로 만들기"를 누르면 문서\수업정리 로 복사된다
Source: "..\..\.claude\commands\ln.md"; DestDir: "{app}\workspace_template\.claude\commands"; Flags: ignoreversion
Source: "..\..\_template\README.md"; DestDir: "{app}\workspace_template\_template"; Flags: ignoreversion
Source: "..\..\_template\build.py"; DestDir: "{app}\workspace_template\_template"; Flags: ignoreversion
Source: "..\..\_template\add_theme_toggle.py"; DestDir: "{app}\workspace_template\_template"; Flags: ignoreversion
Source: "..\..\_template\theme_toggle.html"; DestDir: "{app}\workspace_template\_template"; Flags: ignoreversion
Source: "..\..\_template\html_reference.html"; DestDir: "{app}\workspace_template\_template"; Flags: ignoreversion
Source: "..\..\_template\paper_reference.html"; DestDir: "{app}\workspace_template\_template"; Flags: ignoreversion
Source: "..\..\_template\fonts\*"; DestDir: "{app}\workspace_template\_template\fonts"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\사용 설명서"; Filename: "{app}\README.md"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
; Claude Code는 Windows에서 Git Bash를 쓰므로 Git for Windows를 먼저 깐다(winget, 이미 있으면 건너뜀)
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""if (-not (Get-Command git -ErrorAction SilentlyContinue)) {{ winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements }}"""; StatusMsg: "Git for Windows 설치 중..."; Flags: runhidden waituntilterminated; Tasks: claudecode
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""if (-not (Test-Path (Join-Path $env:USERPROFILE '.local\bin\claude.exe'))) {{ irm https://claude.ai/install.ps1 | iex }}"""; StatusMsg: "Claude Code 설치 중..."; Flags: runhidden waituntilterminated; Tasks: claudecode
Filename: "{app}\{#AppExe}"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent
