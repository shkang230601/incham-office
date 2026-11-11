# -*- coding: utf-8 -*-
"""인천상의 오피스 배포 묶음 만들기.

사용:
    python tools/release.py --version 3.2 --notes-file notes.txt --app <app 폴더> [--python <python 폴더>] [--out <출력 폴더>]

하는 일:
 1) <app 폴더>에서 배포할 파일만 골라(시험용 파일 제외) 묶음 폴더를 만듦. VERSION.txt 는 --version 으로 씀.
 2) 개인 정보(휴대폰·메일 등)가 남았는지 검사 — 남으면 멈춤.
 3) <out>/app.zip (업데이트용)과, --python 이 있으면 <out>/인천상의오피스_<버전>.zip (첫 설치용) 생성.
 4) 저장소의 app/ 폴더, release/app_<버전>.zip, release/latest.json 을 새 버전으로 바꿈.
    (git commit·push 는 따로)
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 배포에 넣는 것 (이 밖의 파일은 시험용으로 보고 뺌)
APP_FILES = ["main.py", "hwpctl.py", "logic.py", "styles.py", "updater.py", "update_config.json"]
APP_DIRS = ["assets", "forms", "vendor"]
# 들어가면 안 되는 개인 정보 (글자 파일만 검사)
PRIVATE = [r"강신현", r"topka23", r"010-?6554-?9409", r"032-?810-?2836"]


def copy_app(src, dst, version):
    os.makedirs(dst, exist_ok=True)
    missing = [f for f in APP_FILES if not os.path.exists(os.path.join(src, f))]
    if missing:
        sys.exit("app 폴더에 없는 파일: " + ", ".join(missing))
    for f in APP_FILES:
        shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
    for d in APP_DIRS:
        shutil.copytree(os.path.join(src, d), os.path.join(dst, d),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "prep_*", "st_*"))
    with open(os.path.join(dst, "VERSION.txt"), "w", encoding="utf-8") as f:
        f.write(version + "\n")


def check_private(folder):
    bad = []
    for root, _, files in os.walk(folder):
        for fn in files:
            if not fn.lower().endswith((".py", ".json", ".txt", ".xml", ".bat", ".md")):
                continue
            p = os.path.join(root, fn)
            t = open(p, encoding="utf-8", errors="ignore").read()
            for pat in PRIVATE:
                if re.search(pat, t):
                    bad.append("{} ({})".format(os.path.relpath(p, folder), pat))
    if bad:
        sys.exit("개인 정보가 남아 있어 멈춤:\n  " + "\n  ".join(bad))


# 업데이트 묶음(app.zip)에서 빼는 것: 글꼴은 프로그램이 켜져 있는 동안 잠겨 있어
# 3.1의 옛 업데이트 기능이 덮어쓰다 멈춤. 글꼴은 바뀌지 않으니 첫 설치용에만 넣는다.
# (글꼴을 바꿔야 하면 이 줄을 비우고, 3.2 이상 사용자만 받게 된다는 점을 확인할 것)
UPDATE_SKIP = ("assets/fonts/",)


def zip_dir(folder, zpath, arc_prefix="", skip=()):
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, folder).replace("\\", "/")
                if any(rel.startswith(s) for s in skip):
                    continue
                z.write(p, os.path.join(arc_prefix, rel).replace("\\", "/"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--notes-file", required=True, help="업데이트 창에 보일 내용 (글자 파일)")
    ap.add_argument("--app", required=True, help="원본 app 폴더 (보통 PC의 D:\\클로드\\인천상의오피스\\인천상의오피스\\app 를 받아 온 것)")
    ap.add_argument("--python", help="파이썬 폴더 (첫 설치용 zip을 만들 때만)")
    ap.add_argument("--out", default=os.path.join(REPO, "_build"))
    a = ap.parse_args()
    v = a.version.strip().lstrip("vV")
    notes = open(a.notes_file, encoding="utf-8").read().strip()

    out = os.path.join(a.out, v)
    if os.path.exists(out):
        shutil.rmtree(out)
    stage = os.path.join(out, "인천상의오피스")
    copy_app(a.app, os.path.join(stage, "app"), v)
    for f in ("run_IncheonOffice.bat", "README.txt"):
        shutil.copy2(os.path.join(REPO, f), os.path.join(stage, f))
    check_private(stage)

    app_zip = os.path.join(out, "app.zip")
    zip_dir(os.path.join(stage, "app"), app_zip, skip=UPDATE_SKIP)
    print("업데이트용:", app_zip, os.path.getsize(app_zip) // 1024, "KB")
    if a.python:
        shutil.copytree(a.python, os.path.join(stage, "python"), ignore=shutil.ignore_patterns("__pycache__"))
        full = os.path.join(out, "인천상의오피스_{}.zip".format(v))
        zip_dir(stage, full, "인천상의오피스")
        print("첫 설치용:", full, os.path.getsize(full) // 1024 // 1024, "MB")

    # 저장소 갱신
    repo_app = os.path.join(REPO, "app")
    if os.path.exists(repo_app):
        shutil.rmtree(repo_app)
    shutil.copytree(os.path.join(stage, "app"), repo_app)
    rel = os.path.join(REPO, "release")
    os.makedirs(rel, exist_ok=True)
    for fn in os.listdir(rel):
        if fn.startswith("app") and fn.endswith(".zip"):
            os.remove(os.path.join(rel, fn))
    name = "app_{}.zip".format(v)            # 버전마다 이름이 달라야 GitHub 캐시에 옛 파일이 걸리지 않음
    shutil.copy2(app_zip, os.path.join(rel, name))
    with open(os.path.join(rel, "latest.json"), "w", encoding="utf-8") as f:
        json.dump({"version": v, "notes": notes, "file": name}, f, ensure_ascii=False, indent=1)
    print("저장소 갱신 완료 → git add -A && git commit && git push")


if __name__ == "__main__":
    main()
