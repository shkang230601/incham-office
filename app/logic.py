# -*- coding: utf-8 -*-
"""한글 없이도 시험할 수 있는 순수 텍스트 계산 모음."""
import re
import datetime

# 공무원 기준: '하' 다음은 '거, 너, 더 ...'
HANGUL = list("가나다라마바사아자차카타파하") + list("거너더러머버서어저처커터퍼허")
CIRCLED = [chr(c) for c in range(0x2460, 0x2474)]        # ① ~ ⑳
CIRCLED_HANGUL = [chr(c) for c in range(0x326E, 0x327C)]  # ㉮ ~ ㉻

# 8단계 항목 기호: (모양, 번호종류)
NUM_LEVELS = [
    ("{}.", "n"), ("{}.", "h"), ("{})", "n"), ("{})", "h"),
    ("({})", "n"), ("({})", "h"), ("{}", "c"), ("{}", "ch"),
]
NUM_PATTERNS = [
    re.compile(r"^(\d{1,2})\.(?:\s|$)"),
    re.compile(r"^([가-힣])\.(?:\s|$)"),
    re.compile(r"^(\d{1,2})\)(?:\s|$)"),
    re.compile(r"^([가-힣])\)(?:\s|$)"),
    re.compile(r"^\((\d{1,2})\)(?:\s|$)"),
    re.compile(r"^\(([가-힣])\)(?:\s|$)"),
    re.compile(r"^([①-⑳])"),
    re.compile(r"^([㉮-㉻])"),
]

# 보고서 공통 서식 (기호, 글꼴, 크기, 굵게, 줄간격 %, 문단 위 pt)
# □ 휴먼명조 16 굵게 180% / ○·-·· 휴먼명조 15 160% (1·2·3칸 들여) / ※ 중고딕 12 130%
BULLETS = {
    "□": {"text": "□ ", "face": "휴먼명조", "size": 16, "bold": True, "spacing": 180, "prev": 10},
    "○": {"text": " ○ ", "face": "휴먼명조", "size": 15, "bold": False, "spacing": 160, "prev": 5},
    "-": {"text": "  - ", "face": "휴먼명조", "size": 15, "bold": False, "spacing": 160, "prev": 5},
    "·": {"text": "   · ", "face": "휴먼명조", "size": 15, "bold": False, "spacing": 160, "prev": 5},
    "※": {"text": "    ※ ", "face": "중고딕", "size": 12, "bold": False, "spacing": 130, "prev": 0},
    "*": {"text": "     * ", "face": "중고딕", "size": 12, "bold": False, "spacing": 130, "prev": 0},
}
# 간부회의 자료 서식 (2026. 10. 26. 간부회의 자료에서 읽은 값 — 색은 한글 색값 0xBBGGRR)
_MG = {"face": "맑은 고딕", "spacing": 180, "prev": 0, "ratio": 100}
MEETING = {
    "sec": dict(_MG, text="[ ", size=16, bold=True, color=0x008000, left=0),             # [ 사업계획 ] 초록
    "□": dict(_MG, text="  □ ", size=16, bold=True, color=0x000000, left=0),            # 검정 네모
    "○": dict(_MG, text="○ ", size=15, bold=True, color=0xFF0000, left=51.48),          # 파란 동그라미 (줄 전체 파랑)
    "-": dict(_MG, text="- ", size=15, bold=False, color=0x000000, char_spacing=-5, left=108.18),
    "·": dict(_MG, text="· ", size=15, bold=False, color=0x000000, char_spacing=-4, left=133),
    "▶": dict(_MG, text="▶ 추진사항 : ", size=14, bold=False, color=0x0000FF, char_spacing=-9, left=130),  # 빨강
}
_PUSH = re.compile(r"^\s*▶?\s*(?:추진사항\s*[:：]?)?\s*")
_SEC = re.compile(r"^\s*\[\s*(.*?)\s*\]\s*$")


def meeting_body(kind, line):
    """버튼을 다시 눌러도 기호가 겹치지 않게 줄 앞 기호를 걷어 낸 본문."""
    line = (line or "").rstrip()
    if kind == "▶":
        return _PUSH.sub("", line, count=1)
    if kind == "sec":
        m = _SEC.match(line)
        return m.group(1) if m else line.strip()
    return strip_bullet(line)


# 업무보고·보고서 개조식 순서: □ → ○ → - → ·
BOX_SYMBOLS = ["□", "○", "-", "·"]
BOX_LEVELS = [BULLETS[s] for s in BOX_SYMBOLS]

_STRIP = re.compile(
    r"^\s*(?:[□■○◦❍\-※*·•▪]|\U000F03DA|\d{1,2}[.)]|[가-힣][.)]|\(\d{1,2}\)|\([가-힣]\)|[①-⑳]|[㉮-㉻])\s*"
)


def strip_bullet(line):
    """줄 맨 앞의 기존 기호와 앞 공백을 걷어냄."""
    return _STRIP.sub("", line, count=1).lstrip()


def _token(level, idx):
    fmt, kind = NUM_LEVELS[level]
    if kind == "n":
        v = str(idx)
    elif kind == "h":
        v = HANGUL[min(idx, len(HANGUL)) - 1]
    elif kind == "c":
        v = CIRCLED[min(idx, len(CIRCLED)) - 1]
    else:
        v = CIRCLED_HANGUL[min(idx, len(CIRCLED_HANGUL)) - 1]
    return fmt.format(v)


