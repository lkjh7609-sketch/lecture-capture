# lctool.exe: Python이 없는 노트북에서 _template의 .py 스크립트를 실행하는 도구 (pymupdf 포함)
# 사용: lctool.exe _template/build.py <src.html> <out.pdf>
#       lctool.exe _template/add_theme_toggle.py <file.html>
import os, runpy, sys
# 스크립트들이 쓰는 표준 모듈을 exe에 같이 묶기 위해 미리 import
import html, json, re, shutil, subprocess, pathlib, math, base64, tempfile  # noqa: F401
import pymupdf  # noqa: F401

if len(sys.argv) < 2:
    sys.exit("사용: lctool.exe <스크립트.py> [인자...]")
script = os.path.abspath(sys.argv[1])
sys.argv = [script] + sys.argv[2:]
sys.path.insert(0, os.path.dirname(script))
runpy.run_path(script, run_name="__main__")
