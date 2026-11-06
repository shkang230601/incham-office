# -*- coding: utf-8 -*-
"""한글(HWP) 자동화 연결과 동작 모음 — 시험판 3"""
import os
import random
import re
import shutil
import datetime

import pythoncom
import win32com.client

import logic
import styles

HFT_FONTS = {"한양신명조", "한양중고딕", "한양견명조", "한양견고딕", "신명조", "중고딕", "견명조"}
# 한글 버전에 따라 이름이 다른 글꼴 (앞에서부터 시도)
FACE_ALIAS = {"중고딕": ["한양중고딕", "HY중고딕"], "신명조": ["한양신명조", "HY신명조"],
              "견명조": ["한양견명조", "HY견명조"], "휴먼명조": ["한양신명조"]}
FONT_OK = {}  # 실제로 먹힌 (글꼴, 종류)를 기억
NAVY = (0, 51, 102)          # 큰 제목 칸 #003366
BAR_NAVY = (52, 54, 119)     # 제목 상자 띠 #343677
BAR_BLUE = (0, 109, 219)     # 제목 상자 띠 #006DDB
TITLE_GRAY = (239, 239, 239)  # 제목 상자 칸 #EFEFEF
HEAD_BLUE = (230, 238, 247)  # 인천상의 표 머리줄 #E6EEF7 (인천시 제목 상자 색과 같음)
THIN, THICK = 1, 6           # 선 굵기 번호 (0.12mm / 0.4mm)
SOLID, NONE, DOT, DOUBLE = 1, 0, 3, 8


TRACE = None  # main에서 log 함수를 넣음


def trace(msg):
    if TRACE:
        try:
            TRACE("[진단] " + msg)
        except Exception:
            pass


class UserError(Exception):
    """사용자에게 그대로 보여줄 안내."""


ACCESS_DENIED = -2147024891
BUSY_MSG = ("한글이 응답하지 않습니다.\n\n한글 창에 저장할지 묻는 창, 문서 복구 창, 업데이트 안내 같은 확인 창이 떠 있는지 "
            "봐 주세요(다른 모니터나 작업 표시줄에 숨어 있을 수 있습니다).\n닫은 뒤 [한글 다시 연결]을 누르면 됩니다.\n\n"
            "그래도 안 되면 한글을 완전히 껐다 켜 주세요.")
DENIED_MSG = ("한글이 연결을 거부했습니다(액세스 거부).\n\n한글이 관리자 권한으로 켜졌거나 다른 프로그램이 켠 한글일 때 생깁니다.\n"
              "한글을 모두 끄고 다시 켠 뒤 [한글 다시 연결]을 눌러 주세요.")


def probe(timeout=4.0):
    """한글 상태를 화면을 멈추지 않고 확인: 'ok' 'none'(꺼짐) 'busy'(응답 없음) 'denied'(액세스 거부) 'error'.
    한글이 확인 창 등에 붙잡혀 있으면 호출이 끝나지 않으므로 따로 돌리고 timeout초만 기다림."""
    import threading
    res = {"state": None}

    def work():
        pythoncom.CoInitialize()
        try:
            obj = Hwp()._find_running()
            if obj is None:
                res["state"] = "none"
            else:
                _ = obj.Version
                res["state"] = "ok"
        except pythoncom.com_error as e:
            res["state"] = "denied" if e.hresult == ACCESS_DENIED else "error"
            res["msg"] = str(e)
        except Exception as e:
            res["state"] = "error"
            res["msg"] = str(e)
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive() or res["state"] is None:
        return "busy"
    if res["state"] == "error":
        trace("한글 확인 오류: {}".format(res.get("msg")))
    return res["state"]


def launch():
    """한글 실행 파일을 켜기만 함 (기다리지 않음). 켰으면 True."""
    import subprocess
    exe = Hwp._hwp_exe()
    if not exe:
        return False
    try:
        subprocess.Popen([exe])
        return True
    except Exception as e:
        trace("한글 켜기 실패: {} ({})".format(e, exe))
        return False


