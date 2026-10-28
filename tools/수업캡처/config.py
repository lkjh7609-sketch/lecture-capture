# 설정 로드/저장 + 프로젝트 루트 찾기
# 사용자 설정은 tools/수업캡처/config.json (exe를 다시 빌드해도 유지됨)
import json, os, sys
from pathlib import Path

DEFAULTS = {
    "window_title": "Discord",       # 이 글자가 제목에 들어간 창을 캡처
    "region": None,                  # [x0, y0, x1, y1] 창 기준 비율. None이면 창 전체
    "backend": "auto",               # auto | printwindow | screen
    "minimize_guard": True,          # 녹화 중 디스코드 최소화 → 되살려 맨 뒤로(최소화된 창은 못 찍음)
    "interval_sec": 2.0,             # 화면 확인 주기
    "stable_sec": 3.0,               # 이만큼 안 바뀌어야 저장(타이핑·스크롤 도중 제외)
    "major_diff": 0.12,              # 슬라이드 전환급 변화 → 바로 저장
    "minor_cells": 3,                # 펜 필기·코드 한 줄급 변화(바뀐 칸 수, 커서 제외) → min_gap_sec 간격으로 저장
    "min_gap_sec": 20.0,             # 간격 안의 변화는 화면이 넘어가기 직전에 마지막 모습으로 저장
    "hotkey_capture": "shift+z",
    "hotkey_memo": "shift+x",
    "ocr": True,
    "audio": True,
    "chunk_min": 5,
    "transcribe_live": True,         # False면 녹화 중엔 녹음만, 받아쓰기는 정지(점심·종료) 후
    "whisper_model": "small",        # 느리면 base
    "whisper_beam": 1,
    "whisper_prompt": "SAPUI5, ABAP, XML View, Controller, JSONModel, OData, 바인딩, aggregation, manifest.json, Component.js",
    "refine": True,                  # 받아쓰기 초안을 Claude로 다듬기
    "refine_model": "claude-haiku-5-5",  # 가벼운 교정만. 최종 정리(Opus)에서 화면 기준으로 한 번 더 바로잡음
    "refine_effort": "",                 # 빈 값이면 --effort 안 붙임
    "refine_batch": 3,                   # 조각 3개(15분)씩 묶어서 다듬기
    "notes": True,                       # 캡처를 미리 글로 옮겨 둠(최종 정리가 이미지 수백 장을 읽지 않게)
    "notes_model": "claude-opus-5-5",
    "notes_effort": "medium",
    "notes_batch": 20,                   # 이미지 20장마다, 또는
    "notes_every_min": 60,               # 가장 오래된 미처리 캡처가 60분 지나면
    "course": "SAP_UI5",
}

def app_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

COMMAND = "ln"   # .claude/commands/ln.md = /ln (수업정리 명령)

def is_root(p):
    return (Path(p) / ".claude" / "commands" / f"{COMMAND}.md").is_file()

# 설치판은 프로젝트 밖(%LOCALAPPDATA%\Programs)에 깔리므로 고른 폴더를 여기에 기억
ROOT_FILE = Path(os.environ.get("APPDATA") or Path.home()) / "LectureCapture" / "project_root.txt"
# 설치 파일에 들어 있는 빈 작업 폴더 틀(명령 + _template)
TEMPLATE_DIR = app_dir() / "workspace_template"

def new_workspace():
    """문서\\수업정리 에 템플릿을 복사해 새 작업 폴더를 만든다"""
    import shutil
    d = Path.home() / "Documents" / "수업정리"
    if not is_root(d):
        shutil.copytree(TEMPLATE_DIR, d, dirs_exist_ok=True)
        (d / "_template" / "days").mkdir(parents=True, exist_ok=True)
        # 견본 표지의 "과정명 이름"을 내 것으로 (PDF 표지에 그대로 들어감)
        from tkinter import simpledialog
        who = simpledialog.askstring("수업캡처", "PDF 표지에 넣을 과정명과 이름 (예: SAP CODE 2기 홍길동)")
        if who and who.strip():
            p = d / "_template" / "paper_reference.html"
            p.write_text(p.read_text(encoding="utf-8").replace(
                '<div class="sub">과정명 이름</div>', f'<div class="sub">{who.strip()}</div>'), encoding="utf-8")
    return d

def project_root():
    # .claude/commands/ln.md 가 있는 폴더 = 작업 폴더(SAPCODE1)
    for p in [app_dir(), *app_dir().parents]:
        if is_root(p):
            return p
    if ROOT_FILE.is_file() and is_root(ROOT_FILE.read_text(encoding="utf-8").strip()):
        return Path(ROOT_FILE.read_text(encoding="utf-8").strip())
    import tkinter as tk
    from tkinter import filedialog, messagebox
    tk_root = tk.Tk()
    tk_root.withdraw()
    d = None
    if TEMPLATE_DIR.is_dir() and messagebox.askyesno(
            "수업캡처", "수업 자료를 저장할 폴더가 필요합니다.\n\n"
            "예: 새로 만들기 (문서\\수업정리)\n아니오: 이미 있는 폴더(SAPCODE1 등) 고르기"):
        d = new_workspace()
    while d is None:
        sel = filedialog.askdirectory(title="수업 자료 폴더(SAPCODE1) 선택")
        if not sel:
            sys.exit("폴더를 고르지 않아 종료")
        if is_root(sel):
            d = Path(sel)
        else:
            messagebox.showwarning("수업캡처", f"이 폴더에는 .claude/commands/{COMMAND}.md 가 없습니다. 다시 골라 주세요.")
    tk_root.destroy()
    ROOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROOT_FILE.write_text(str(d), encoding="utf-8")
    return Path(d)

def find_claude():
    """claude 실행 파일. 설치 직후엔 PATH가 갱신 안 됐을 수 있어 기본 설치 위치도 본다"""
    import shutil
    hit = shutil.which("claude")
    if hit:
        return hit
    home = Path.home()
    for p in (home / ".local" / "bin" / "claude.exe", home / ".local" / "bin" / "claude",
              Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"):
        if p.is_file():
            return str(p)
    return None

def lctool():
    """설치판에 들어 있는 Python 대용 실행기(lctool.exe). 없으면 None"""
    p = app_dir() / "lctool.exe"
    return str(p) if p.is_file() else None

ROOT = project_root()
CFG_PATH = ROOT / "tools" / "수업캡처" / "config.json"

def load():
    cfg = dict(DEFAULTS)
    if CFG_PATH.is_file():
        cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
    return cfg

def save(cfg):
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
