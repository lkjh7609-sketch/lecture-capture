# 사용: python build.py <paper.html> <out.pdf>      (Mac은 python3)
# 2패스 렌더(목차 쪽번호 채움) → 쪽별 PNG → 6쪽씩 컨택트시트
# 필요: Google Chrome(또는 Edge), pip install pymupdf
import html, json, os, re, shutil, subprocess, sys
from pathlib import Path
import pymupdf as fitz

T = Path(__file__).resolve().parent
W = T / ".build"   # _template/.build → ../fonts 상대경로가 days/ 와 동일하게 동작

def find_browser():
    cands = [
        os.environ.get("CHROME", ""),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    cands += [shutil.which(n) or "" for n in ("google-chrome", "chrome", "chromium", "msedge")]
    for c in cands:
        if c and Path(c).is_file():
            return c
    sys.exit("Chrome/Edge를 찾지 못함. 환경변수 CHROME에 실행파일 경로 지정")

def to_pdf(src, out):
    subprocess.run([BROWSER, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=4000", f"--print-to-pdf={out}", src.as_uri()],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def map_headings(src_text, pdf):
    norm = lambda t: re.sub(r"\s+", "", t)
    pages = [p.get_text() for p in fitz.open(pdf)]
    # 일부 뷰어/폰트에서 줄이 뒤집혀 추출되므로 역순도 같이 검색
    np_ = [norm(p + "\n" + "\n".join(l[::-1] for l in p.split("\n"))) for p in pages]
    heads = re.findall(r'<h[23] id="([^"]+)"><span class="n">([^<]+)</span>([^<]+)</h[23]>', src_text)
    keys = [(i, norm(html.unescape(n + t))) for i, n, t in heads]
    toc_end = next((k for k, p in enumerate(np_) if keys and keys[-1][1] in p), 0)
    res, miss, cur = {}, [], toc_end + 1
    for hid, k in keys:
        f = next((j for j in range(cur, len(np_)) if k in np_[j]), None)
        if f is None:
            miss.append(hid); continue
        res[hid] = f + 1; cur = f
    return len(pages), res, miss

def render(pdf):
    (W / "png").mkdir()
    doc = fitz.open(pdf)
    for i, p in enumerate(doc):
        p.get_pixmap(dpi=65).save(str(W / "png" / f"p{i+1:02d}.png"))
    # 6쪽(3x2)씩 한 장으로
    r = doc[0].rect
    for n in range(0, len(doc), 6):
        sheet = fitz.open()
        pg = sheet.new_page(width=r.width * 3 + 20, height=r.height * 2 + 10)
        pg.draw_rect(pg.rect, color=None, fill=(0.5, 0.5, 0.5))
        for i in range(min(6, len(doc) - n)):
            x, y = (i % 3) * (r.width + 10), (i // 3) * (r.height + 10)
            pg.show_pdf_page(fitz.Rect(x, y, x + r.width, y + r.height), doc, n + i)
        pg.get_pixmap(dpi=40).save(str(W / f"sheet{n//6+1}.png"))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__ or "사용: python build.py <paper.html> <out.pdf>")
    BROWSER = find_browser()
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    shutil.rmtree(W, ignore_errors=True); W.mkdir()
    text = src.read_text(encoding="utf-8")
    shutil.copy(src, W / "pass1.html")   # 1패스도 같은 위치에서 렌더(폰트 경로 동일)
    to_pdf(W / "pass1.html", W / "pass1.pdf")
    n, res, miss = map_headings(text, W / "pass1.pdf")
    i = text.rfind("<script>")
    final = text[:i] + "<script>window.__PAGES=" + json.dumps(res) + ";</script>\n" + text[i:]
    (W / "final.html").write_text(final, encoding="utf-8")
    to_pdf(W / "final.html", out)
    render(out)
    print(f"{n} pages, headings mapped {len(res)} missing {miss}")
    print("png:", W / "png", " sheets:", W / "sheet*.png")
