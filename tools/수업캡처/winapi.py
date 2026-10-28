# Windows API (ctypes): DPI, 창 찾기, 창 캡처, 전역 단축키
# Windows가 아니면 IS_WIN=False, 창 관련 함수는 빈 결과를 돌려준다(Mac 개발용)
import ctypes, sys, threading
from PIL import Image

IS_WIN = sys.platform == "win32"

if IS_WIN:
    from ctypes import wintypes as W
    user32, gdi32, kernel32, dwmapi = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32, ctypes.windll.dwmapi
    # 64비트 핸들이 int로 잘리지 않게 타입 지정
    user32.GetWindowDC.restype = W.HDC
    user32.GetWindowDC.argtypes = [W.HWND]
    user32.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user32.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    user32.WindowFromPoint.restype = W.HWND
    user32.WindowFromPoint.argtypes = [W.POINT]
    user32.GetAncestor.restype = W.HWND
    user32.GetAncestor.argtypes = [W.HWND, W.UINT]
    user32.GetWindowTextLengthW.argtypes = [W.HWND]
    user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [W.HWND]
    user32.IsWindow.argtypes = [W.HWND]
    user32.IsIconic.argtypes = [W.HWND]
    user32.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
    gdi32.CreateCompatibleDC.restype = W.HDC
    gdi32.CreateCompatibleDC.argtypes = [W.HDC]
    gdi32.CreateCompatibleBitmap.restype = W.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [W.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = W.HGDIOBJ
    gdi32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    gdi32.DeleteObject.argtypes = [W.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [W.HDC]
    gdi32.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT]
    dwmapi.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, ctypes.c_void_p, W.DWORD]
    user32.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, W.WPARAM, W.LPARAM]
    user32.RegisterHotKey.argtypes = [W.HWND, ctypes.c_int, W.UINT, W.UINT]
    user32.UnregisterHotKey.argtypes = [W.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
    user32.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
    user32.GetWindowPlacement.argtypes = [W.HWND, ctypes.c_void_p]
    user32.MonitorFromWindow.restype = W.HANDLE
    user32.MonitorFromWindow.argtypes = [W.HWND, W.DWORD]
    user32.GetMonitorInfoW.argtypes = [W.HANDLE, ctypes.c_void_p]

    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [("length", W.UINT), ("flags", W.UINT), ("showCmd", W.UINT), ("ptMinPosition", W.POINT),
                    ("ptMaxPosition", W.POINT), ("rcNormalPosition", W.RECT)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]

def set_dpi_aware():
    if IS_WIN:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            user32.SetProcessDPIAware()

def list_windows():
    """[(hwnd, title)] 보이는 최상위 창"""
    if not IS_WIN:
        return []
    out = []
    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                out.append((hwnd, buf.value))
        return True
    user32.EnumWindows(cb, 0)
    return out

def window_rect(hwnd):
    """그림자 테두리를 뺀 실제 화면 좌표 (l, t, r, b)"""
    r = W.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:  # DWMWA_EXTENDED_FRAME_BOUNDS
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def find_window(sub, iconic=False):
    """제목에 sub가 들어간 창 중 가장 큰 것. 제목이 sub로 끝나면 우선. iconic=True면 최소화된 창도 찾음"""
    if not IS_WIN:
        return None
    cands = [(h, t) for h, t in list_windows() if sub.lower() in t.lower() and (iconic or not user32.IsIconic(h))]
    if not cands:
        return None
    def score(c):
        l, t, r, b = window_rect(c[0])
        return (c[1].lower().endswith(sub.lower()), (r - l) * (b - t))
    return max(cands, key=score)[0]

def alive(hwnd):
    return IS_WIN and bool(hwnd) and bool(user32.IsWindow(hwnd)) and not user32.IsIconic(hwnd)

def iconic(hwnd):
    return IS_WIN and bool(hwnd) and bool(user32.IsIconic(hwnd))

def send_to_back(hwnd):
    """최소화 대신: 포커스를 뺏지 않고 복원한 뒤 모든 창 맨 뒤로. 안 보이지만 계속 그려져서 캡처됨"""
    flags = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(wp)
    user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
    user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, flags)  # HWND_BOTTOM
    user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE: 최대화였어도 보통 크기로 돌아옴
    if wp.flags & 2:  # WPF_RESTORETOMAXIMIZED → 포커스 없이 최대화 크기로 맞춤(최대화 명령은 포커스를 뺏음)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
        r = mi.rcWork
        user32.SetWindowPos(hwnd, 1, r.left, r.top, r.right - r.left, r.bottom - r.top, 0x0010)
    else:
        user32.SetWindowPos(hwnd, 1, 0, 0, 0, 0, flags)

