# -*- coding: utf-8 -*-
"""서식 세트: 부서별 양식에서 읽은 기호 서식을 저장·불러오기 (한글 없이 동작)"""
import json
import os
import re
from collections import Counter

# 화면에 보여줄 기호 순서
KEY_ORDER = ["Ⅰ", "1.", "가.", "1)", "가)", "(1)", "(가)", "①", "㉮", "□", "○", "◯", "◦", "-", "·", "※", "*"]
BOX_KEYS = {"□", "○", "◯", "◦", "-", "·", "※", "*"}
# 항목 자동 입력 단계별로 쓸 수 있는 기호 (앞쪽이 우선)
BOX_LEVEL_KEYS = [["□"], ["○", "◯", "◦"], ["-"], ["·"]]
NUM_LEVEL_KEYS = ["1.", "가.", "1)", "가)", "(1)", "(가)", "①", "㉮"]

_LEAD = re.compile(
    r"^(\s*(?:[Ⅰ-Ⅹ]\.?|\d{1,2}[.)]|[가-힣][.)]|\(\d{1,2}\)|\([가-힣]\)|[①-⑳]|[㉮-㉻]"
    r"|[□■○◯◦❍\-※*·•▪])\s?)"
)

FIELDS = ["face", "size", "bold", "italic", "spacing", "prev", "char_spacing", "ratio", "align", "left", "color"]


def lead_of(line):
    m = _LEAD.match(line)
    return m.group(1) if m else ""


def key_of(lead):
    s = lead.strip()
    if not s:
        return None
    c = s[0]
    if "Ⅰ" <= c <= "Ⅹ":
        return "Ⅰ"
    if re.match(r"^\d{1,2}\.", s):
        return "1."
    if re.match(r"^[가-힣]\.", s):
        return "가."
    if re.match(r"^\d{1,2}\)", s):
        return "1)"
    if re.match(r"^[가-힣]\)", s):
        return "가)"
    if re.match(r"^\(\d", s):
        return "(1)"
    if re.match(r"^\([가-힣]", s):
        return "(가)"
    if "①" <= c <= "⑳":
        return "①"
    if "㉮" <= c <= "㉻":
        return "㉮"
    if c in "□■":
        return "□"
    if c in "○◯◦❍•":
        return {"○": "○", "◯": "◯", "◦": "◦", "❍": "○", "•": "◦"}[c]
    if c in "-":
        return "-"
    if c in "·▪":
        return "·"
    if c == "※":
        return "※"
    if c == "*":
        return "*"
    return None


def normalize_text(lead, key):
    """기호 앞 칸 수는 그대로 두고, 기호 뒤는 한 칸으로."""
    spaces = len(lead) - len(lead.lstrip())
    sym = lead.strip()
    if key in BOX_KEYS:
        sym = key
    return " " * spaces + sym + " "


def _sig(spec):
    return tuple((k, spec.get(k)) for k in FIELDS)


def pick(specs):
    """같은 기호의 여러 서식 중 가장 많이 쓰인 것. (서식, 줄 수, 섞였는지)"""
    cnt = Counter(_sig(s) for s in specs)
    best_sig, _ = cnt.most_common(1)[0]
    best = next(s for s in specs if _sig(s) == best_sig)
    texts = Counter(s.get("text", "") for s in specs)
    out = dict(best)
    out["text"] = texts.most_common(1)[0][0]
    return out, len(specs), len(cnt) > 1


def summarize(collected):
    """collected: {key: [spec, ...]} → {key: spec(+count, mixed)} (화면 순서대로)"""
    out = {}
    for key in KEY_ORDER:
        if key in collected and collected[key]:
            spec, n, mixed = pick(collected[key])
            spec["count"] = n
            spec["mixed"] = mixed
            out[key] = spec
    return out


def describe(spec):
    parts = [spec.get("face", "?"), "{:g}pt".format(spec.get("size", 0))]
    if spec.get("bold"):
        parts.append("굵게")
    if spec.get("italic"):
        parts.append("기울임")
    parts.append("{}%".format(spec.get("spacing", 160)))
    return " ".join(parts)


# ---------- 저장 ----------
def store_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "IncheonOffice")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "styles.json")


def load(path=None):
    path = path or store_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("sets"), dict):
            raise ValueError
        data.setdefault("current", "기본")
        return data
    except Exception:
        return {"current": "기본", "sets": {}}


def save(data, path=None):
    path = path or store_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def clean_spec(spec):
    return {k: v for k, v in spec.items() if k in FIELDS or k == "text"}


def export_set(data, name, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"incham_style_set": 1, "name": name, "styles": data["sets"][name]}, f, ensure_ascii=False, indent=1)


def import_file(data, path):
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if not obj.get("incham_style_set") or "styles" not in obj:
        raise ValueError("인천상의 오피스 서식 세트 파일이 아닙니다.")
    name = obj.get("name") or os.path.splitext(os.path.basename(path))[0]
    base, i = name, 2
    while name in data["sets"]:
        name = "{} ({})".format(base, i)
        i += 1
    data["sets"][name] = {k: clean_spec(v) for k, v in obj["styles"].items()}
    return name


# ---------- 내 정보 (소속·직위·이름·전화·이메일) ----------
def profile_path():
    return os.path.join(os.path.dirname(store_path()), "profile.json")


def load_profile():
    try:
        with open(profile_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_profile(d):
    try:
        if not d:
            if os.path.exists(profile_path()):
                os.remove(profile_path())
            return
        with open(profile_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


# ---------- 내 서식 (부서 양식) ----------
def myforms_dir():
    d = os.path.join(os.path.dirname(store_path()), "myforms")
    os.makedirs(d, exist_ok=True)
    return d


def myform_path(entry):
    return os.path.join(myforms_dir(), entry["file"])
