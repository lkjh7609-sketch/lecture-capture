# 세션 폴더 → timeline.md (/ln 입력)
# 사용: python timeline.py 캡처/2026-10-28
# 캡처 한 장 = 한 블록. 그 캡처부터 다음 캡처 전까지의 메모·강사 발화를 그 블록에 붙인다
import sys
from bisect import bisect_right
from pathlib import Path
from session import read_jsonl

KIND = {"major": "화면 전환", "minor": "같은 화면에 추가", "manual": "★ 직접 캡처"}

def load(sdir):
    sdir = Path(sdir)
    speech = sorted(read_jsonl(sdir / "transcript.jsonl"), key=lambda r: r["ts"])
    refined = {(r["wav"], r["i"]): r["text"] for r in read_jsonl(sdir / "refined.jsonl")}
    for r in speech:  # 다듬은 문장이 있으면 그것, 없으면 초안
        r["text"] = refined.get((r.get("wav"), r.get("i")), r["text"])
    return {"shots": sorted(read_jsonl(sdir / "shots.jsonl"), key=lambda s: s["ts"]),
            "ocr": {r["file"]: r["text"] for r in read_jsonl(sdir / "ocr.jsonl")},
            "memos": read_jsonl(sdir / "memos.jsonl"),
            "speech": speech,
            "notes": {r["file"]: r for r in read_jsonl(sdir / "notes.jsonl")}}

def make_blocks(shots, memos, speech):
    starts = [s["ts"] for s in shots]
    blocks = [{"shot": None, "memos": [], "speech": []}] + [{"shot": s, "memos": [], "speech": []} for s in shots]
    for m in memos:
        blocks[bisect_right(starts, m["ts"])]["memos"].append(m)
    for r in speech:
        blocks[bisect_right(starts, r["ts"])]["speech"].append(r)
    # 다음 장이 minor(같은 화면에 추가)면 이 장은 다음 장에 다 들어 있음 → 화면마다 마지막 모습만 남김
    # (★·메모 붙은 장은 유지)
    for k, b in enumerate(blocks[1:], 1):
        nxt = blocks[k + 1]["shot"] if k + 1 < len(blocks) else None
        b["skip"] = nxt is not None and nxt["kind"] == "minor" and not b["shot"]["star"] and not b["memos"]
    return blocks

def build(sdir):
    sdir = Path(sdir)
    d = load(sdir)
    shots, notes, ocr = d["shots"], d["notes"], d["ocr"]
    blocks = make_blocks(shots, d["memos"], d["speech"])
    shown = [b["shot"] for b in blocks[1:] if not b["skip"]]
    noted = lambda s: notes.get(s["file"], {}).get("ok")
    mins = sum(r["te"] - r["ts"] for r in d["speech"]) / 60
    out = [f"# 수업 타임라인 {sdir.name}", "",
           f"> 자동 기록. 캡처 {len(shots)}장(글로 옮김 {sum(map(bool, map(noted, shown)))}장, "
           f"이미지 {sum(1 for s in shown if s['star'] or not noted(s))}장, ★ {sum(s['star'] for s in shots)}), "
           f"메모 {len(d['memos'])}개, 받아쓰기 {mins:.0f}분.",
           "> ★ = 내가 직접 찍은 중요 장면. '같은 화면에 추가' = 강사가 펜으로 쓰거나 코드를 더 친 그 화면의 마지막 모습.",
           "> '화면 내용(캡처에서 옮김)' = 수업 중에 캡처를 미리 글로 옮긴 것. 이미지 줄(![])이 있는 블록만 이미지를 직접 볼 것.", ""]
    for b in blocks:
        s = b["shot"]
        if s is None and not (b["memos"] or b["speech"]):
            continue
        if s is None:
            out += ["## 수업 시작 전", ""]
        else:
            out += [f"## {s['t']} · {KIND.get(s['kind'], s['kind'])} · {s['file']}", ""]
            if b["skip"]:
                out += ["(중간 단계, 다음 캡처에 포함됨. 이미지 생략)", ""]
            elif noted(s):
                out += ["**화면 내용(캡처에서 옮김)**", "", notes[s["file"]]["text"].strip(), ""]
                out += [f"![]({s['file']})", ""] if s["star"] else [f"(원본 이미지: `{s['file']}`, 필요할 때만 열기)", ""]
            else:
                out += [f"![]({s['file']})", ""]
                if ocr.get(s["file"], "").strip():
                    out += ["**화면 텍스트(OCR)**", "", "```text", ocr[s["file"]].strip(), "```", ""]
        if b["memos"]:
            out += ["**내 메모**", ""] + [f"- ({m['t'][:5]}) {m['text']}" for m in b["memos"]] + [""]
        if b["speech"]:
            out += ["**강사 설명(받아쓰기)**", "", " ".join(r["text"] for r in b["speech"]), ""]
    p = sdir / "timeline.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용: python timeline.py <세션 폴더>")
    print("ok", build(sys.argv[1]))
