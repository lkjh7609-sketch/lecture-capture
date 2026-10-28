# 사용: python add_theme_toggle.py <file.html> [...]      (Mac은 python3)
# 오른쪽 최상단 라이트/다크 토글을 넣는다. 이미 있으면 최신 내용으로 교체한다(여러 번 실행해도 안전).
# 페이지 CSS에 :root[data-theme="dark"] 토큰 블록이 있어야 다크 모드가 실제로 바뀐다.
import re, sys
from pathlib import Path

SNIP = (Path(__file__).resolve().parent / "theme_toggle.html").read_text(encoding="utf-8").strip()
BLOCK = re.compile(r"<!-- theme-toggle:start -->.*?<!-- theme-toggle:end -->", re.S)

def apply(path):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if BLOCK.search(s):
        s = BLOCK.sub(lambda m: SNIP, s, count=1)
    else:
        m = re.search(r"</title>\s*\n", s)
        if not m:
            sys.exit(f"{p}: <title>을 찾지 못함")
        s = s[:m.end()] + SNIP + "\n" + s[m.end():]
    if 'data-theme="dark"' not in s.replace(SNIP, ""):
        print(f"주의: {p.name}에 다크 토큰 블록이 없음 (토글을 눌러도 색이 안 바뀜)")
    p.write_text(s, encoding="utf-8")
    print("ok", p.name)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__ or "사용: python add_theme_toggle.py <file.html> ...")
    for a in sys.argv[1:]:
        apply(a)
