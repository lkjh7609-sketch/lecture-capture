# exe 진입점. 자동 점검(--selftest <폴더>)에서는 오류를 창 대신 <폴더>/error.txt로 남기고 종료 코드로 알림
import os, sys, traceback

if __name__ == "__main__":
    test = "--selftest" in sys.argv
    try:
        import app
        app.main()
    except Exception:
        if not test:
            raise
        out = sys.argv[sys.argv.index("--selftest") + 1]
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "error.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        os._exit(1)
    if test:
        os._exit(0)
