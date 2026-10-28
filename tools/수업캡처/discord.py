# 디스코드를 "가림방지" 옵션으로 다시 실행
# 크롬 기반 앱은 창이 다른 창에 완전히 덮이면 그리기를 멈춘다 → 덮인 동안 캡처가 멈춤
# 아래 옵션을 붙여 실행하면 덮여 있어도 계속 그린다
import os, subprocess, time
from pathlib import Path

FLAGS = ("--disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows "
         "--disable-renderer-backgrounding --disable-background-timer-throttling")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def updater():
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "Discord" / "Update.exe"
    return p if p.is_file() else None

def running_flags():
    """None: 디스코드 안 켜짐 / True: 가림방지로 실행 중 / False: 일반 실행"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"name='Discord.exe'\" | ForEach-Object CommandLine"],
                       capture_output=True, creationflags=NOWIN)
    lines = [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
    if not lines:
        return None
    return any("CalculateNativeWinOcclusion" in l for l in lines)

def relaunch(log):
    upd = updater()
    if not upd:
        log("디스코드 설치 위치(%LOCALAPPDATA%\\Discord)를 찾지 못함")
        return False
    subprocess.run(["taskkill", "/IM", "Discord.exe", "/F"], capture_output=True, creationflags=NOWIN)
    time.sleep(2)
    subprocess.Popen([str(upd), "--processStart", "Discord.exe", "--process-start-args", FLAGS], creationflags=NOWIN)
    log("디스코드를 가림방지 옵션으로 다시 실행함. 방송에 다시 들어가세요")
    return True