class Hwp:
    def __init__(self):
        self.h = None
        self.mem = {}  # 기호 복사, 셀 크기 복사 등 기억
        self.active = {}  # 고른 서식 세트 {기호: 서식}. 비어 있으면 보고서 공통 서식
        self.me = {}  # 내 정보 {dept, title, name, phone, email} — 화면에서 넣어 줌

    # ================= 연결 =================
    def _find_running(self):
        ctx = pythoncom.CreateBindCtx(0)
        rot = pythoncom.GetRunningObjectTable()
        enum = rot.EnumRunning()
        while True:
            got = enum.Next(1)
            if not got:
                break
            mk = got[0]
            try:
                name = mk.GetDisplayName(ctx, None)
            except pythoncom.com_error:
                continue
            if name.startswith("!HwpObject"):
                obj = rot.GetObject(mk)
                return win32com.client.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
        return None

    def connect(self, create=True):
        h = self._find_running()
        if h is None and create:                     # 보이지 않는 한글을 따로 만들지 않고, 실행 파일로 켜서 기다림
            import time
            if launch():
                for _ in range(40):
                    time.sleep(0.5)
                    h = self._find_running()
                    if h is not None:
                        break
        if h is None:
            raise UserError("실행 중인 한글을 찾지 못했습니다. 한글을 먼저 켜 주세요.")
        self.h = h
        return h

    @staticmethod
    def _hwp_exe():
        """한글 실행 파일 경로. 레지스트리(32비트 등록 포함) → 흔한 설치 폴더 순서로 찾음."""
        import winreg
        import glob
        try:
            clsid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, r"HWPFrame.HwpObject\CLSID")
            for key in (r"CLSID\%s\LocalServer32" % clsid, r"WOW6432Node\CLSID\%s\LocalServer32" % clsid):
                try:
                    cmd = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, key).strip()
                except OSError:
                    continue
                exe = cmd.split('"')[1] if cmd.startswith('"') else cmd.split(" /")[0].split(" -")[0]
                if os.path.isfile(exe):
                    return exe
        except OSError:
            pass
        for k in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Hwp.exe",
                  r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Hwp.exe"):
            try:
                exe = winreg.QueryValue(winreg.HKEY_LOCAL_MACHINE, k).strip().strip('"')
                if os.path.isfile(exe):
                    return exe
            except OSError:
                pass
        for base in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("ProgramFiles", r"C:\Program Files")):
            found = sorted(glob.glob(os.path.join(base, "HNC", "*", "HOffice*", "Bin", "Hwp.exe")) +
                           glob.glob(os.path.join(base, "Hnc", "Hwp*", "Bin", "Hwp.exe")) +
                           glob.glob(os.path.join(base, "HNC", "Office*", "HOffice*", "Bin", "Hwp.exe")))
            if found:
                return found[-1]
        return None

    def start_new(self):
        """프로그램을 켤 때: 한글이 켜져 있으면 새 문서를 열고, 꺼져 있으면 한글을 새로 켬."""
        import subprocess
        import time
        h = self._find_running()
        if h is not None:
            self.h = h
            self.run("FileNew")
            return "새 문서를 열었습니다"
        exe = None
        try:
            exe = self._hwp_exe()
            if not exe:
                raise OSError("한글 실행 파일 경로를 찾지 못함")
            subprocess.Popen([exe])
            for _ in range(40):
                time.sleep(0.5)
                h = self._find_running()
                if h is not None:
                    break
        except Exception as e:
            trace("한글 실행 파일로 켜기 실패: {} ({})".format(e, exe))
        if h is None:
            raise UserError("한글을 켜지 못했습니다. 한글을 직접 켠 뒤 [한글 다시 연결]을 눌러 주세요.")
        self.h = h
        return "한글을 켰습니다"

    def new_doc(self):
        """새 문서 열기. 지금 문서가 비어 있고 고친 적 없으면 그대로 씀 (창이 쌓이지 않게)."""
        try:
            if self.h.IsEmpty and not self.h.IsModified:
                return
        except Exception:
            pass
        self.run("FileNew")

    def ok(self):
        if self.h is None:
            return False
        try:
            _ = self.h.Version
            return True
        except Exception:
            return False

    def ensure(self):
        if not self.ok():
            self.connect()
        return self.h

    # ================= 기본 도구 =================
    def run(self, action):
        self.h.HAction.Run(action)

    def move(self, where):
        """MovePos(이동 종류, 문단, 위치) — 2 문서 처음, 3 문서 끝, 104~107 셀 이동, 201 훑기 위치"""
        return self.h.MovePos(where, 0, 0)

    def runs(self, *actions):
        for a in actions:
            self.run(a)

    def insert(self, text):
        p = self.h.HParameterSet.HInsertText
        self.h.HAction.GetDefault("InsertText", p.HSet)
        p.Text = text
        self.h.HAction.Execute("InsertText", p.HSet)

    def rgb(self, c):
        return self.h.RGBColor(*c)

    def selected_text(self):
        try:
            t = self.h.GetTextFile("UNICODE", "saveblock")
        except Exception:
            t = ""
        return t or ""

    def has_selection(self):
        return bool(self.selected_text().strip())

    def in_table(self):
        try:
            return self.h.CellShape is not None
        except Exception:
            return False

    def char_shape(self, face=None, size=None, bold=None, italic=None, color=None, spacing=None,
                   ratio=None, normal=False):
        """글자 모양 바꾸기. (HParameterSet.HCharShape 방식은 이 한글에서 조용히 무시되어
        CreateAction/SetItem 방식을 씀 — 자가 점검으로 확인)"""
        if normal:
            self.run("CharShapeNormal")
        items = {}
        langs = ("Hangul", "Latin", "Hanja", "Japanese", "Other", "Symbol", "User")
        if face:
            ftype = 2 if face in HFT_FONTS else 1
            for k in langs:
                items["FaceName" + k] = face
                items["FontType" + k] = ftype
        if spacing is not None:
            for k in langs:
                items["Spacing" + k] = spacing
        if ratio is not None:
            for k in langs:
                items["Ratio" + k] = ratio
        if size:
            items["Height"] = int(round(size * 100))
        if bold is not None:
            items["Bold"] = 1 if bold else 0
        if italic is not None:
            items["Italic"] = 1 if italic else 0
        if color is not None:
            items["TextColor"] = self.rgb(color) if isinstance(color, tuple) else color
        self.char_items(items)

    def char_items(self, items):
        """CharShape 항목을 한 번에 적용.
        한글은 글꼴 종류(TTF=1, HFT=2)가 틀리면 동작 전체를 무시하므로,
        글꼴 이름·종류를 바꿔 가며 되는 조합을 찾고 기억해 둠."""
        h = self.h

        def go(its):
            act = h.CreateAction("CharShape")
            s = act.CreateSet()
            act.GetDefault(s)
            for k, v in its.items():
                try:
                    s.SetItem(k, v)
                except Exception as e:
                    trace("글자 모양 항목 실패 {}={} ({})".format(k, v, e))
            return bool(act.Execute(s))

        face = items.get("FaceNameHangul")
        if not face:
            ok = go(items)
            if not ok:
                trace("글자 모양 적용 실패: {}".format(items))
            return ok
        rest = {k: v for k, v in items.items() if not k.startswith(("FaceName", "FontType"))}
        langs = [k[len("FaceName"):] for k in items if k.startswith("FaceName")]
        tries = []
        if face in FONT_OK:
            tries.append(FONT_OK[face])
        for f in [face] + FACE_ALIAS.get(face, []):
            for t in ((2, 1) if f in HFT_FONTS else (1, 2)):
                if (f, t) not in tries:
                    tries.append((f, t))
        for f, t in tries:
            its = dict(rest)
            for k in langs:
                its["FaceName" + k] = f
                its["FontType" + k] = t
            if go(its):
                FONT_OK[face] = (f, t)
                return True
        trace("글꼴 '{}'을(를) 찾지 못해 글꼴은 그대로 두고 크기·굵기만 적용".format(face))
        return go(rest)

    def para_shape(self, line_spacing=None, align=None, indent=None, left=None,
                   prev=None, nxt=None, break_char=None, condense=None):
        """align: 0 양쪽, 1 왼쪽, 2 오른쪽, 3 가운데 / prev·nxt·left는 pt"""
        h = self.h
        p = h.HParameterSet.HParaShape
        h.HAction.GetDefault("ParagraphShape", p.HSet)
        if line_spacing is not None:
            p.LineSpacingType = 0
            p.LineSpacing = line_spacing
        if align is not None:
            p.AlignType = align
        if indent is not None:
            p.Indentation = h.PointToHwpUnit(indent)
        if left is not None:
            p.LeftMargin = h.PointToHwpUnit(left)
        if prev is not None:
            p.PrevSpacing = h.PointToHwpUnit(prev)
        if nxt is not None:
            p.NextSpacing = h.PointToHwpUnit(nxt)
        if break_char is not None:
            p.BreakNonLatinWord = break_char
        if condense is not None:
            p.Condense = condense
        h.HAction.Execute("ParagraphShape", p.HSet)

    def select_para(self):
        """커서가 있는 문단 전체를 선택. 빈 문단이면 False."""
        h = self.h
        self.run("MoveParaEnd")
        lst, para, end = h.GetPos()
        if end <= 0:
            return False
        try:
            h.SelectText(para, 0, para, end)
        except Exception:
            self.runs("MoveParaBegin", "MoveSelParaEnd")
        return True

    def para_text(self):
        pos = self.h.GetPos()
        self.select_para()
        t = self.selected_text()
        self.run("Cancel")
        self.h.SetPos(*pos)
        return t.replace("\r", "").replace("\n", "")

    def text_before_cursor(self):
        pos = self.h.GetPos()
        t = ""
        for act in ("MoveSelListBegin", "MoveSelTopLevelBegin", "MoveSelDocBegin"):
            try:
                self.run(act)
                t = self.selected_text()
                if t:
                    break
            except Exception:
                continue
        self.run("Cancel")
        self.h.SetPos(*pos)
        return logic.split_lines(t)

    def find(self, text, forward=True, regex=False, color=None):
        """찾으면 그 글자를 선택하고 True."""
        h = self.h
        act = h.CreateAction("RepeatFind")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("FindString", text)
        s.SetItem("Direction", 0 if forward else 1)
        s.SetItem("IgnoreMessage", 1)
        s.SetItem("FindRegExp", 1 if regex else 0)
        if color is not None:
            s.SetItem("FindType", 1)
            cs = s.CreateItemSet("FindCharShape", "CharShape")
            cs.SetItem("TextColor", self.rgb(color))
        return bool(act.Execute(s))

    def find_from_top(self, text):
        self.move(2)
        return self.find(text)

    def replace_all(self, find, rep):
        h = self.h
        p = h.HParameterSet.HFindReplace
        h.HAction.GetDefault("AllReplace", p.HSet)
        p.FindString = find
        p.ReplaceString = rep
        p.IgnoreMessage = 1
        p.FindRegExp = 0
        try:
            p.Direction = h.FindDir("AllDoc")
        except Exception:
            p.Direction = 2
        h.HAction.Execute("AllReplace", p.HSet)

    def do_phone_tidy(self):
        """숫자만 붙은 전화번호에 하이픈 (블록이 있으면 그 안에서 찾고, 없으면 문서 전체). 바꾼 개수를 돌려줌."""
        text = self.selected_text() if self.has_selection() else self.doc_text()
        pairs = logic.find_phones(text)
        if not pairs:
            raise UserError("하이픈을 넣을 전화번호를 찾지 못했습니다.\n(숫자만 붙은 010·032·02… 번호, 1588 같은 대표번호를 찾습니다)")
        for raw, f in pairs:
            self.replace_all(raw, f)
        return len(pairs)

    # ---------- 선택한 글/셀을 한꺼번에 고치기 ----------
    def _scan_cells(self):
        """선택 범위를 훑어 [(목록번호, 글)] 을 차례대로."""
        h = self.h
        order, texts = [], {}
        h.InitScan(1, 255, 0, 0, 0, 0)
        try:
            guard = 0
            while guard < 20000:
                guard += 1
                state, text = h.GetText()
                if state in (0, 1, 101, 102):
                    break
                self.move(201)
                lst = h.GetPos()[0]
                if lst not in texts:
                    order.append(lst)
                    texts[lst] = ""
                if state == 2:
                    texts[lst] += text
                elif state == 3:
                    texts[lst] += "\n"
        finally:
            h.ReleaseScan()
        return [(l, texts[l].rstrip("\n")) for l in order]

    def _write_cell(self, lst, text):
        h = self.h
        h.SetPos(lst, 0, 0)
        try:
            self.run("MoveSelListEnd")
        except Exception:
            self.run("MoveSelParaEnd")
        if text:
            self.insert(text)
        else:
            self.run("Delete")

    def transform(self, fn, per_line=True, need=True):
        """선택한 글(줄마다) 또는 선택한 셀(칸마다)에 fn 적용."""
        t = self.selected_text()
        if need and not t.strip():
            raise UserError("고칠 글이나 셀을 먼저 선택(블록 지정)해 주세요.")
        user_fn = fn

        def fn(s):
            try:
                return user_fn(s)
            except ValueError as e:
                raise UserError(str(e))

        cells = self._scan_cells() if self.in_table() else []
        if len(cells) > 1:
            self.run("Cancel")
            for lst, text in cells:
                new = logic.map_lines(text, fn) if per_line else fn(text)
                if new != text:
                    self._write_cell(lst, new)
            return
        new = logic.map_lines(t, fn) if per_line else fn(t)
        self.insert(new)

    def cell_values(self):
        """선택한 셀들의 (목록번호, 글) — 셀을 2개 이상 선택해야 함."""
        if not self.in_table():
            raise UserError("표 안의 셀을 먼저 선택해 주세요.")
        cells = self._scan_cells()
        if not cells:
            raise UserError("표 안의 셀을 먼저 선택(F5)해 주세요.")
        self.run("Cancel")
        return cells

    # ================= 개조식 기호·항목 번호 =================
    def _shape_now(self):
        try:
            cs = self.h.CharShape
            return "{} {}pt 굵게={}".format(cs.Item("FaceNameHangul"), cs.Item("Height") / 100.0, cs.Item("Bold"))
        except Exception as e:
            return "읽기 실패 {}".format(e)

    def _apply_bullet_style(self, spec, left=None):
        self.select_para()
        self.char_shape(face=spec.get("face"), size=spec.get("size"), bold=spec.get("bold", False),
                        italic=spec.get("italic", False), spacing=spec.get("char_spacing", 0),
                        ratio=spec.get("ratio", 100))
        if spec.get("color") is not None:
            self.char_items({"TextColor": spec["color"]})
        if left is None:
            left = spec.get("left", 0)
        self.para_shape(line_spacing=spec.get("spacing", 160), indent=0, left=left,
                        prev=spec.get("prev", 0), align=spec.get("align", 0))
        self.run("Cancel")
        self._indent_after(len(spec["text"]))

    def _indent_after(self, n):
        self.run("MoveParaBegin")
        for _ in range(n):
            self.run("MoveRight")
        self.run("ParagraphShapeIndentAtCaret")
        self.run("MoveParaEnd")

    def put_bullet(self, spec, left=None):
        """커서가 있는 문단 맨 앞 기호를 바꾸고 서식 적용."""
        body = logic.strip_bullet(self.para_text())
        if not self.select_para():
            self.run("MoveParaBegin")
        self.insert(spec["text"] + body)
        self._apply_bullet_style(spec, left)

    # ---------- 간부회의 자료 서식 ----------
    def _para_has_shape(self):
        """커서가 있는 문단에 글상자(보도 표시 등)가 붙어 있는지."""
        h = self.h
        lst, para, _ = h.GetPos()
        c = h.HeadCtrl
        while c is not None:
            if c.CtrlID == "gso":
                try:
                    a = c.GetAnchorPos(0)
                    if a.Item("List") == lst and a.Item("Para") == para:
                        return True
                except Exception:
                    pass
            c = c.Next
        return False

    def do_meeting(self, kind):
        """커서 줄을 간부회의 자료 서식으로 (kind: sec □ ○ - · ▶)."""
        spec = logic.MEETING[kind]
        if self._para_has_shape():
            raise UserError("'보도' 상자가 붙은 줄은 서식을 다시 바꿀 수 없습니다.\n"
                            "상자를 지우고 서식을 바꾼 뒤 [보도]를 다시 눌러 주세요.")
        body = logic.meeting_body(kind, self.para_text())
        if not self.select_para():
            self.run("MoveParaBegin")
        if kind == "sec":
            self.insert("[ " + (body or "사업계획") + " ]")
        else:
            self.insert(spec["text"] + body)
        self._apply_bullet_style(spec)

    def do_press_tag(self):
        """커서 자리에 보라색 '보도' 글상자를 넣음 (간부회의 자료 원본에서 떠 온 그대로)."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forms", "press_tag.xml")
        if not os.path.exists(path):
            raise UserError("'보도' 상자 파일(press_tag.xml)을 찾지 못했습니다.")
        data = open(path, encoding="utf-8").read()
        if self.has_selection():
            self.run("Cancel")
        lst, para, pos = self.h.GetPos()
        self.h.SetTextFile(data, "HWPML2X", "insertfile")
        if tuple(self.h.GetPos()) == (lst, para, pos):  # 커서가 상자 앞에 남으므로 상자 뒤로 옮김 (상자는 8칸)
            try:
                self.h.SetPos(lst, para, pos + 8)
            except Exception:
                pass

    def spec_for(self, key):
        """세트에 있으면 세트 서식, 없으면 보고서 공통 서식."""
        if key in self.active:
            return self.active[key]
        return logic.BULLETS.get(key)

    def do_bullet(self, sym):
        spec = self.spec_for(sym)
        if spec is None:
            raise UserError("'{}' 기호 서식이 없습니다.".format(sym))
        if sym in styles.NUM_LEVEL_KEYS:
            self.do_level(styles.NUM_LEVEL_KEYS.index(sym))
        else:
            self.put_bullet(spec)

    def _box_spec(self, level):
        for k in styles.BOX_LEVEL_KEYS[level]:
            if k in self.active:
                return self.active[k]
        return logic.BOX_LEVELS[level]

    def _num_text(self, level, idx):
        """세트에 그 단계가 있으면 세트의 기호 앞 칸 수를 따름."""
        key = styles.NUM_LEVEL_KEYS[level]
        if key in self.active:
            t = self.active[key]["text"]
            spaces = len(t) - len(t.lstrip())
            return " " * spaces + logic._token(level, idx) + " "
        return logic.num_text(level, idx)

    def _style_num(self, level, text):
        """세트에 그 번호가 있으면 세트 서식, 없으면 개조식 기호와 같은 서식."""
        key = styles.NUM_LEVEL_KEYS[level]
        if key in self.active:
            spec = dict(self.active[key])
            spec["text"] = text
        else:
            spec = logic.num_spec(level, text)
        self._apply_bullet_style(spec)

    def do_item(self, action):
        lines = self.text_before_cursor()
        cur = self.para_text()
        if cur.strip():
            prev = lines[:-1] + [cur]
            self.run("MoveParaEnd")
            self.run("BreakPara")
        else:
            prev = lines[:-1]
        spec = logic.next_item(prev, action)
        self.para_shape(indent=0, left=0)
        if spec["scheme"] == "box":
            spec = self._box_spec(spec["level"])
            self.insert(spec["text"])
            self._apply_bullet_style(spec)
        else:
            d = logic.detect(spec["text"])
            text = self._num_text(spec["level"], d[2] if d else 1)
            self.insert(text)
            self._style_num(spec["level"], text)

    def do_level(self, level):
        """선택이 있으면 그 줄들을 다시 매기고, 없으면 커서 자리에 넣기."""
        t = self.selected_text()
        if t.strip():
            # 선택한 줄마다 번호를 다시 매기고 같은 서식을 입힘
            self.run("Delete")
            n = 0
            for i, l in enumerate(logic.split_lines(t)):
                if i > 0:
                    self.run("BreakPara")
                if not l.strip():
                    continue
                n += 1
                text = self._num_text(level, n)
                self.para_shape(indent=0, left=0)
                self.insert(text + logic.strip_bullet(l))
                self._style_num(level, text)
            return
        lines = self.text_before_cursor()
        cur = self.para_text()
        # 커서 줄에 글이 있으면 그 줄도 위쪽 줄로 봄 (그 줄 다음에 새 번호를 넣으므로)
        lines = lines[:-1] + [cur] if cur.strip() else lines[:-1]
        idx = 1
        for l in reversed(lines):
            d = logic.detect(l)
            if d and d[0] == "num":
                if d[1] == level:
                    idx = d[2] + 1
                    break
                if d[1] < level:
                    break
        text = self._num_text(level, idx)
        if self.para_text().strip():
            self.run("MoveParaEnd")
            self.run("BreakPara")
        self.para_shape(indent=0, left=0)
        self.insert(text)
        self._style_num(level, text)

    # ================= 서식 불러오기 =================
    def _scan_paras(self):
        """선택 범위의 문단을 [((목록, 문단), 글)] 차례대로."""
        h = self.h
        # GetText 상태: 2 같은 문단 글, 3 다음 문단 시작(글은 새 문단 것), 4·5 표 등 안팎 드나듦.
        # 표 안 글(업무보고 양식의 칸 등)도 읽도록 옵션 7.
        order, texts = [], {}
        sel = self.has_selection()
        h.InitScan(7, 0xff if sel else 0x77, 0, 0, 0, 0)
        try:
            guard = 0
            while guard < 40000:
                guard += 1
                state, text = h.GetText()
                if state in (0, 1, 101, 102):
                    break
                self.move(201)
                lst, para, _ = h.GetPos()
                k = (lst, para)
                if k not in texts:
                    order.append(k)
                    texts[k] = ""
                texts[k] += text.replace("\r", "").replace("\n", "")
        finally:
            h.ReleaseScan()
        return [(k, texts[k]) for k in order]

    def _read_style_at(self, lst, para, line):
        """줄 맨 앞 기호 뒤 첫 글자 자리의 글자·문단 모양을 읽음."""
        h = self.h
        lead = styles.lead_of(line)
        key = styles.key_of(lead)
        if not key:
            return None, None
        body = line[len(lead):]
        pos = len(lead) + (1 if body.strip() else 0)
        if pos == len(lead):
            pos = max(len(lead.rstrip()), 1)
        h.SetPos(lst, para, pos)
        cs = h.CharShape
        ps = h.ParaShape
        spec = {
            "text": styles.normalize_text(lead, key),
            "face": cs.Item("FaceNameHangul"),
            "size": round(cs.Item("Height") / 100.0, 1),
            "bold": bool(cs.Item("Bold")),
            "italic": bool(cs.Item("Italic")),
            "char_spacing": int(cs.Item("SpacingHangul")),
            "ratio": int(cs.Item("RatioHangul")),
            "color": int(cs.Item("TextColor")) or None,
            "spacing": int(ps.Item("LineSpacing")),
            "prev": round(ps.Item("PrevSpacing") / 100.0, 1),
            "align": int(ps.Item("AlignType")),
            "left": round(ps.Item("LeftMargin") / 100.0, 1),
        }
        if spec["size"] == int(spec["size"]):
            spec["size"] = int(spec["size"])
        return key, spec

    def read_styles(self, scope):
        """scope: 'sel' 선택한 부분 / 'doc' 문서 전체 → {기호: 서식(+줄 수, 섞임)}"""
        h = self.h
        start = h.GetPos()
        if scope == "doc":
            self.run("Cancel")
        elif not self.has_selection():
            raise UserError("읽을 부분을 먼저 선택해 주세요. (양식 하나를 블록으로 지정)")
        win = None
        try:
            # 읽는 동안 화면을 숨기면 커서 이동 때 다시 그리지 않아 훨씬 빠름
            win = h.XHwpWindows.Active_XHwpWindow
            win.Visible = False
        except Exception:
            win = None
        try:
            return self._read_styles_body(start)
        finally:
            if win is not None:
                try:
                    win.Visible = True
                except Exception:
                    pass

    def _read_styles_body(self, start):
        h = self.h
        paras = self._scan_paras()
        self.run("Cancel")
        collected = {}
        for (lst, para), line in paras:
            k0 = styles.key_of(styles.lead_of(line))
            if not k0 or len(collected.get(k0, [])) >= 20:
                continue  # 기호마다 20줄이면 충분 (긴 문서도 빨리 읽게)
            try:
                key, spec = self._read_style_at(lst, para, line)
            except Exception:
                continue
            if key:
                collected.setdefault(key, []).append(spec)
        h.SetPos(*start)
        if not collected:
            raise UserError("기호(□ ○ - 1. 가. 등)로 시작하는 줄을 찾지 못했습니다.")
        return styles.summarize(collected)

    def doc_name(self):
        """지금 문서 파일 이름 (확장자·날짜 꼬리 뺌). 새 문서면 빈 글."""
        try:
            p = self.h.Path or ""
        except Exception:
            p = ""
        n = os.path.splitext(os.path.basename(p))[0]
        import re
        return re.sub(r"_\d{8}_\d{6}$", "", n)

    def read_styles_auto(self):
        """선택이 있으면 선택한 부분, 없으면 문서 전체를 읽음 → (결과, 범위 설명)"""
        if self.has_selection():
            return self.read_styles("sel"), "선택한 부분"
        return self.read_styles("doc"), "문서 전체"

    def try_style(self, spec):
        """서식 하나를 커서 줄에 입혀 보기 (서식 불러오기 창의 [써 보기])."""
        self.put_bullet(spec)

    def read_current_style(self):
        h = self.h
        start = h.GetPos()
        line = self.para_text()
        lst, para, _ = h.GetPos()
        key, spec = self._read_style_at(lst, para, line)
        h.SetPos(*start)
        if not key:
            raise UserError("커서가 있는 줄이 기호(□ ○ - 1. 가. 등)로 시작하지 않습니다.")
        return key, spec

    def do_circled(self):
        t = self.selected_text()
        if not t.strip():
            raise UserError("번호를 붙일 줄들을 먼저 선택해 주세요.")
        self.insert(logic.join_lines(logic.circled_lines(logic.split_lines(t))))

    def do_lead(self, mode):
        t = self.selected_text()
        if not t.strip():
            raise UserError("줄들을 먼저 선택해 주세요.")
        lines = logic.split_lines(t)
        if mode == "copy":
            self.mem["lead"] = [logic.lead_of(l) for l in lines if l.strip()]
            raise UserError("기호 {}개를 기억했습니다. 붙일 줄들을 선택하고 [기호 붙임]을 누르세요.".format(len(self.mem["lead"])))
        if mode == "del":
            self.insert(logic.join_lines([logic.strip_bullet(l) if l.strip() else l for l in lines]))
            return
        leads = self.mem.get("lead")
        if not leads:
            raise UserError("먼저 [기호 복사]로 기호를 기억시켜 주세요.")
        out, i = [], 0
        for l in lines:
            if l.strip():
                out.append(leads[i % len(leads)] + logic.strip_bullet(l))
                i += 1
            else:
                out.append(l)
        self.insert(logic.join_lines(out))

    # ================= 글자 =================
    def do_base(self):
        """기본 정리: 휴먼명조 15pt, 줄간격 160%, 자간 0, 장평 100, 꾸밈·음영 없음."""
        self.run("CharShapeNormal")
        self.char_shape(face="휴먼명조", size=15, spacing=0, ratio=100)
        self.char_items({"ShadeColor": 0xFFFFFFFF})
        self.para_shape(line_spacing=160, align=0, indent=0, left=0, prev=0, nxt=0, break_char=1)

    def do_shape_copy(self):
        act = self.h.CreateAction("ShapeCopyPaste")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("Type", 2)
        act.Execute(s)

    def do_undo(self, n=1):
        for _ in range(n):
            self.run("Undo")

    def do_redo(self, n=1):
        for _ in range(n):
            self.run("Redo")

    def do_split_view(self, on):
        if on:
            self.runs("ViewZoomNormal", "SplitVert")
        else:
            self.run("NoSplit")

    def do_jagan(self, mode):
        if mode == "base":
            self.para_shape(indent=0, break_char=1)
        elif mode == "hunter":
            self.para_shape(break_char=0, condense=75)
        elif mode == "double":
            self.para_shape(break_char=0, condense=75)
            self.char_shape(spacing=-10)

    def do_super(self, s):
        self.run("CharShapeSuperscript")
        self.insert(s)
        self.run("CharShapeSuperscript")

    # ================= 문서: 양식 =================
    @staticmethod
    def _docs_dir():
        try:
            from win32com.shell import shell, shellcon
            base = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, None, 0)
        except Exception:
            base = os.path.join(os.path.expanduser("~"), "Documents")
        d = os.path.join(base, "인천상의 문서")
        os.makedirs(d, exist_ok=True)
        return d

    def _open_copy(self, template, name):
        if not os.path.exists(template):
            raise UserError("양식 파일을 찾지 못했습니다: " + os.path.basename(template))
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(self._docs_dir(), "{}_{}.hwp".format(name, stamp))
        shutil.copyfile(template, dst)
        self.new_doc()
        self.h.Open(dst, "HWP", "forceopen:true")
        return dst

    def do_open_report(self, template):
        dst = self._open_copy(template, "업무보고")
        self.replace_all("2026. 2. 12", logic.today_text())
        self.replace_all("\U000F03DA", "")
        return dst

    def do_open_letter(self, template, lang):
        d = datetime.date.today()
        name = {"ko": "공문", "en": "공문_영문", "ja": "공문_일문"}[lang]
        dst = self._open_copy(template, name)
        if lang == "ko":
            self.replace_sure("2024. 00. 00", logic.date_fmt(d, "dot"))
        elif lang == "en":
            self.replace_sure("February 26, 2026", logic.date_fmt(d, "en"),
                              r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                              r" \d{1,2}, \d{4}")
        else:
            self.replace_sure("2026年9月30日", logic.date_fmt(d, "ja"), r"\d{4}年\s?\d{1,2}月\s?\d{1,2}日")
        self.replace_all("(신명조 12 포인트 진하게)", "")
        self.replace_all("(신명조 12 포인트)", "")
        self.fill_me("letter_" + lang)
        return dst

    def replace_sure(self, find, rep, pattern=None):
        """바꾸고 나서 문서에 남아 있는지 확인. 남았으면 찾아서 한 번 더 바꿈.
        find가 없으면(양식 날짜가 바뀌어 있으면) pattern에 맞는 첫 글자를 바꿈. 바꿨으면 True."""
        import re as _re
        self.replace_all(find, rep)
        t = self.doc_text()
        if find in t:                                   # 모두 바꾸기가 안 먹은 경우(한글 버전 차이 등)
            trace("모두 바꾸기 실패 → 하나씩 바꿈: " + find)
            self.replace_first(find, rep, 20)
            t = self.doc_text()
            if find in t:
                trace("하나씩 바꾸기도 실패: " + find)
                return False
            return True
        if rep in t:
            return True
        if pattern:
            m = _re.search(pattern, t)
            if m and m.group(0) != rep:
                trace("양식 날짜가 달라 모양으로 찾아 바꿈: " + m.group(0))
                self.replace_first(m.group(0), rep)
                return rep in self.doc_text()
        return False

    # ---------- 내 정보 넣기 ----------
    def replace_first(self, find, rep, count=1):
        """문서 처음부터 find를 count번까지 rep로 바꿈."""
        self.move(2)
        n = 0
        while n < count and self.find(find):
            self.insert(rep)
            n += 1
        self.move(2)
        return n

    @staticmethod
    def _intl(phone):
        """032-810-0000 → +82-32-810-0000"""
        p = phone.strip()
        return "+82-" + p[1:] if p.startswith("0") else p

    def fill_me(self, kind):
        """양식의 담당자·연락처 자리를 내 정보로 바꿈. 빈 칸은 건드리지 않음."""
        me = self.me or {}
        dept, title, name = me.get("dept", ""), me.get("title", ""), me.get("name", "")
        phone, email = me.get("phone", ""), me.get("email", "")
        person = " ".join(x for x in (name, title) if x)
        rep = self.replace_all
        if kind == "letter_ko":
            code = logic.dept_code(dept)
            if code:
                rep("인상경 제", code + " 제")  # 문서번호 기호 (양식은 인상경)
            fax = logic.dept_fax(dept)
            if fax:
                rep("/전송032-810-2800", "/전송" + fax)  # 부서 팩스
            if phone:
                rep("/전화032-810-2800", "/전화" + phone)
            if email:
                rep("/00000000@incham.net", "/" + email)
            if name:
                rep("/홍길동 차장", "/" + person)
        elif kind in ("letter_en", "letter_ja"):  # 영문·일문은 이름은 그대로
            if phone:
                rep("/ +82-32-810-2800", "/ " + self._intl(phone))
            if email:
                rep("/0000@incham.net", "/" + email)
        elif kind == "press":
            d = datetime.date.today()
            rep("2026년 00월", "{}년 {}월".format(d.year, d.month))  # 보도 날짜: 년·월만 (일·시는 직접)
            head = logic.dept_head(dept)
            if head:
                rep("000 실장", head)  # 담당자 첫 줄: 부서장
            if dept:
                rep("0000실", dept)
            if name:
                rep("000 과장", person)
            if phone:
                rep("032-810-0000", phone)
        elif kind == "travel":
            if dept:
                rep("○○○○실 여비교통비", dept + " 여비교통비")
            code = logic.dept_budget(dept)
            if code:
                rep("Code. 000", "Code. " + code)  # 예산과목 코드 (부서별)
            cmd = logic.dept_cmd(dept)
            if cmd:
                rep("○○명령", cmd + "명령")        # 명령 이름 (부서별)
            rep("25-0000", "{:02d}-0000".format(datetime.date.today().year % 100))  # 명령번호 연도 = 올해
        elif kind == "card":
            rep("0000. 00. 00( )", "")  # 사용일시는 비워 둠 (직접 씀)
            if dept:
                rep("○○○○실", dept)
            if title:  # 참석 인원 줄의 ○○는 그대로 두고 사용자 직위 칸만
                rep("○○○ ○○ 외 ○명", "§참석§")
                rep("○○", title)
                rep("§참석§", "○○○ ○○ 외 ○명")
            if name:
                rep("홍길동", name)

    # ---------- 내 서식 (부서 양식 등록) ----------
    def doc_text(self):
        try:
            return self.h.GetTextFile("UNICODE", "") or ""
        except Exception:
            return ""

    def myform_preview(self, stored):
        """등록한 양식 복사본을 임시 파일로 열고, 흔한 빈칸 글자를 찾아 돌려줌."""
        import tempfile
        ext = os.path.splitext(stored)[1] or ".hwp"
        # 이전 확인용 파일이 한글에 열려 있어도 겹치지 않게 매번 새 이름
        tmp = os.path.join(tempfile.gettempdir(), "인천상의_서식확인_{}{}".format(
            datetime.datetime.now().strftime("%H%M%S%f"), ext))
        shutil.copyfile(stored, tmp)
        self.new_doc()
        self.h.Open(tmp, "HWPX" if ext.lower() == ".hwpx" else "HWP", "forceopen:true")
        return logic.detect_fields(self.doc_text())

    def selection_for_field(self):
        t = self.selected_text().replace("\r", "").replace("\n", "").strip()
        if not t:
            raise UserError("한글에서 바꿀 글자(예: 홍길동)를 먼저 블록으로 잡아 주세요.")
        if len(t) > 40:
            raise UserError("블록이 너무 깁니다. 바꿀 글자만 잡아 주세요.")
        return t

    def open_myform(self, entry, stored):
        """내 서식을 새 파일로 열고 정해 둔 자리에 내 정보·오늘 날짜를 넣음."""
        if not os.path.exists(stored):
            raise UserError("'{}' 양식 파일을 찾지 못했습니다. 다시 등록해 주세요.".format(entry.get("name")))
        ext = os.path.splitext(stored)[1] or ".hwp"
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c for c in entry.get("name", "내서식") if c not in '\\/:*?"<>|')
        dst = os.path.join(self._docs_dir(), "{}_{}{}".format(safe, stamp, ext))
        shutil.copyfile(stored, dst)
        self.new_doc()
        self.h.Open(dst, "HWPX" if ext.lower() == ".hwpx" else "HWP", "forceopen:true")
        # 예전 규칙으로 등록한 서식이면 이번에 자리를 다시 찾아 합침 (다른 PC에서 등록한 것도 같음)
        if entry.get("rules", 1) < logic.FIELD_RULES:
            found = [{"find": t, "kind": k} for t, k in logic.detect_fields(self.doc_text())]
            entry["fields"] = logic.merge_fields(entry.get("fields", []), found)
            entry["rules"] = logic.FIELD_RULES
        done, skipped = [], []
        fields = sorted(entry.get("fields", []), key=lambda f: -len(f["find"]))
        protect = {}
        for i, f in enumerate(fields):
            v = logic.field_value(f["kind"], f["find"], self.me)
            label = logic.FIELD_LABEL.get(f["kind"], f["kind"])
            if not v:
                skipped.append(label)
                if f["kind"] == "head_full":  # 부서장을 못 바꾸면 그 안의 부서 이름도 그대로 두게 잠시 가림
                    key = "§§{}§§".format(i)
                    self.replace_all(f["find"], key)
                    protect[key] = f["find"]
                continue
            self.replace_all(f["find"], v)
            done.append(label)
        for key, orig in protect.items():
            self.replace_all(key, orig)
        self.active = dict(entry.get("styles") or {})
        self.move(2)
        return dst, done, skipped

    def do_open_weekly(self, template):
        """주간 주요 일정 및 보도자료 배포 계획: 기간(다가오는 일~토)과 담당자 칸(소속 / 이름 직위 / 전화)."""
        dst = self._open_copy(template, "보도자료배포계획")
        import re as _re
        t = self.doc_text()
        m = _re.search(r"\d{2}\.\s?\d{1,2}\.\s?\d{1,2}\.\s?~\s?\d{2}\.\s?\d{1,2}\.\s?\d{1,2}\.", t)
        if m:
            self.replace_all(m.group(0), logic.week_period())
        me = self.me or {}
        vals = logic.field_values(me)
        # 담당자 칸 세 줄: ▸소속 / ▸이름 직위 / ▸전화 (처음 나오는 칸 하나)
        self.move(2)
        if self.find("▸경제진흥실"):
            if vals["dept"]:
                self.insert("▸" + vals["dept"])
            if self.find("▸") and vals["person"]:
                self.insert("▸" + vals["person"])
            if self.find("▸032-810") and vals["phone"]:
                self.insert("▸" + vals["phone"])
        self.move(2)
        return dst

    def do_open_press(self, template):
        dst = self._open_copy(template, "보도자료")
        self.fill_me("press")
        return dst

    def do_open_plain(self, template, name):
        return self._open_copy(template, name)

    def _cell_put(self, text):
        """커서가 있는 셀의 글을 text로 바꿈 (빈 글이면 지움)."""
        self.run("MoveParaBegin")
        self.run("MoveSelParaEnd")
        if text:
            self.insert(text)
        elif self.has_selection():
            self.run("Delete")

    def do_open_travel(self, template, companions=None, days=1):
        """여비계산서: 위쪽 기간은 오늘이 속한 년·월만 (일은 비움), 아래 청구일·영수일은 오늘 날짜.
        companions: 출장 간 사람 [{"dept","name","title"}] 전체 — 두 명 이상이면 영수인 줄에 모두 넣고 끝에 <붙임> 표."""
        dst = self._open_copy(template, "여비계산서")
        self._act_calc = None
        d = datetime.date.today()
        self.move(2)
        hits = 0
        filled = 0
        while filled < 2 and hits < 6 and self.find("2025"):
            hits += 1
            self.insert(str(d.year))
            try:
                self.run("TableRightCell")   # 년
                self.run("TableRightCell")   # 월 칸
                if hits <= 2:                # 위쪽 기간 (시작·끝)
                    self._cell_put(str(d.month))
                    self.run("TableRightCell")   # 월
                    self.run("TableRightCell")   # 일 칸
                    self._cell_put("")
                    continue
                self.insert(str(d.month))
                self.run("TableRightCell")   # 월
                self.run("TableRightCell")   # 일 칸
                self.insert(str(d.day))
                filled += 1
            except Exception:
                pass
        self.fill_me("travel")
        me = self.me or {}
        mine = {"dept": me.get("dept", ""), "name": me.get("name", ""), "title": me.get("title", "")}
        # companions = 출장 간 사람 전체(적은 차례 그대로, 나도 적어야 들어감). 없으면 나 혼자.
        people = [c for c in (companions or []) if (c.get("name") or "").strip()] or [mine]
        self._travel_signers(mine["name"], [p["name"] for p in people])
        try:
            self._travel_transport()
            self._travel_activity(people, days)
        except Exception as e:
            trace("여비계산서 활동비·교통비 넣기 실패: {}".format(e))
        if len(people) > 1:
            self._travel_attach(people, days)
        self._travel_recalc()
        self.move(2)
        return dst

    def _travel_signers(self, me_name, names):
        """청구인 = 나, 영수인 = names (양식 칸은 두 줄: 첫 칸 · 둘째 칸, 셋째부터는 둘째 칸에 줄을 더함)"""
        stamp = "\U000f0099"
        if not me_name:                                # 내 이름이 없으면 양식 그대로
            return
        self.move(2)
        if me_name and self.find("홍길동"):
            self.insert(me_name)                       # 청구인
        if self.find("홍길동") and names[0]:
            self.insert(names[0])                      # 영수인 첫 칸
        if not self.find("홍길동"):                     # 영수인 둘째 칸
            return
        rest = [n for n in names[1:] if n]
        if not rest:                                   # 혼자: 둘째 칸 이름과 도장 표시 지움
            self.run("Delete")
            try:
                self.run("TableRightCell")
                self._cell_put("")
            except Exception:
                pass
            return
        self.insert("\r\n".join(rest))
        if len(rest) > 1:                              # 셋째 사람부터: 도장 칸에도 줄을 더함
            try:
                hn = self._cell_height()
                self._cell_spacing(160)                # 이름 칸 줄 간격 160%
                self.run("TableRightCell")
                self.run("MoveParaEnd")
                self.insert(("\r\n" + stamp) * (len(rest) - 1))
                hs = self._cell_height()
                if hn and hs:                          # 도장 글자가 작아도 이름과 같은 높이로 줄이 가게
                    self._cell_spacing(int(round(160.0 * hn / hs)))
            except Exception:
                pass

    def _cell_height(self):
        """커서가 있는 셀 첫 글자의 크기 (HWPUNIT)."""
        self.run("MoveListBegin")
        try:
            return int(self.h.CharShape.Item("Height"))
        except Exception:
            return 0

    def _cell_spacing(self, percent):
        """커서가 있는 셀 안 문단 모두 줄 간격(%)."""
        h = self.h
        self.run("MoveListBegin")
        self.run("MoveSelListEnd")
        p = h.HParameterSet.HParaShape
        h.HAction.GetDefault("ParagraphShape", p.HSet)
        p.LineSpacingType = 0
        p.LineSpacing = percent
        h.HAction.Execute("ParagraphShape", p.HSet)
        self.run("Cancel")
        self.run("MoveListEnd")

    TRANSPORT_NOTE = "자동차 운행 : ○○km × 250원"

    def _travel_transport(self):
        """교통비 첫 줄에 자동차 운행 문구를 미리 넣음 (규정: 1km당 250원)."""
        self.move(2)
        if not self.find("교 통 비"):
            return
        self.run("Cancel")
        self.run("TableRightCell")                     # '교 통 비' 칸 가운데 줄 →
        for _ in range(5):
            self.run("TableUpperCell")                 # 맨 윗줄로 (교통비 칸은 11줄)
        self._cell_put(self.TRANSPORT_NOTE)
        # 오른쪽 금액 칸 11줄에 0 — 합계 계산식(위쪽 합)은 빈 칸에서 끊기므로 0을 채워 두면 어느 줄에 적어도 합계에 들어감
        self.run("TableRightCell")
        for r in range(self.TRANSPORT_ROWS):
            if r:
                self.run("TableLowerCell")
            self._cell_put("0")

    ACT_FIXED = ["원", None, "일", None, "명", "", "", "(", "갑", ",", "을", ")"]   # 금액 칸 다음 칸들 (None = 값)
    TRANSPORT_ROWS = 11                                 # 교통비 칸 줄 수
    ACT_SPAN = 13                                       # 금액 칸 → 오른쪽 금액 칸까지 칸 수

    def _hwp_front(self):
        """한글 창을 맨 앞으로. 한글은 창이 앞에 있을 때만 표 계산식(곱·합)을 바로 다시 계산함."""
        try:
            import win32gui
            want = os.path.basename(self.h.Path or "")
            wins = []

            def cb(hw, _):
                if win32gui.IsWindowVisible(hw) and win32gui.GetClassName(hw).startswith("HwpApp"):
                    wins.append(hw)
            win32gui.EnumWindows(cb, None)
            if not wins:
                return False
            hw = next((w for w in wins if want and want in win32gui.GetWindowText(w)), wins[0])
            if win32gui.GetForegroundWindow() == hw:
                return True
            import win32con
            if win32gui.IsIconic(hw):
                win32gui.ShowWindow(hw, win32con.SW_RESTORE)
            try:
                win32gui.SetForegroundWindow(hw)
            except Exception:
                pass
            if win32gui.GetForegroundWindow() != hw:   # 윈도가 막으면 지금 앞 창의 입력에 잠깐 붙어서 다시
                try:
                    import win32api, win32process
                    fg = win32gui.GetForegroundWindow()
                    a = win32api.GetCurrentThreadId()
                    b = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
                    if b and b != a:
                        win32process.AttachThreadInput(a, b, True)
                    try:
                        win32gui.BringWindowToTop(hw)
                        win32gui.SetForegroundWindow(hw)
                    finally:
                        if b and b != a:
                            win32process.AttachThreadInput(a, b, False)
                except Exception:
                    pass
            if win32gui.GetForegroundWindow() != hw:   # 그래도 안 되면 Alt 한 번 누른 셈 치고 다시
                try:
                    import win32com.client
                    win32com.client.Dispatch("WScript.Shell").SendKeys("%")
                    win32gui.SetForegroundWindow(hw)
                except Exception:
                    pass
            ok = win32gui.GetForegroundWindow() == hw
            if not ok:
                trace("한글 창을 앞으로 못 가져옴 (앞 창: {})".format(win32gui.GetClassName(win32gui.GetForegroundWindow())))
            return ok
        except Exception as e:
            trace("한글 창 앞으로 실패: {}".format(e))
            return False

    def _travel_total_shown(self):
        """여비계산서 맨 아래 합계 칸에 보이는 금액 (못 읽으면 None)."""
        t = self.doc_text()
        k = t.find("합   계")
        if k < 0:
            return None
        line = t[k + len("합   계"):].lstrip("\r\n").split("\r\n")[0]
        digits = re.sub(r"[^0-9]", "", line)
        return int(digits) if digits else None

    def _travel_activity(self, people, days):
        """활동비: 사람마다 한 줄 — [금액]원 [일수]일 1명 (갑,을) [금액].
        양식의 두 줄 오른쪽 금액과 맨 아래 합계는 양식에 있던 계산식을 그대로 둠 → 교통비·숙박비를 나중에 적어도 합계가 바뀜.
        세 번째 사람부터는 줄을 늘리고 고정 글자와 계산한 금액을 넣은 뒤 '활동비' 칸을 합침."""
        self.move(2)
        if not self.find("활동비"):
            return
        self.run("Cancel")
        self.run("TableRightCell")                     # 첫 줄 금액 칸
        n = len(people)
        total = 0
        rows = []
        for i, p in enumerate(people):
            fee = logic.activity_fee(p.get("title", ""))
            amt = fee * days if fee else 0
            total += amt
            rows.append(amt)
            self._cell_put("{:,}".format(fee) if fee else "")
            vals = [str(days) if k == 1 else ("1" if k == 3 else v) for k, v in enumerate(self.ACT_FIXED)]
            for k, v in enumerate(vals):
                self.run("TableRightCell")
                if i >= 2 or k in (1, 3):              # 양식 줄은 일수·명만, 늘린 줄은 고정 글자까지
                    self._cell_put(v)
            self.run("TableRightCell")                 # 오른쪽 금액 칸
            if i >= 2:                                 # 늘린 줄엔 계산식이 없어 계산한 값을 넣음
                self._cell_put("{:,}".format(amt))
            for _ in range(self.ACT_SPAN):
                self.run("TableLeftCell")              # 금액 칸
            if i < n - 1:
                if i >= 1:
                    self.run("TableInsertLowerRow")    # 세 번째 사람부터 줄 추가
                self.run("TableLowerCell")
        if n > 2:                                      # 늘린 줄까지 '활동비' 칸을 하나로 합침
            try:
                self.move(2)
                self.find("활동비")
                self.run("Cancel")
                self.run("TableCellBlock")
                self.run("TableCellBlockExtend")
                for _ in range(n - 2):                 # '활동비' 칸(이미 두 줄) + 늘린 줄 수만큼
                    self.run("TableLowerCell")
                self.run("TableMergeCell")
                self.run("Cancel")
            except Exception as e:
                trace("활동비 칸 합치기 실패: {}".format(e))
        self._act_calc = (rows, total)

    def _travel_recalc(self):
        """다 채운 뒤 한글을 앞으로 가져와 첫 줄 금액을 한 번 더 넣음 → 표 계산식(곱·합)이 다시 계산됨.
        (한글은 창이 앞에 있을 때만 다시 계산함. 채우는 동안 앞에 두면 화면을 매번 다시 그려 몹시 느림)
        그래도 합계가 안 맞으면 계산한 값을 직접 넣음."""
        rows, total = getattr(self, "_act_calc", None) or ([], 0)
        if not rows:
            return
        live = self._hwp_front()
        try:
            self.move(2)
            if self.find("활동비"):
                self.run("Cancel")
                self.run("TableRightCell")
                self.run("MoveParaEnd")
                self.insert("0")                       # 글자 하나 넣었다 지움 (값은 그대로, 다시 계산만 일어남)
                self.run("DeleteBack")
        except Exception as e:
            trace("여비 다시 계산 실패: {}".format(e))
        import time
        shown = None
        for _ in range(15):                            # 한글은 잠깐 쉬는 틈에 다시 계산함 → 최대 3초 기다림
            time.sleep(0.2)
            shown = self._travel_total_shown()
            if shown == total:
                return
        trace("여비 합계 계산식 미반영(앞={}, 보임={}, 계산={}) → 값으로 넣음".format(live, shown, total))
        try:
            self.move(2)
            self.find("활동비")
            self.run("Cancel")
            self.run("TableRightCell")
            for i in range(min(len(rows), 2)):
                for _ in range(self.ACT_SPAN):
                    self.run("TableRightCell")
                self._cell_put("{:,}".format(rows[i]))
                for _ in range(self.ACT_SPAN):
                    self.run("TableLeftCell")
                self.run("TableLowerCell")
            self.move(2)
            if self.find("합   계"):
                self.run("Cancel")
                self.run("TableRightCell")
                self._cell_put("￦{:,}".format(total))
        except Exception as e:
            trace("여비 합계 넣기 실패: {}".format(e))

    def _travel_attach(self, people, days=1):
        """문서 끝에 새 쪽을 넣고 <붙임> 여비계산서 표(부서·성명·직위·청구금액=활동비×일수, 합계)를 채움."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forms", "travel_attach.hwp")
        if not os.path.exists(path):
            return
        self.move(3)
        self._insert_file(path)                        # 구역째 넣으므로 새 쪽에서 시작함
        self.move(3)
        if not self.find("청구금액", forward=False):
            return
        self.run("Cancel")
        n = len(people)
        total = 0
        for i, p in enumerate(people):
            self.run("TableRightCell")                 # 다음 줄 부서 칸
            self._cell_put(p.get("dept", ""))
            self.run("TableRightCell")
            self._cell_put(p.get("name", ""))
            self.run("TableRightCell")
            self._cell_put(p.get("title", ""))
            self.run("TableRightCell")                 # 청구금액 칸
            fee = logic.activity_fee(p.get("title", ""))
            amt = fee * days if fee else 0
            total += amt
            self._cell_put("￦{:,}".format(amt) if amt else "￦")
            if i >= 1 and i < n - 1:                   # 양식의 두 줄을 넘으면 아래에 줄 추가
                self.run("TableInsertLowerRow")
        self.run("TableRightCell")                     # 합계 줄
        self.run("TableRightCell")
        self._cell_put("￦{:,}".format(total) if total else "￦")

    def _cell_put_all(self, text):
        """커서가 있는 셀의 글 전체(여러 줄)를 text로 바꿈."""
        self.run("MoveListBegin")
        self.run("MoveSelListEnd")
        if text:
            self.insert(text)
        elif self.has_selection():
            self.run("Delete")

    def ot_fill_rows(self, rows):
        """시간외 근무 표: rows = [(순번, 대상자, 근무내용, 합계)]. 첫 데이터 줄부터 채우고 모자라면 줄을 늘림."""
        self.move(2)
        if not self.find("합계"):
            raise UserError("양식에서 표 머리줄(합계)을 찾지 못했습니다.")
        self.run("Cancel")
        n = len(rows)
        for i, cells in enumerate(rows):
            for j, val in enumerate(cells):
                self.run("TableRightCell")
                self._cell_put_all(val)
            if i < n - 1:
                lst, para, pos = self.h.GetPos()
                self.run("TableInsertLowerRow")    # 아래에 같은 모양 줄 추가
                try:
                    self.h.SetPos(lst, para, pos)
                except Exception:
                    pass

    def do_open_overtime(self, template, d1, d2, place, what, people):
        """시간외 근로 현황: d1·d2 = 시작일·끝일(date, 하루면 d2=None),
        people = [{"name","title","start","end","total"}] — total을 비우면 하루짜리는 시간에서 계산."""
        dst = self._open_copy(template, "시간외근로")
        dept = (self.me or {}).get("dept", "")
        self.replace_all("시간외 근무 현황", "시간외 근로 현황")
        if dept:
            self.replace_all("○○○○실 시간외 근로 현황", dept + " 시간외 근로 현황")
        rows = []
        for i, p in enumerate(people, 1):
            who = " ".join(x for x in (p.get("name", ""), p.get("title", "")) if x)
            day, tm = logic.ot_period(d1, d2, p.get("start", ""), p.get("end", ""))
            total = logic.ot_total(p.get("total", ""), d1, d2, p.get("start", ""), p.get("end", ""))
            rows.append((str(i), who, logic.ot_content(day, tm, place, what), total))
        if rows:
            self.ot_fill_rows(rows)
        self.move(2)
        return dst

    def do_open_card(self, template):
        """법인카드 사용 내역: 사용일시 오늘(요일), 사용자 부서·직위·성명."""
        dst = self._open_copy(template, "법인카드사용내역")
        self.fill_me("card")
        self.move(2)
        return dst

    # ---------- 수료증 ----------
    def _insert_file(self, path):
        h = self.h
        p = h.HParameterSet.HInsertFile
        h.HAction.GetDefault("InsertFile", p.HSet)
        for key in ("filename", "FileName"):
            try:
                setattr(p, key, path)
                break
            except Exception:
                continue
        for key in ("KeepSection", "KeepCharshape", "KeepParashape", "KeepStyle"):
            try:
                setattr(p, key, 1)
            except Exception:
                pass
        h.HAction.Execute("InsertFile", p.HSet)

    def do_make_certs(self, template, people, common, numbers):
        h = self.h
        work = self._docs_dir()
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp = os.path.join(work, "_수료증_틀_{}.hwp".format(stamp))
        shutil.copyfile(template, tmp)
        self.run("FileNew")
        h.Open(tmp, "HWP", "forceopen:true")
        missing = []
        for field, sample in logic.CERT_SAMPLES:
            if self.find_from_top(sample):
                self.run("Delete")
                h.CreateField(field, "", field)
            else:
                missing.append(field)
        h.SaveAs(tmp, "HWP", "")
        self.runs("SelectAll", "Delete")
        for i in range(len(people)):
            if i > 0:
                self.move(3)
                self.run("BreakPage")
            self.move(3)
            self._insert_file(tmp)
        names, values = [], []
        for i, (org, rank, name) in enumerate(people):
            row = {"번호": numbers[i], "소속": org, "직급": rank, "성명": name}
            row.update(common)
            for field, _ in logic.CERT_SAMPLES:
                if field in missing:
                    continue
                names.append("{}{{{{{}}}}}".format(field, i))
                values.append(row.get(field, ""))
        h.PutFieldText("\x02".join(names), "\x02".join(values))
        safe = "".join(c for c in common.get("과정명", "") if c not in '\\/:*?"<>|')[:40].strip() or "교육"
        dst = os.path.join(work, "수료증_{}_{}.hwp".format(safe, stamp))
        h.SaveAs(dst, "HWP", "")
        try:
            os.remove(tmp)
        except Exception:
            pass
        self.move(2)
        return dst, missing

    # ================= 표 기본 도구 =================
    def table_create(self, rows, cols, widths=None, heights=None):
        """widths/heights: mm 목록. 커서 자리에 글자처럼 취급하는 표를 만듦."""
        h = self.h
        p = h.HParameterSet.HTableCreation
        h.HAction.GetDefault("TableCreate", p.HSet)
        p.Rows = rows
        p.Cols = cols
        if widths:
            p.WidthType = 2
            p.CreateItemArray("ColWidth", cols)
            for i, w in enumerate(widths):
                p.ColWidth.SetItem(i, h.MiliToHwpUnit(w))
        else:
            p.WidthType = 0
        if heights:
            p.HeightType = 1
            p.CreateItemArray("RowHeight", rows)
            for i, v in enumerate(heights):
                p.RowHeight.SetItem(i, h.MiliToHwpUnit(v))
        else:
            p.HeightType = 0
        try:
            p.TableProperties.TreatAsChar = 1
        except Exception:
            pass
        h.HAction.Execute("TableCreate", p.HSet)

    def cell_block_all(self):
        """표 전체 셀 선택."""
        self.runs("TableCellBlock", "TableCellBlockExtend", "TableCellBlockExtend")

    def cell_block_row(self):
        """커서 셀부터 그 행 끝까지 선택."""
        self.runs("TableCellBlock", "TableCellBlockExtend")
        self.move(105)

    def go_first_cell(self):
        self.move(106)  # 열의 맨 위
        self.move(104)  # 행의 맨 앞

    def borders(self, top=None, bottom=None, left=None, right=None, horz=None, vert=None, color=None):
        """각 면: (종류, 굵기) — 종류 0 없음, 1 실선, 3 점선, 8 이중선"""
        h = self.h
        act = h.CreateAction("CellBorderFill")
        s = act.CreateSet()
        act.GetDefault(s)
        for name, v in (("Top", top), ("Bottom", bottom), ("Left", left), ("Right", right),
                        ("Horz", horz), ("Vert", vert)):
            if v is None:
                continue
            s.SetItem("BorderType" + name, v[0])
            s.SetItem("BorderWidth" + name, v[1])
            if color is not None:
                try:
                    s.SetItem("BorderColor" + name, self.rgb(color))
                except Exception:
                    pass
        act.Execute(s)

    def cell_fill(self, color=None):
        h = self.h
        p = h.HParameterSet.HCellBorderFill
        h.HAction.GetDefault("CellFill", p.HSet)
        if color is None:
            p.FillAttr.type = h.BrushType("NullBrush")
        else:
            p.FillAttr.type = h.BrushType("NullBrush|WinBrush")
            p.FillAttr.WinBrushFaceColor = self.rgb(color)
            p.FillAttr.WinBrushHatchColor = self.rgb(color)
            p.FillAttr.WinBrushFaceStyle = h.HatchStyle("None")
            p.FillAttr.WindowsBrush = 1
        h.HAction.Execute("CellFill", p.HSet)

    def _table_prop(self, cell_size=None, **cell_items):
        h = self.h
        p = h.HParameterSet.HShapeObject
        h.HAction.GetDefault("TablePropertyDialog", p.HSet)
        p.HSet.SetItem("ShapeType", 3)
        if cell_size is not None:
            p.HSet.SetItem("ShapeCellSize", cell_size)
        for k, v in cell_items.items():
            setattr(p.ShapeTableCell, k, v)
        h.HAction.Execute("TablePropertyDialog", p.HSet)

    # ================= 인천상의 표 =================
    def style_incham_table(self):
        if not self.in_table():
            raise UserError("표 안에 커서를 두고 눌러 주세요.")
        self.cell_block_all()
        self.char_shape(face="맑은 고딕", size=12, normal=True)
        self.run("ParagraphShapeAlignCenter")
        self.borders(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(NONE, THIN), right=(NONE, THIN),
                     horz=(SOLID, THIN), vert=(SOLID, THIN), color=(0, 0, 0))
        self.cell_fill(None)
        self.run("Cancel")
        self.go_first_cell()
        self.cell_block_row()
        self.cell_fill(HEAD_BLUE)
        self.char_shape(bold=True)
        self.run("Cancel")
        self.go_first_cell()

    def do_incham_table(self, rows, cols):
        if self.in_table():
            raise UserError("표 밖에서 눌러 주세요. (지금 커서가 표 안에 있습니다)")
        self.table_create(rows, cols)
        self.style_incham_table()

    def do_roster_table(self):
        rows = logic.roster_table_rows(10)
        self.table_create(len(rows), len(rows[0]), widths=[14, 54, 30, 30, 42])
        self.style_incham_table()
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if v:
                    self.insert(v)
                if not (r == len(rows) - 1 and c == len(row) - 1):
                    self.run("TableRightCell")
        self.go_first_cell()

    # ---------- 표 모양 ----------
    def table_look(self, kind):
        if not self.in_table():
            raise UserError("표 안에 커서를 두고 눌러 주세요.")
        self.cell_block_all()
        b = self.borders
        if kind == "thin":
            b(top=(SOLID, THIN), bottom=(SOLID, THIN), left=(SOLID, THIN), right=(SOLID, THIN),
              horz=(SOLID, THIN), vert=(SOLID, THIN), color=(0, 0, 0))
        elif kind == "outer_thick":
            b(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(SOLID, THICK), right=(SOLID, THICK),
              horz=(SOLID, THIN), vert=(SOLID, THIN))
        elif kind == "none":
            b(top=(NONE, THIN), bottom=(NONE, THIN), left=(NONE, THIN), right=(NONE, THIN),
              horz=(NONE, THIN), vert=(NONE, THIN))
        elif kind == "topbottom":
            b(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(NONE, THIN), right=(NONE, THIN),
              horz=(NONE, THIN), vert=(NONE, THIN))
        elif kind == "dot":
            b(top=(DOT, THIN), bottom=(DOT, THIN), left=(DOT, THIN), right=(DOT, THIN))
        elif kind == "excel":
            self.char_shape(normal=True)
            b(top=(SOLID, THIN), bottom=(SOLID, THIN), left=(SOLID, THIN), right=(SOLID, THIN),
              horz=(SOLID, THIN), vert=(SOLID, THIN), color=(0, 0, 0))
        elif kind == "3d":
            b(top=(SOLID, THIN), bottom=(SOLID, THIN), left=(SOLID, THICK), right=(SOLID, THICK))
        elif kind in ("black", "blue", "red"):
            c = {"black": (0, 0, 0), "blue": (0, 0, 255), "red": (255, 0, 0)}[kind]
            b(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(SOLID, THICK), right=(SOLID, THICK), color=c)
        self.run("Cancel")

    def border_side(self, side, style):
        """side: top/bottom/left/right, style: thin/thick/none/dot/double"""
        v = {"thin": (SOLID, THIN), "thick": (SOLID, THICK), "none": (NONE, THIN), "dot": (DOT, THIN),
             "double": (DOUBLE, THICK)}[style]
        self.borders(**{side: v})

    def border_top_lr_thick(self):
        self.borders(top=(SOLID, THICK), left=(SOLID, THICK), right=(SOLID, THICK))

    def merge_thick(self):
        self.borders(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(SOLID, THICK), right=(SOLID, THICK))
        self.run("TableMergeCell")

    def fill_with_text(self, bg, fg):
        self.cell_fill(bg)
        self.char_shape(color=fg)

    # ---------- 셀 ----------
    def split_cell(self):
        h = self.h
        p = h.HParameterSet.HTableSplitCell
        h.HAction.GetDefault("TableSplitCell", p.HSet)
        p.Rows = 0
        p.Cols = 2
        h.HAction.Execute("TableSplitCell", p.HSet)

    def cell_size_copy(self):
        cell = self.h.CellShape.Item("Cell")
        self.mem["cell"] = (cell.Item("Width"), cell.Item("Height"))
        raise UserError("셀 크기를 기억했습니다. 붙일 셀을 선택하고 [높이 붙이기]·[너비 붙이기]를 누르세요.")

    def cell_size_paste(self, which):
        if "cell" not in self.mem:
            raise UserError("먼저 [크기 복사]를 눌러 셀 크기를 기억시켜 주세요.")
        w, ht = self.mem["cell"]
        if which == "height":
            self._table_prop(cell_size=1, Height=ht)
        else:
            self._table_prop(cell_size=1, Width=w)

    def cell_margin_zero(self):
        h = self.h
        act = h.CreateAction("TablePropertyDialog")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("ShapeType", 3)
        s.SetItem("ShapeCellSize", 0)
        for k in ("CellMarginLeft", "CellMarginRight", "CellMarginTop", "CellMarginBottom"):
            s.SetItem(k, 0)
        act.Execute(s)

    def cell_valign(self, where):
        self.run({"top": "TableVAlignTop", "mid": "TableVAlignCenter", "bot": "TableVAlignBottom"}[where])

    def cell_one_line(self, on):
        self._table_prop(LineWrap=1 if on else 0)

    def cell_unprotect(self):
        self.cell_block_all()
        try:
            self._table_prop(Protected=0)
        finally:
            self.run("Cancel")

    def cell_width_auto(self):
        """칸마다 가장 긴 글 길이에 맞춰 너비를 나눔 (어림값)."""
        raise UserError("셀 너비 자동 조절은 다음 시험판에 넣겠습니다.")

    # ---------- 셀 계산 ----------
    def cells_map(self, fn):
        for lst, text in self.cell_values():
            new = fn(text)
            if new != text:
                self._write_cell(lst, new)

    def cells_number(self):
        cells = self.cell_values()
        for i, (lst, _) in enumerate(cells):
            self._write_cell(lst, str(i + 1))

    def cells_percent(self):
        cells = self.cell_values()
        vals = [logic.to_number(t, 0) or 0 for _, t in cells]
        ps = logic.percents(vals)
        for (lst, t), p in zip(cells, ps):
            base = logic.remove_paren(t)
            self._write_cell(lst, "{}({})".format(base, logic.pct_text(p)))

    def cells_shuffle(self):
        cells = self.cell_values()
        texts = [t for _, t in cells]
        random.shuffle(texts)
        for (lst, _), t in zip(cells, texts):
            self._write_cell(lst, t)

    def cells_sort(self, mode):
        cells = self.cell_values()
        texts = [t for _, t in cells]
        key = {"asc": None, "desc": None, "num_asc": lambda x: logic.to_number(x, 0),
               "num_desc": lambda x: logic.to_number(x, 0)}[mode]
        texts.sort(key=key, reverse=mode in ("desc", "num_desc"))
        for (lst, _), t in zip(cells, texts):
            self._write_cell(lst, t)

    def cells_math(self, op, value):
        def f(t):
            v = logic.to_number(t)
            if v is None:
                return t
            r = {"+": v + value, "-": v - value, "*": v * value, "/": v / value if value else v,
                 "round": round(v)}[op]
            return logic.fmt_number(r)
        self.cells_map(f)

    def caption(self, text):
        h = self.h
        self.run("ShapeObjAttachCaption")
        act = h.CreateAction("TablePropertyDialog")
        s = act.CreateSet()
        act.GetDefault(s)
        cap = s.CreateItemSet("ShapeCaption", "Caption")
        cap.SetItem("Side", 2)
        cap.SetItem("Gap", h.MiliToHwpUnit(1))
        act.Execute(s)
        self.runs("SelectAll", "Delete", "ParagraphShapeAlignRight")
        self.char_shape(face="맑은 고딕", size=10)
        self.insert(text)

    def table_to_text(self):
        act = self.h.CreateAction("TableTableToString")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("DelimiterType", 3)
        s.SetItem("UserDefine", ":")
        act.Execute(s)

    def text_to_table(self):
        if not self.has_selection():
            raise UserError("표로 바꿀 글을 선택해 주세요. (칸은 탭으로 나뉘어 있어야 합니다)")
        self.run("TableStringToTable")

    def table_swap(self):
        act = self.h.CreateAction("TableSwap")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("Type", 2)
        act.Execute(s)

    def table_as_char(self):
        act = self.h.CreateAction("ShapeObjDialog")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("TreatAsChar", 1)
        act.Execute(s)

    def pictures(self, paths, background):
        h = self.h
        for i, path in enumerate(paths):
            if i > 0:
                self.run("TableRightCellAppend")
            if background:
                h.InsertBackgroundPicture("SelectedCell", path, 1, 5, 0, 0, 0, 0)
            else:
                h.InsertPicture(path, True, 3, False, False, 0, 0, 0)

    # ================= 정리 =================
    def do_markpen(self, color):
        h = self.h
        p = h.HParameterSet.HMarkpenShape
        h.HAction.GetDefault("MarkPenShape", p.HSet)
        p.Color = 0xFFFFFFFF if color is None else self.rgb(color)
        h.HAction.Execute("MarkPenShape", p.HSet)

    def do_sort_lines(self, mode):
        t = self.selected_text()
        if not t.strip():
            raise UserError("정렬할 줄들을 먼저 선택해 주세요.")
        if self.in_table() and len(self._scan_cells()) > 1:
            self.cells_sort({"asc": "asc", "desc": "desc", "short": "asc"}.get(mode, mode))
            return
        self.insert(logic.join_lines(logic.sort_lines(logic.split_lines(t), mode)))

    def do_calc(self):
        t = self.selected_text()
        if not t.strip():
            raise UserError("계산할 식을 선택해 주세요. 예: 1,200 + 800")
        try:
            self.insert(logic.calc_expr(t))
        except ValueError as e:
            raise UserError(str(e))

    def do_markdown(self):
        t = self.selected_text()
        if not t.strip():
            raise UserError("ChatGPT·Claude에서 복사한 글을 붙여 넣고, 그 글을 선택한 뒤 눌러 주세요.")
        items = logic.markdown_lines(t)
        self.run("Delete")
        for i, (sym, body) in enumerate(items):
            if i > 0:
                self.run("BreakPara")
            if sym:
                spec = logic.BULLETS[sym]
                self.insert(spec["text"] + body)
                self._apply_bullet_style(spec)
            else:
                self.insert(body)
                self.select_para()
                self.char_shape(face="휴먼명조", size=15, bold=False)
                self.para_shape(line_spacing=160, indent=0, left=0)
                self.run("Cancel")
                self.run("MoveParaEnd")

    def do_small_line(self):
        self.char_shape(size=3)

    # ================= 문서: 보고서 =================
    def page_margins(self, left=20, right=20, top=15, bottom=10, header=10, footer=10):
        h = self.h
        p = h.HParameterSet.HSecDef
        h.HAction.GetDefault("PageSetup", p.HSet)
        p.PageDef.LeftMargin = h.MiliToHwpUnit(left)
        p.PageDef.RightMargin = h.MiliToHwpUnit(right)
        p.PageDef.TopMargin = h.MiliToHwpUnit(top)
        p.PageDef.BottomMargin = h.MiliToHwpUnit(bottom)
        p.PageDef.HeaderLen = h.MiliToHwpUnit(header)
        p.PageDef.FooterLen = h.MiliToHwpUnit(footer)
        p.HSet.SetItem("ApplyClass", 24)
        p.HSet.SetItem("ApplyTo", 3)
        h.HAction.Execute("PageSetup", p.HSet)

    def _new_line_if_needed(self):
        if self.para_text().strip():
            self.run("MoveParaEnd")
            self.run("BreakPara")

    def _after_table(self):
        """방금 만든 표 바로 뒤 줄로 나가기."""
        try:
            self.run("CloseEx")
        except Exception:
            pass
        self.run("MoveLineEnd")
        self.run("BreakPara")
        self.para_shape(align=0, indent=0, left=0)

    def _take_line(self):
        """커서 줄에 글이 써 있으면 그 글을 지우고 돌려줌 (제목 등으로 바꿀 때). 표 안이면 쓰지 않음."""
        if self.in_table():
            return None
        t = self.para_text().strip()
        if not t:
            return None
        if self.select_para():
            self.run("Delete")
        return t

    def title_box(self, text=None, subtitle=None):
        """인천상의 제목 상자: 위 남색+파랑 띠 / 연회색 칸 / 아래 파랑+남색 띠.
        커서 줄에 글을 써 두고 누르면 그 글이 제목이 됨."""
        if text is None:
            text = self._take_line() or "보고서 제목"
        self._new_line_if_needed()
        self.run("ParagraphShapeAlignCenter")
        self.table_create(3, 2, widths=[37, 133], heights=[1, 14, 1])
        self.cell_block_all()
        self.borders(top=(NONE, THIN), bottom=(NONE, THIN), left=(NONE, THIN), right=(NONE, THIN),
                     horz=(NONE, THIN), vert=(NONE, THIN))
        self.char_shape(size=1)
        self.para_shape(line_spacing=100)
        self.run("Cancel")
        self.go_first_cell()
        colors = [BAR_NAVY, BAR_BLUE, None, None, BAR_BLUE, BAR_NAVY]
        for i, c in enumerate(colors):
            if c:
                self.run("TableCellBlock")
                self.cell_fill(c)
                self.run("Cancel")
            if i < len(colors) - 1:
                self.run("TableRightCell")
        # 가운데 행 합치고 제목
        self.go_first_cell()
        self.run("TableLowerCell")
        self.cell_block_row()
        self.run("TableMergeCell")
        self.run("Cancel")
        self.run("TableCellBlock")
        self.cell_fill(TITLE_GRAY)
        self.run("Cancel")
        self.char_shape(face="HY헤드라인M", size=24, bold=False)
        self.para_shape(line_spacing=160, align=3, break_char=0)  # 긴 제목은 낱말 단위로 줄바꿈
        self.run("TableVAlignCenter")
        self.insert(text)
        if subtitle:  # 표지: 둘째 줄에 보고서 종류 (예: 결 과 보 고 서)
            self.run("BreakPara")
            self.insert(subtitle)
        self._after_table()

    def summary_line(self, text=None):
        """요지: ❖ 한 줄, 가운데, 상자 없음 (인천상의 모양) + 중고딕 15pt, 줄간격 160% (보고서 공통 서식)"""
        if text is None:
            t = self._take_line()
            text = t.lstrip("❖ ").strip() if t else "요지를 한 줄로 입력하세요"
        self._new_line_if_needed()
        self.insert("❖ " + text)
        self.select_para()
        self.char_shape(face="중고딕", size=15, bold=False, italic=False, spacing=0, ratio=100)
        self.para_shape(line_spacing=160, align=3, indent=0, left=0, prev=0)
        self.run("Cancel")
        self.run("MoveParaEnd")
        self.run("BreakPara")
        self.para_shape(align=0)
        self.char_shape(bold=False)

    def big_title(self, text=None):
        """큰 제목: 남색 칸 흰 글자 Ⅰ + 제목 + 아래 밑줄, HY헤드라인M 16pt 180%"""
        if text is None:
            t = self._take_line()
            text = logic.strip_bullet(t).strip() if t else "제목"
        lines = self.text_before_cursor()
        num = logic.next_roman(lines)
        self._new_line_if_needed()
        self.para_shape(prev=15)
        self.table_create(1, 3, widths=[9, 2, 159], heights=[9.7])
        self.cell_block_all()
        self.borders(top=(NONE, THIN), bottom=(NONE, THIN), left=(NONE, THIN), right=(NONE, THIN),
                     vert=(NONE, THIN))
        self.char_shape(face="HY헤드라인M", size=16)
        self.para_shape(line_spacing=180)
        self.run("TableVAlignCenter")
        self.run("Cancel")
        self.go_first_cell()
        self.run("TableCellBlock")
        self.cell_fill(NAVY)
        self.run("Cancel")
        self.char_shape(color=(255, 255, 255), bold=True)
        self.run("ParagraphShapeAlignCenter")
        self.insert(num)
        self.run("TableRightCell")
        self.run("TableRightCell")
        self.run("TableCellBlock")
        self.borders(bottom=(SOLID, THIN), color=(0, 0, 0))
        self.run("Cancel")
        self.insert(text)
        self._after_table()

    def report_frame(self):
        self.report_build("보고서 제목", "요지를 한 줄로 입력하세요", ["사업개요", "세부 추진계획", "소요예산(안)"],
                          new_doc=False)

    # ---------- 보고서 양식 2: 표지 + 요약 + 본문 ----------
    @staticmethod
    def spaced(t):
        """결과보고서 → 결 과 보 고 서"""
        return " ".join(t.replace(" ", ""))

    def _blank_lines(self, n, size=15):
        self.char_shape(face="휴먼명조", size=size, bold=False)
        self.para_shape(line_spacing=160, align=0, indent=0, left=0, prev=0)
        for _ in range(n):
            self.run("BreakPara")

    def report_cover(self, title, kind, period):
        """표지: 오른쪽 위 기간 · 가운데 제목 상자(사업명 + 띄어 쓴 보고서 종류) · 아래 로고"""
        if period:
            self.char_shape(face="휴먼명조", size=15, bold=False, color=(0, 0, 255))
            self.para_shape(line_spacing=160, align=2, indent=0, left=0, prev=0)
            self.insert(period)
            self.run("BreakPara")
            self.char_shape(color=(0, 0, 0))
        self._blank_lines(8)
        self.title_box(title or "보고서 제목", subtitle=self.spaced(kind) if kind else None)
        self._blank_lines(14)
        logo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo_kor.jpg")
        self.para_shape(align=3)
        if os.path.exists(logo):
            try:
                pic = self.h.InsertPicture(logo, True, 1, False, False, 0, 70, 13)
                try:
                    pr = pic.Properties
                    pr.SetItem("TreatAsChar", 1)
                    pic.Properties = pr
                except Exception:
                    pass
            except Exception as e:
                trace("표지 로고 넣기 실패: {}".format(e))
        self.run("BreakPage")
        self.para_shape(align=0)

    def report_summary(self, heads):
        """요약 쪽: 노란 '요 약' 상자 + 초록 테두리 칸 안에 Ⅰ. Ⅱ. 소제목과 □ ○ 자리 (본문과 같은 서식)"""
        h = self.h
        # 노란 '요 약' 상자
        self.para_shape(align=3, indent=0, left=0, prev=0)
        self.table_create(1, 1, widths=[45], heights=[11])
        self.cell_block_all()
        self.borders(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(SOLID, THICK), right=(SOLID, THICK), color=(0, 0, 0))
        self.cell_fill((255, 255, 204))
        self.run("Cancel")
        self.char_shape(face="HY헤드라인M", size=20, bold=False, color=(0, 0, 160))
        self.para_shape(line_spacing=130, align=3)
        self.run("TableVAlignCenter")
        self.insert("요   약")
        self._after_table()
        # 초록 테두리 칸
        self.para_shape(align=3, prev=3)
        self.table_create(1, 1, widths=[170])
        self.cell_block_all()
        green = (0, 153, 102)
        self.borders(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(SOLID, THICK), right=(SOLID, THICK), color=green)
        self.run("Cancel")
        self.char_shape(color=(0, 0, 0))
        roman = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ"
        for i, head in enumerate(heads or []):
            if i > 0:
                self.run("BreakPara")
            self.char_shape(face="HY헤드라인M", size=16, bold=False, color=(0, 0, 0))
            self.para_shape(line_spacing=180, align=0, indent=0, left=0, prev=15 if i else 5)
            self.insert("{}. {}".format(roman[i % 10], head))
            self.run("BreakPara")
            self._bullet_set(last_break=False)
        self._after_table()
        self.run("BreakPage")

    def report_build2(self, title, kind, period, summary_heads, summary, sections, bullets=True, new_doc=True):
        """보고서 양식 2: 표지 → 요약 → 본문(양식 1과 같음)"""
        if new_doc:
            self.new_doc()
        self.page_margins()
        self.report_cover(title, kind, period)
        self.report_summary(summary_heads)
        self.report_build(title, summary, sections, bullets=bullets, new_doc=False)

    def _bullet_set(self, last_break=True):
        """□ ○ - · 네 단계 자리를 차례로 넣음 (본문 공통 서식). □ 줄 위치를 돌려줌."""
        first = None
        keys = ["□", "○", "-", "·"]
        for i, k in enumerate(keys):
            self.put_bullet(logic.BULLETS[k])
            if i == 0:
                first = self.h.GetPos()
            if i < len(keys) - 1 or last_break:
                self.run("BreakPara")
        return first

    def report_build(self, title, summary, sections, bullets=True, new_doc=True):
        """보고서 한 번에 만들기: 제목 상자 → (날짜) → 요지 → 큰 제목마다 □·○ 자리.
        끝나면 첫 □ 줄 끝에 커서를 둠."""
        if new_doc:
            self.new_doc()
        self.page_margins()
        self.title_box(title or "보고서 제목")
        if summary:
            self.summary_line(summary)
        first = None
        for s in sections or []:
            self.big_title(s)
            if bullets:
                pos = self._bullet_set(last_break=True)
                if first is None:
                    first = pos
        if first is not None:
            try:
                self.h.SetPos(*first)
            except Exception:
                pass

    # ---------- 보도자료 서식 ----------
    def press_style(self, kind):
        spec = {
            "title": ("", "HY그래픽", 23, True, 160, 0),
            "sub": ("- ", "HY그래픽", 14, True, 160, 1),
            "body": ("  ", "한양신명조", 13, False, 160, 0),
            "photo": ("", "한양중고딕", 11, True, 160, 0),
        }[kind]
        prefix, face, size, bold, spacing, align = spec
        cur = self.para_text()
        if kind == "photo":
            n = sum(1 for l in self.text_before_cursor() if l.strip().startswith("(사진설명")) + 1
            prefix = "(사진설명{}) ".format(n)
        if prefix and not cur.startswith(prefix):
            self.run("MoveParaBegin")
            self.insert(prefix)
        self.select_para()
        self.char_shape(face=face, size=size, bold=bold)
        self.para_shape(line_spacing=spacing, align=align, indent=0, left=0)
        self.run("Cancel")
        self.run("MoveParaEnd")

    def press_end(self):
        self._new_line_if_needed()
        self.char_shape(face="한양신명조", size=13, bold=False)
        self.para_shape(align=1)
        self.insert("별첨 : 행사사진 ○매.   끝.")

    # ================= 날짜 =================
    def do_insert_text(self, text):
        self.insert(text)

    def do_convert_dates(self, style):
        self.transform(lambda t: logic.convert_dates(t, style), per_line=False)

    # ================= 이동 =================
    def go(self, where):
        if where == "top":
            self.move(2)
        elif where == "end":
            self.move(3)
        elif where in ("up", "down", "up5", "down5"):
            act = "MovePageUp" if where.startswith("up") else "MovePageDown"
            for _ in range(5 if where.endswith("5") else 1):
                self.run(act)

    def find_color(self, color, forward):
        if not self.find("", forward=forward, color=color):
            raise UserError("더 찾을 글자가 없습니다.")

    def find_regex(self, pattern, forward):
        if not self.find(pattern, forward=forward, regex=True):
            raise UserError("더 찾을 곳이 없습니다.")

    def page_number(self):
        act = self.h.CreateAction("PageNumPos")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("DrawPos", 5)  # 아래 가운데
        act.Execute(s)

    def page_number_clear(self):
        act = self.h.CreateAction("DeleteCtrls")
        s = act.CreateSet()
        act.GetDefault(s)
        arr = s.CreateItemArray("DeleteCtrlType", 3)
        for i, v in enumerate((45, 47, 49)):
            arr.SetItem(i, v)
        act.Execute(s)

    def page_hide(self, hide):
        act = self.h.CreateAction("PageHiding")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("Fields", 32 if hide else 0)
        act.Execute(s)

    def page_new_number(self, n=1):
        self.page_number()
        act = self.h.CreateAction("NewNumber")
        s = act.CreateSet()
        act.GetDefault(s)
        s.SetItem("NumType", 0)
        s.SetItem("NewNumber", int(n))
        act.Execute(s)

    def add_page_top(self):
        self.move(2)
        self.run("BreakPage")
        self.move(2)

    # ================= 편리 =================
    def make_toc(self, min_size):
        """정한 크기 이상인 문단을 모아 커서 자리에 목차."""
        h = self.h
        start = h.GetPos()
        items = []
        self.move(2)
        last = None
        for _ in range(5000):
            pos = h.GetPos()
            if pos == last:
                break
            last = pos
            try:
                size = h.CharShape.Item("Height") / 100.0
            except Exception:
                size = 0
            if size >= min_size:
                t = self.para_text().strip()
                if t:
                    try:
                        page = h.KeyIndicator()[3]
                    except Exception:
                        page = ""
                    items.append((t, page))
            self.run("MoveNextParaBegin")
        h.SetPos(*start)
        if not items:
            raise UserError("{}pt 이상인 제목을 찾지 못했습니다. 기준 크기를 낮춰 보세요.".format(min_size))
        for t, page in items:
            self.insert("{}\t{}".format(t[:40], page))
            self.run("BreakPara")
        return len(items)

    def memo(self, kind):
        if kind == "add":
            self.run("InsertFieldMemo")
        elif kind == "from_sel":
            t = self.selected_text()
            if not t.strip():
                raise UserError("메모로 만들 글을 선택해 주세요.")
            self.run("Delete")
            self.run("InsertFieldMemo")
            self.insert(t)
        elif kind == "view":
            self.run("ViewOptionMemo")
        elif kind == "del":
            self.run("DeleteFieldMemo")

    def clear_para_styles(self):
        self.run("SelectAll")
        try:
            act = self.h.CreateAction("Style")
            s = act.CreateSet()
            act.GetDefault(s)
            s.SetItem("Apply", 0)
            act.Execute(s)
        finally:
            self.run("Cancel")

    def save_small(self):
        self.run("FileSaveAsMobileOptimized")

    def purify_scan(self):
        self.run("SelectAll")
        t = self.selected_text()
        self.run("Cancel")
        return logic.find_purify(t)

    def mailmerge_field(self, n):
        self.h.CreateField("필드{}".format(n), "", "필드{}".format(n))

    # ================= 인천광역시 탭 (인천시 양식 그대로) =================
    def icn_title(self, text="보고서 제목"):
        self._new_line_if_needed()
        self.table_create(1, 1, heights=[17])
        self.cell_block_all()
        self.borders(top=(SOLID, 5), bottom=(SOLID, 5), left=(SOLID, 5), right=(SOLID, 5))
        self.cell_fill(HEAD_BLUE)
        self.run("Cancel")
        self.char_shape(face="HY헤드라인M", size=24)
        self.para_shape(line_spacing=160, align=3)
        self.run("TableVAlignCenter")
        self.insert(text)
        self._after_table()

    def icn_cover(self):
        """인천시 보고서 새 표지(슬로건·두 색 줄·제목·날짜·로고·부서 상자)를 커서 자리에 넣고 표지 뒤로 이동."""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forms", "icn_cover.xml")
        if not os.path.exists(path):
            raise UserError("인천시 표지 파일(icn_cover.xml)을 찾지 못했습니다.")
        self.h.SetTextFile(open(path, encoding="utf-8").read(), "HWPML2X", "insertfile")
        self.move(3)

    def icn_big_title(self, text="표준보고서 양식", sub="업무방식 개선을 위한"):
        self._new_line_if_needed()
        self.char_shape(face="휴먼명조", size=20, bold=True, italic=True, color=(43, 86, 134))
        self.para_shape(align=3, line_spacing=110)
        self.insert(sub)
        self.run("BreakPara")
        self.char_shape(face="HY헤드라인M", size=32, bold=False, italic=False, color=(0, 0, 0))
        self.insert(text)
        self.run("BreakPara")
        self.para_shape(align=0)

    def icn_dot_box(self, text="… 보고 목적(생략하여도 무방)"):
        self._new_line_if_needed()
        self.table_create(1, 1)
        self.cell_block_all()
        self.borders(top=(DOT, THIN), bottom=(DOT, THIN), left=(DOT, THIN), right=(DOT, THIN))
        self.run("Cancel")
        self.char_shape(face="중고딕", size=15)
        self.para_shape(line_spacing=160)
        self.insert(text)
        self._after_table()

    def icn_summary(self):
        self._new_line_if_needed()
        self.table_create(1, 1)
        self.cell_block_all()
        self.borders(top=(SOLID, THICK), bottom=(SOLID, THICK), left=(NONE, THIN), right=(NONE, THIN))
        self.run("Cancel")
        self.char_shape(face="휴먼명조", size=15)
        self.para_shape(line_spacing=160)
        self.insert("◇ 요지 내용을 2~3줄 이내로 작성")
        self._after_table()

    def icn_ref(self):
        self._new_line_if_needed()
        self.table_create(1, 2, widths=[25, 145])
        self.go_first_cell()
        self.run("TableCellBlock")
        self.cell_fill((217, 217, 217))
        self.run("Cancel")
        self.char_shape(face="HY헤드라인M", size=15)
        self.run("ParagraphShapeAlignCenter")
        self.insert("참고 1")
        self.run("TableRightCell")
        self.char_shape(face="HY헤드라인M", size=15)
        self.insert(" 참고자료")
        self._after_table()

    def icn_order_table(self):
        self._new_line_if_needed()
        self.table_create(4, 3, widths=[40, 90, 40])
        self.cell_block_all()
        self.char_shape(face="휴먼명조", size=14)
        self.run("ParagraphShapeAlignCenter")
        self.run("Cancel")
        self.go_first_cell()
        self.cell_block_row()
        self.cell_fill(HEAD_BLUE)
        self.char_shape(bold=True)
        self.run("Cancel")
        self.go_first_cell()
        for i, v in enumerate(["시    간", "내    용", "비    고"]):
            self.insert(v)
            if i < 2:
                self.run("TableRightCell")
        self._after_table()

    def icn_line(self, text, face, size, bold=False, spacing=160, prev=0, left=0):
        self._new_line_if_needed()
        self.insert(text)
        self.select_para()
        self.char_shape(face=face, size=size, bold=bold)
        self.para_shape(line_spacing=spacing, prev=prev, left=left, indent=0)
        self.run("Cancel")
        self.run("MoveParaEnd")

    def icn_heading(self, text):
        self.icn_line("□ " + text, "HY헤드라인M", 16, spacing=180, prev=15)

    def icn_body(self, text=" ○ "):
        self.icn_line(text, "휴먼명조", 15, spacing=160, prev=5)

    ICN_FRAMES = {
        "policy": ("정책보고서 제목", "… 보고 목적(생략하여도 무방)", ["사업개요", "쟁점", "문제점 분석", "대책 및 추진계획"]),
        "status": ("상황보고서 제목", "… 상황을 보고드림(생략하여도 무방)", ["사업개요", "현황(추진경과)"]),
        "review": ("검토보고서 제목", "현안사항 및 대책을 보고드림(생략하여도 무방)",
                   ["사업개요", "추진배경", "검토내용(결과)", "향후계획"]),
        "meet_plan": ("회의개최 보고서 제목", "…회의 개최계획을 보고드림(삭제하여도 무방)",
                      ["회의개요", "회의안건", "진행순서", "행정사항"]),
        "meet_result": ("회의결과 보고서 제목", "…회의 개최결과를 보고드림(삭제하여도 무방)",
                        ["회의개요", "회의결과", "향후계획"]),
        "event": ("행사 보고서 제목", None, ["행사목적", "행사개요", "행사내용", "진행순서"]),
    }

    def icn_frame(self, kind):
        self.page_margins()
        if kind == "standard":
            self.icn_cover()                           # 2026년 인천시 새 표지 (제목·날짜·부서는 빈 자리)
            self.run("BreakPage")
            self.icn_summary()
            self.run("BreakPage")
            self.icn_title("보고서 제목")
            self.icn_dot_box("…방안을 수립, 추진함")
            for t in ("1. 추진배경", "2. ○○현황", "3. ○○활용실태 및 문제점", "4. ○○추진방안", "5. 행정사항"):
                self.icn_line(t, "휴먼명조", 18, bold=True, spacing=180, prev=15)
                self.icn_body()
            self.icn_ref()
            return
        title, purpose, sections = self.ICN_FRAMES[kind]
        self.icn_title(title)
        if purpose:
            self.icn_dot_box(purpose)
        for s in sections:
            self.icn_heading(s)
            if s in ("회의개요", "행사개요"):
                items = [" ○ 일시/장소 : ", " ○ 참 석 자 : ", " ○ 회의목적 : "] if s == "회의개요" else \
                        [" ○ 일시/장소 : ", " ○ 주    관 : ", " ○ 참 석 자 : "]
                for it in items:
                    self.icn_body(it)
            elif s == "검토내용(결과)":
                self.icn_body(" ○ 1안) ")
                self.icn_body(" ○ 2안) ")
            elif s == "회의결과":
                for it in (" ① 안건1", "   ○ 결론", "   ○ 참석자별 주요의견", " ② 안건2"):
                    self.icn_body(it)
            elif s == "진행순서":
                self.icn_order_table()
            else:
                self.icn_body()
        if kind == "meet_plan":
            self.icn_line("붙임  회의자료 1부.", "휴먼명조", 15)
        elif kind == "meet_result":
            self.icn_line("붙임  회의록 1부.", "휴먼명조", 15)

    def icn_bullet(self, kind):
        specs = {
            "box": ({"text": "□ ", "face": "HY헤드라인M", "size": 16, "bold": False, "spacing": 180, "prev": 10}, 0),
            "y_box": ({"text": "□ ", "face": "HY헤드라인M", "size": 16, "bold": False, "spacing": 180, "prev": 10}, 5),
            "y_circle": ({"text": " ○ ", "face": "휴먼명조", "size": 15, "bold": False, "spacing": 160, "prev": 5}, 5),
            "y_bar": ({"text": "  - ", "face": "휴먼명조", "size": 15, "bold": False, "spacing": 160, "prev": 5}, 5),
            "dot18": ({"text": ". ", "face": "휴먼명조", "size": 18, "bold": True, "spacing": 180, "prev": 15}, 0),
        }
        spec, left = specs[kind]
        self.put_bullet(spec, left=left)
