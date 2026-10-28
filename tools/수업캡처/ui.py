# 화면 공통: 색·글꼴·아이콘 (customtkinter)
# 색은 (라이트, 다크) 짝. Windows 다크 모드를 따라감
import os, sys, tempfile
import customtkinter as ctk
import make_icon

ctk.set_appearance_mode("system")

FONT = "Malgun Gothic" if sys.platform == "win32" else "Apple SD Gothic Neo"

ACCENT, ACCENT_H = "#0a6ed1", "#0858a8"
REC, REC_H = "#e5484d", "#c93a3f"
OK = "#2f9e5a"
BG = ("#f3f5f9", "#131519")
CARD = ("#ffffff", "#1d2026")
TILE = ("#f3f5f9", "#262a31")
LINE = ("#e2e6ee", "#2d3139")
TEXT = ("#161a22", "#eceef2")
MUTED = ("#6b7280", "#9aa1ad")
GHOST = ("#eef1f6", "#2a2e36")
GHOST_H = ("#e2e7ef", "#343943")

# 세그먼트 버튼: 고른 칸만 흰 카드처럼 떠 보이게
SEG = dict(fg_color=GHOST, selected_color=CARD, selected_hover_color=CARD, unselected_color=GHOST,
           unselected_hover_color=GHOST_H, text_color=TEXT)

def font(size=13, bold=False):
    return ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")

_ICO = None

def set_icon(win):
    """창 제목줄 아이콘. customtkinter 기본 아이콘을 덮음"""
    global _ICO
    if sys.platform != "win32":
        return
    try:
        if _ICO is None:
            _ICO = make_icon.save_ico(os.path.join(tempfile.gettempdir(), "lecture_capture.ico"))
        win.iconbitmap(_ICO)
        win.after(250, lambda: win.iconbitmap(_ICO))  # CTkToplevel은 200ms 뒤 기본 아이콘을 다시 넣음
    except Exception:
        pass

def card(master, **kw):
    return ctk.CTkFrame(master, fg_color=CARD, corner_radius=14, border_width=1, border_color=LINE, **kw)

def button(master, text, command=None, kind="ghost", height=38, size=13, **kw):
    colors = {"primary": (ACCENT, ACCENT_H, "white"), "rec": (REC, REC_H, "white"),
              "ghost": (GHOST, GHOST_H, TEXT)}[kind]
    return ctk.CTkButton(master, text=text, command=command, height=height, corner_radius=10,
                         fg_color=colors[0], hover_color=colors[1], text_color=colors[2],
                         font=font(size, kind != "ghost"), **kw)

def label(master, text="", size=13, bold=False, muted=False, **kw):
    return ctk.CTkLabel(master, text=text, font=font(size, bold), text_color=MUTED if muted else TEXT, **kw)

def grab(win, path):
    """창 스크린샷(자동 점검 미리보기용)"""
    from PIL import ImageGrab
    win.update()
    if sys.platform == "win32":
        import ctypes, winapi
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        box = winapi.window_rect(hwnd)
    else:
        box = (win.winfo_rootx(), win.winfo_rooty(), win.winfo_rootx() + win.winfo_width(), win.winfo_rooty() + win.winfo_height())
    ImageGrab.grab(bbox=box, all_screens=True).save(path)