def num_text(level, idx):
    """개조식 기호(□ ○ - ·)와 같이 단계마다 1칸씩 들여씀."""
    return " " * level + _token(level, idx) + " "


# 항목 번호 서식: 개조식 기호와 통일 (1. = □, 가. = ○, 1) = -, 가) 이하 = ·)
_NUM_STYLE_FROM = ["□", "○", "-", "·", "·", "·", "·", "·"]


def num_spec(level, text):
    spec = dict(BULLETS[_NUM_STYLE_FROM[level]])
    spec["text"] = text
    return spec


def detect(line):
    """한 줄에서 (체계, 단계, 순번)을 찾음. 없으면 None."""
    s = line.strip()
    if not s:
        return None
    for i, sym in enumerate(BOX_SYMBOLS):
        if s.startswith(sym + " ") or s == sym:
            return ("box", i, 1)
    if s[:1] in ("◯", "◦", "❍") and (len(s) == 1 or s[1] == " "):
        return ("box", 1, 1)
    for lv, pat in enumerate(NUM_PATTERNS):
        m = pat.match(s)
        if not m:
            continue
        v = m.group(1)
        kind = NUM_LEVELS[lv][1]
        if kind == "n":
            return ("num", lv, int(v))
        if kind == "h":
            if v in HANGUL:
                return ("num", lv, HANGUL.index(v) + 1)
            continue
        if kind == "c":
            return ("num", lv, CIRCLED.index(v) + 1)
        return ("num", lv, CIRCLED_HANGUL.index(v) + 1)
    return None


def next_item(prev_lines, action):
    """action: 'next' | 'down' | 'up'
    돌려주는 값: {'scheme','level','text', (box면) 'face','size','bold'}"""
    found = None
    found_at = -1
    for i in range(len(prev_lines) - 1, -1, -1):
        d = detect(prev_lines[i])
        if d:
            found, found_at = d, i
            break

    if not found:
        return {"scheme": "num", "level": 0, "text": num_text(0, 1)}

    scheme, level, idx = found
    maxlv = len(BOX_LEVELS) - 1 if scheme == "box" else len(NUM_LEVELS) - 1

    if action == "down":
        level, idx = min(level + 1, maxlv), 1
        if found[1] == maxlv:  # 더 내려갈 단계가 없으면 같은 단계 다음 번호
            level, idx = found[1], found[2] + 1
    elif action == "up" and level > 0:
        target = level - 1
        idx = 1
        for j in range(found_at - 1, -1, -1):
            d = detect(prev_lines[j])
            if d and d[0] == scheme:
                if d[1] == target:
                    idx = d[2] + 1
                    break
                if d[1] < target:
                    break
        level = target
    else:  # next (또는 이미 맨 위 단계에서 up)
        idx += 1

    if scheme == "box":
        spec = dict(BOX_LEVELS[level])
        spec.update({"scheme": "box", "level": level})
        return spec
    return {"scheme": "num", "level": level, "text": num_text(level, idx)}


