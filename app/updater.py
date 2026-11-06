# -*- coding: utf-8 -*-
"""새 버전 확인·받기 (GitHub 공개 저장소의 Releases).

- 새 버전 = 저장소의 최신 Release. 이름(tag)이 v3.2 처럼 버전 번호, 첨부 파일은 app.zip (app 폴더 내용).
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


def latest(timeout=5):
    """최신 Release 정보 {version, notes, url} — 없거나 못 읽으면 None."""
    rp = repo()
    if not rp:
        return None
    data = json.loads(_get("https://api.github.com/repos/{}/releases/latest".format(rp), timeout).decode("utf-8"))
    tag = data.get("tag_name") or ""
    asset = next((a for a in data.get("assets", []) if a.get("name", "").lower() == "app.zip"), None)
    if not tag or not asset:
        return None
    return {"version": tag.lstrip("vV"), "notes": (data.get("body") or "").strip(),
            "url": asset.get("browser_download_url"), "size": asset.get("size", 0)}


def newer(info):
    return bool(info) and vtuple(info["version"]) > vtuple(current_version())


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
    for n in names:
        rel = n[len(prefix):]
        if not rel or rel.split("/")[0] in KEEP or ".." in rel.split("/"):
            continue
        dst = os.path.join(APP, *rel.split("/"))
        if os.path.exists(dst):
            b = os.path.join(backup, *rel.split("/"))
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.copy2(dst, b)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with zf.open(n) as src, open(dst, "wb") as out:
            shutil.copyfileobj(src, out)
        count += 1
    return count