def grab_printwindow(hwnd):
    """가려져 있어도 찍힘(PW_RENDERFULLCONTENT). 하드웨어 가속 화면은 검게 나올 수 있음"""
    r = W.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None
    wdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        if not user32.PrintWindow(hwnd, mdc, 2):
            return None
        class BIH(ctypes.Structure):
            _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD),
                        ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                        ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD),
                        ("biClrImportant", W.DWORD)]
        bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
        return Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, wdc)

def is_on_top(hwnd, box):
    """box(화면 좌표) 안 5개 점이 모두 이 창이면 True. 화면 캡처 방식에서 다른 창이 덮었는지 확인"""
    l, t, r, b = box
    pts = [((l + r) // 2, (t + b) // 2), (l + 10, t + 10), (r - 10, t + 10), (l + 10, b - 10), (r - 10, b - 10)]
    for x, y in pts:
        h = user32.GetAncestor(user32.WindowFromPoint(W.POINT(x, y)), 2)  # GA_ROOT
        if h != hwnd:
            return False
    return True


# ---- 전역 단축키 ----
MODS = {"alt": 1, "ctrl": 2, "shift": 4, "win": 8}
WM_HOTKEY, WM_QUIT, WM_ON, WM_OFF = 0x0312, 0x0012, 0x8001, 0x8002

def parse_hotkey(spec):
    """'shift+z' → (mods, vk)"""
    *mods, key = spec.lower().replace(" ", "").split("+")
    m = 0x4000  # MOD_NOREPEAT
    for x in mods:
        m |= MODS[x]
    if len(key) == 1:
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit():
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"모르는 키: {spec}")
    return m, vk

class Hotkeys(threading.Thread):
    """RegisterHotKey는 등록한 스레드에서만 해제 가능 → 전용 스레드 + 메시지로 on/off"""
    def __init__(self, binds, log):
        super().__init__(daemon=True)
        self.binds = list(binds)  # [(spec, callback)]
        self.log, self.tid, self.ready = log, None, threading.Event()

    def run(self):
        if not IS_WIN:
            self.ready.set()
            return
        msg = W.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # 메시지 큐 생성
        self.tid = kernel32.GetCurrentThreadId()
        self.ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and 0 <= msg.wParam < len(self.binds):
                try:
                    self.binds[msg.wParam][1]()
                except Exception as e:
                    self.log(f"단축키 오류: {e}")
            elif msg.message == WM_ON:
                for i, (spec, _) in enumerate(self.binds):
                    if not user32.RegisterHotKey(None, i, *parse_hotkey(spec)):
                        self.log(f"단축키 {spec} 등록 실패(다른 프로그램이 사용 중)")
            elif msg.message == WM_OFF:
                for i in range(len(self.binds)):
                    user32.UnregisterHotKey(None, i)

    def _post(self, m):
        self.ready.wait()
        if self.tid:
            user32.PostThreadMessageW(self.tid, m, 0, 0)

    def enable(self):
        self._post(WM_ON)

    def disable(self):
        self._post(WM_OFF)

    def stop(self):
        self._post(WM_OFF)
        self._post(WM_QUIT)
