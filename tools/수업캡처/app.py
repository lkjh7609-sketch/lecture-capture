# 수업캡처: 디스코드 화면 자동 캡처 + 현장 녹음/받아쓰기 + 메모 → 버튼 하나로 /ln(수업정리)
# 실행: python app.py   (exe는 build_exe.bat)
import os, queue, subprocess, sys, threading, time
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk

import config, discord, winapi
from audio import Recorder, Transcriber
from capture import Capturer, Grabber
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

class App:
    def __init__(self):
        winapi.set_dpi_aware()
        self.cfg = config.load()
        self.ui_q = queue.Queue()
        self.session = self.capturer = self.recorder = self.transcriber = self.refiner = self.notes = self.ocr = self.runner = None
        self.hk_paused = False

        self.root = tk.Tk()
        self.root.title("수업캡처")
        self.root.geometry("560x460")
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build_ui()

        self.hotkeys = winapi.Hotkeys([(self.cfg["hotkey_capture"], lambda: self.call(self.manual)),
                                       (self.cfg["hotkey_memo"], lambda: self.call(self.memo))], self.log)
        self.hotkeys.start()
        self.tray = self._tray()
        self.root.after(100, self._pump)
        self.root.after(1000, self._refresh)
        self.log(f"작업 폴더: {config.ROOT}")
        if not config.find_claude():
            self.log("Claude Code가 없습니다. 설치 파일의 'Claude Code 설치'를 켜고 다시 설치하거나, 설치 후 [Claude 로그인]을 누르세요")
        self.log(f"단축키(녹화 중에만): {self.cfg['hotkey_capture']} 수동 캡처★ · {self.cfg['hotkey_memo']} 메모")

    # ---- UI ----
    def _build_ui(self):
        f = ttk.Frame(self.root, padding=10)
        f.pack(fill="both", expand=True)
        self.status = ttk.Label(f, text="대기", font=("", 11, "bold"))
        self.status.pack(anchor="w")
        self.sub = ttk.Label(f, text="")
        self.sub.pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Label(row, text="DAY").pack(side="left")
        self.day = tk.IntVar(value=next_day(config.ROOT))
        ttk.Spinbox(row, from_=1, to=99, width=4, textvariable=self.day).pack(side="left", padx=(4, 12))
        self.v_audio = tk.BooleanVar(value=self.cfg["audio"])
        self.v_ocr = tk.BooleanVar(value=self.cfg["ocr"])
        ttk.Checkbutton(row, text="현장 녹음+받아쓰기", variable=self.v_audio).pack(side="left")
        ttk.Checkbutton(row, text="OCR", variable=self.v_ocr).pack(side="left", padx=8)
        self.v_when = tk.StringVar(value="수업 중" if self.cfg["transcribe_live"] else "정지 후")
        ttk.Label(row, text="받아쓰기").pack(side="left")
        ttk.Combobox(row, textvariable=self.v_when, values=["수업 중", "정지 후"], width=7, state="readonly").pack(side="left", padx=4)

        row = ttk.Frame(f)
        row.pack(fill="x", pady=(6, 0))
        self.v_guard = tk.BooleanVar(value=self.cfg["minimize_guard"])
        ttk.Checkbutton(row, text="디스코드 최소화 가로채기(맨 뒤로 숨김)", variable=self.v_guard).pack(side="left")
        ttk.Button(row, text="디스코드 가림방지 실행", command=self.relaunch_discord).pack(side="right")
        ttk.Button(row, text="Claude 로그인", command=self.claude_login).pack(side="right", padx=6)

        row = ttk.Frame(f)
        row.pack(fill="x", pady=8)
        self.b_start = ttk.Button(row, text="시작", command=self.start)
        self.b_stop = ttk.Button(row, text="정지", command=self.stop, state="disabled")
        self.b_make = ttk.Button(row, text="정리 만들기", command=self.make)
        for b in (self.b_start, self.b_stop, self.b_make):
            b.pack(side="left", padx=(0, 6))
        ttk.Button(row, text="영역 지정", command=self.pick_region).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="폴더", command=lambda: open_path(Session(config.ROOT).dir)).pack(side="left")

        self.logbox = tk.Text(f, height=14, wrap="word", state="disabled")
        self.logbox.pack(fill="both", expand=True)

    def _tray(self):
        try:
            import pystray
        except ImportError:
            return None
        img = Image.new("RGB", (64, 64), "white")
        ImageDraw.Draw(img).ellipse((12, 12, 52, 52), fill="#1f6feb")
        menu = pystray.Menu(
            pystray.MenuItem("창 열기", lambda: self.call(self.show), default=True),
            pystray.MenuItem("수동 캡처★", lambda: self.call(self.manual)),
            pystray.MenuItem("메모", lambda: self.call(self.memo)),
            pystray.MenuItem("단축키 일시정지", lambda: self.call(self.toggle_hk), checked=lambda _: self.hk_paused),
            pystray.MenuItem("종료", lambda: self.call(self.quit)))
        icon = pystray.Icon("suupcapture", img, "수업캡처", menu)
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
            self.logbox.insert("end", f"{datetime.now():%H:%M:%S} {msg}\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.call(w)

    def _refresh(self):
        try:
            self._refresh_status()
        except Exception as e:
            self.log(f"상태 갱신 오류: {e}")
        finally:
            self.root.after(2000, self._refresh)

    def _refresh_status(self):
        s = self.session or Session(config.ROOT)
        c = s.counts()
        rec = self.capturer is not None
        self.status.configure(text=("● 녹화 중" if rec else "대기") + (" · 단축키 일시정지" if self.hk_paused and rec else ""))
        extra = []
        if self.ocr:
            extra.append(f"OCR 대기 {self.ocr.pending()}")
        if self.transcriber:
            extra.append(f"받아쓰기 대기 {self.transcriber.pending()}")
        if self.refiner:
            extra.append(f"다듬기 대기 {self.refiner.pending()}")
        if self.notes:
            extra.append(f"글 옮기기 대기 {self.notes.pending()}")
        self.sub.configure(text=f"{s.date} · 캡처 {c['shots']}장(★{c['star']}) · 메모 {c['memos']}" +
                                ("".join(" · " + e for e in extra)))

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
    def start(self):
        self.cfg.update(audio=self.v_audio.get(), ocr=self.v_ocr.get(), minimize_guard=self.v_guard.get(),
                        transcribe_live=self.v_when.get() == "수업 중")
        config.save(self.cfg)
        if winapi.IS_WIN:
            threading.Thread(target=self._check_discord, daemon=True).start()
        s = Session(config.ROOT)
        if self.session is None or self.session.date != s.date:  # 날짜가 바뀌면 작업자도 새로
            self.session, self.ocr, self.transcriber, self.refiner, self.notes = s, None, None, None, None
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
        self.b_start.configure(state="disabled")
        self.b_stop.configure(state="normal")
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
        self.b_start.configure(state="normal")
        self.b_stop.configure(state="disabled")
        self.log("정지")

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
        if not self.session:
            return
        self.hotkeys.disable()  # 메모에 대문자 Z/X를 칠 수 있게
        t = time.time()
        w = tk.Toplevel(self.root)
        w.title("메모")
        w.attributes("-topmost", True)
        w.geometry(f"520x70+{self.root.winfo_screenwidth() // 2 - 260}+80")
        e = ttk.Entry(w, font=("", 12))
        e.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(w, text="Enter 저장 · Esc 취소").pack()

        def close(save):
            if save and e.get().strip():
                self.session.add_memo(e.get().strip(), ts=t)
                self.log(f"메모: {e.get().strip()[:40]}")
            w.destroy()
            if self.capturer and not self.hk_paused:
                self.hotkeys.enable()
        e.bind("<Return>", lambda _: close(True))
        e.bind("<Escape>", lambda _: close(False))
        w.protocol("WM_DELETE_WINDOW", lambda: close(False))
        w.after(50, lambda: (w.focus_force(), e.focus_set()))

    # ---- 영역 지정 ----
    def pick_region(self):
        w = tk.Toplevel(self.root)
        w.title("캡처할 창과 방송 영역")
        top = ttk.Frame(w, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="창 제목에 포함된 글자").pack(side="left")
        title = tk.StringVar(value=self.cfg["window_title"])
        ttk.Combobox(top, textvariable=title, width=40,
                     values=sorted({t for _, t in winapi.list_windows()})).pack(side="left", padx=6)
        cv = tk.Canvas(w, width=900, height=540, bg="#222")
        cv.pack()
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
            st["rect"] = cv.create_rectangle(ev.x, ev.y, ev.x, ev.y, outline="#1f6feb", width=2)

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
        bot = ttk.Frame(w, padding=8)
        bot.pack(fill="x")
        ttk.Button(bot, text="찍기", command=snap).pack(side="left")
        ttk.Label(bot, text="  방송 화면 부분만 드래그 (채팅·사이드바 제외)").pack(side="left")
        ttk.Button(bot, text="저장", command=lambda: save(False)).pack(side="right")
        ttk.Button(bot, text="창 전체", command=lambda: save(True)).pack(side="right", padx=6)
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
            self.status.configure(text=f"정리 준비 중… 남은 작업 {left}")
            self.root.after(3000, lambda: self._wait_then_run(s))
            return
        tl = build_timeline(s.dir)
        self.log(f"타임라인 생성: {tl.relative_to(config.ROOT)}")
        self.runner = Runner(config.ROOT, tl, self.day.get(), s.date, self.log, lambda ok: self.call(lambda: self._done(ok, s)))
        self.runner.start()

    def _done(self, ok, s):
        self.b_make.configure(text="정리 만들기")
        if ok:
            p = out_html(config.ROOT, s.date)
            self.log(f"완료: {p.name}")
            open_path(p)
        else:
            self.log("정리 실패/취소. 로그 확인")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
