# -*- coding: utf-8 -*-
"""새 버전 확인·받기 (GitHub 공개 저장소).

- 새 버전 = 저장소 main 의 release/latest.json {"version": "3.2", "notes": "..."} 과 release/app.zip (app 폴더 내용).
- 받은 app.zip 의 파일로 app 폴더 파일을 덮어씀. 내 정보·내 서식 등은 app 폴더 밖(APPDATA)에 있어 그대로 남음.
- 덮어쓰기 전 원래 파일은 app\\_backup\\<원래 버전>\\ 에 보관.
"""
import os
import io
import re
import json
import shutil
import zipfile
import urllib.request

APP = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(APP, "VERSION.txt")
CONFIG_FILE = os.path.join(APP, "update_config.json")
UA = "IncheonOffice-Updater"
KEEP = {"log.txt", "_backup"}          # 업데이트로 건드리지 않는 것


def current_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip() or "0"
    except Exception:
        return "0"


def vtuple(v):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) or (0,)


def repo():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return (json.load(f).get("repo") or "").strip().strip("/")
    except Exception:
        return ""


def _get(url, timeout, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


RAW = "https://raw.githubusercontent.com/{}/main/release/{}"


def latest(timeout=5):
    """최신 버전 정보 {version, notes, url} — 없거나 못 읽으면 None."""
    rp = repo()
    if not rp:
        return None
    data = json.loads(_get(RAW.format(rp, "latest.json"), timeout, "application/json").decode("utf-8-sig"))
    ver = str(data.get("version") or "").strip()
    if not ver:
        return None
    return {"version": ver.lstrip("vV"), "notes": (data.get("notes") or "").strip(),
            "url": RAW.format(rp, data.get("file") or "app.zip")}


def newer(info):
    return bool(info) and vtuple(info["version"]) > vtuple(current_version())


def _release_font(path):
    """이 프로그램이 불러 둔 글꼴 파일을 놓아 줌 (그래야 새 파일로 바꿀 수 있음)."""
    try:
        import ctypes
        for _ in range(4):
            if not ctypes.windll.gdi32.RemoveFontResourceExW(path, 0x10, 0):
                break
    except Exception:
        pass


def install(info, timeout=60):
    """app.zip 을 받아 app 폴더에 덮어씀. 바뀐 파일 수를 돌려줌. 문제가 있으면 예외."""
    raw = _get(info["url"], timeout, "application/octet-stream")
    zf = zipfile.ZipFile(io.BytesIO(raw))
    if zf.testzip() is not None:
        raise RuntimeError("받은 파일이 손상되었습니다.")
    names = [n for n in zf.namelist() if not n.endswith("/")]
    # zip 안에 app/ 폴더째 들어 있어도 됨
    prefix = "app/" if names and all(n.startswith("app/") for n in names) else ""
    if (prefix + "main.py") not in names:
        raise RuntimeError("받은 파일에 프로그램(main.py)이 없습니다.")
    backup = os.path.join(APP, "_backup", current_version())
    count = 0
    later = []                                  # 쓰지 못한 파일 (다른 프로그램이 붙잡고 있는 경우)
    items = []
    for n in names:
        rel = n[len(prefix):]
        if not rel or rel.split("/")[0] in KEEP or ".." in rel.split("/"):
            continue
        items.append((n, rel))
    items.sort(key=lambda t: t[1] == "VERSION.txt")     # 버전 파일은 맨 마지막에 (중간에 실패하면 버전이 안 바뀜)
    for n, rel in items:
        dst = os.path.join(APP, *rel.split("/"))
        data = zf.read(n)
        if os.path.exists(dst):
            try:
                with open(dst, "rb") as f:
                    if f.read() == data:        # 같은 파일은 건드리지 않음 (쓰는 중인 글꼴 등)
                        continue
            except Exception:
                pass
            b = os.path.join(backup, *rel.split("/"))
            os.makedirs(os.path.dirname(b), exist_ok=True)
            try:
                shutil.copy2(dst, b)
            except Exception:
                pass
            if dst.lower().endswith((".ttf", ".otf")):
                _release_font(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            with open(dst, "wb") as out:
                out.write(data)
        except PermissionError:
            if rel.endswith((".py", ".txt", ".json")) and rel != "log.txt":
                raise
            later.append(rel)                   # 글꼴·그림 등은 다음에 켤 때 받아도 됨
            continue
        count += 1
    install.skipped = later
    return count
