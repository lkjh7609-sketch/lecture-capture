# 수업정리 템플릿

Claude Code에서 `/ln <노트파일> [DAY번호] [YYYY-MM-DD]`를 입력하면 루트에 두 파일이 만들어진다. 규칙 전체는 `.claude/commands/ln.md`에 있다.

| 파일 | 역할 |
|---|---|
| `페이지_SAP_UI5_DD_MM_YYYY.html` | **전체 기록.** 원본 내용을 하나도 빼지 않는다. 맨 위에 "오늘의 핵심"과 클릭할 수 있는 "구조 한눈에 보기", 세부(줄별 설명·받아쓰기 원문·용어 정리)는 접어 둔다. 오른쪽 위 라이트/다크 토글 |
| `강의노트_SAP_UI5_DD_MM_YYYY.pdf` | **핵심 노트(보통 10~15쪽).** 처음 배우는 사람이 이것만 보고 따라 쓸 수 있게: 오늘의 핵심 → 구조 그림 → 문법마다 쓰는 법·예제와 결과·함정 → 실습 → 에러 표 → ABAP 대응표·셀프 체크 → "HTML에만 있는 내용" 목록 |

입력은 수업 메모 텍스트 파일이나 수업캡처 앱이 만든 `캡처/YYYY-MM-DD/timeline.md`(화면 캡처·받아쓰기·메모를 시간순으로 합친 것) 둘 다 된다.

## PDF 구성 규칙 요약
1. **오늘의 핵심** 3~5줄(표지).
2. **구조 한눈에 보기**: 그날 핵심 흐름 1~3개를 번호 붙은 흐름도로. 그림 아래 **간단한 설명**(생활 비유), **따라가 보기**(단계마다 코드 한 줄), **고치려면 / 자주 끊기는 곳**.
3. **개념 절**: 그날 나온 문법·함수·양식은 빠짐없이 `한 줄 정의 → 쓰는 법(문법 틀) → 예제와 결과 → 함정`.
4. 실습 문제와 정답 코드, 원본의 "주의"는 반드시 넣는다.
5. 에러 표(증상 / 원인 / 해결), ABAP 대응표, 셀프 체크 5문항.
6. 부록 C **HTML에만 있는 내용**: PDF에서 뺀 원본 항목을 "항목 → HTML n장"으로 모두 적는다. 원본 전체가 PDF 본문이나 이 목록 중 한 곳에 있어야 한다.

## 준비
- **Windows 노트북**: 수업캡처 설치 파일(`tools/수업캡처/README.md`)을 쓰면 Python 없이 된다. 설치 파일 안에 PDF 빌드 도구(`lctool.exe`)가 들어 있고, 브라우저는 Windows 기본 Edge를 쓴다. Claude Code와 로그인만 필요하다.
- **직접 실행(Mac 등)**: Python 3 + `pip install pymupdf`, Chrome(또는 Edge).

## 구성
| 경로 | 역할 |
|---|---|
| `../.claude/commands/ln.md` | 명령 본문(규칙 전체) |
| `html_reference.html` | HTML 디자인 기준 |
| `paper_reference.html` | PDF 디자인 기준(코드 글꼴 합자 끔: `===`가 `≡`로 안 보이게) |
| `days/dayN.html` | 회차별 PDF 원본 |
| `fonts/` | Noto Serif/Sans KR, JetBrains Mono (OFL). OS와 상관없이 PDF가 같게 나오도록 들어 있음 |
| `build.py` | 2패스 PDF 빌드(목차 쪽번호) + 검사용 PNG |
| `theme_toggle.html` | 페이지 오른쪽 위 라이트/다크 토글 조각 |
| `add_theme_toggle.py` | HTML에 토글 넣기: `python _template/add_theme_toggle.py 파일.html` |

## 빌드만 직접 할 때
```
python _template/build.py _template/days/day1.html out.pdf
```
설치판 노트북에서는 `python` 대신 `"%LOCALAPPDATA%\Programs\LectureCapture\lctool.exe"`.
