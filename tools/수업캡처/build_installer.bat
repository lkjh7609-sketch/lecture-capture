@echo off
rem 수업캡처 설치 파일 빌드 (Windows)
rem 1) exe 빌드  2) Inno Setup으로 묶기  → Output\LectureCapture-Setup-1.0.0.exe
rem Inno Setup이 없으면: winget install JRSoftware.InnoSetup
chcp 65001 >nul
cd /d "%~dp0"
call build_exe.bat nopause || goto :err

set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%P
if not defined ISCC (
  echo Inno Setup 6을 찾지 못함. 설치: winget install JRSoftware.InnoSetup
  goto :err
)
%ISCC% installer.iss || goto :err
echo.
echo 완료: Output 폴더의 LectureCapture-Setup-*.exe 를 실행하면 설치됩니다
pause
exit /b 0
:err
echo 설치 파일 빌드 실패
pause
exit /b 1
