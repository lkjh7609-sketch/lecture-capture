# 공개 저장소(lecture-capture)용 파일 만들기: 프로그램 코드 + 템플릿(수업 내용·이름을 뺀 디자인 견본)
# 사용: python publish_public.py <공개 저장소 clone 폴더>
# 강의 자료(PDF·HTML·노트·캡처)는 복사하지 않는다
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]).resolve()

DEMO_MAIN = '''<main>
<header class="hero">
  <h1>강의 정리 견본</h1>
  <p>디자인 기준 견본. /ln 은 이 파일의 레이아웃·CSS·JS·컴포넌트를 그대로 쓰고 본문만 그날 수업 내용으로 채운다.</p>
  <div class="meta"><span>YYYY-MM-DD</span><span>과목</span><span>실습 n개 · 에러 n개</span></div>
</header>

<div class="keys">
  <div class="key"><b>핵심 카드</b><span>오늘의 핵심을 한 줄씩. 3~6개.</span></div>
  <div class="key"><b>코드 표기</b><span>본문 속 <code>코드</code>는 이렇게.</span></div>
</div>

<section class="sec" id="s1">
  <div class="sec-h"><div class="num">1</div><h2>예시 절: 자주 쓰는 컴포넌트</h2></div>
  <p class="lead">절 첫 문단은 lead. 이 절의 결론을 한두 문장으로.</p>
  <h3>설명 상자</h3>
  <div class="callout"><b>보충</b> 일반 설명 상자. <span class="pill add">보충</span> 배지는 원본에 없던 설명 표시.</div>
  <div class="callout warn"><b>주의</b> 실수가 자주 나는 부분.</div>
  <h3>카드 두 칸</h3>
  <div class="grid2">
    <div class="card" style="margin:0"><b>왼쪽 카드</b><br>짧은 설명.</div>
    <div class="card" style="margin:0"><b>오른쪽 카드</b><br>짧은 설명.</div>
  </div>
  <h3>코드</h3>
  <script type="text/x-code" data-lang="xml" data-title="예시.view.xml">
<Page title="{i18n>title}">
    <content>
        <Button text="OK" press=".onPress" />
    </content>
</Page>
  </script>
  <script type="text/x-code" data-lang="js" data-title="예시.controller.js">
onPress: function () {
    let sValue = this.byId("inp").getValue();   // 값 읽기
}
  </script>
  <h3>표</h3>
  <table class="t"><tr><th>항목</th><th>설명</th></tr><tr><td><code>a</code></td><td>첫 번째</td></tr><tr><td><code>b</code></td><td>두 번째</td></tr></table>
  <h3>접기 (자세히)</h3>
  <div class="acc"><button class="acc-h"><span class="eno">자세히</span>펼치면 세부 내용<span class="chev">▶</span></button><div class="acc-b"><p>줄별 설명, 받아쓰기 원문 같은 세부는 여기에.</p></div></div>
</section>

<section class="sec" id="sQ">
  <div class="sec-h"><div class="num">Q</div><h2>셀프 체크</h2></div>
  <p class="hint no-print">문제를 클릭하면 정답이 열린다.</p>
  <div class="acc q"><button class="acc-h"><span class="eno">Q1</span>문제<span class="chev">▶</span></button><div class="acc-b"><p>정답과 한 줄 이유.</p></div></div>
</section>
</main>'''

DEMO_NAV = '''<nav class="toc" aria-label="목차">
  <div class="brand">과목 Day N</div>
  <div class="sub">YYYY-MM-DD 수업 정리</div>
  <ol id="tocList">
    <li><a href="#s1"><span class="n">1</span>예시 절</a></li>
    <li><a href="#sQ"><span class="n">Q</span>셀프 체크</a></li>
  </ol>
</nav>'''

# 견본에서 지운 요소를 찾는 스크립트가 멈추지 않게: 없는 id는 빈 div를 돌려줌
SHIM = '<script>(function(){var g=document.getElementById.bind(document);document.getElementById=function(i){return g(i)||document.createElement("div");};})();</script>\n'

def html_ref():
    s = (ROOT / "_template/html_reference.html").read_text(encoding="utf-8")
    s = re.sub(r'<nav class="toc".*?</nav>', lambda m: DEMO_NAV, s, count=1, flags=re.S)
    s = re.sub(r'<main>.*?</main>', lambda m: DEMO_MAIN, s, count=1, flags=re.S)
    s = re.sub(r'<title>.*?</title>', '<title>강의 정리 견본</title>', s, count=1)
    i = s.rindex('</main>')
    j = s.index('<script>', i)
    return s[:j] + SHIM + s[j:]

