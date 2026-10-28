# 세션 폴더: 캡처/YYYY-MM-DD/ (같은 날 다시 시작하면 이어서 씀)
import json, threading, time
from datetime import datetime
from pathlib import Path

def now_hms(ts=None):
    return datetime.fromtimestamp(ts or time.time()).strftime("%H:%M:%S")

def read_jsonl(p):
    p = Path(p)
    if not p.is_file():
        return []
    out = []
    for l in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass  # 다른 스레드가 쓰는 중인 마지막 줄
    return out

class Session:
    def __init__(self, root, date=None):
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.dir = Path(root) / "캡처" / self.date
        (self.dir / "shots").mkdir(parents=True, exist_ok=True)
        (self.dir / "audio").mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def _append(self, name, rec):
        with self._lock, open(self.dir / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def add_shot(self, img, kind, star=False):
        ts = time.time()
        name = datetime.fromtimestamp(ts).strftime("%H%M%S")
        p = self.dir / "shots" / f"{name}.png"
        n = 2
        while p.exists():
            p = self.dir / "shots" / f"{name}_{n}.png"
            n += 1
        img.save(p, optimize=True)
        self._append("shots.jsonl", {"ts": ts, "t": now_hms(ts), "file": f"shots/{p.name}", "kind": kind, "star": star})
        return p

    def add_memo(self, text, ts=None):
        ts = ts or time.time()  # 메모 창을 연 시각 = 그 장면
        self._append("memos.jsonl", {"ts": ts, "t": now_hms(ts), "text": text})

    def add_ocr(self, file, text):
        self._append("ocr.jsonl", {"file": file, "text": text})

    def add_note(self, file, text, ok=True):
        """캡처를 글로 옮긴 것(notes.py). ok=False면 포기 → 최종 정리가 이미지를 직접 봄"""
        self._append("notes.jsonl", {"file": file, "text": text, "ok": ok})

    def add_transcript(self, wav, segs):
        """받아쓰기 초안. segs: [(ts_start, ts_end, text)] 한 조각 분량을 한 번에 기록 → 끝까지 쓴 조각만 done 처리"""
        w = Path(wav).name
        for i, (a, b, t) in enumerate(segs):
            self._append("transcript.jsonl", {"wav": w, "i": i, "ts": a, "te": b, "t": now_hms(a), "text": t})
        self._append("transcribed.jsonl", {"wav": w})

    def add_refined(self, wav, texts, ok=True):
        """다듬은 문장. texts: {i: text}. ok=False면 실패로 기록(초안을 그대로 씀)"""
        for i, t in texts.items():
            self._append("refined.jsonl", {"wav": wav, "i": i, "text": t})
        self._append("refined_done.jsonl", {"wav": wav, "ok": ok})

    def segments(self, wav):
        return [r for r in read_jsonl(self.dir / "transcript.jsonl") if r.get("wav") == wav]

    def pending_refine(self):
        done = {r["wav"] for r in read_jsonl(self.dir / "refined_done.jsonl")}
        return [r["wav"] for r in read_jsonl(self.dir / "transcribed.jsonl") if r["wav"] not in done]

    def ocr_between(self, a, b):
        """a~b 시각에 찍힌 캡처의 OCR 글자(받아쓰기 다듬기 참고용)"""
        ocr = {r["file"]: r["text"] for r in read_jsonl(self.dir / "ocr.jsonl")}
        return [ocr[s["file"]] for s in read_jsonl(self.dir / "shots.jsonl") if a <= s["ts"] <= b and ocr.get(s["file"])]

    def counts(self):
        shots = read_jsonl(self.dir / "shots.jsonl")
        return {"shots": len(shots), "star": sum(s["star"] for s in shots),
                "memos": len(read_jsonl(self.dir / "memos.jsonl"))}

    def pending_ocr(self):
        done = {r["file"] for r in read_jsonl(self.dir / "ocr.jsonl")}
        return [s["file"] for s in read_jsonl(self.dir / "shots.jsonl") if s["file"] not in done]

    def pending_wav(self, exclude=()):
        done = {r["wav"] for r in read_jsonl(self.dir / "transcribed.jsonl")}
        return [p for p in sorted((self.dir / "audio").glob("*.wav")) if p.name not in done and p.name not in exclude]
