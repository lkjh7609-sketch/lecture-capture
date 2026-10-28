# 처음 실행: 작업 폴더 정하기(새로 만들기 / 이미 있는 폴더)
import customtkinter as ctk
from tkinter import filedialog, messagebox
import ui
from make_icon import draw

def choose(can_create, is_root, new_workspace, command, preview=None):
    """고른 작업 폴더 Path. 창을 닫으면 None"""
    root = ctk.CTk(fg_color=ui.BG)
    root.title("수업캡처 시작하기")
    root.geometry("500x520")
    root.resizable(False, False)
    ui.set_icon(root)
    out = {"dir": None}

    f = ctk.CTkFrame(root, fg_color="transparent")
    f.pack(fill="both", expand=True, padx=28, pady=26)
    ctk.CTkLabel(f, text="", image=ctk.CTkImage(draw(96), size=(52, 52))).pack(anchor="w")
    ui.label(f, "수업캡처 시작하기", 22, True).pack(anchor="w", pady=(14, 2))
    ui.label(f, "캡처·받아쓰기·수업정리를 저장할 작업 폴더를 정해 주세요.", 13, muted=True).pack(anchor="w")

    c = ui.card(f)
    c.pack(fill="x", pady=(20, 10))
    ui.label(c, "새 작업 폴더 만들기", 15, True).pack(anchor="w", padx=18, pady=(16, 0))
    ui.label(c, "문서\\수업정리 에 정리 규칙과 템플릿이 들어간 폴더를 만듭니다.", 12, muted=True).pack(anchor="w", padx=18)
    name = ctk.CTkEntry(c, height=40, corner_radius=10, font=ui.font(13), border_color=ui.LINE,
                        placeholder_text="PDF 표지에 넣을 과정명과 이름 (예: SAP CODE 2기 홍길동)")
    name.pack(fill="x", padx=18, pady=(12, 10))

    def create():
        out["dir"] = new_workspace(name.get().strip())
        root.destroy()
    ui.button(c, "만들기", create, "primary", height=42, size=14,
              state="normal" if can_create else "disabled").pack(fill="x", padx=18, pady=(0, 18))

    def pick():
        sel = filedialog.askdirectory(parent=root, title="수업 자료 폴더(SAPCODE1 등) 선택")
        if not sel:
            return
        if not is_root(sel):
            messagebox.showwarning("수업캡처", f"이 폴더에는 .claude/commands/{command}.md 가 없습니다.\n다른 폴더를 골라 주세요.", parent=root)
            return
        out["dir"] = sel
        root.destroy()
    ui.button(f, "이미 있는 폴더 고르기 (SAPCODE1 등)", pick, height=42, size=13).pack(fill="x")

    if preview:  # 자동 점검: 스크린샷만 찍고 닫기
        root.after(1500, lambda: (ui.grab(root, preview), root.destroy()))
    root.mainloop()
    return out["dir"]
