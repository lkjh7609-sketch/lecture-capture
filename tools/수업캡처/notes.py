# 수업 중 백그라운드: 캡처를 notes_batch장씩 claude -p (기본 Opus)로 읽어 글로 옮겨 둔다
# 8시간 수업이면 이미지가 수백 장 → 마지막 /ln(수업정리)이 한 번에 다 읽다 터지는 걸 막는다
# 결과: notes.jsonl {file, text, ok}. timeline.md가 이미지 대신 이 글을 넣는다
import re, subprocess, threading
import config, time
from timeline import KIND, load, make_blocks

PROMPT = """수업 화면 캡처 {n}장을 글로 옮긴다. 아래 파일을 순서대로 Read 도구로 열어서, 보이는 내용을 빠짐없이 옮겨라.
- 코드: 보이는 그대로 전부, 언어를 표시한 코드블록으로. 줄을 빼거나 고치지 않는다. 파일명·탭 이름도 적는다.
- 슬라이드·문서 글자: 전부. 표는 마크다운 표로.
- 에러 메시지, 콘솔 출력, 파일 트리, 메뉴 경로, 설정 화면 값: 그대로.
- 펜 필기(동그라미, 밑줄, 화살표, 손글씨): 어디에 무엇을 했는지 "[강사 필기] …"로 적는다. 손글씨 글자도 옮긴다.
- 종류가 '같은 화면에 추가'인 장은 펜 필기와 새로 친 코드를 특히 꼼꼼히 본다.
- 요약·해설·추측 금지. 화면에 없는 내용 금지. 디스코드 UI(채팅, 버튼, 참가자 목록)는 무시한다.
출력 형식: 파일마다 아래 머리줄로 시작, 목록 순서대로. 다른 말 금지.
### shots/파일명.png
(내용)

파일:
{files}"""

HEAD = re.compile(r"^###\s+(shots/\S+?)\s*$", re.M)
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

class Notes(threading.Thread):
    def __init__(self, cfg, session, log):
        super().__init__(daemon=True)
        self.cfg, self.session, self.log = cfg, session, log
        self.wake = threading.Event()
        self.flushing, self.busy, self.tries = False, 0, {}

    def flush(self, on=True):
        self.flushing = on
        self.wake.set()

    def targets(self, final):
        d = load(self.session.dir)
        done = set(d["notes"])
        shots = [b["shot"] for b in make_blocks(d["shots"], d["memos"], []) [1:] if not b["skip"]]
        shots = [s for s in shots if s["file"] not in done]
        # 마지막 장은 뒤에 '같은 화면에 추가'가 붙어 중간 단계가 될 수 있으니, 끝낼 때만 처리
        return shots if final else shots[:-1]

    def pending(self):
        return len(self.targets(True)) if self.is_alive() else 0

    def run(self):
        exe = config.find_claude()
        if not exe:
            self.log("캡처 글 옮기기 꺼짐: claude 명령 없음")
            return
        while True:
            self.wake.wait(60)
            self.wake.clear()
            try:
                todo = self.targets(self.flushing)
                if not todo:
                    continue
                if not (self.flushing or len(todo) >= self.cfg["notes_batch"]
                        or time.time() - todo[0]["ts"] >= self.cfg["notes_every_min"] * 60):
                    continue
                n = self.cfg["notes_batch"]
                for k in range(0, len(todo), n):
                    self.busy = 1
                    try:
                        self.transcribe(exe, todo[k:k + n])
                    finally:
                        self.busy = 0
            except Exception as e:  # 스레드가 죽으면 이후 캡처가 전부 이미지로 남으므로 계속 돈다
                self.log(f"캡처 글 옮기기 오류: {e}")

    def transcribe(self, exe, shots):
        files = "\n".join(f"- {s['file']} ({s['t']}, {KIND.get(s['kind'], s['kind'])})" for s in shots)
        cmd = [exe, "-p", "--model", self.cfg["notes_model"], "--tools", "Read", "--allowedTools", "Read",
               "--no-session-persistence", "--output-format", "text"]
        if self.cfg.get("notes_effort"):
            cmd += ["--effort", self.cfg["notes_effort"]]
        name = f"{shots[0]['t']}~{shots[-1]['t']} {len(shots)}장"
        self.log(f"캡처 글 옮기기 시작: {name}")
        try:
            r = subprocess.run(cmd, input=PROMPT.format(n=len(shots), files=files).encode("utf-8"), cwd=self.session.dir,
                               capture_output=True, timeout=1800, creationflags=NOWIN)
            parts = HEAD.split(r.stdout.decode("utf-8", "replace"))
            got = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2) if parts[i + 1].strip()}
        except Exception as e:
            self.log(f"캡처 글 옮기기 오류: {e}")
            got = {}
        for s in shots:
            f = s["file"]
            if f in got:
                self.session.add_note(f, got[f], ok=True)
            else:
                self.tries[f] = self.tries.get(f, 0) + 1
                if self.tries[f] >= 2:  # 두 번 실패하면 포기 → 최종 정리가 이미지를 직접 봄
                    self.session.add_note(f, "", ok=False)
        self.log(f"캡처 글 옮기기 {name}: {sum(s['file'] in got for s in shots)}장 완료")