def clean_enters(text):
    """빈 줄 지우기 (범피스 엔터정리)."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n+", "\n", text).strip("\n")
    return text.replace("\n", "\r\n")


_DIG = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
_SMALL = ["", "십", "백", "천"]
_BIG = ["", "만", "억", "조"]


def korean_amount(n):
    if n == 0:
        return "영"
    out = []
    g = 0
    while n > 0:
        part = n % 10000
        if part:
            s = ""
            for pos in range(3, -1, -1):
                d = (part // (10 ** pos)) % 10
                if d:
                    s += _DIG[d] + _SMALL[pos]
            out.append(s + _BIG[g])
        n //= 10000
        g += 1
    return "".join(reversed(out))


def amount_text(selected):
    """범피스 금액한글화: 1000000 → 금1,000,000원(금일백만원)"""
    digits = re.sub(r"[^0-9]", "", selected)
    if not digits:
        raise ValueError("선택한 글에 숫자가 없습니다.")
    n = int(digits)
    return "금{:,}원(금{}원)".format(n, korean_amount(n))


def today_text(d=None):
    """공무원 기준 날짜 표기: 2026. 10. 30."""
    d = d or datetime.date.today()
    return "{}. {}. {}.".format(d.year, d.month, d.day)


# ---------- 수료증 ----------
# 양식 속 예시 글자 → 칸 이름
CERT_SAMPLES = [
    ("번호", "2026-303"),
    ("소속", "인천부평지역자활센터"),
    ("직급", "팀장"),
    ("성명", "김미숙"),
    ("과정명", "전자입찰 실무교육(초·중급과정) 2차"),
    ("수강기간", "2026. 7. 1.(수) 14:00~17:00 (3H)"),
    ("교육구분", "오프라인 교육"),
    ("발급일", "2026년  7월  3일"),
]
_HEADER_WORDS = {"소속", "직급", "성명", "이름", "기관명", "회사명", "직위"}


def parse_roster_rows(rows):
    """[[소속, 직급, 성명], ...] 형태로 정리. 칸이 2개면 소속·성명, 1개면 성명."""
    out = []
    for r in rows:
        cells = ["" if c is None else str(c).strip() for c in r]
        while cells and cells[-1] == "":
            cells.pop()
        if not any(cells):
            continue
        if any(c in _HEADER_WORDS for c in cells):
            continue  # 머리줄 건너뜀
        if len(cells) >= 3:
            org, rank, name = cells[0], cells[1], cells[2]
        elif len(cells) == 2:
            org, rank, name = cells[0], "", cells[1]
        else:
            org, rank, name = "", "", cells[0]
        if name:
            out.append([org, rank, name])
    return out


def parse_roster_text(text):
    """엑셀에서 복사해 붙여 넣은 글(탭으로 나뉨)을 명단으로."""
    rows = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if "\t" in line:
            rows.append(line.split("\t"))
        else:
            rows.append(re.split(r"\s{2,}|,", line))
    return parse_roster_rows(rows)


def cert_numbers(start, count):
    """'2026-303' → ['2026-303', '2026-304', ...] (앞자리 0 유지)"""
    m = re.match(r"^(.*?)(\d+)$", start.strip())
    if not m:
        raise ValueError("시작 번호는 숫자로 끝나야 합니다. 예: 2026-303")
    prefix, num = m.group(1), m.group(2)
    width = len(num)
    return ["{}{}".format(prefix, str(int(num) + i).zfill(width)) for i in range(count)]


def cert_date_text(d=None):
    """수료증 양식 표기: 2026년  10월  30일 (년·월 뒤 두 칸)"""
    d = d or datetime.date.today()
    return "{}년  {}월  {}일".format(d.year, d.month, d.day)


# =====================================================================
# 시험판 3: 줄·숫자·날짜 처리 (한글 없이 계산되는 부분)
# =====================================================================
WEEK = "월화수목금토일"


def split_lines(text):
    return text.replace("\r\n", "\n").split("\n")


def join_lines(lines):
    return "\r\n".join(lines)


def map_lines(text, fn):
    return join_lines([fn(l) for l in split_lines(text)])


# ---------- 줄 정리 ----------
def clean_spaces(text):
    return map_lines(text, lambda l: re.sub(r"[ \t]{2,}", " ", l).strip())


def cut_first_char(l):
    s = l.lstrip()
    return l[: len(l) - len(s)] + s[1:] if s else l


def cut_first_word(l):
    s = l.lstrip()
    parts = s.split(" ", 1)
    return l[: len(l) - len(s)] + (parts[1] if len(parts) > 1 else "")


def cut_last_char(l):
    s = l.rstrip()
    return s[:-1] if s else l


def cut_last_word(l):
    s = l.rstrip()
    return s.rsplit(" ", 1)[0] if " " in s else ""


def add_around(l, front="", back=""):
    return front + l + back if l.strip() else l


def remove_text(l, word):
    return l.replace(word, "") if word else l


def replace_pairs(text, pairs):
    for a, b in pairs:
        if a:
            text = text.replace(a, b)
    return text


def sort_lines(lines, mode):
    body = [l for l in lines if l.strip()]
    if mode == "asc":
        body.sort()
    elif mode == "desc":
        body.sort(reverse=True)
    elif mode == "short":
        body.sort(key=len)
    elif mode == "num_asc":
        body.sort(key=lambda x: to_number(x, 0))
    elif mode == "num_desc":
        body.sort(key=lambda x: to_number(x, 0), reverse=True)
    return body


# ---------- 숫자·금액 ----------
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def to_number(s, default=None):
    m = _NUM.search(s.replace(" ", ""))
    if not m:
        return default
    v = m.group(0).replace(",", "")
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return default


def fmt_number(v, digits=None):
    if digits is not None:
        v = round(v, digits)
        return ("{:,.%df}" % digits).format(v) if digits else "{:,}".format(int(v))
    if isinstance(v, float) and not v.is_integer():
        return "{:,.2f}".format(v).rstrip("0").rstrip(".")
    return "{:,}".format(int(v))


def add_commas(text):
    return _NUM.sub(lambda m: fmt_number(float(m.group(0).replace(",", ""))) if "." in m.group(0)
                    else "{:,}".format(int(m.group(0).replace(",", ""))), text)


def remove_commas(text):
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def unit_convert(text, unit):
    """원 · 천원 · 백만원 · 억원 단위로 나눠 고쳐 씀."""
    div = {"원": 1, "천원": 1000, "백만원": 1000000, "억원": 100000000}[unit]
    v = to_number(text)
    if v is None:
        return text
    r = v / div
    digits = 0 if div < 100000000 else 1
    return fmt_number(r, digits)


def numbers_only(text):
    return re.sub(r"[^0-9.,\-]", "", text)


def remove_paren(text):
    return re.sub(r"\([^)]*\)", "", text).strip()


def paren_inside(text):
    found = re.findall(r"\(([^)]*)\)", text)
    return " ".join(found) if found else text


def calc_expr(text):
    """'1,200 + 800', '3곱하기4' 같은 식 계산."""
    s = text.replace(",", "")
    for k, v in (("더하기", "+"), ("빼기", "-"), ("곱하기", "*"), ("나누기", "/"), ("×", "*"), ("÷", "/"), ("x", "*"), ("X", "*")):
        s = s.replace(k, v)
    s = re.sub(r"[^\d+\-*/().]", "", s)
    if not s or not re.search(r"\d", s):
        raise ValueError("계산할 식을 찾지 못했습니다.")
    import ast
    node = ast.parse(s, mode="eval")
    for n in ast.walk(node):
        if not isinstance(n, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
                              ast.Mult, ast.Div, ast.USub, ast.UAdd)):
            raise ValueError("계산할 수 없는 식입니다.")
    v = eval(compile(node, "<식>", "eval"), {"__builtins__": {}})
    return fmt_number(v)


def percents(values, digits=1):
    total = sum(values)
    if not total:
        raise ValueError("합계가 0이라 비율을 계산할 수 없습니다.")
    return [round(v / total * 100, digits) for v in values]


def pct_text(p):
    return ("{:.1f}".format(p)).rstrip("0").rstrip(".") + "%"


# ---------- 주민번호·나이·개월 ----------
_RRN = re.compile(r"(\d{6})\s*-?\s*(\d)(\d{6})?")


def _birth_from(text):
    m = _RRN.search(text)
    if m:
        yymmdd, g = m.group(1), m.group(2)
        century = {"1": 1900, "2": 1900, "5": 1900, "6": 1900, "3": 2000, "4": 2000, "7": 2000, "8": 2000,
                   "9": 1800, "0": 1800}.get(g, 1900)
        y, mo, d = century + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
        return datetime.date(y, mo, d)
    m = re.search(r"\b(\d{6})\b", text)
    if m:
        yy = int(m.group(1)[:2])
        y = (2000 if yy <= datetime.date.today().year % 100 else 1900) + yy
        return datetime.date(y, int(m.group(1)[2:4]), int(m.group(1)[4:6]))
    d = parse_date(text)
    if d:
        return d
    raise ValueError("주민번호나 생년월일을 찾지 못했습니다.")


def rrn_to_birth(text):
    return date_fmt(_birth_from(text), "dot")


def rrn_mask(text):
    return _RRN.sub(lambda m: "{}-{}******".format(m.group(1), m.group(2)), text)


def age_of(text, today=None):
    b = _birth_from(text)
    t = today or datetime.date.today()
    a = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    return "만 {}세".format(a)


def months_between(text):
    ds = find_dates(text)
    if len(ds) < 2:
        raise ValueError("기간(시작일 ~ 종료일)을 찾지 못했습니다.")
    a, b = ds[0], ds[1]
    m = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        m -= 1
    return "{}개월".format(max(m, 0))


# ---------- 날짜 ----------
_DATE_PATS = [
    re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"),
    re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\.?"),
    re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"),
    re.compile(r"(?<![\d.])(\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\.?"),
]


def find_dates(text):
    out = []
    used = []
    for i, p in enumerate(_DATE_PATS):
        for m in p.finditer(text):
            if any(s <= m.start() < e for s, e in used):
                continue
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if i == 3:
                y += 2000
            try:
                out.append((m.start(), datetime.date(y, mo, d)))
                used.append((m.start(), m.end()))
            except ValueError:
                pass
    return [d for _, d in sorted(out)]


def parse_date(text):
    ds = find_dates(text)
    return ds[0] if ds else None


def date_fmt(d, style):
    w = WEEK[d.weekday()]
    return {
        "dot": "{}. {}. {}.".format(d.year, d.month, d.day),
        "dotw": "{}. {}. {}.({})".format(d.year, d.month, d.day, w),
        "kor": "{}년 {}월 {}일".format(d.year, d.month, d.day),
        "korw": "{}년 {}월 {}일({})".format(d.year, d.month, d.day, w),
        "korfull": "{}년 {}월 {}일 {}요일".format(d.year, d.month, d.day, w),
        "short": "{}. {}. {}.".format(d.year % 100, d.month, d.day),
        "shortw": "{}. {}. {}.({})".format(d.year % 100, d.month, d.day, w),
        "dash": "{:04d}-{:02d}-{:02d}".format(d.year, d.month, d.day),
        "slash": "{:04d}/{:02d}/{:02d}".format(d.year, d.month, d.day),
        "num": "{:04d}{:02d}{:02d}".format(d.year, d.month, d.day),
        "md": "{}. {}.".format(d.month, d.day),
        "mdw": "{}. {}.({})".format(d.month, d.day, w),
        "en": "{} {}, {}".format(["January", "February", "March", "April", "May", "June", "July", "August",
                                  "September", "October", "November", "December"][d.month - 1], d.day, d.year),
        "ja": "{}年{}月{}日".format(d.year, d.month, d.day),
    }[style]


DATE_STYLES = [
    ("dot", "2026. 10. 30."), ("dotw", "2026. 10. 30.(금)"), ("kor", "2026년 10월 30일"),
    ("korw", "2026년 10월 30일(금)"), ("korfull", "2026년 10월 30일 금요일"),
    ("short", "26. 10. 30."), ("shortw", "26. 10. 30.(금)"),
]
CONVERT_STYLES = DATE_STYLES + [("dash", "2026-10-30"), ("slash", "2026/10/30"), ("num", "20261030")]


def convert_dates(text, style):
    """글 속 날짜를 모두 찾아 고른 형식으로."""
    spans = []
    for i, p in enumerate(_DATE_PATS):
        for m in p.finditer(text):
            if any(s <= m.start() < e or s < m.end() <= e for s, e, _ in spans):
                continue
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if i == 3:
                y += 2000
            try:
                dt = datetime.date(y, mo, d)
            except ValueError:
                continue
            end = m.end()
            w = re.match(r"\s*\(([월화수목금토일])\)", text[end:])
            if w:
                end += w.end()
            spans.append((m.start(), end, dt))
    for s, e, dt in sorted(spans, reverse=True):
        text = text[:s] + date_fmt(dt, style) + text[e:]
    return text


def period_text(a, b, style):
    """기간: 2026. 10. 26.(월) ~ 10. 30.(금) — 같은 해면 뒤 연도 생략."""
    same = a.year == b.year
    if style == "dotw":
        right = date_fmt(b, "mdw") if same else date_fmt(b, "dotw")
        return "{} ~ {}".format(date_fmt(a, "dotw"), right)
    if style == "dot":
        right = date_fmt(b, "md") if same else date_fmt(b, "dot")
        return "{} ~ {}".format(date_fmt(a, "dot"), right)
    return "{} ~ {}".format(date_fmt(a, "dotw"), date_fmt(b, "dotw"))


def named_period(name, today=None):
    t = today or datetime.date.today()
    mon = t - datetime.timedelta(days=t.weekday())
    if name == "이번 주":
        return mon, mon + datetime.timedelta(days=4)
    if name == "다음 주":
        s = mon + datetime.timedelta(days=7)
        return s, s + datetime.timedelta(days=4)
    if name == "지난주":
        s = mon - datetime.timedelta(days=7)
        return s, s + datetime.timedelta(days=4)

    def month_range(y, m):
        first = datetime.date(y, m, 1)
        nxt = datetime.date(y + (m == 12), m % 12 + 1, 1)
        return first, nxt - datetime.timedelta(days=1)

    if name == "이번 달":
        return month_range(t.year, t.month)
    if name == "다음 달":
        return month_range(t.year + (t.month == 12), t.month % 12 + 1)
    if name == "지난달":
        return month_range(t.year - (t.month == 1), (t.month - 2) % 12 + 1)
    if name == "올해":
        return datetime.date(t.year, 1, 1), datetime.date(t.year, 12, 31)
    if name == "내년":
        return datetime.date(t.year + 1, 1, 1), datetime.date(t.year + 1, 12, 31)
    if name == "작년":
        return datetime.date(t.year - 1, 1, 1), datetime.date(t.year - 1, 12, 31)
    raise ValueError(name)


def now_text(seconds=False):
    n = datetime.datetime.now()
    s = "{} {:02d}:{:02d}".format(date_fmt(n.date(), "dotw"), n.hour, n.minute)
    return s + ":{:02d}".format(n.second) if seconds else s


def parse_date_input(s):
    d = parse_date(s.strip())
    if not d:
        raise ValueError("날짜를 알아보지 못했습니다: " + s)
    return d


# ---------- 로마 숫자 (큰 제목 번호) ----------
ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ"]


def next_roman(lines):
    last = 0
    for l in lines:
        s = l.strip()
        for i, r in enumerate(ROMAN):
            # 큰 제목 칸의 번호만 셈 ("Ⅰ. 사업내용"처럼 점이 붙은 요약 쪽 소제목은 뺌)
            if s.startswith(r) and not s[len(r):].lstrip().startswith("."):
                last = max(last, i + 1)
    return ROMAN[min(last, len(ROMAN) - 1)]


# ---------- 기호 다루기 ----------
_LEAD = re.compile(r"^(\s*(?:[□■○◦❍\-※*·•▪]|\d{1,2}[.)]|[가-힣][.)]|\(\d{1,2}\)|\([가-힣]\)|[\u2460-\u2473]|[\u326E-\u327B])\s*)")


def lead_of(line):
    m = _LEAD.match(line)
    return m.group(1) if m else ""


def renumber(lines, level):
    """선택한 줄들을 해당 단계 기호로 다시 매김 (빈 줄은 건너뜀)."""
    out, n = [], 0
    for l in lines:
        if not l.strip():
            out.append(l)
            continue
        n += 1
        out.append(num_text(level, n) + strip_bullet(l))
    return out


def circled_lines(lines):
    out, n = [], 0
    for l in lines:
        if l.strip():
            n += 1
            out.append(CIRCLED[min(n, 20) - 1] + " " + strip_bullet(l))
        else:
            out.append(l)
    return out


# ---------- 공문 언어 순화 (국립국어원 행정용어 순화 사례 중 자주 쓰는 말) ----------
PURIFY = [
    ("금일", "오늘"), ("익일", "다음 날"), ("명일", "내일"), ("작일", "어제"), ("상기", "위"),
    ("하기", "아래"), ("기 시행", "이미 시행"), ("기시행", "이미 시행"), ("제고", "높임"), ("지양", "피함"),
    ("가일층", "한층 더"), ("감안하여", "고려하여"), ("개최하고자", "열고자"), ("견지", "입장"),
    ("공람", "돌려 봄"), ("구비서류", "갖출 서류"), ("기재", "적음"), ("내역", "명세"), ("당해", "해당"),
    ("득하여", "받아"), ("만전을 기하", "빈틈없이 하"), ("미연에", "미리"), ("별도", "따로"),
    ("부의", "회의에 올림"), ("불입", "납입"), ("사료됨", "생각됨"), ("사료됩니다", "생각됩니다"),
    ("상이", "서로 다름"), ("수범사례", "모범 사례"), ("시건장치", "잠금장치"), ("여타", "그 밖의"),
    ("요망", "바람"), ("일체", "모두"), ("입회", "참관"), ("잔여", "남은"), ("적의 조치", "알맞게 처리"),
    ("제반", "여러"), ("준수", "지킴"), ("징구", "받음"), ("차기", "다음"),
    ("통보", "알림"), ("필히", "반드시"), ("하시", "언제든지"), ("향후", "앞으로"), ("현행화", "최신화"),
    ("회람", "돌려 봄"), ("가료", "치료"), ("경유", "거침"), ("계도", "깨우침"), ("과년도", "지난해"),
    ("금회", "이번"), ("기존의", "그동안의"), ("노견", "갓길"), ("등재", "올림"), ("만료일", "끝나는 날"),
    ("소정의", "정해진"), ("시달", "알림"), ("일응", "우선"), ("저감", "줄임"),
]


def find_purify(text):
    found = []
    for a, b in PURIFY:
        c = text.count(a)
        if c:
            found.append((a, b, c))
    return found


# ---------- 마크다운 → 한글 ----------
def markdown_lines(text):
    """마크다운 줄을 (기호, 내용) 목록으로. 기호: □ ○ - · ※ 또는 '' (일반 문단)"""
    out = []
    for raw in split_lines(text):
        l = raw.rstrip()
        if not l.strip():
            continue
        s = l.lstrip()
        indent = len(l) - len(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"__(.+?)__", r"\1", s)
        s = s.replace("`", "")
        if re.match(r"^#{1,3}\s+", s):
            out.append(("□", re.sub(r"^#{1,3}\s+", "", s)))
        elif re.match(r"^#{4,6}\s+", s):
            out.append(("○", re.sub(r"^#{4,6}\s+", "", s)))
        elif re.match(r"^[-*+]\s+", s):
            sym = "○" if indent < 2 else ("-" if indent < 4 else "·")
            out.append((sym, re.sub(r"^[-*+]\s+", "", s)))
        elif re.match(r"^\d+[.)]\s+", s):
            sym = "○" if indent < 2 else "-"
            out.append((sym, re.sub(r"^\d+[.)]\s+", "", s)))
        elif s.startswith(">"):
            out.append(("※", s.lstrip("> ")))
        elif re.match(r"^\|?[\s:\-|]+\|?$", s):
            continue  # 표 구분선
        else:
            out.append(("", s))
    return out


def roster_table_rows(n=10):
    return [["연번", "소속", "직위", "성명", "비고"]] + [[str(i + 1), "", "", "", ""] for i in range(n)]


# ---------- 내 서식: 담당자·날짜 자리 ----------
FIELD_RULES = 2  # 자리 찾기 규칙 판 번호 (올리면 예전에 등록한 서식도 열 때 다시 찾음)
# 넣을 정보 종류 (화면 표시 순서)
FIELD_KINDS = [("person", "이름 직위"), ("name", "이름"), ("title", "직위"), ("dept", "소속"),
               ("head_full", "부서장 (유영석 경제진흥실장)"), ("head", "부서장 (유영석 실장)"),
               ("phone", "전화"), ("email", "이메일"), ("date", "날짜 (오늘)"),
               ("date_kor", "날짜 (2026년 10월 31일)")]
FIELD_LABEL = dict(FIELD_KINDS)

_TITLES = "회장|부회장|상근부회장|사무처장|본부장|실장|소장|부장|차장|과장|대리|주임|사원|팀장|국장|위원"
# 직위 뒤 '대우', 괄호 (예: 차장대우(기획))까지 한 덩어리로
_TITLE_FULL = r"(?:" + _TITLES + r")(?:\s?대우)?(?:\s?\([^()\n]{1,12}\))?"
_WEEK = r"(?:\s?\([월화수목금토일]\))?"
_DETECT = [
    ("person", r"(?:홍길동|홍 길 동|○○○|000)\s?" + _TITLE_FULL),
    ("name", r"홍\s?길\s?동"),
    ("email", r"[0○]{3,}@incham\.net"),
    ("phone", r"0\d{1,2}-\d{3,4}-[0○]{4}"),
    ("dept", r"[○0]{2,}(?:실|팀|부|과|센터)(?![가-힣])"),
    # 날짜: 0으로 비운 것뿐 아니라 실제 날짜(예: 2025. 12. 31(월))도 자리로
    ("date", r"20\d\d\.\s?\d{1,2}\.\s?\d{1,2}\.?" + _WEEK),
    ("date_kor", r"20\d\d년\s?\d{1,2}월\s?\d{1,2}일" + _WEEK),
]


def _dept_patterns():
    """부서장 '장조영 경영지원실장' / 부서 이름 '경영지원실' (부서 목록은 아래에 정의)"""
    alt = "|".join(sorted(DEPTS, key=len, reverse=True))
    return [("head_full", r"[가-힣]{2,4}\s?(?:" + alt + r")장"),
            ("dept", r"(?:" + alt + r")(?!장)")]


def detect_fields(text):
    """양식 글에서 바꿀 자리를 찾아 [(찾을 글자, 종류)]로. 이미 넓은 자리에 포함된 글자는 뺌."""
    found = []
    taken = []
    for kind, pat in _dept_patterns() + _DETECT:
        for m in re.finditer(pat, text):
            s, e = m.span()
            if any(s < b and e > a for a, b in taken):  # 겹치면 먼저 잡은(넓은) 자리 우선
                continue
            taken.append((s, e))
            t = m.group(0)
            if t not in [f for f, _ in found]:
                found.append((t, kind))
    return found


def date_like(find, d=None):
    """양식의 날짜 모양을 따라 오늘 날짜로: 요일이 있으면 요일도. 일 뒤에는 늘 점 (공문서 기준)."""
    d = d or datetime.date.today()
    w = "월화수목금토일"[d.weekday()]
    has_w = re.search(r"\([월화수목금토일]\)\s*$", find) is not None
    if "년" in find:
        out = "{}년 {}월 {}일".format(d.year, d.month, d.day)
        return out + ("({})".format(w) if has_w else "")
    return today_text(d) + ("({})".format(w) if has_w else "")


def field_value(kind, find, me, d=None):
    """자리 하나에 넣을 글. 비면 그 자리는 바꾸지 않음."""
    if kind in ("date", "date_kor"):
        return date_like(find, d)
    return field_values(me, d).get(kind, "")


def field_values(me, d=None):
    """종류 → 넣을 글. 비어 있으면 그 자리는 바꾸지 않음."""
    d = d or datetime.date.today()
    me = me or {}
    name, title = me.get("name", "").strip(), me.get("title", "").strip()
    dept = me.get("dept", "").strip()
    head = dept_head(dept)  # 예: '유영석 실장'
    head_name = head.split()[0] if head else ""
    return {
        "person": " ".join(x for x in (name, title) if x) if name else "",
        "name": name, "title": title, "dept": dept,
        "head": head, "head_full": "{} {}장".format(head_name, dept) if head_name else "",
        "phone": me.get("phone", "").strip(), "email": me.get("email", "").strip(),
        "date": today_text(d), "date_kor": "{}년 {}월 {}일".format(d.year, d.month, d.day),
    }


def merge_fields(old, new):
    """예전에 정한 자리와 새로 찾은 자리를 합침: 새로 찾은 것 우선, 예전 것 중 새 자리에 포함되면 뺌."""
    out = [dict(f) for f in new]
    finds = [f["find"] for f in out]
    for f in old or []:
        if f["find"] in finds or any(f["find"] in g for g in finds):
            continue
        out.append(dict(f))
        finds.append(f["find"])
    return out


# ---------- 부서와 문서번호 기호 ----------
DEPT_CODES = [("경영지원실", "인상경"), ("회원협력실", "인상회"), ("경제진흥실", "인상진"), ("국제통상실", "인상국"),
              ("서북부사무소", "인상서북"), ("미래혁신실", "인상미"), ("소통강화공공사업실", "인상소")]
DEPTS = [d for d, _ in DEPT_CODES]


def dept_code(dept):
    return dict(DEPT_CODES).get((dept or "").strip(), "")


# 부서별 팩스번호 (공문 머리글 '전송' 자리)
DEPT_FAX = {"경영지원실": "032-810-2807", "회원협력실": "032-810-2829", "경제진흥실": "032-810-2858",
            "국제통상실": "032-810-2806", "서북부사무소": "032-521-3088", "미래혁신실": "032-810-2807",
            "소통강화공공사업실": "032-810-2913"}


def dept_fax(dept):
    return DEPT_FAX.get((dept or "").strip(), "")


# 부서장 (보도자료 담당자 첫 줄). 미래혁신실은 보류
DEPT_HEAD = {"경영지원실": "장조영 실장", "회원협력실": "최경훈 실장", "경제진흥실": "유영석 실장",
             "국제통상실": "성홍용 실장", "서북부사무소": "고상범 소장", "소통강화공공사업실": "함지현 실장"}


def dept_head(dept):
    return DEPT_HEAD.get((dept or "").strip(), "")


# 여비계산서 예산과목 코드 (여비교통비)
DEPT_BUDGET = {"경영지원실": "371", "회원협력실": "372", "경제진흥실": "373", "국제통상실": "375",
               "미래혁신실": "376", "소통강화공공사업실": "377", "서북부사무소": "530"}


def dept_budget(dept):
    return DEPT_BUDGET.get((dept or "").strip(), "")


# 여비계산서 활동비 (여비 규정 별표, 2025. 9. 1. 개정) — 직위 → 1일 활동비
ACTIVITY_FEE = [
    (("회장",), 300000), (("상근부회장",), 120000), (("사무처장", "사무처 임원", "상무", "전무"), 100000),
    (("실장", "소장", "부서장"), 50000),
    (("차장대우", "차장", "부장대우", "부장"), 45000),
    (("과장대우", "과장"), 40000),
    (("주임", "대리", "사원"), 35000),
]


def activity_fee(title):
    """직위 → 활동비(원). '차장대우(기획)'는 괄호 앞으로 판단. 모르면 None."""
    t = re.sub(r"\(.*?\)", "", title or "").replace(" ", "")
    if not t:
        return None
    for names, fee in ACTIVITY_FEE:
        if t in names:
            return fee
    for names, fee in ACTIVITY_FEE:             # '경제진흥실장'처럼 앞에 말이 붙은 경우
        if any(t.endswith(n) for n in names if n not in ("회장", "장")):
            return fee
    return None


# 여비계산서 명령번호 앞머리 (예: 경제명령 26-0000)
DEPT_CMD = {"경영지원실": "경영", "회원협력실": "회원", "경제진흥실": "경제", "국제통상실": "국제",
            "미래혁신실": "미래", "소통강화공공사업실": "소통", "서북부사무소": "서북"}


def dept_cmd(dept):
    return DEPT_CMD.get((dept or "").strip(), "")


def card_date(d=None):
    """법인카드 사용일시: 2026. 11. 4(수)"""
    d = d or datetime.date.today()
    return "{}. {}. {}({})".format(d.year, d.month, d.day, "월화수목금토일"[d.weekday()])


def fmt_phone(s):
    """0328102865 → 032-810-2865, 0212345678 → 02-1234-5678, 01012345678 → 010-1234-5678.
    숫자가 아닌 글자가 섞였거나 자리 수가 안 맞으면 그대로."""
    raw = (s or "").strip()
    d = re.sub(r"[\\s\\-\\.]", "", raw)
    if not d.isdigit():
        return raw
    if d.startswith("02"):
        if len(d) == 9:
            return "{}-{}-{}".format(d[:2], d[2:5], d[5:])
        if len(d) == 10:
            return "{}-{}-{}".format(d[:2], d[2:6], d[6:])
    elif len(d) == 10:
        return "{}-{}-{}".format(d[:3], d[3:6], d[6:])
    elif len(d) == 11:
        return "{}-{}-{}".format(d[:3], d[3:7], d[7:])
    elif len(d) == 8:  # 1588-0000 같은 대표번호
        return "{}-{}".format(d[:4], d[4:])
    return raw


_PHONE = re.compile(r"(?<![\d\-])(0\d{8,10}|1[568]\d{6})(?![\d\-])")


def find_phones(text):
    """글 속 숫자만 붙은 전화번호 → [(원래, 하이픈 넣은 것)] (겹치지 않게, 나온 차례대로)."""
    out, seen = [], set()
    for m in _PHONE.finditer(text or ""):
        raw = m.group(1)
        f = fmt_phone(raw)
        if f != raw and raw not in seen:
            seen.add(raw)
            out.append((raw, f))
    return out


def fmt_email(s, domain="incham.net"):
    t = (s or "").strip()
    if t and "@" not in t:
        return t + "@" + domain
    return t


def week_period(d=None):
    """주간 일정 기간: 다가오는 일요일~토요일 (오늘이 일요일이면 오늘부터). 예: 26. 11. 1. ~ 26. 11. 7."""
    d = d or datetime.date.today()
    start = d + datetime.timedelta(days=(6 - d.weekday()) % 7)
    end = start + datetime.timedelta(days=6)
    f = lambda x: "{}. {}. {}.".format(x.year % 100, x.month, x.day)
    return "{} ~ {}".format(f(start), f(end))


# ---------- 시간외 근무 ----------
def parse_hm(s):
    """'07:00' '7:30' '0730' '7' '19시 30분' → 분. 못 읽으면 None."""
    t = re.sub(r"[^0-9:]", " ", (s or "").replace("시", ":").replace("분", "")).strip()
    m = re.match(r"^(\d{1,2})\s*:\s*(\d{1,2})", t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        d = re.sub(r"\D", "", t)
        if len(d) in (3, 4):
            h, mi = int(d[:-2]), int(d[-2:])
        elif 1 <= len(d) <= 2:
            h, mi = int(d), 0
        else:
            return None
    if h > 24 or mi > 59:
        return None
    return h * 60 + mi


def hm_text(s):
    v = parse_hm(s)
    return "{:02d}:{:02d}".format(v // 60, v % 60) if v is not None else (s or "").strip()


def ot_hours(a, b):
    """시작·끝 → '1h' '1.5h' (밤을 넘기면 다음 날로 계산). 못 읽으면 ''."""
    x, y = parse_hm(a), parse_hm(b)
    if x is None or y is None:
        return ""
    m = y - x if y > x else y + 24 * 60 - x
    hrs = m / 60.0
    txt = ("%.2f" % hrs).rstrip("0").rstrip(".")
    return txt + "h"


def parse_day(s, today=None):
    """'2026. 6. 24.' '6/24' '2026-06-24' '6월 24일' → date. 비우면 오늘. 못 읽으면 None."""
    today = today or datetime.date.today()
    nums = [int(n) for n in re.findall(r"\d+", s or "")]
    try:
        if not nums:
            return today
        if len(nums) >= 3:
            y = nums[0] + (2000 if nums[0] < 100 else 0)
            return datetime.date(y, nums[1], nums[2])
        if len(nums) == 2:
            return datetime.date(today.year, nums[0], nums[1])
    except ValueError:
        return None
    return None


def ot_day_text(d):
    return "{}년 {}월 {}일({})".format(d.year, d.month, d.day, "월화수목금토일"[d.weekday()])


def ot_period(d1, d2, start, end):
    """(일자 줄, 시간 줄). 하루: '2026년 11월 6일(금)', '07:00~09:00'
    여러 날: '2026년 11월 1일(일) ~ 11월 3일(화)', '11. 1.(일) 06:00 ~ 11. 3.(화) 17:00' (해를 넘기면 끝일에도 연도)."""
    wk = "월화수목금토일"
    if not d2 or d2 == d1:
        return ot_day_text(d1), "{}~{}".format(hm_text(start), hm_text(end))
    end_day = "{}월 {}일({})".format(d2.month, d2.day, wk[d2.weekday()])
    if d2.year != d1.year:
        end_day = "{}년 ".format(d2.year) + end_day
    day = "{} ~ {}".format(ot_day_text(d1), end_day)
    tm = "{}. {}.({}) {} ~ {}. {}.({}) {}".format(d1.month, d1.day, wk[d1.weekday()], hm_text(start),
                                                d2.month, d2.day, wk[d2.weekday()], hm_text(end))
    return day, tm


def ot_total(given, d1, d2, start, end):
    """합계: 직접 적은 값이 우선('6' → '6h'). 비우면 하루짜리만 시간에서 계산, 여러 날은 빈칸."""
    g = (given or "").strip()
    if g:
        return g if re.search(r"[A-Za-z시간]", g) else g + "h"
    if not d2 or d2 == d1:
        return ot_hours(start, end)
    return ""


def ot_content(day, tm, place, what):
    return ("- 일   자 : {}\r\n- 시   간 : {}\r\n- 장   소 : {}\r\n- 내   용 : {}"
            .format(day, tm, place, what))
