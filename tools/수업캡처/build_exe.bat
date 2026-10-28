@echo off
rem 수업캡처 exe 빌드 (빌드하는 컴퓨터에만 Python 3.12 필요. 설치하는 노트북에는 필요 없음)
rem 결과: dist\LectureCapture\ (LectureCapture.exe + lctool.exe)   설치 파일까지 만들려면 build_installer.bat
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv python -m venv .venv || goto :err
call .venv\Scripts\activate.bat
pip install -r requirements.txt || goto :err
python make_icon.py || goto :err
rem 1) 앱
pyinstaller --noconfirm --windowed --name LectureCapture --icon icon.ico ^
  --collect-all customtkinter --collect-all faster_whisper --collect-all ctranslate2 --collect-all winsdk ^
  --hidden-import pystray._win32 ^
  main.py || goto :err
rem 2) Python 대용 실행기: PDF 빌드(build.py)·토글(add_theme_toggle.py)을 Python 없이 돌림
pyinstaller --noconfirm --onefile --console --name lctool --collect-all pymupdf lctool.py || goto :err
copy /y dist\lctool.exe dist\LectureCapture\lctool.exe >nul || goto :err
echo.
echo 완료: dist\LectureCapture\LectureCapture.exe
if "%1"=="nopause" exit /b 0
pause
exit /b 0
:err
echo 빌드 실패
if "%1"=="nopause" exit /b 1
pause
exit /b 1
