# claude CLI로 /ln(수업정리) 실행. stream-json 출력을 한 줄씩 요약해 log로 넘김
import json, os, re, subprocess, threading
from pathlib import Path
import config

def next_day(root):
    ns = [int(m.group(1)) for p in (Path(root) / "_template" / "days").glob("day*.html")
          if (m := re.fullmatch(r"day(\d+)", p.stem))]
    return max(ns, default=0) + 1

def out_html(root, date):
    y, m, d = date.split("-")
    return Path(root) / f"페이지_SAP_UI5_{d}_{m}_{y}.html"

class Runner(threading.Thread):
    def __init__(self, root, timeline, day, date, log, done):
        super().__init__(daemon=True)
        self.root, self.timeline, self.day, self.date = Path(root), Path(timeline), day, date
        self.log, self.done = log, done
        self.proc = None

    def run(self):
        exe = config.find_claude()
        if not exe:
            self.log("Claude Code를 찾지 못함. 설치 후 [Claude 로그인] 버튼으로 로그인하세요")
            return self.done(False)
        rel = self.timeline.relative_to(self.root).as_posix()
        prompt = f"/{config.COMMAND} {rel} {self.day} {self.date}"
        cmd = [exe, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--permission-mode", "acceptEdits", "--allowedTools", "Read,Write,Edit,Glob,Grep,Bash"]
        self.log(f"실행: claude -p \"{prompt}\"")
        ok = False
        try:
            env = dict(os.environ)
            if config.lctool():   # 설치판: Python 대신 lctool.exe로 build.py 등을 실행 (ln.md 규칙)
                env["LC_PY"] = config.lctool()
            self.proc = subprocess.Popen(cmd, cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for raw in self.proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                try:
                    ev = json.loads(line)
                except ValueError:
                    if line:
                        self.log(line)
                    continue
                if ev.get("type") == "assistant":
                    for c in ev.get("message", {}).get("content", []):
                        if c.get("type") == "text" and c["text"].strip():
                            self.log("Claude: " + c["text"].strip()[:300])
                        elif c.get("type") == "tool_use":
                            arg = c.get("input", {})
                            hint = arg.get("file_path") or arg.get("command") or arg.get("pattern") or ""
                            self.log(f"  · {c['name']} {str(hint)[:120]}")
                elif ev.get("type") == "result":
                    ok = not ev.get("is_error")
                    self.log(f"끝 ({ev.get('duration_ms', 0) / 60000:.0f}분)")
            self.proc.wait()
            ok = ok and self.proc.returncode == 0
        except Exception as e:
            self.log(f"실행 오류: {e}")
        self.done(ok and out_html(self.root, self.date).is_file())

    def cancel(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