DEMO_PAPER = '''<div class="title-page">
  <div class="kicker">STUDY NOTE · DAY 1</div>
  <h1>강의 정리</h1>
  <div class="sub">과정명 이름</div>
  <div class="rule"></div>
  <div class="meta">YYYY년 MM월 DD일<br>과목 · 주제</div>
  <div class="abstract">
    <div class="abs-h">오늘의 핵심</div>
    <ol style="margin:0; padding-left:5mm"><li>핵심 한 줄.</li><li>핵심 한 줄.</li></ol>
    <div class="kw"><b>주제어</b> 키워드1, 키워드2</div>
  </div>
  <div class="legend-note">본문의 † 표시는 원본 수업 노트에 없던 보충 설명이다.</div>
</div>

<div class="toc-page toc">
  <h2>목차</h2>
  <ol id="tocList"></ol>
</div>

<section class="ch">
<h2 id="s1"><span class="n">1.</span>예시 절</h2>
<h3 id="s1-1"><span class="n">1.1</span>그림 · 표 · 코드</h3>
<p><b>한 줄 정의</b> 문단 예시.</p>
<figure>
  <div class="dg"><div class="bx"><b>A</b><small>설명</small></div><span class="ar">→</span><div class="bx"><b>B</b><small>설명</small></div></div>
  <figcaption><b>그림 1.</b> 그림 설명</figcaption>
</figure>
<div class="tw"><table class="t">
  <caption><b>표 1.</b> 표 설명</caption>
  <tr><th>항목</th><th>설명</th></tr>
  <tr><td class="nw">a</td><td>첫 번째</td></tr>
</table></div>
<div class="listing"><div class="cap"><b>코드 1.</b> 코드 설명</div>
<script type="text/x-code" data-lang="js">
let total = 0;   // 주석
</script></div>
<div class="note"><b>주의</b> 메모 상자.</div>
</section>
'''

def paper_ref():
    s = (ROOT / "_template/paper_reference.html").read_text(encoding="utf-8")
    a = s.index('<body>') + len('<body>')
    b = s.rindex('<script>\n(function(){')
    s = s[:a] + '\n' + DEMO_PAPER + '\n' + s[b:]
    return re.sub(r'<title>.*?</title>', '<title>강의 정리 견본</title>', s, count=1)

def main():
    for sub in (".claude/commands", "_template/fonts", "tools/수업캡처", ".github/workflows"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / ".claude/commands/ln.md", OUT / ".claude/commands/ln.md")
    for f in ("README.md", "build.py", "add_theme_toggle.py", "theme_toggle.html"):
        shutil.copy2(ROOT / "_template" / f, OUT / "_template" / f)
    for f in (ROOT / "_template/fonts").iterdir():
        shutil.copy2(f, OUT / "_template/fonts" / f.name)
    (OUT / "_template/html_reference.html").write_text(html_ref(), encoding="utf-8")
    (OUT / "_template/paper_reference.html").write_text(paper_ref(), encoding="utf-8")
    src = ROOT / "tools/수업캡처"
    for f in src.iterdir():
        if f.is_file() and f.suffix in (".py", ".bat", ".iss", ".md", ".txt"):
            shutil.copy2(f, OUT / "tools/수업캡처" / f.name)
    (OUT / ".github/workflows/lecture-capture.yml").write_text(WORKFLOW, encoding="utf-8")
    (OUT / ".gitignore").write_text((ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
    (OUT / "README.md").write_text(PUBLIC_README, encoding="utf-8")
    # 공개본에 이름이 남지 않았는지 확인
    for p in OUT.rglob("*"):
        if p.is_file() and p.suffix in (".html", ".md", ".py"):
            assert "이" + "재헌" not in p.read_text(encoding="utf-8", errors="ignore"), p
    print("ok", OUT)

WORKFLOW = '''# 수업캡처 Windows 설치 파일 자동 빌드
# GitHub → Actions → "수업캡처 설치 파일" → 최신 실행 → Artifacts의 LectureCapture-Setup 다운로드
name: 수업캡처 설치 파일
on:
  workflow_dispatch:
  push:
    paths: ["tools/수업캡처/**", ".github/workflows/lecture-capture.yml"]
jobs:
  build:
    runs-on: windows-latest
    defaults:
      run:
        shell: cmd
        working-directory: tools/수업캡처
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: exe 빌드
        run: call build_exe.bat nopause
      - name: Inno Setup 준비
        run: if not exist "%ProgramFiles(x86)%\\Inno Setup 6\\ISCC.exe" choco install innosetup -y --no-progress
      - name: 설치 파일 만들기
        run: '"%ProgramFiles(x86)%\\Inno Setup 6\\ISCC.exe" installer.iss'
      - uses: actions/upload-artifact@v4
        with:
          name: LectureCapture-Setup
          path: tools/수업캡처/Output/*.exe
          retention-days: 30
'''

PUBLIC_README = '''# 수업캡처 (Lecture Capture)

디스코드 화면공유 수업을 자동으로 캡처하고, 현장 음성을 받아쓰고, 메모를 모아 버튼 하나로 강의 정리(인터랙티브 HTML + 핵심 PDF)를 만드는 Windows 프로그램.

- 설치·사용법: [tools/수업캡처/README.md](tools/수업캡처/README.md)
- 정리 규칙(/ln 명령): [.claude/commands/ln.md](.claude/commands/ln.md)
- 템플릿: [_template/](_template/) (`html_reference.html`, `paper_reference.html`은 수업 내용을 뺀 디자인 견본)

## 설치 파일 받기
Actions → "수업캡처 설치 파일" → 최신 실행 → Artifacts → `LectureCapture-Setup`.

이 저장소에는 프로그램 코드와 템플릿만 있다. 강의 자료는 개인 저장소에 따로 둔다.
'''

if __name__ == "__main__":
    main()
