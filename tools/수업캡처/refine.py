# 받아쓰기 초안 → claude -p (기본 Haiku)로 용어·띄어쓰기 교정. 백그라운드
# refine_batch개 조각(기본 15분)씩 묶어 호출 수를 줄인다. 정지·정리 때는 남은 것을 바로 처리(flush)
# 줄마다 [번호]를 붙여 보내고 같은 번호로 받아서 시각 정보를 그대로 유지한다
import re, subprocess, threading
import config

SYSTEM = "너는 강의 받아쓰기 교정기다. 지시한 출력 형식만 지키고 다른 말은 하지 않는다."

PROMPT = """다음은 한국어 IT 강의(SAPUI5, JavaScript, ABAP) 현장 녹음을 자동 받아쓰기한 초안이다. 줄마다 [번호] 텍스트 형식이다.
할 일:
- 잘못 알아들은 용어, API명, 파일명, 코드 이름을 바로잡는다. 아래 '같은 시간대 화면 글자'와 용어 목록을 참고한다.
- 띄어쓰기와 문장부호를 고친다. 말버릇(어, 음, 그…)은 뺀다.
- 뜻을 바꾸거나 내용을 더하거나 요약하지 않는다. 알아들을 수 없는 줄은 원문 그대로 둔다.
출력: 입력과 같은 [번호] 텍스트 줄만. 다른 말, 머리말, 코드블록 금지.

용어: {terms}

같은 시간대 화면 글자(OCR, 틀릴 수 있음):
{ocr}

초안:
{draft}"""

LINE = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

class Refiner(threading.Thread):
    def __init__(self, cfg, session, log):
        super().__init__(daemon=True)
        self.cfg, self.session, self.log = cfg, session, log
        self.waiting = session.pending_refine()  # 지난번에 못 끝낸 것
        self.lock, self.wake = threading.Lock(), threading.Event()
        self.flushing = False
        self.busy = 0

    def put(self, wav):
        with self.lock:
            self.waiting.append(wav)
        self.wake.set()

    def flush(self, on=True):
        """on: 묶음을 기다리지 않고 바로 처리(정지·정리 때). off: 다시 묶어서 처리(녹화 재개)"""
        self.flushing = on
        self.wake.set()

    def pending(self):
        return len(self.waiting) + self.busy

    def run(self):
        exe = config.find_claude()
        if not exe:
            self.log("받아쓰기 다듬기 꺼짐: claude 명령 없음")
            return
        while True:
            self.wake.wait(30)
            self.wake.clear()
            with self.lock:
                if not self.waiting or (len(self.waiting) < self.cfg["refine_batch"] and not self.flushing):
                    continue
                batch, self.waiting = self.waiting[:self.cfg["refine_batch"]], self.waiting[self.cfg["refine_batch"]:]
                self.busy = len(batch)
            try:
                self.refine(exe, batch)
            except Exception as e:
                self.log(f"받아쓰기 다듬기 오류: {e}")
            finally:
                self.busy = 0
                if self.waiting:
                    self.wake.set()

    def refine(self, exe, wavs):
        segs = [s for w in wavs for s in self.session.segments(w)]
        name = f"{wavs[0]}~{wavs[-1]}" if len(wavs) > 1 else wavs[0]
        if not segs:
            for w in wavs:
                self.session.add_refined(w, {}, ok=True)
            return
        ocr = "\n---\n".join(self.session.ocr_between(segs[0]["ts"] - 60, segs[-1]["te"]))[:8000] or "(없음)"
        prompt = PROMPT.format(terms=self.cfg["whisper_prompt"], ocr=ocr,
                               draft="\n".join(f"[{k}] {s['text']}" for k, s in enumerate(segs)))
        cmd = [exe, "-p", "--model", self.cfg["refine_model"], "--system-prompt", SYSTEM,
               "--tools", "", "--no-session-persistence", "--output-format", "text"]
        if self.cfg.get("refine_effort"):
            cmd += ["--effort", self.cfg["refine_effort"]]
        for attempt in (1, 2):
            try:
                r = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=900, creationflags=NOWIN)
                out = {}
                for line in r.stdout.decode("utf-8", "replace").splitlines():
                    m = LINE.match(line)
                    if m and m.group(2).strip() and int(m.group(1)) < len(segs):
                        out[int(m.group(1))] = m.group(2).strip()
                if r.returncode == 0 and len(out) >= len(segs) * 0.8:  # 대부분 돌아왔으면 성공. 빠진 줄은 초안 사용
                    for w in wavs:
                        self.session.add_refined(w, {s["i"]: out[k] for k, s in enumerate(segs) if s["wav"] == w and k in out})
                    self.log(f"받아쓰기 다듬기 {name}: {len(out)}/{len(segs)}줄")
                    return
                self.log(f"받아쓰기 다듬기 {name} 응답 이상({len(out)}/{len(segs)}줄), 시도 {attempt}")
            except Exception as e:
                self.log(f"받아쓰기 다듬기 {name} 오류: {e}")
        for w in wavs:
            self.session.add_refined(w, {}, ok=False)
        self.log(f"받아쓰기 다듬기 {name} 실패 → 초안 사용")
