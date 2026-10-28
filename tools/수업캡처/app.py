# 수업캡처: 디스코드 화면 자동 캡처 + 현장 녹음/받아쓰기 + 메모 → 버튼 하나로 /ln(수업정리)
# 실행: python app.py   (exe는 build_exe.bat)   자동 점검: app.py --selftest <스크린샷 폴더>
import os, queue, subprocess, sys, threading, time
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from PIL import ImageTk
import customtkinter as ctk

import config, discord, ui, winapi
from audio import Recorder, Transcriber
from capture import Capturer, Grabber
from make_icon import draw
from notes import Notes
from ocr import OcrWorker
from refine import Refiner
from runner import Runner, next_day, out_html
from session import Session
from timeline import build as build_timeline

def open_path(p):
    if sys.platform == "win32":
        os.startfile(p)
    else:
        subprocess.run(["open", str(p)])

def beep():
    if sys.platform == "win32":
        import winsound
        winsound.MessageBeep()

def hms(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"

class App:
    def __init__(self, preview=None):
        winapi.set_dpi_aware()
        self.cfg = config.load()
        self.preview = preview
        self.ui_q = queue.Queue()
        self.session = self.capturer = self.recorder = self.transcriber = self.refiner = self.notes = self.ocr = self.runner = None
        self.hk_paused = False
        self.phase = ""          # "" | 정리 준비 중… | 정리 만드는 중
        self.rec_total, self.rec_since = 0.0, None

        self.root = ctk.CTk(fg_color=ui.BG)
        self.root.title("수업캡처")
        self.root.geometry("600x620")
        self.root.minsize(560, 560)
        ui.set_icon(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build_ui()

        self.hotkeys = winapi.Hotkeys([(self.cfg["hotkey_capture"], lambda: self.call(self.manual)),
                                       (self.cfg["hotkey_memo"], lambda: self.call(self.memo))], self.log)
        self.hotkeys.start()
        self.tray = None if preview else self._tray()
        self.root.after(100, self._pump)
        self.root.after(300, self._refresh)
        self.log(f"작업 폴더: {config.ROOT}")
        if not config.find_claude():
            self.log("Claude Code가 없습니다. 설치 파일의 'Claude Code 설치'를 켜고 다시 설치하거나, 설치 후 설정 → [Claude 로그인]")
        self.log(f"단축키(녹화 중에만): {self.cfg['hotkey_capture']} 중요 캡처★ · {self.cfg['hotkey_memo']} 메모")

    # ---- UI ----
    def _build_ui(self):
        r = self.root
        top = ctk.CTkFrame(r, fg_color="transparent")
        top.pack(fill="x", padx=22, pady=(18, 10))
        ctk.CTkLabel(top, text="", image=ctk.CTkImage(draw(96), size=(38, 38))).pack(side="left")
        t = ctk.CTkFrame(top, fg_color="transparent")
        t.pack(side="left", padx=12)
        ui.label(t, "수업캡처", 19, True).pack(anchor="w")
        ui.label(t, f"{datetime.now():%Y-%m-%d} · {config.ROOT.name}", 12, muted=True).pack(anchor="w")
        self.tabs = ctk.CTkSegmentedButton(top, values=["홈", "설정"], command=self._tab, height=34, width=140,
                                           font=ui.font(13, True), corner_radius=10, **ui.SEG)
        self.tabs.pack(side="right")
        self.tabs.set("홈")

        self.page_home = ctk.CTkFrame(r, fg_color="transparent")
        self.page_set = ctk.CTkScrollableFrame(r, fg_color="transparent")
        self._build_home(self.page_home)
        self._build_settings(self.page_set)
        self._tab("홈")

    def _tab(self, name):
        for p in (self.page_home, self.page_set):
            p.pack_forget()
        (self.page_home if name == "홈" else self.page_set).pack(fill="both", expand=True, padx=22, pady=(0, 18))

    def _build_home(self, f):
        c = ui.card(f)
        c.pack(fill="x")
        head = ctk.CTkFrame(c, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(16, 4))
        self.dot = ctk.CTkLabel(head, text="●", font=ui.font(16), text_color=ui.MUTED)
        self.dot.pack(side="left")
        self.status = ui.label(head, "대기", 17, True)
        self.status.pack(side="left", padx=(6, 0))

        day = ctk.CTkFrame(head, fg_color=ui.TILE, corner_radius=10)
        day.pack(side="right")
        self.day = tk.IntVar(value=next_day(config.ROOT))
        step = lambda d: self.day.set(max(1, min(99, self.day.get() + d)))
        sb = dict(width=30, height=30, corner_radius=8, fg_color="transparent", hover_color=ui.GHOST_H,
                  text_color=ui.TEXT, font=ui.font(15, True))
        ctk.CTkButton(day, text="−", command=lambda: step(-1), **sb).pack(side="left", padx=(3, 0), pady=3)
        ui.label(day, "DAY", 11, True, muted=True).pack(side="left", padx=(6, 2))
        ctk.CTkLabel(day, textvariable=self.day, width=26, font=ui.font(15, True), text_color=ui.TEXT).pack(side="left")
        ctk.CTkButton(day, text="+", command=lambda: step(1), **sb).pack(side="left", padx=(0, 3), pady=3)

        self.sub = ui.label(c, "", 12, muted=True)
        self.sub.pack(anchor="w", padx=18)

        tiles = ctk.CTkFrame(c, fg_color="transparent")
        tiles.pack(fill="x", padx=12, pady=(12, 16))
        self.tile = {}
        for i, (k, name) in enumerate([("shots", "캡처"), ("star", "중요 ★"), ("memos", "메모"), ("time", "녹화 시간")]):
            tiles.grid_columnconfigure(i, weight=1, uniform="t")
            b = ctk.CTkFrame(tiles, fg_color=ui.TILE, corner_radius=12)
            b.grid(row=0, column=i, sticky="nsew", padx=6)
            self.tile[k] = ui.label(b, "0", 24, True)
            self.tile[k].pack(anchor="w", padx=14, pady=(12, 0))
            ui.label(b, name, 12, muted=True).pack(anchor="w", padx=14, pady=(0, 12))

        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.pack(fill="x", pady=(14, 4))
        btns.grid_columnconfigure((0, 1), weight=1, uniform="b")
        self.b_rec = ui.button(btns, "● 녹화 시작", self.toggle_rec, "primary", height=54, size=16)
        self.b_rec.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.b_make = ui.button(btns, "정리 만들기", self.make, height=54, size=16)
        self.b_make.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ui.label(f, f"녹화 중 단축키   {self.cfg['hotkey_capture'].upper()}  중요 화면 캡처   ·   "
                    f"{self.cfg['hotkey_memo'].upper()}  메모", 12, muted=True).pack(pady=(6, 10))

        lg = ui.card(f)
        lg.pack(fill="both", expand=True)
        ui.label(lg, "기록", 12, True, muted=True).pack(anchor="w", padx=16, pady=(10, 0))
        self.logbox = ctk.CTkTextbox(lg, fg_color="transparent", font=ui.font(12), text_color=ui.MUTED,
                                     wrap="word", activate_scrollbars=True)
        self.logbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.logbox.configure(state="disabled")

    def _row(self, parent, title, desc, widget_fn):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=7)
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ui.label(txt, title, 14, True).pack(anchor="w")
        if desc:
            ui.label(txt, desc, 12, muted=True, justify="left").pack(anchor="w")
        widget_fn(row).pack(side="right")

    def _switch(self, var):
        return lambda row: ctk.CTkSwitch(row, text="", variable=var, command=self._save_opts, width=46,
                                         progress_color=ui.ACCENT)

    def _section(self, f, title):
        ui.label(f, title, 12, True, muted=True).pack(anchor="w", padx=4, pady=(12, 6))
        c = ui.card(f)
        c.pack(fill="x")
        ctk.CTkFrame(c, height=8, fg_color="transparent").pack()
        return c

    def _build_settings(self, f):
        self.v_audio = tk.BooleanVar(value=self.cfg["audio"])
        self.v_ocr = tk.BooleanVar(value=self.cfg["ocr"])
        self.v_guard = tk.BooleanVar(value=self.cfg["minimize_guard"])
        self.v_when = tk.StringVar(value="수업 중" if self.cfg["transcribe_live"] else "정지 후")

        c = self._section(f, "녹음")
        self._row(c, "현장 녹음 + 받아쓰기", "강사 말을 녹음해 글로 옮김. 녹음 파일은 받아쓰기 후 삭제", self._switch(self.v_audio))
        self._row(c, "받아쓰기 시점", "노트북이 느리면 '정지 후'", lambda row: ctk.CTkSegmentedButton(
            row, values=["수업 중", "정지 후"], variable=self.v_when, command=lambda _: self._save_opts(),
            font=ui.font(12, True), height=32, **ui.SEG))
        self._row(c, "화면 글자 읽기 (OCR)", "캡처 속 글자를 미리 뽑아 정리 정확도를 높임", self._switch(self.v_ocr))
        ctk.CTkFrame(c, height=8, fg_color="transparent").pack()

        c = self._section(f, "디스코드 화면")
        self._row(c, "최소화 막기", "녹화 중 최소화하면 맨 뒤로 숨겨서 계속 캡처", self._switch(self.v_guard))
        self._row(c, "캡처 영역", "방송 화면 부분만 지정 (채팅·사이드바 제외)",
                  lambda row: ui.button(row, "영역 지정", self.pick_region, width=120))
        self._row(c, "가림방지 모드", "다른 창에 가려져도 화면이 멈추지 않게 디스코드 재실행",
                  lambda row: ui.button(row, "다시 실행", self.relaunch_discord, width=120))
        ctk.CTkFrame(c, height=8, fg_color="transparent").pack()

        c = self._section(f, "정리")
        self._row(c, "Claude 로그인", "처음 한 번. 수업정리를 만드는 AI 계정",
                  lambda row: ui.button(row, "로그인", self.claude_login, width=120))
        self._row(c, "작업 폴더", str(config.ROOT),
                  lambda row: ui.button(row, "열기", lambda: open_path(Session(config.ROOT).dir), width=120))
        ctk.CTkFrame(c, height=8, fg_color="transparent").pack()

    def _save_opts(self):
        self.cfg.update(audio=self.v_audio.get(), ocr=self.v_ocr.get(), minimize_guard=self.v_guard.get(),
                        transcribe_live=self.v_when.get() == "수업 중")
        if not self.preview:
            config.save(self.cfg)

    def _tray(self):
        try:
            import pystray
        except ImportError:
            return None
        menu = pystray.Menu(
            pystray.MenuItem("창 열기", lambda: self.call(self.show), default=True),
            pystray.MenuItem("중요 캡처★", lambda: self.call(self.manual)),
            pystray.MenuItem("메모", lambda: self.call(self.memo)),
            pystray.MenuItem("단축키 일시정지", lambda: self.call(self.toggle_hk), checked=lambda _: self.hk_paused),
            pystray.MenuItem("종료", lambda: self.call(self.quit)))
        icon = pystray.Icon("suupcapture", draw(64), "수업캡처", menu)
        icon.run_detached()
        return icon

    def call(self, fn):
        """다른 스레드 → tk 스레드"""
        self.ui_q.put(fn)

    def _pump(self):
        while not self.ui_q.empty():
            try:
                self.ui_q.get_nowait()()
            except Exception as e:
                self.log(f"오류: {e}")
        self.root.after(100, self._pump)

    def log(self, msg):
        def w():
            self.logbox.configure(state="normal")
            self.logbox.insert("end", f"{datetime.now():%H:%M:%S}  {msg}\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.call(w)

    def _refresh(self):
        if self.preview:
            return
        try:
            self._refresh_status()
        except Exception as e:
            self.log(f"상태 갱신 오류: {e}")
        finally:
            self.root.after(1000, self._refresh)

    def _refresh_status(self):
        s = self.session or Session(config.ROOT)
        pend = {}
        for name, w in (("받아쓰기", self.transcriber), ("다듬기", self.refiner), ("글 옮기기", self.notes), ("OCR", self.ocr)):
            if w:
                pend[name] = w.pending()
        rec = self.rec_total + (time.time() - self.rec_since if self.rec_since else 0)
        self._render(self.capturer is not None, s.date, s.counts(), pend, rec)

    def _render(self, recording, date, counts, pend, rec_sec):
        if self.phase:
            dot, text = ui.ACCENT, self.phase
        elif recording:
            dot, text = ui.REC, "녹화 중" + (" · 단축키 일시정지" if self.hk_paused else "")
        else:
            dot, text = ui.MUTED, "대기"
        self.dot.configure(text_color=dot)
        self.status.configure(text=text)
        busy = [f"{k} {v}" for k, v in pend.items() if v]
        self.sub.configure(text=date + ("  ·  처리 대기  " + " · ".join(busy) if busy else
                                        "  ·  밀린 작업 없음" if pend else ""))
        self.tile["shots"].configure(text=str(counts["shots"]))
        self.tile["star"].configure(text=str(counts["star"]))
        self.tile["memos"].configure(text=str(counts["memos"]))
        self.tile["time"].configure(text=hms(rec_sec))
        if recording:
            self.b_rec.configure(text="■ 녹화 정지", fg_color=ui.REC, hover_color=ui.REC_H)
        else:
            self.b_rec.configure(text="● 녹화 시작", fg_color=ui.ACCENT, hover_color=ui.ACCENT_H)

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        if self.tray:
            self.root.withdraw()
        else:
            self.quit()

    def quit(self):
        if self.capturer and not messagebox.askyesno("수업캡처", "녹화 중입니다. 정지하고 종료할까요?"):
            return
        self.stop()
        self.hotkeys.stop()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    # ---- 녹화 ----
    def toggle_rec(self):
        (self.stop if self.capturer else self.start)()

    def start(self):
        self._save_opts()
        if winapi.IS_WIN:
            threading.Thread(target=self._check_discord, daemon=True).start()
        s = Session(config.ROOT)
        if self.session is None or self.session.date != s.date:  # 날짜가 바뀌면 작업자도 새로
            self.session, self.ocr, self.transcriber, self.refiner, self.notes = s, None, None, None, None
            self.rec_total = 0.0
        if self.cfg["ocr"] and self.ocr is None:
            self.ocr = OcrWorker(self.session, self.log)
            self.ocr.start()
        if self.cfg["notes"] and self.notes is None:
            self.notes = Notes(self.cfg, self.session, self.log)
            self.notes.start()
        self.capturer = Capturer(self.cfg, self.session, self._on_saved, self.log)
        self.capturer.start()
        if self.cfg["audio"]:
            self.recorder = Recorder(self.cfg, self.session, self._on_chunk, self.log)
            if self.cfg["refine"] and self.refiner is None:
                self.refiner = Refiner(self.cfg, self.session, self.log)
                self.refiner.start()
            if self.transcriber is None:
                self.transcriber = Transcriber(self.cfg, self.session, self.log, self._on_draft,
                                               can_run=lambda: self.cfg["transcribe_live"] or self.capturer is None)
                self.transcriber.start()
            self.recorder.start()
        for w in (self.refiner, self.notes):  # 녹화 중엔 묶어서 처리
            if w:
                w.flush(False)
        self.hk_paused = False
        self.hotkeys.enable()
        self.rec_since = time.time()
        self._set_tray_icon(True)
        self.log(f"시작 → {self.session.dir.relative_to(config.ROOT)}")

    def stop(self):
        if not self.capturer:
            return
        self.capturer.stop()
        self.capturer = None
        if self.recorder:
            self.recorder.stop()
        for w in (self.refiner, self.notes):  # 점심·종료: 남은 것 바로 처리
            if w:
                w.flush()
        self.hotkeys.disable()
        if self.rec_since:
            self.rec_total += time.time() - self.rec_since
            self.rec_since = None
        self._set_tray_icon(False)
        self.log("정지")

    def _set_tray_icon(self, rec):
        if self.tray:
            self.tray.icon = draw(64, rec)

    def _check_discord(self):
        """디스코드가 가림방지 옵션 없이 떠 있으면 다시 실행할지 물어봄"""
        try:
            st = discord.running_flags()
        except Exception:
            return
        if st is False:
            self.call(lambda: messagebox.askyesno(
                "수업캡처", "디스코드가 일반 모드로 실행 중입니다.\n다른 창에 가려지면 화면이 멈춰 캡처가 안 될 수 있습니다.\n\n"
                "가림방지 모드로 디스코드를 다시 실행할까요? (방송에 다시 들어가야 함)") and self.relaunch_discord())

    def claude_login(self):
        """새 터미널에서 claude를 실행해 처음 한 번 로그인"""
        exe = config.find_claude()
        if not exe:
            messagebox.showwarning("수업캡처", "Claude Code를 찾지 못했습니다.\n설치 파일을 다시 실행해 'Claude Code 설치'를 체크하세요.")
            return
        if sys.platform == "win32":
            subprocess.Popen(["cmd", "/k", exe], cwd=config.ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(["open", "-a", "Terminal", str(config.ROOT)])
        self.log("터미널에서 Claude 로그인을 마치면 창을 닫아도 됩니다")

    def relaunch_discord(self):
        if winapi.IS_WIN:
            threading.Thread(target=discord.relaunch, args=(self.log,), daemon=True).start()

    def _on_saved(self, path, star):
        if self.ocr:
            self.ocr.put(f"shots/{path.name}")
        if star:
            beep()
            self.log(f"★ 캡처 {path.name}")

    def _on_draft(self, wav):
        if self.refiner:
            self.refiner.put(wav)

    def _on_chunk(self, path):
        if self.transcriber:
            self.transcriber.put(path)

    def manual(self):
        if self.capturer:
            self.capturer.manual()

    def toggle_hk(self):
        self.hk_paused = not self.hk_paused
        if self.capturer:
            (self.hotkeys.disable if self.hk_paused else self.hotkeys.enable)()

    def memo(self):
        if not self.session and not self.preview:
            return
        self.hotkeys.disable()  # 메모에 대문자 Z/X를 칠 수 있게
        t = time.time()
        w = ctk.CTkToplevel(self.root, fg_color=ui.CARD)
        w.title("메모")
        ui.set_icon(w)
        w.attributes("-topmost", True)
        w.resizable(False, False)
        w.geometry(f"560x118+{self.root.winfo_screenwidth() // 2 - 280}+80")
        head = ctk.CTkFrame(w, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(14, 0))
        ui.label(head, "메모", 14, True).pack(side="left")
        ui.label(head, f"{datetime.fromtimestamp(t):%H:%M:%S} 화면에 붙음", 12, muted=True).pack(side="left", padx=8)
        ui.label(head, "Enter 저장 · Esc 취소", 12, muted=True).pack(side="right")
        e = ctk.CTkEntry(w, height=44, corner_radius=10, font=ui.font(15), border_color=ui.ACCENT, border_width=2,
                         placeholder_text="여기에 입력")
        e.pack(fill="x", padx=18, pady=(8, 16))

        def close(save):
            if save and e.get().strip() and self.session:
                self.session.add_memo(e.get().strip(), ts=t)
                self.log(f"메모: {e.get().strip()[:40]}")
            w.destroy()
            if self.capturer and not self.hk_paused:
                self.hotkeys.enable()
        e.bind("<Return>", lambda _: close(True))
        e.bind("<Escape>", lambda _: close(False))
        w.protocol("WM_DELETE_WINDOW", lambda: close(False))
        w.after(150, lambda: (w.lift(), w.focus_force(), e.focus_set()))
        return w

    # ---- 영역 지정 ----
    def pick_region(self):
        w = ctk.CTkToplevel(self.root, fg_color=ui.BG)
        w.title("캡처 영역 지정")
        ui.set_icon(w)
        top = ctk.CTkFrame(w, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        ui.label(top, "캡처할 창", 13, True).pack(side="left")
        title = tk.StringVar(value=self.cfg["window_title"])
        ctk.CTkComboBox(top, variable=title, width=360, height=34, font=ui.font(13), corner_radius=8,
                        values=sorted({t for _, t in winapi.list_windows()}) or [self.cfg["window_title"]]).pack(side="left", padx=10)
        ui.button(top, "다시 찍기", lambda: snap(), width=100, height=34).pack(side="left")
        frame = ui.card(w)
        frame.pack(padx=16)
        cv = tk.Canvas(frame, width=900, height=540, bg="#111318", highlightthickness=0)
        cv.pack(padx=6, pady=6)
        st = {"img": None, "scale": 1, "box": None, "rect": None}

        def snap():
            cfg = dict(self.cfg, window_title=title.get(), region=None)
            g = Grabber(cfg, self.log)
            img = g.grab()
            if img is None:
                messagebox.showwarning("수업캡처", "창을 찍지 못했습니다. 창이 열려 있고 최소화되지 않았는지 확인하세요.", parent=w)
                return
            sc = min(900 / img.width, 540 / img.height, 1)
            st.update(img=ImageTk.PhotoImage(img.resize((int(img.width * sc), int(img.height * sc)))), scale=sc,
                      size=img.size, box=None)
            cv.delete("all")
            cv.create_image(0, 0, anchor="nw", image=st["img"])

        def press(ev):
            st["p0"] = (ev.x, ev.y)
            st["rect"] = cv.create_rectangle(ev.x, ev.y, ev.x, ev.y, outline=ui.ACCENT, width=3)

        def drag(ev):
            if st.get("rect"):
                cv.coords(st["rect"], *st["p0"], ev.x, ev.y)

        def release(ev):
            if not st.get("img"):
                return
            (x0, y0), (x1, y1) = st["p0"], (ev.x, ev.y)
            W_, H_ = st["size"][0] * st["scale"], st["size"][1] * st["scale"]
            st["box"] = [max(0, min(x0, x1)) / W_, max(0, min(y0, y1)) / H_, min(W_, max(x0, x1)) / W_, min(H_, max(y0, y1)) / H_]

        def save(full):
            box = None if full else st["box"]
            if not full and not box:
                messagebox.showinfo("수업캡처", "방송 화면 부분을 드래그하세요.", parent=w)
                return
            self.cfg.update(window_title=title.get(), region=[round(v, 4) for v in box] if box else None,
                            region_size=list(st["size"]))
            config.save(self.cfg)
            self.log(f"캡처 대상: '{title.get()}' · 영역 {self.cfg['region'] or '창 전체'}")
            w.destroy()

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>", drag)
        cv.bind("<ButtonRelease-1>", release)
        bot = ctk.CTkFrame(w, fg_color="transparent")
        bot.pack(fill="x", padx=16, pady=(8, 14))
        ui.label(bot, "방송 화면 부분만 드래그하세요 (채팅·사이드바 제외)", 12, muted=True).pack(side="left")
        ui.button(bot, "저장", lambda: save(False), "primary", width=110).pack(side="right")
        ui.button(bot, "창 전체", lambda: save(True), width=110).pack(side="right", padx=8)
        w.after(200, snap)

    # ---- 정리 ----
    def make(self):
        if self.runner and self.runner.is_alive():
            if messagebox.askyesno("수업캡처", "정리 생성 중입니다. 취소할까요?"):
                self.runner.cancel()
            return
        if self.capturer:
            if not messagebox.askyesno("수업캡처", "녹화를 정지하고 정리를 만들까요?"):
                return
            self.stop()
        s = self.session or Session(config.ROOT)
        if s.counts()["shots"] == 0:
            messagebox.showinfo("수업캡처", f"{s.date} 캡처가 없습니다.")
            return
        if self.session is None:  # 앱을 다시 켠 뒤라면 남은 받아쓰기·다듬기·글 옮기기부터 마저 함
            self.session = s
            self.ocr = OcrWorker(s, self.log) if self.cfg["ocr"] else None
            self.notes = Notes(self.cfg, s, self.log) if self.cfg["notes"] else None
            self.refiner = Refiner(self.cfg, s, self.log) if self.cfg["refine"] else None
            self.transcriber = Transcriber(self.cfg, s, self.log, self._on_draft) if s.pending_wav() else None
            for w in (self.ocr, self.notes, self.refiner, self.transcriber):
                if w:
                    w.start()
            for w in (self.notes, self.refiner):
                if w:
                    w.flush()
        self.b_make.configure(text="정리 취소")
        self._wait_then_run(s)

    def _wait_then_run(self, s):
        """마지막 녹음 조각·OCR·받아쓰기가 끝날 때까지 기다린 뒤 실행"""
        left = (self.recorder.is_alive() if self.recorder else False) + \
               (self.transcriber.pending() if self.transcriber and self.transcriber.is_alive() else 0) + \
               (self.refiner.pending() if self.refiner and self.refiner.is_alive() else 0) + \
               (self.notes.pending() if self.notes else 0) + \
               (self.ocr.pending() if self.ocr and self.ocr.is_alive() else 0)
        if left:
            self.phase = f"정리 준비 중… 남은 작업 {left}"
            self.root.after(3000, lambda: self._wait_then_run(s))
            return
        self.phase = "정리 만드는 중…"
        tl = build_timeline(s.dir)
        self.log(f"타임라인 생성: {tl.relative_to(config.ROOT)}")
        self.runner = Runner(config.ROOT, tl, self.day.get(), s.date, self.log, lambda ok: self.call(lambda: self._done(ok, s)))
        self.runner.start()

    def _done(self, ok, s):
        self.phase = ""
        self.b_make.configure(text="정리 만들기")
        if ok:
            p = out_html(config.ROOT, s.date)
            self.log(f"완료: {p.name}")
            open_path(p)
        else:
            self.log("정리 실패/취소. 기록 확인")

    # ---- 자동 점검: 화면을 가짜 데이터로 채워 스크린샷 ----
    def _shots(self, out):
        os.makedirs(out, exist_ok=True)
        demo = ["작업 폴더: C:\\Users\\me\\Documents\\수업정리", "시작 → 캡처/2026-10-29",
                "자동 캡처 103512.png (화면 전환)", "받아쓰기 10:30~10:35 완료", "★ 캡처 104301.png",
                "메모: setModel 순서 중요", "다듬기(Haiku) 3조각 완료", "글 옮기기(Opus) 20장 완료"]
        for m in demo:
            self.log(m)
        steps = []
        for mode in ("light", "dark"):
            steps += [lambda m=mode: ctk.set_appearance_mode(m),
                      lambda: (self.tabs.set("홈"), self._tab("홈"),
                               self._render(True, "2026-10-29", {"shots": 132, "star": 8, "memos": 5},
                                            {"받아쓰기": 1, "다듬기": 0, "글 옮기기": 12, "OCR": 0}, 5025)),
                      lambda m=mode: ui.grab(self.root, os.path.join(out, f"home_{m}.png")),
                      lambda: (self.tabs.set("설정"), self._tab("설정")),
                      lambda m=mode: ui.grab(self.root, os.path.join(out, f"settings_{m}.png")),
                      lambda: (self.tabs.set("홈"), self._tab("홈"), self._render(False, "2026-10-29",
                               {"shots": 0, "star": 0, "memos": 0}, {}, 0))]
            steps += [lambda m=mode: ui.grab(self.root, os.path.join(out, f"idle_{m}.png"))]
            steps += [lambda: setattr(self, "_m", self.memo()),
                      lambda m=mode: ui.grab(self._m, os.path.join(out, f"memo_{m}.png")),
                      lambda: self._m.destroy()]
        steps.append(lambda: (self.hotkeys.stop(), self.root.destroy()))

        def run(i=0):
            try:
                steps[i]()
            except Exception:
                import traceback
                open(os.path.join(out, "error.txt"), "w", encoding="utf-8").write(traceback.format_exc())
                os._exit(1)
            if i + 1 < len(steps):
                self.root.after(700, lambda: run(i + 1))
        self.root.after(1500, run)

    def run(self):
        if self.preview:
            self._shots(self.preview)
        self.root.mainloop()

def main():
    """main.py가 부름"""
    if "--selftest" in sys.argv:
        out = sys.argv[sys.argv.index("--selftest") + 1]
        import firstrun
        os.makedirs(out, exist_ok=True)
        firstrun.choose(True, config.is_root, lambda who: None, config.COMMAND, preview=os.path.join(out, "firstrun.png"))
        App(preview=out).run()
        return
    App().run()

if __name__ == "__main__":
    main()
