# -*- coding: utf-8 -*-
"""인천상의 오피스 (시험판 3)"""
import os
import re
import sys
import json
import traceback
import datetime

APP = os.path.dirname(os.path.abspath(__file__))
PY = os.path.dirname(sys.executable)
LOG = os.path.join(APP, "log.txt")


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def fatal(msg):
    log("FATAL " + msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg + "\n\n자세한 내용: " + LOG, "인천상의 오피스", 0x10)
    except Exception:
        pass
    sys.exit(1)


_lib = os.path.join(PY, "Library", "lib")
os.environ.setdefault("TCL_LIBRARY", os.path.join(_lib, "tcl8.6"))
os.environ.setdefault("TK_LIBRARY", os.path.join(_lib, "tk8.6"))
_DLL = []
for d in (os.path.join(PY, "Library", "bin"), PY):
    if os.path.isdir(d):
        try:
            _DLL.append(os.add_dll_directory(d))
        except Exception:
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
sys.path.insert(0, APP)

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except Exception:
    fatal("화면 구성 요소를 불러오지 못했습니다.\n" + traceback.format_exc())

try:
    import hwpctl
    import logic
    import styles
    hwpctl.TRACE = log
except Exception:
    fatal("한글 연결 구성 요소를 불러오지 못했습니다.\n" + traceback.format_exc())

try:
    import updater
    VERSION = updater.current_version()
except Exception:
    updater = None
    VERSION = "?"
TITLE = "인천상의 오피스 " + VERSION
# 색: 인천상의 남색을 포인트로, 바탕·테두리·보조 글자색은 대한상의 소플(sople.me) 계열
NAVY = "#2b2a7a"        # 포인트 (고른 탭, 주요 버튼, 제목)
NAVY_HOVER = "#3d3c99"
BG = "#ffffff"          # 카드 바탕
SHELL = "#f1f5fb"       # 창 바깥 바탕
LINE = "#dfe6f1"        # 얇은 테두리
HOVER = "#e3eaf6"       # 마우스 올렸을 때
BTN_BG = "#f7f9fc"      # 버튼 바탕 (흰 카드 위에서 칸이 보이게)
BTN_LINE = "#c3cfe2"    # 버튼 테두리 (칸 구분선)
TEXT = "#222222"
MUTED = "#8694b6"       # 보조 글자
OK_GREEN = "#1e9e6a"
FONT = ("맑은 고딕", 9)
FONT_S = ("맑은 고딕", 8)
FONT_B = ("맑은 고딕", 9, "bold")
FONT_T = ("맑은 고딕", 10, "bold")
FORMS = os.path.join(APP, "forms")
PRIMARY_BG = "#e8edf8"  # 예전 '주요 버튼' 표시 색 → 남색 버튼으로 그림


class _Button(tk.Button):
    """평평한 버튼: 얇은 테두리, 마우스를 올리면 연한 파랑. bg=PRIMARY_BG면 남색 주요 버튼."""
    def __init__(self, master=None, **kw):
        primary = kw.get("bg") == PRIMARY_BG
        kw.pop("relief", None)
        base = kw.get("bg", "white")
        base = NAVY if primary else (BTN_BG if base in ("white", "#ffffff") else base)
        kw.update(relief="flat", bd=0, highlightthickness=1, highlightbackground=NAVY if primary else BTN_LINE,
                  highlightcolor=NAVY, bg=base, cursor="hand2")
        kw.setdefault("fg", TEXT)
        if primary:
            kw["fg"] = "white"
        kw.setdefault("activebackground", NAVY_HOVER if primary else HOVER)
        kw.setdefault("activeforeground", "white" if primary else NAVY)
        kw.setdefault("pady", 2)
        super().__init__(master, **kw)
        hov = NAVY_HOVER if primary else HOVER
        self.bind("<Enter>", lambda e: self.config(bg=hov), add="+")
        self.bind("<Leave>", lambda e: self.config(bg=base), add="+")


class _Entry(tk.Entry):
    def __init__(self, master=None, **kw):
        kw.pop("relief", None)
        kw.pop("bd", None)
        kw.update(relief="flat", bd=0, highlightthickness=1, highlightbackground=LINE, highlightcolor=NAVY,
                  bg="white", fg=TEXT, insertwidth=1)
        super().__init__(master, **kw)


class _LabelFrame(tk.LabelFrame):
    """묶음 상자 → 흰 카드 (얇은 테두리, 남색 제목)."""
    def __init__(self, master=None, **kw):
        kw.update(relief="flat", bd=0, highlightthickness=1, highlightbackground=LINE, highlightcolor=LINE)
        kw.setdefault("fg", NAVY)
        kw["padx"] = max(kw.get("padx", 0), 5)
        kw["pady"] = max(kw.get("pady", 0), 2)
        super().__init__(master, **kw)


class _Checkbutton(tk.Checkbutton):
    def __init__(self, master=None, **kw):
        kw.setdefault("activebackground", kw.get("bg", BG))
        kw.setdefault("fg", TEXT)
        kw.update(highlightthickness=0, bd=0, selectcolor="white", cursor="hand2")
        super().__init__(master, **kw)


tk.Button, tk.Entry, tk.LabelFrame, tk.Checkbutton = _Button, _Entry, _LabelFrame, _Checkbutton


def greeting(me=None):
    hr = datetime.datetime.now().hour
    hi = "좋은 아침이에요" if hr < 12 else ("좋은 오후예요" if hr < 18 else "좋은 저녁이에요")
    me = me or {}
    who = " ".join(x for x in (me.get("name", ""), me.get("title", "")) if x)
    return "{}, {}님".format(hi, who) if who else hi + "."

SPECIAL = list("ⅠⅡⅢⅣⅤⅥⅦⅧ①②③④⑤⑥⑦⑧❶❷❸❹❺❻❼❽") + \
    [chr(c) for c in range(0xF02B1, 0xF02B9)] + \
    list("←→↑↓") + ["", "", "", ""] + list("⇒⇨➪➜▶▸☞▷○") + [""] + \
    list("∘∙·․･□") + [""] + list("▣☑▪∎△㎡℃✓☎★…※'×∼▲▼")
WRAPS = [("《", "》"), ("“", "”"), ("‘", "’"), ("【", "】"), ("「", "」"), ("『", "』"), ("〈", "〉"), ("［", "］")]
SHADES = [((255, 255, 255), (0, 0, 0), "흰색"), ((242, 242, 242), (0, 0, 0), "연회색"),
          ((255, 255, 229), (0, 0, 0), "연노랑"), ((255, 245, 211), (0, 0, 0), "연주황"),
          ((255, 231, 216), (0, 0, 0), "살구"), ((249, 237, 237), (0, 0, 0), "연분홍"),
          ((236, 248, 212), (0, 0, 0), "연두"), ((205, 242, 228), (0, 0, 0), "연녹"),
          ((231, 244, 246), (0, 0, 0), "연하늘"), ((32, 58, 123), (255, 255, 255), "진남색"),
          ((48, 87, 185), (255, 255, 255), "파랑"), ((223, 230, 247), (0, 0, 0), "연파랑"),
          ((230, 238, 247), (0, 0, 0), "인천상의")]

MARKDOWN_HELP = """마크다운 → 한글 사용법

ChatGPT·Claude가 쓴 글을 한글에 붙여 넣고, 그 글을 선택한 뒤 [마크다운→한글]을 누르면
아래처럼 개조식 기호와 보고서 서식으로 바뀝니다.

  # 제목, ## 제목      →  □ (휴먼명조 16pt 굵게)
  - 항목, 1. 항목      →  ○ (휴먼명조 15pt)
    - 들여 쓴 항목     →  -
      - 더 들여 쓴 항목 →  ·
  > 인용               →  ※ (중고딕 12pt)
  **굵게**             →  굵게 표시 기호만 지움
  그 밖의 줄           →  본문 (휴먼명조 15pt)
"""


def make_shortcut():
    root_dir = os.path.dirname(APP)
    lnk = os.path.join(root_dir, "인천상의 오피스.lnk")
    target = os.path.join(PY, "pythonw.exe")
    icon = os.path.join(APP, "assets", "icon_kcci.ico")  # 아이콘을 바꾸면 파일 이름도 바꿔야 윈도우가 새 그림을 씀
    if not os.path.exists(icon):
        icon = os.path.join(APP, "assets", "icon.ico")
    try:
        import win32com.client
        sh = win32com.client.Dispatch("WScript.Shell")
        s = sh.CreateShortcut(lnk)  # 있으면 그 바로가기를 읽음
        same_target = os.path.normcase(s.TargetPath or "") == os.path.normcase(target)
        same_icon = os.path.normcase((s.IconLocation or "").split(",")[0]) == os.path.normcase(icon)
        if os.path.exists(lnk) and same_target and same_icon:
            return  # 지금 위치·아이콘이 맞으면 그대로
        # 없거나, 폴더를 옮겼거나, 아이콘이 바뀌었으면 새로 씀
        s.TargetPath = target
        s.Arguments = '"{}"'.format(os.path.join(APP, "main.py"))
        s.WorkingDirectory = root_dir
        s.IconLocation = icon + ",0"
        s.Description = "인천상의 오피스"
        s.Save()
    except Exception:
        log("바로가기 생성 실패\n" + traceback.format_exc())


class App:
    def __init__(self, root):
        self.root = root
        self._imgs = []
        self.hwp = hwpctl.Hwp()
        self.store = styles.load()
        cur = self.store.get("current")
        mine = [e for e in self.store.get("myforms", []) if e.get("name") == cur]
        self.hwp.active = dict(mine[0].get("styles") or {}) if mine else {}
        root.title(TITLE)
        root.configure(bg=SHELL)
        root.option_add("*Foreground", TEXT)
        root.option_add("*Font", FONT)
        root.resizable(False, False)
        root.attributes("-topmost", True)
        try:
            root.iconbitmap(os.path.join(APP, "assets", "icon_kcci.ico"))
        except Exception:
            pass

        top = tk.Frame(root, bg="white")
        top.pack(fill="x")
        try:
            self.logo = tk.PhotoImage(file=os.path.join(APP, "assets", "logo.png"))
            tk.Label(top, image=self.logo, bg="white").pack(side="left", padx=(10, 8), pady=8)
        except Exception:
            tk.Label(top, text="인천상공회의소", font=FONT_B, bg="white").pack(side="left", padx=(10, 8), pady=8)
        self.pin = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="항상 위", variable=self.pin, bg="white", font=FONT_S, fg=MUTED,
                       command=lambda: root.attributes("-topmost", self.pin.get())).pack(side="right", padx=10)
        self.hello = tk.Label(top, text=greeting(styles.load_profile()), font=FONT_T, fg=TEXT, bg="white")
        self.hello.pack(side="left", padx=(4, 0))
        tk.Frame(root, bg=LINE, height=1).pack(fill="x")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=SHELL, borderwidth=0, bordercolor=SHELL, lightcolor=SHELL,
                        darkcolor=SHELL, tabmargins=(0, 0, 0, 0))
        # 탭: 알약 모양 칩 — 고른 탭만 남색, 나머지는 회색 글씨
        style.configure("TNotebook.Tab", font=FONT, padding=(10, 4), background=SHELL, foreground=MUTED,
                        borderwidth=0, bordercolor=SHELL, lightcolor=SHELL, focuscolor=SHELL)
        style.map("TNotebook.Tab",
                  background=[("selected", NAVY), ("active", HOVER)],
                  foreground=[("selected", "white"), ("active", NAVY)],
                  lightcolor=[("selected", NAVY)], bordercolor=[("selected", NAVY)],
                  font=[("selected", FONT_B)], expand=[("selected", (0, 0, 0, 0))])
        style.configure("TCombobox", fieldbackground="white", background="white", bordercolor=LINE,
                        lightcolor="white", darkcolor="white", arrowcolor=NAVY, foreground=TEXT, padding=2)
        style.map("TCombobox", fieldbackground=[("readonly", "white")], bordercolor=[("focus", NAVY)],
                  selectbackground=[("readonly", "white")], selectforeground=[("readonly", TEXT)])
        style.configure("Treeview", background="white", fieldbackground="white", bordercolor=LINE, rowheight=22)
        style.configure("Treeview.Heading", background=SHELL, foreground=NAVY, font=FONT_B, bordercolor=LINE,
                        lightcolor=SHELL, darkcolor=SHELL)
        style.configure("Vertical.TScrollbar", background=SHELL, troughcolor="white", bordercolor=LINE,
                        lightcolor=SHELL, darkcolor=SHELL, arrowcolor=MUTED)
        self.build_profile(root)
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", padx=10, pady=(8, 0))

        self.build_tabs()
        self.refresh_sets()
        self.refresh_myforms()

        bottom = tk.Frame(root, bg=SHELL)
        bottom.pack(fill="x", padx=10, pady=(8, 2))
        tk.Button(bottom, text="한글 다시 연결", font=FONT_S, command=self.reconnect, padx=6).pack(side="left")
        self.status = tk.Label(bottom, text="", font=FONT_S, bg=SHELL, fg=MUTED, anchor="w")
        self.status.pack(side="left", padx=8)
        self.tip = tk.Label(root, text="버튼에 마우스를 올리면 설명이 나옵니다", font=FONT_S, bg=SHELL, fg=MUTED,
                            anchor="w", wraplength=440, justify="left")
        self.tip.pack(fill="x", padx=10, pady=(0, 8))
        root.after(300, self.startup)

    # ---------------- 공통 ----------------
    def tab(self, name):
        f = tk.Frame(self.nb, bg=SHELL, padx=0, pady=6)
        self.nb.add(f, text=name)
        return f

    def group(self, parent, title, buttons, cols=4, height=None):
        """height: 버튼 높이(글줄 수). 주면 그 칸 버튼을 모두 같은 높이로."""
        f = tk.LabelFrame(parent, text=" " + title + " ", font=FONT_B, fg=NAVY, bg=BG, padx=5, pady=2)
        f.pack(fill="x", pady=(0, 5))
        for i, item in enumerate(buttons):
            label, fn, tip = item[:3]
            opts = item[3] if len(item) > 3 else {}
            dot = None
            if opts.get("dot"):                          # 양식 버튼 앞 종류별 작은 색 표시
                dot = tk.PhotoImage(width=8, height=8)
                dot.put(opts["dot"], to=(0, 0, 8, 8))
                self._imgs.append(dot)
            hh = height
            if dot and height:                          # 그림이 붙은 버튼은 높이를 픽셀로 받음
                import tkinter.font as tkfont
                hh = tkfont.Font(font=opts.get("font", FONT)).metrics("linespace") * height + 6
            b = tk.Button(f, text=label, font=opts.get("font", FONT), height=hh,
                          bg=opts.get("bg", "white"), fg=opts.get("fg", TEXT), padx=2, pady=2,
                          image=dot or "", compound="left" if dot else "none",
                          command=fn if opts.get("raw") else (lambda fn=fn, label=label: self.call(fn, label.replace("\n", " "))))
            b.grid(row=i // cols, column=i % cols, padx=2, pady=1, sticky="ew")
            b.bind("<Enter>", lambda e, t=tip, l=label.replace("\n", " "): self.tip.config(text="{} : {}".format(l, t)),
                   add="+")
            b.bind("<Leave>", self._tip_reset, add="+")
        for c in range(cols):
            f.grid_columnconfigure(c, weight=1, uniform="g")
        return f

    TIP_DEFAULT = "버튼에 마우스를 올리면 설명이 나옵니다"

    def phone_tidy(self):
        n = self.hwp.do_phone_tidy()
        self.root.after(20, lambda: self.set_status("완료: 전화번호 {}개에 하이픈을 넣었습니다".format(n)))

    def _tip_reset(self, event=None):
        self.tip.config(text=self.TIP_DEFAULT)

    def set_status(self, text, ok=True):
        self.status.config(text=text, fg=OK_GREEN if ok else "#e5484d")

    def startup(self, new_doc=True):
        """한글 연결을 화면과 따로 돌림 — 한글이 바쁘거나 늦게 켜져도 창은 멈추지 않음.
        new_doc: 켤 때는 새 문서로 시작, [한글 다시 연결]은 연결만."""
        import threading
        import time
        if getattr(self, "_connecting", False):
            return
        self._connecting = True
        self._conn = {"state": None, "t0": time.time(), "hinted": False, "new_doc": new_doc}
        self.set_status("한글 준비 중…")

        def worker():
            st = hwpctl.probe(4)
            if st == "none":
                hwpctl.launch()
            t0 = time.time()
            while st in ("none", "busy") and time.time() - t0 < 60:   # 켜지는 중이거나 확인 창이 닫히길 기다림
                time.sleep(1)
                st = hwpctl.probe(3)
            self._conn["state"] = st
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(300, self._startup_poll)

    def _startup_poll(self):
        import time
        c = self._conn
        sec = int(time.time() - c["t0"])
        if c["state"] is None:
            self.set_status("한글 준비 중… {}초".format(sec))
            if sec >= 15 and not c["hinted"]:   # 오래 걸리면 확인 창 안내
                c["hinted"] = True
                self.tip.config(text="한글이 답하지 않습니다 — 한글에 확인 창(저장·복구·업데이트)이 떠 있으면 닫아 주세요.")
            self.root.after(500, self._startup_poll)
            return
        self._connecting = False
        self._tip_reset()
        st = c["state"]
        try:
            if st == "ok":
                if c["new_doc"]:
                    msg = self.hwp.start_new()
                else:
                    self.hwp.connect(create=False)
                    msg = "다시 연결했습니다"
                self.set_status("● 한글 연결됨 · " + msg)
                return
            if st == "busy":
                self.set_status("한글이 응답하지 않음 — 확인 창을 닫고 [한글 다시 연결]", ok=False)
                messagebox.showinfo(TITLE, hwpctl.BUSY_MSG, parent=self.root)
            elif st == "denied":
                self.set_status("한글 연결 거부됨 — 한글을 껐다 켜 주세요", ok=False)
                messagebox.showinfo(TITLE, hwpctl.DENIED_MSG, parent=self.root)
            else:
                self.set_status("한글 연결 안 됨 — 한글을 켠 뒤 [한글 다시 연결]", ok=False)
        except hwpctl.UserError as e:
            self.set_status("한글 연결 안 됨", ok=False)
            log(str(e))
        except Exception:
            self.set_status("한글 연결 안 됨", ok=False)
            log("시작 연결 오류\n" + traceback.format_exc())

    # ---------------- 업데이트 ----------------
    def check_update(self, manual=False):
        """새 버전 확인은 화면과 따로 돌림 (인터넷이 느려도 창이 멈추지 않게)."""
        if updater is None:
            return
        import threading
        box = {}

        def work():
            try:
                box["info"] = updater.latest(timeout=5)
            except Exception as e:
                box["err"] = e

        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if th.is_alive():
                self.root.after(200, poll)
                return
            info = box.get("info")
            if box.get("err") is not None:
                log("업데이트 확인 실패: {}".format(box["err"]))
                if manual:
                    self.notice("확인하지 못했습니다", "새 버전을 확인하지 못했습니다.\n인터넷 연결을 확인해 주세요.", ok=False)
                return
            if not updater.newer(info):
                if manual:
                    self.notice("최신 버전입니다", "지금 쓰는 버전({})이 최신입니다.".format(VERSION))
                return
            self.ask_update(info)
        self.root.after(200, poll)

    # --- 업데이트 창 (이음오피스 느낌: 남색 머리 + 로고 + 버전 알약 + 내용 + 큰 버튼) ---
    UPD_W = 380
    NAVY_LIGHT = "#4b4ab3"

    def _upd_icon(self, size):
        """로고 아이콘을 size 픽셀 근처로 줄인 그림 (창마다 따로 보관)."""
        try:
            img = tk.PhotoImage(file=os.path.join(APP, "assets", "icon.png"))
            k = max(1, img.width() // size)
            img = img.subsample(k, k)
            self._imgs.append(img)
            return img
        except Exception:
            return None

    @staticmethod
    def _round_rect(cv, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    def _upd_window(self, title):
        w = tk.Toplevel(self.root)
        w.title(title)
        w.configure(bg="white")
        w.resizable(False, False)
        w.attributes("-topmost", True)
        try:
            w.iconbitmap(os.path.join(APP, "assets", "icon_kcci.ico"))
        except Exception:
            pass
        w.transient(self.root)
        return w

    def _upd_header(self, w, height, title, sub=None, icon=56):
        """남색 그라데이션 머리: 흰 바탕 둥근 칸 안 로고 + 제목 (+ 버전 알약)."""
        W = self.UPD_W
        cv = tk.Canvas(w, width=W, height=height, highlightthickness=0, bd=0, bg=NAVY)
        cv.pack(fill="x")
        c1 = tuple(int(NAVY[i:i + 2], 16) for i in (1, 3, 5))
        c2 = tuple(int(self.NAVY_LIGHT[i:i + 2], 16) for i in (1, 3, 5))
        for y in range(height):                     # 위는 밝게, 아래로 갈수록 남색
            t = y / max(1, height - 1)
            col = "#%02x%02x%02x" % tuple(int(c2[k] + (c1[k] - c2[k]) * t) for k in range(3))
            cv.create_line(0, y, W, y, fill=col)
        top = 18
        if icon:
            tile = icon + 14
            x0 = (W - tile) // 2
            self._round_rect(cv, x0, top, x0 + tile, top + tile, 16, fill="white", outline="")
            img = self._upd_icon(icon)
            if img:
                cv.create_image(W // 2, top + tile // 2, image=img)
            top += tile + 12
        cv.create_text(W // 2, top + 10, text=title, fill="white", font=("맑은 고딕", 14, "bold"))
        if sub:                                     # (지금 버전, 새 버전) 알약
            y = top + 40
            old, new = "v" + sub[0], "v" + sub[1]
            fo = ("맑은 고딕", 9)
            fb = ("맑은 고딕", 9, "bold")
            import tkinter.font as tkfont
            wo = tkfont.Font(font=fo).measure(old) + 24
            wn = tkfont.Font(font=fb).measure(new) + 24
            gap = 30
            x = (W - (wo + gap + wn)) // 2
            self._round_rect(cv, x, y - 11, x + wo, y + 11, 11, fill="#6564c2", outline="")
            cv.create_text(x + wo // 2, y, text=old, fill="#e6e6fa", font=fo)
            cv.create_text(x + wo + gap // 2, y, text="→", fill="white", font=fb)
            x2 = x + wo + gap
            self._round_rect(cv, x2, y - 11, x2 + wn, y + 11, 11, fill="white", outline="")
            cv.create_text(x2 + wn // 2, y, text=new, fill=NAVY, font=fb)
        return cv

    def _upd_button(self, parent, text, cmd, primary=True):
        """둥근 느낌의 넓은 버튼 (Label로 그려 테두리 없이)."""
        bg, fg, hov = (NAVY, "white", NAVY_HOVER) if primary else ("white", MUTED, "white")
        b = tk.Label(parent, text=text, bg=bg, fg=fg, cursor="hand2",
                     font=("맑은 고딕", 11, "bold") if primary else ("맑은 고딕", 9, "underline"),
                     pady=10 if primary else 2)
        b.enabled = True

        def click(e=None):
            if b.enabled:
                cmd()
        b.bind("<Button-1>", click)
        if primary:
            b.bind("<Enter>", lambda e: b.enabled and b.config(bg=hov))
            b.bind("<Leave>", lambda e: b.enabled and b.config(bg=bg))
        return b

    def _upd_center(self, w):
        w.update_idletasks()
        W, H = self.UPD_W, w.winfo_reqheight()      # 너비는 머리 그림과 같게 고정 (내용은 그 안에서 줄바꿈)
        x = self.root.winfo_rootx() + (self.root.winfo_width() - W) // 2
        y = self.root.winfo_rooty() + 80
        w.geometry("{}x{}+{}+{}".format(W, H, max(0, x), max(0, y)))
        w.lift()
        w.focus_force()

    def notice(self, title, msg, ok=True):
        """작은 안내 창 — 업데이트 창과 같은 모양 (남색 머리 + 로고 + 한두 줄 + 확인)."""
        w = self._upd_window(TITLE)
        self._upd_header(w, 112, title, icon=40)
        body = tk.Frame(w, bg="white", padx=24, pady=16)
        body.pack(fill="both")
        tk.Label(body, text=msg, bg="white", fg=TEXT if ok else "#d93636", font=("맑은 고딕", 10),
                 justify="center", wraplength=self.UPD_W - 48).pack(pady=(0, 14))
        btn = self._upd_button(body, "확인", w.destroy)
        btn.pack(fill="x")
        w.bind("<Return>", lambda e: w.destroy())
        w.bind("<Escape>", lambda e: w.destroy())
        self._upd_center(w)
        return w

    def ask_update(self, info):
        """새 버전 안내 창. [지금 업데이트] → 받는 중 → 바꿈 → 다시 켜기 (모두 이 창 안에서)."""
        w = self._upd_window("업데이트")
        self._upd_header(w, 184, "새 버전이 있습니다", sub=(VERSION, info["version"]))
        body = tk.Frame(w, bg="white", padx=20, pady=14)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="업데이트 내용", bg="white", fg=MUTED, font=("맑은 고딕", 9)).pack(anchor="w", pady=(0, 6))
        box = tk.Frame(body, bg="#f7f9fc", highlightthickness=1, highlightbackground=LINE)
        box.pack(fill="both", expand=True)
        txt = tk.Text(box, height=9, width=30, wrap="word", bd=0, bg="#f7f9fc", fg=TEXT,
                      font=("맑은 고딕", 10), padx=12, pady=10, spacing1=2, spacing3=3, cursor="arrow")
        sb = ttk.Scrollbar(box, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        txt.tag_configure("b", font=("맑은 고딕", 10, "bold"), spacing1=6)
        txt.tag_configure("li", lmargin1=6, lmargin2=20)
        notes = (info.get("notes") or "").strip() or "자잘한 부분을 고쳤습니다."
        for line in notes.splitlines():
            ln = line.rstrip()
            if not ln.strip():
                txt.insert("end", "\n")
            elif ln.lstrip().startswith(("- ", "· ", "* ")):
                txt.insert("end", "•  " + ln.lstrip()[2:] + "\n", "li")
            elif ln.endswith(":") or ln.startswith("#"):
                txt.insert("end", ln.lstrip("# ").rstrip(":") + "\n", "b")
            else:
                txt.insert("end", ln + "\n")
        txt.configure(state="disabled")
        rp = updater.repo() if updater else ""
        if rp:
            link = tk.Label(body, text="GitHub에서 전체 보기", bg="white", fg="#3b5bdb", cursor="hand2",
                            font=("맑은 고딕", 9, "underline"))
            link.pack(anchor="w", pady=(6, 0))

            def open_link(e=None):
                import webbrowser
                webbrowser.open("https://github.com/{}/commits/main".format(rp))
            link.bind("<Button-1>", open_link)
        status = tk.Label(body, text="", bg="white", fg=MUTED, font=("맑은 고딕", 9))
        status.pack(fill="x", pady=(8, 0))
        main_btn = None

        def do_update():
            main_btn.enabled = False
            main_btn.config(text="받는 중…", bg="#9a99c9", cursor="watch")
            later.pack_forget()
            status.config(text="새 버전을 받고 있습니다. 잠깐만 기다려 주세요.", fg=MUTED)
            w.update()
            import threading
            res = {}

            def work():
                try:
                    res["n"] = updater.install(info)
                except Exception as e:
                    res["err"] = e
                    res["tb"] = traceback.format_exc()
            th = threading.Thread(target=work, daemon=True)
            th.start()

            def poll():
                if th.is_alive():
                    w.after(200, poll)
                    return
                if "err" in res:
                    log("업데이트 실패\n" + res.get("tb", ""))
                    status.config(text="업데이트하지 못했습니다: {}\n지금 버전은 그대로 쓸 수 있습니다.".format(res["err"]),
                                  fg="#d93636")
                    main_btn.enabled = True
                    main_btn.config(text="다시 시도", bg=NAVY, cursor="hand2")
                    later.config(text="닫기")
                    later.pack(pady=(8, 0))
                    return
                log("업데이트 {} → {} (파일 {}개)".format(VERSION, info["version"], res["n"]))
                main_btn.config(text="완료", bg=OK_GREEN, cursor="arrow")
                status.config(text="{} 버전으로 바꿨습니다. 프로그램을 다시 켭니다…".format(info["version"]), fg=OK_GREEN)
                w.after(1500, restart)
            w.after(200, poll)

        def restart():
            try:
                import subprocess
                subprocess.Popen([sys.executable, os.path.join(APP, "main.py")], cwd=os.path.dirname(APP))
            except Exception:
                log("다시 켜기 실패\n" + traceback.format_exc())
                self.notice("다시 켜 주세요", "프로그램을 닫았다가 다시 켜 주세요.")
                return
            self.root.destroy()

        main_btn = self._upd_button(body, "지금 업데이트", do_update)
        main_btn.pack(fill="x", pady=(8, 0))
        later = self._upd_button(body, "나중에", w.destroy, primary=False)
        later.pack(pady=(8, 0))
        w.bind("<Escape>", lambda e: main_btn.enabled and w.destroy())
        self._upd_center(w)
        return w

    def reconnect(self, create=False):
        self.startup(new_doc=False)

    def hwp_ready(self, parent):
        """버튼을 누를 때 한글이 답하는지 먼저 확인 (답이 없으면 안내만 하고 멈추지 않음)."""
        st = hwpctl.probe(3)
        if st == "ok":
            return True
        if st == "busy":
            self.set_status("한글이 응답하지 않음", ok=False)
            messagebox.showinfo(TITLE, hwpctl.BUSY_MSG, parent=parent)
        elif st == "denied":
            self.set_status("한글 연결 거부됨", ok=False)
            messagebox.showinfo(TITLE, hwpctl.DENIED_MSG, parent=parent)
        elif st == "none":
            self.startup(new_doc=True)
            messagebox.showinfo(TITLE, "한글이 꺼져 있어서 켜는 중입니다.\n한글 창이 뜨고 아래에 '한글 연결됨'이 나오면 다시 눌러 주세요.",
                                parent=parent)
        else:
            self.set_status("한글 확인 오류", ok=False)
        return False

    def call(self, fn, label, parent=None):
        parent = parent or self.root
        if not self.hwp_ready(parent):
            return None
        try:
            self.hwp.ensure()
            self.hwp.me = self.profile_values()
            r = fn()
            self.set_status("완료: " + label)
            return r
        except hwpctl.UserError as e:
            self.set_status("안내: " + label, ok=False)
            messagebox.showinfo(TITLE, str(e), parent=parent)
        except Exception:
            log("오류 [{}]\n{}".format(label, traceback.format_exc()))
            self.set_status("오류: " + label, ok=False)
            messagebox.showerror(TITLE, "'{}' 실행 중 오류가 났습니다.\n\napp 폴더의 log.txt 파일을 보내주시면 고치겠습니다.".format(label),
                                 parent=parent)

    def popup(self, title, width=None):
        w = tk.Toplevel(self.root)
        w.title(title)
        w.configure(bg="white", padx=10, pady=8)
        w.attributes("-topmost", True)
        w.resizable(False, False)
        try:
            w.iconbitmap(os.path.join(APP, "assets", "icon_kcci.ico"))
        except Exception:
            pass
        x = self.root.winfo_rootx() + self.root.winfo_width() + 6
        y = self.root.winfo_rooty()
        w.geometry("+{}+{}".format(x, y))
        return w

    def pop_buttons(self, w, items, cols=4, title=None, row=0):
        """items: (label, fn) — fn은 한글 동작"""
        if title:
            tk.Label(w, text=title, font=FONT_B, fg=NAVY, bg="white").grid(row=row, column=0, columnspan=cols, sticky="w", pady=(4, 2))
            row += 1
        for i, it in enumerate(items):
            label, fn = it[:2]
            opts = it[2] if len(it) > 2 else {}
            b = tk.Button(w, text=label, font=opts.get("font", FONT), relief="groove", bg=opts.get("bg", "white"),
                          fg=opts.get("fg", "black"), width=opts.get("width", 9),
                          command=lambda fn=fn, label=label: self.call(fn, label, parent=w))
            b.grid(row=row + i // cols, column=i % cols, padx=1, pady=1, sticky="ew")
        return row + (len(items) + cols - 1) // cols

    def entry(self, w, label, row, default="", width=30):
        tk.Label(w, text=label, font=FONT, bg="white", anchor="w").grid(row=row, column=0, sticky="w", pady=2)
        e = tk.Entry(w, font=FONT, width=width, relief="solid", bd=1)
        e.insert(0, default)
        e.grid(row=row, column=1, columnspan=3, sticky="w", pady=2)
        return e

    def close_btn(self, w, row, cols=4):
        tk.Button(w, text="닫기", font=FONT, relief="groove", bg="white", width=8,
                  command=w.destroy).grid(row=row, column=cols - 1, sticky="e", pady=(8, 0))

    # ---------------- 탭 구성 ----------------
    def build_tabs(self):
        h = self.hwp

        # ===== 문서 =====
        t = self.tab("문서")
        self.group(t, "양식 열기", [
            ("업무보고", lambda: self.open_form("report"), "빈 업무보고 양식 + 오늘 날짜", {"dot": "#2b2a7a"}),
            ("공문 ▸", self.dlg_letter, "국문·영문·일문 중 골라 열기 (직인 포함, 시행일 오늘 날짜)", {"raw": True, "dot": "#2361ff"}),
            ("보도자료", lambda: self.open_form("press"), "빈 보도자료 양식 (칸마다 서식이 들어 있음)", {"dot": "#7c4dff"}),
            ("보도자료\n배포계획", lambda: self.open_form("weekly"), "주간 주요 일정 및 보도자료 배포 계획 — 다가오는 일~토 기간, 담당자 칸 자동", {"dot": "#a68bff"}),
            ("여비계산서 ▸", self.dlg_travel, "기간 년·월, 청구일·영수일, 청구인·영수인, 예산과목·코드 자동 — 함께 간 사람을 넣으면 <붙임> 표까지", {"raw": True, "dot": "#1e9e6a"}),
            ("법인카드\n사용내역", lambda: self.open_form("card"), "법인카드 사용 내역 — 사용일시 오늘, 사용자 부서·직위·성명 자동", {"dot": "#4d9193"}),
            ("시간외근로 ▸", self.dlg_overtime, "시간외 근로 현황 — 하루·여러 날 모두, 사람별 시간을 넣으면 표를 채우고 하루짜리는 합계(1h) 계산", {"raw": True, "dot": "#e5484d"}),
            ("수료증 ▸", self.dlg_cert, "명단을 넣으면 사람 수만큼 수료증을 채워 한 파일로", {"raw": True, "dot": "#e8833a"}),
        ], cols=3, height=2)
        self.group(t, "보고서", [
            ("보고서 만들기 ▸", self.dlg_report, "양식 1(본문) 또는 양식 2(표지 + 요약 + 본문) — 제목·큰 제목만 적으면 보고서 틀을 한 번에", {"raw": True, "bg": "#e8edf8", "font": FONT_B}),
            ("제목 상자", h.title_box, "줄에 제목을 써 두고 누르면 그 글로 제목 상자 (HY헤드라인M 24pt)"),
            ("요지", h.summary_line, "줄에 요지를 써 두고 누르면 ❖ 요지 줄로 (중고딕 15pt, 가운데)"),
            ("큰 제목", h.big_title, "줄에 제목을 써 두고 누르면 남색 칸 Ⅰ·Ⅱ·Ⅲ 큰 제목으로 (번호 자동)"),
        ])
        self.group(t, "간부회의 자료", [
            ("[ 구분 ]", lambda: h.do_meeting("sec"), "줄에 사업계획·사업실적 등을 써 두고 누르면 [ 사업계획 ] 초록 제목 (맑은 고딕 16 굵게)", {"fg": "#008000"}),
            ("□ 사업", lambda: h.do_meeting("□"), "사업명 줄 — 검정 □ (맑은 고딕 16 굵게)"),
            ("○ 항목", lambda: h.do_meeting("○"), "항목 줄 — 파란 ○, 줄 전체 파랑 (맑은 고딕 15 굵게)", {"fg": "#0000ff"}),
            ("보도", h.do_press_tag, "누르면 커서 자리에 보라색 '보도' 글상자가 들어감", {"fg": "#7030a0", "font": FONT_B}),
            ("- 세부", lambda: h.do_meeting("-"), "세부 줄 — 검정 - (맑은 고딕 15)"),
            ("· 내용", lambda: h.do_meeting("·"), "내용 줄 — 검정 · (맑은 고딕 15)"),
            ("▶ 추진사항", lambda: h.do_meeting("▶"), "추진사항 줄 — 빨간 ▶ 추진사항 : (맑은 고딕 14). 내용만 써 두고 눌러도 됨", {"fg": "#ff0000"}),
        ], cols=4)
        self.group(t, "예산", [
            ("예산코드 찾기 ▸", self.dlg_budget, "예산과목·코드 찾기 (과목명·코드·부서로 검색, 커서 자리에 넣기·복사)", {"raw": True}),
        ], cols=4)
        mf = tk.LabelFrame(t, text=" 내 서식 (부서 양식 등록 → 다음부터 바로 열기) ", font=FONT_B, fg=NAVY, bg=BG, padx=4, pady=2)
        mf.pack(fill="x", pady=2)
        bar = tk.Frame(mf, bg=BG)
        bar.pack(fill="x")
        for lab, cmd, tip, opt in (
                ("서식 불러오기 ▸", self.dlg_register, "내 PC의 부서 양식(.hwp)을 골라 등록 — 이름·날짜 자리를 한 번 정해 두면 다음부터 자동 입력", {"bg": "#e8edf8", "font": FONT_B}),
                ("정리 ▸", self.dlg_myforms, "등록한 서식 이름 바꾸기·자리 다시 정하기·지우기", {}),
                ("기본 서식으로", self.reset_format, "기호 버튼을 보고서 공통 서식으로 되돌림", {})):
            b = tk.Button(bar, text=lab, command=cmd, relief="groove", bg=opt.get("bg", "white"), font=opt.get("font", FONT))
            b.pack(side="left", padx=1, pady=1)
            b.bind("<Enter>", lambda e, t_=tip, l=lab: self.tip.config(text="{} : {}".format(l, t_)), add="+")
            b.bind("<Leave>", self._tip_reset, add="+")
        self.mf_list = tk.Frame(mf, bg=BG)
        self.mf_list.pack(fill="x")
        self.fmt_hint = tk.Label(mf, text="", font=FONT_S, bg=BG, fg=MUTED, anchor="w", justify="left", wraplength=440)
        self.fmt_hint.pack(fill="x", padx=2)

        # ===== 글자 =====
        t = self.tab("글자")
        self.group(t, "되돌리기·화면", [
            ("↶↶ 5번", lambda: h.do_undo(5), "다섯 번 되돌리기"),
            ("↶ 되돌리기", lambda: h.do_undo(1), "한 번 되돌리기"),
            ("↷ 다시", lambda: h.do_redo(1), "한 번 다시 실행"),
            ("↷↷ 5번", lambda: h.do_redo(5), "다섯 번 다시 실행"),
            ("화면 분할", lambda: h.do_split_view(True), "화면을 좌우로 나눠 같은 문서 두 곳 보기"),
            ("화면 기본", lambda: h.do_split_view(False), "화면 나누기 풀기"),
        ], cols=6)
        self.group(t, "기본", [
            ("기본 정리", h.do_base, "선택한 부분을 휴먼명조 15pt, 줄간격 160%, 자간 0, 꾸밈 없음으로"),
            ("모양 복사", h.do_shape_copy, "커서 위치 글자·문단 모양을 복사 → 다른 곳에서 다시 누르면 붙임"),
            ("고급 붙임", lambda: h.run("PasteSpecial"), "골라 붙이기 (서식 없이 붙이기 등)"),
            ("특수문자 ▸", self.dlg_special, "특수문자 80개와 괄호 감싸기", {"raw": True}),
        ])
        self.group(t, "개조식 기호 (불러온 서식, 없으면 보고서 공통 서식)", [
            ("□", lambda: h.do_bullet("□"), "휴먼명조 16pt 굵게, 180%"),
            ("○", lambda: h.do_bullet("○"), "휴먼명조 15pt, 160%, 1칸 들여"),
            ("-", lambda: h.do_bullet("-"), "휴먼명조 15pt, 160%, 2칸 들여"),
            ("·", lambda: h.do_bullet("·"), "휴먼명조 15pt, 160%, 3칸 들여"),
            ("※", lambda: h.do_bullet("※"), "중고딕 12pt, 130%"),
            ("*", lambda: h.do_bullet("*"), "중고딕 12pt, 130%"),
        ], cols=6)
        self.set_extra = tk.Frame(t, bg=SHELL)
        self.set_extra.pack(fill="x")
        self.group(t, "항목 번호 (선택하면 다시 매기기)", [
            (lab, (lambda lv=lv: h.do_level(lv)), "{}단계 · {} (기호 앞 {}칸)".format(
                lv + 1, "휴먼명조 16pt 굵게, 180%" if lv == 0 else "휴먼명조 15pt, 160%", lv))
            for lv, lab in enumerate(["1.", "가.", "1)", "가)", "(1)", "(가)", "①", "㉮"])
        ], cols=8)
        self.group(t, "항목 자동 입력", [
            ("다음 항목", lambda: h.do_item("next"), "위쪽 기호를 보고 같은 단계 다음 번호"),
            ("한 단계 아래", lambda: h.do_item("down"), "하위 단계 첫 번호"),
            ("한 단계 위", lambda: h.do_item("up"), "상위 단계 다음 번호"),
        ], cols=3)
        self.group(t, "기호 다루기", [
            ("기호 복사", lambda: h.do_lead("copy"), "선택한 줄들의 맨 앞 기호를 기억"),
            ("기호 붙임", lambda: h.do_lead("paste"), "기억한 기호를 선택한 줄들에 붙임"),
            ("기호 삭제", lambda: h.do_lead("del"), "선택한 줄들의 맨 앞 기호 지우기"),
            ("①② 번호", h.do_circled, "선택한 줄 앞에 ①②③ 차례로"),
        ])
        self.group(t, "들여쓰기·자간", [
            ("기본쓰기", lambda: h.do_jagan("base"), "내어쓰기 해제"),
            ("내어쓰기", lambda: h.run("ParagraphShapeIndentAtCaret"), "커서 위치 기준 둘째 줄부터 맞춤 (Shift+Tab)"),
            ("자간헌터", lambda: h.do_jagan("hunter"), "줄 끝 한두 글자가 넘어가지 않게"),
            ("더블헌터", lambda: h.do_jagan("double"), "자간헌터 + 자간 -10%"),
            ("자간+", lambda: h.run("CharShapeSpacingIncrease"), "자간 넓게"),
            ("자간−", lambda: h.run("CharShapeSpacingDecrease"), "자간 좁게"),
        ], cols=6)
        self.group(t, "크기·색", [
            ("글자−", lambda: h.run("CharShapeHeightDecrease"), "1pt 작게"),
            ("글자+", lambda: h.run("CharShapeHeightIncrease"), "1pt 크게"),
            ("검정", lambda: h.char_shape(color=(0, 0, 0)), "글자색"),
            ("빨강", lambda: h.char_shape(color=(255, 0, 0)), "글자색", {"fg": "#d00000"}),
            ("파랑", lambda: h.char_shape(color=(0, 0, 255)), "글자색", {"fg": "#0000d0"}),
            ("초록", lambda: h.char_shape(color=(0, 150, 0)), "글자색", {"fg": "#009600"}),
            ("하양", lambda: h.char_shape(color=(255, 255, 255)), "글자색", {"bg": "#666", "fg": "white"}),
            ("위첨자 *", lambda: h.do_super("*"), "각주용 * 위첨자"),
            ("위첨자 **", lambda: h.do_super("**"), "각주용 ** 위첨자"),
        ], cols=5)
        self.group(t, "글꼴·크기", [
            ("휴먼명조", lambda: h.char_shape(face="휴먼명조"), "글꼴"),
            ("중고딕", lambda: h.char_shape(face="중고딕"), "글꼴"),
            ("맑은 고딕", lambda: h.char_shape(face="맑은 고딕"), "글꼴"),
            ("HY헤드라인M", lambda: h.char_shape(face="HY헤드라인M"), "글꼴", {"font": FONT_S}),
        ] + [("{}pt".format(s), (lambda s=s: h.char_shape(size=s)), "글자 크기") for s in (12, 13, 15, 16, 18, 24)],
            cols=5)

        # ===== 표 =====
        t = self.tab("표")
        self.group(t, "인천상의 표", [
            ("표 만들기 ▸", self.dlg_table, "머리줄 연파랑, 좌우 바깥선 없음, 위·아래 굵게, 맑은 고딕 12pt", {"raw": True}),
            ("표 색 입히기", h.style_incham_table, "커서가 있는 표를 인천상의 표 모양으로"),
            ("테두리 ▸", self.dlg_border, "위·아래·왼쪽·오른쪽 선 하나씩", {"raw": True}),
            ("배경색 ▸", self.dlg_shade, "선택한 셀 배경색 + 글자색", {"raw": True}),
        ])
        self.group(t, "표 모양 (표 전체)", [
            ("얇은 선", lambda: h.table_look("thin"), "모든 선 얇은 검정"),
            ("겉 굵게", lambda: h.table_look("outer_thick"), "바깥선 굵게, 안쪽 얇게"),
            ("투명", lambda: h.table_look("none"), "선 모두 없애기"),
            ("위아래만", lambda: h.table_look("topbottom"), "위·아래 굵은 선만"),
            ("점선", lambda: h.table_look("dot"), "바깥선 점선"),
            ("엑셀표 정리", lambda: h.table_look("excel"), "엑셀에서 붙인 표의 꾸밈 지우고 기본 선"),
            ("3D", lambda: h.table_look("3d"), "위·아래 얇게, 좌우 굵게"),
            ("겉 검정", lambda: h.table_look("black"), "바깥선 굵은 검정"),
            ("겉 파랑", lambda: h.table_look("blue"), "바깥선 굵은 파랑"),
            ("겉 빨강", lambda: h.table_look("red"), "바깥선 굵은 빨강"),
        ], cols=5)
        self.group(t, "행·열", [
            ("아래 행+", lambda: h.run("TableInsertLowerRow"), "아래에 행 추가"),
            ("행 삭제", lambda: h.run("TableDeleteRow"), "행 삭제"),
            ("왼쪽 열+", lambda: h.run("TableInsertLeftColumn"), "왼쪽에 열 추가"),
            ("오른쪽 열+", lambda: h.run("TableInsertRightColumn"), "오른쪽에 열 추가"),
            ("열 삭제", lambda: h.run("TableDeleteColumn"), "열 삭제"),
        ], cols=5)
        self.group(t, "셀", [
            ("나누기", h.split_cell, "선택한 셀을 둘로"),
            ("합치기", lambda: h.run("TableMergeCell"), "선택한 셀 합치기"),
            ("굵게 합치기", h.merge_thick, "합치고 바깥선 굵게"),
            ("너비 같게", lambda: h.run("TableDistributeCellWidth"), "선택한 셀 너비 똑같이"),
            ("높이 같게", lambda: h.run("TableDistributeCellHeight"), "선택한 셀 높이 똑같이"),
            ("크기 복사", h.cell_size_copy, "커서 셀의 높이·너비 기억"),
            ("높이 붙이기", lambda: h.cell_size_paste("height"), "기억한 높이를 선택한 셀에"),
            ("너비 붙이기", lambda: h.cell_size_paste("width"), "기억한 너비를 선택한 셀에"),
            ("여백 0", h.cell_margin_zero, "셀 안쪽 여백 없애기"),
            ("보호 해제", h.cell_unprotect, "표 전체 셀 보호 풀기"),
        ], cols=5)
        self.group(t, "셀 정렬", [
            ("위", lambda: h.cell_valign("top"), "세로 위"),
            ("가운데", lambda: h.cell_valign("mid"), "세로 가운데"),
            ("아래", lambda: h.cell_valign("bot"), "세로 아래"),
            ("한 줄로", lambda: h.cell_one_line(True), "글이 길어도 한 줄로"),
            ("한 줄 해제", lambda: h.cell_one_line(False), "한 줄로 풀기"),
        ], cols=5)
        self.group(t, "계산·단위", [
            ("합계", lambda: h.run("TableFormulaSumAuto"), "자동 합계 계산식"),
            ("곱", lambda: h.run("TableFormulaProAuto"), "자동 곱 계산식"),
            ("평균", lambda: h.run("TableFormulaAvgAuto"), "자동 평균 계산식"),
            ("자동 채우기", lambda: h.run("TableAutoFill"), "1, 2, 3… 규칙대로 채우기"),
            ("가로 합", lambda: h.run("TableFormulaSumHor"), "가로 합계"),
            ("세로 합", lambda: h.run("TableFormulaSumVer"), "세로 합계"),
            ("퍼센트", h.cells_percent, "선택한 셀 값마다 비율 (25%) 덧붙이기"),
            ("번호 매기기", h.cells_number, "선택한 셀에 1, 2, 3…"),
            ("대량 계산 ▸", self.dlg_mass, "선택한 셀에 같은 값을 한꺼번에 + − × ÷", {"raw": True}),
            ("원", lambda: h.transform(lambda s: logic.unit_convert(s, "원"), per_line=False), "콤마 붙인 원 단위로"),
            ("천원", lambda: h.transform(lambda s: logic.unit_convert(s, "천원"), per_line=False), "÷1,000"),
            ("백만원", lambda: h.transform(lambda s: logic.unit_convert(s, "백만원"), per_line=False), "÷1,000,000"),
            ("억원", lambda: h.transform(lambda s: logic.unit_convert(s, "억원"), per_line=False), "÷100,000,000"),
            ("(단위:원)", lambda: h.caption("(단위:원)"), "표 위 오른쪽에 단위 표시"),
            ("기준일", lambda: h.caption("({} 기준)".format(logic.today_text())), "표 위 오른쪽에 기준일"),
            ("표시 지우기", lambda: h.run("ShapeObjDetachCaption"), "표 위 표시 지우기"),
        ], cols=5)
        self.group(t, "내용·변환", [
            ("괄호 지우기", lambda: h.transform(logic.remove_paren), "괄호와 괄호 속 글 지우기"),
            ("괄호 안만", lambda: h.transform(logic.paren_inside), "괄호 속 글만 남기기"),
            ("숫자만", lambda: h.transform(logic.numbers_only), "숫자 말고 다 지우기"),
            ("섞기", h.cells_shuffle, "선택한 셀 순서 무작위로"),
            ("정렬 ▸", self.dlg_sort, "선택한 셀 가나다순·숫자순", {"raw": True}),
            ("표→글", h.table_to_text, "표를 '항목 : 내용' 글로"),
            ("글→표", h.text_to_table, "탭으로 나뉜 글을 표로"),
            ("행·열 뒤집기", h.table_swap, "가로줄과 세로칸 맞바꿈"),
            ("글자처럼", h.table_as_char, "표를 글자처럼 취급 (위치 고정)"),
            ("사진(배경)", lambda: self.pick_pictures(True), "셀 배경으로 사진", {"raw": True}),
            ("사진(비율)", lambda: self.pick_pictures(False), "셀에 비율 맞춰 사진", {"raw": True}),
        ], cols=5)

        # ===== 정리 =====
        t = self.tab("정리")
        self.group(t, "줄 정리 (글이나 셀을 선택한 뒤)", [
            ("빈 줄 지우기", lambda: h.transform(logic.clean_enters, per_line=False), "빈 줄 모두 지우기"),
            ("띄어쓰기 정리", lambda: h.transform(logic.clean_spaces, per_line=False), "겹친 띄어쓰기를 한 칸으로"),
            ("맨앞 글자", lambda: h.transform(logic.cut_first_char), "줄마다 맨 앞 한 글자 지우기"),
            ("맨앞 단어", lambda: h.transform(logic.cut_first_word), "줄마다 첫 단어 지우기"),
            ("맨뒤 글자", lambda: h.transform(logic.cut_last_char), "줄마다 맨 뒤 한 글자 지우기"),
            ("맨뒤 단어", lambda: h.transform(logic.cut_last_word), "줄마다 마지막 단어 지우기"),
            ("앞뒤 붙이기 ▸", self.dlg_around, "줄(셀)마다 앞·뒤에 글자 붙이기·지우기", {"raw": True}),
            ("바꾸기 ▸", self.dlg_replace, "선택 범위 안에서만 3쌍까지 바꾸기", {"raw": True}),
        ])
        self.group(t, "정렬", [
            ("가나다순", lambda: h.do_sort_lines("asc"), "선택한 줄 가나다순"),
            ("역순", lambda: h.do_sort_lines("desc"), "선택한 줄 역순"),
            ("짧은 순", lambda: h.do_sort_lines("short"), "글자 수 짧은 순"),
        ], cols=3)
        self.group(t, "숫자·금액", [
            ("금액 한글화", lambda: h.transform(logic.amount_text, per_line=False), "1000000 → 금1,000,000원(금일백만원)"),
            ("콤마 넣기", lambda: h.transform(logic.add_commas, per_line=False), "천 단위 콤마"),
            ("콤마 빼기", lambda: h.transform(logic.remove_commas, per_line=False), "콤마 없애기"),
            ("계산", h.do_calc, "선택한 식을 계산 (더하기·곱하기 한글도 됨)"),
            ("금액 비율 ▸", self.dlg_ratio, "금액 여러 개의 비율(%)", {"raw": True}),
        ], cols=5)
        self.group(t, "주민번호·전화·나이·기간", [
            ("주민→생년월일", lambda: h.transform(logic.rrn_to_birth, per_line=False), "970929-1… → 1997. 9. 29.", {"font": FONT_S}),
            ("주민 가리기", lambda: h.transform(logic.rrn_mask, per_line=False), "970929-1******"),
            ("전화번호 정리", self.phone_tidy, "01012345678 → 010-1234-5678 (블록을 잡으면 그 안, 없으면 문서 전체 · 표 안 포함)"),
            ("나이", lambda: h.transform(lambda s: "{} ({})".format(s.strip(), logic.age_of(s)), per_line=False), "만 나이 덧붙이기"),
            ("개월", lambda: h.transform(lambda s: "{} ({})".format(s.strip(), logic.months_between(s)), per_line=False), "기간의 개월 수 덧붙이기"),
        ], cols=5)
        self.group(t, "형광펜", [
            ("노랑", lambda: h.do_markpen((255, 215, 0)), "형광펜", {"bg": "#ffe680"}),
            ("주황", lambda: h.do_markpen((255, 132, 58)), "형광펜", {"bg": "#ffc29a"}),
            ("초록", lambda: h.do_markpen((105, 216, 173)), "형광펜", {"bg": "#b4ecd6"}),
            ("지우기", lambda: h.do_markpen(None), "형광펜 지우기"),
        ])
        self.group(t, "변환", [
            ("마크다운→한글", h.do_markdown, "ChatGPT·Claude 글을 보고서 서식으로"),
            ("마크다운 설명", lambda: messagebox.showinfo("마크다운 → 한글", MARKDOWN_HELP, parent=self.root), "사용법", {"raw": True}),
            ("빈 줄 좁히기", h.do_small_line, "선택한 빈 줄을 3pt로"),
        ], cols=3)
        self.group(t, "날짜", [
            ("오늘 날짜", lambda: h.do_insert_text(logic.today_text()), "2026. 10. 30."),
            ("오늘(요일)", lambda: h.do_insert_text(logic.date_fmt(datetime.date.today(), "dotw")), "2026. 10. 30.(금)"),
            ("날짜 넣기 ▸", self.dlg_date_insert, "오늘·내일·어제·기간·지금 시각", {"raw": True}),
            ("날짜 바꾸기 ▸", self.dlg_date_convert, "선택한 날짜 형식 바꾸기 (글·셀)", {"raw": True}),
            ("날짜 계산기 ▸", self.dlg_date_calc, "두 날짜 사이 일수, ○일 뒤 날짜", {"raw": True}),
        ], cols=5)

        # ===== 이동 =====
        t = self.tab("이동")
        self.group(t, "페이지", [
            ("처음", lambda: h.go("top"), "문서 처음"),
            ("끝", lambda: h.go("end"), "문서 끝"),
            ("위", lambda: h.go("up"), "한 쪽 위"),
            ("아래", lambda: h.go("down"), "한 쪽 아래"),
            ("위 5쪽", lambda: h.go("up5"), "다섯 쪽 위"),
            ("아래 5쪽", lambda: h.go("down5"), "다섯 쪽 아래"),
        ], cols=6)
        self.group(t, "찾아가기", [
            ("빨간 글자 ↓", lambda: h.find_color((255, 0, 0), True), "다음 빨간 글자", {"fg": "#d00000"}),
            ("빨간 글자 ↑", lambda: h.find_color((255, 0, 0), False), "이전 빨간 글자", {"fg": "#d00000"}),
            ("파란 글자 ↓", lambda: h.find_color((0, 0, 255), True), "다음 파란 글자", {"fg": "#0000d0"}),
            ("파란 글자 ↑", lambda: h.find_color((0, 0, 255), False), "이전 파란 글자", {"fg": "#0000d0"}),
            ("검정 글자 ↑", lambda: h.find_color((0, 0, 0), False), "이전 검정 글자"),
            ("→ 빨강", lambda: h.char_shape(color=(255, 0, 0)), "찾은 글자를 빨강으로", {"fg": "#d00000"}),
            ("→ 파랑", lambda: h.char_shape(color=(0, 0, 255)), "찾은 글자를 파랑으로", {"fg": "#0000d0"}),
            ("→ 검정", lambda: h.char_shape(color=(0, 0, 0)), "찾은 글자를 검정으로"),
            ("숫자 ↓", lambda: h.find_regex("[0-9]+", True), "다음 숫자"),
            ("숫자 ↑", lambda: h.find_regex("[0-9]+", False), "이전 숫자"),
            ("날짜 ↓", lambda: h.find_regex(r"[0-9]+\.\s*[0-9]+\.\s*[0-9]+\.", True), "다음 날짜"),
            ("날짜 ↑", lambda: h.find_regex(r"[0-9]+\.\s*[0-9]+\.\s*[0-9]+\.", False), "이전 날짜"),
        ])
        self.group(t, "쪽번호", [
            ("쪽번호 넣기", h.page_number, "아래 가운데 (문서규칙 제18조)"),
            ("쪽번호 지우기", h.page_number_clear, "넣은 쪽번호 모두 지우기"),
            ("이 쪽 숨기기", lambda: h.page_hide(True), "이 쪽만 쪽번호 감추기 (표지 등)"),
            ("이 쪽 보이기", lambda: h.page_hide(False), "다시 보이기"),
            ("1부터 새로", lambda: h.page_new_number(1), "이 쪽부터 1로 (별첨 따로 매길 때)"),
            ("이어서 ▸", self.dlg_page_number, "정한 번호부터 이어서", {"raw": True}),
        ], cols=3)

        # ===== 편리 =====
        t = self.tab("편리")
        self.group(t, "문서 만들기", [
            ("메일머지 ▸", self.dlg_mailmerge, "필드1~20 자리를 심어 명단으로 여러 장 만들기", {"raw": True}),
            ("목차 만들기 ▸", self.dlg_toc, "정한 크기 이상인 제목 줄로 목차", {"raw": True}),
            ("참석자 명단", h.do_roster_table, "연번·소속·직위·성명·비고 표 (인천상의 표 모양)"),
        ], cols=3)
        self.group(t, "다듬기", [
            ("공문 언어 순화 ▸", self.dlg_purify, "행정 용어를 찾아 쉬운 말로 바꾸기", {"raw": True}),
            ("문단 스타일 지우기", h.clear_para_styles, "문서 전체 문단 스타일을 바탕글로", {"font": FONT_S}),
            ("메모 ▸", self.dlg_memo, "메모 넣기·보기·지우기", {"raw": True}),
        ], cols=3)
        self.group(t, "저장·기타", [
            ("용량 줄여 저장", h.save_small, "그림 용량 줄여서 저장 (메일 첨부용)"),
            ("맨 위에 쪽 추가", h.add_page_top, "문서 맨 앞에 빈 쪽 추가"),
            ("업데이트 확인", lambda: self.check_update(manual=True), "새 버전이 있는지 확인하고 받기 (지금 버전 {})".format(VERSION), {"raw": True}),
        ], cols=3)

        # ===== 인천광역시 =====
        t = self.tab("인천광역시")
        tk.Label(t, text="인천광역시 보고서 품질향상 매뉴얼 양식 그대로 (인천시에 내는 문서용)", font=FONT_S,
                 bg=SHELL, fg=MUTED).pack(anchor="w", padx=2, pady=(0, 4))
        self.group(t, "보고서 틀", [
            ("표준", lambda: h.icn_frame("standard"), "표지 + 1. 추진배경 ~ 5. 행정사항 + 참고자료"),
            ("정책", lambda: h.icn_frame("policy"), "사업개요 / 쟁점 / 문제점 분석 / 대책 및 추진계획"),
            ("상황", lambda: h.icn_frame("status"), "사업개요 / 현황(추진경과)"),
            ("검토", lambda: h.icn_frame("review"), "사업개요 / 추진배경 / 검토내용(1안·2안) / 향후계획"),
            ("회의개최", lambda: h.icn_frame("meet_plan"), "회의개요 / 안건 / 진행순서 표 / 행정사항 / 붙임"),
            ("회의결과", lambda: h.icn_frame("meet_result"), "회의개요 / 회의결과 / 향후계획 / 붙임 회의록"),
            ("행사", lambda: h.icn_frame("event"), "행사목적 / 행사개요 / 행사내용 / 진행순서 표"),
        ])
        self.group(t, "양식 열기", [
            ("업무보고", lambda: self.open_icn("icn_report.hwp", "인천시_업무보고"), "인천시 업무보고 양식"),
            ("업무보고2", lambda: self.open_icn("icn_report2.hwp", "인천시_업무보고2"), "인천시 업무보고 양식 2"),
            ("업무보고 제목", lambda: self.open_icn("icn_report_title.hwp", "인천시_업무보고제목"), "업무보고 제목 양식", {"font": FONT_S}),
            ("종합보고", lambda: self.open_icn("icn_total.hwp", "인천시_종합보고"), "종합보고 양식"),
            ("참석명단", lambda: self.open_icn("icn_roster.hwp", "인천시_참석명단"), "참석명단 양식"),
        ])
        self.group(t, "부품", [
            ("보고서 제목", h.icn_title, "연한 바다색 제목 상자, HY헤드라인M 24pt"),
            ("대제목", h.icn_big_title, "표지용 큰 제목 (HY헤드라인M 32pt)"),
            ("요지", h.icn_summary, "◇ 요지 상자"),
            ("점선 박스", h.icn_dot_box, "보고 목적 점선 상자 (중고딕 15pt)"),
            ("참고", h.icn_ref, "참고 1 + 참고자료"),
            ("진행순서 표", h.icn_order_table, "시간 · 내용 · 비고"),
        ])
        self.group(t, "기호", [
            ("□ 업무보고", lambda: h.icn_bullet("box"), "HY헤드라인M 16pt, 180%"),
            ("요지 □", lambda: h.icn_bullet("y_box"), "요지용 □"),
            ("요지 ○", lambda: h.icn_bullet("y_circle"), "요지용 ○"),
            ("요지 -", lambda: h.icn_bullet("y_bar"), "요지용 -"),
            ("18pt 점", lambda: h.icn_bullet("dot18"), "휴먼명조 18pt 굵게 '. '"),
        ], cols=5)

    # ---------------- 내 정보 ----------------
    PROFILE_FIELDS = [("dept", "소속", "경제진흥실", 12), ("title", "직위", "주임", 7), ("name", "이름", "", 7),
                      ("phone", "전화", "032-810-", 13), ("email", "이메일", "@incham.net", 16)]  # 전화는 숫자만, 이메일은 아이디만 써도 됨

    def build_profile(self, root):
        f = tk.LabelFrame(root, text=" 내 정보  ·  양식을 열 때 담당자·연락처 자리에 자동으로 들어감 ", font=FONT_S,
                          fg=NAVY, bg=BG, padx=8, pady=6)
        f.pack(fill="x", padx=10, pady=(10, 0))
        data = styles.load_profile()
        self.pf = {}
        pos = {"dept": (0, 0), "title": (0, 2), "name": (0, 4), "phone": (1, 0), "email": (1, 2)}
        for key, lab, hint, width in self.PROFILE_FIELDS:
            r, c = pos[key]
            tk.Label(f, text=lab, font=FONT_S, bg=BG, fg=MUTED).grid(row=r, column=c, sticky="e", padx=(6, 3))
            if key == "dept":  # 소속은 목록에서 고르기
                e = ttk.Combobox(f, values=logic.DEPTS, state="readonly", font=FONT, width=16)
                if data.get(key) in logic.DEPTS:
                    e.set(data[key])
                e.bind("<<ComboboxSelected>>", lambda ev: self.save_profile())
            else:
                e = tk.Entry(f, font=FONT, width=width, relief="solid", bd=1)
                e.insert(0, data.get(key, ""))
                e.bind("<FocusOut>", lambda ev: self.save_profile())
                e.bind("<Return>", lambda ev: self.save_profile())
            e.grid(row=r, column=c + 1, columnspan=2 if key == "email" else 1, sticky="we" if key == "email" else "w",
                   pady=2, ipady=2)
            self.pf[key] = e
        self.tidy_profile()  # 예전에 저장한 값도 같은 규칙으로
        self.remember = tk.BooleanVar(value=bool(data.get("remember", False)))
        tk.Checkbutton(f, text="기억하기", variable=self.remember, bg=BG, font=FONT_S,
                       command=self.save_profile).grid(row=1, column=5, sticky="w", padx=(8, 0))

    def profile_values(self):
        return {k: e.get().strip() for k, e in self.pf.items()}

    def tidy_profile(self):
        """전화는 하이픈, 이메일은 @incham.net을 칸에서 바로 맞춤"""
        for key, fn in (("phone", logic.fmt_phone), ("email", logic.fmt_email)):
            e = self.pf.get(key)
            if e is None:
                continue
            v = e.get()
            nv = fn(v)
            if nv != v:
                e.delete(0, "end")
                e.insert(0, nv)

    def save_profile(self):
        self.tidy_profile()
        try:
            self.hello.config(text=greeting(self.profile_values()))
        except Exception:
            pass
        if self.remember.get():
            d = self.profile_values()
            d["remember"] = True
            styles.save_profile(d)
        else:
            styles.save_profile({})

    # ---------------- 서식 불러오기 ----------------
    def refresh_sets(self):
        """불러온 서식 안내 + 세트에만 있는 기호 버튼 (글자 탭)"""
        cur = self.store.get("current")
        if self.hwp.active:
            keys = [k for k in styles.KEY_ORDER if k in self.hwp.active]
            self.fmt_hint.config(text="기호 버튼이 지금 '{}' 서식으로 들어갑니다: {}".format(cur, " ".join(keys)), fg="#1a5fb4")
        else:
            self.fmt_hint.config(text="기호 버튼이 보고서 공통 서식으로 들어갑니다. 등록한 서식을 열면 그 서식으로 바뀝니다.",
                                 fg=MUTED)
        for w in self.set_extra.winfo_children():
            w.destroy()
        extra = [k for k in styles.KEY_ORDER if k in self.hwp.active and k not in ("□", "○", "-", "·", "※", "*")]
        if extra:
            items = [(k, (lambda k=k: self.hwp.do_bullet(k)),
                      "불러온 서식: " + styles.describe(self.hwp.active[k])) for k in extra]
            self.group(self.set_extra, "불러온 양식에만 있는 기호", items, cols=min(8, max(4, len(items))))

    # ---------------- 내 서식 ----------------
    def myforms(self):
        return self.store.setdefault("myforms", [])

    def refresh_myforms(self):
        for w in self.mf_list.winfo_children():
            w.destroy()
        items = self.myforms()
        if not items:
            tk.Label(self.mf_list, text="등록한 서식이 없습니다. [서식 불러오기 ▸]로 부서 양식을 등록하세요.",
                     font=FONT_S, bg=BG, fg=MUTED).pack(anchor="w", padx=2)
            return
        fr = tk.Frame(self.mf_list, bg=BG)
        fr.pack(fill="x")
        for i, e in enumerate(items):
            tip = "새 파일로 열고 자리 {}곳 자동 입력 · 기호 버튼도 이 서식으로".format(len(e.get("fields", [])))
            b = tk.Button(fr, text=e["name"], font=FONT, relief="groove", bg="white",
                          command=lambda e=e: self.open_myform(e))
            b.grid(row=i // 3, column=i % 3, padx=1, pady=1, sticky="ew")
            b.bind("<Enter>", lambda ev, t_=tip, l=e["name"]: self.tip.config(text="{} : {}".format(l, t_)), add="+")
            b.bind("<Leave>", self._tip_reset, add="+")
        for c in range(3):
            fr.grid_columnconfigure(c, weight=1, uniform="m")

    def open_myform(self, entry):
        res = self.call(lambda: self.hwp.open_myform(entry, styles.myform_path(entry)), entry["name"])
        if not res:
            return
        dst, done, skipped = res
        self.store["current"] = entry["name"]
        styles.save(self.store)  # 자리를 다시 찾았으면 그 결과도 저장됨
        self.refresh_sets()
        msg = "열었습니다: " + os.path.basename(dst)
        if done:
            msg += " · 자동 입력: " + ", ".join(done)
        if skipped:
            msg += " · 내 정보가 비어 건너뜀: " + ", ".join(skipped)
        self.set_status(msg, ok=not skipped)
        log("내 서식 열기: " + dst)

    def dlg_register(self, entry=None):
        """서식 불러오기(새 등록) 또는 자리 다시 정하기(entry 있음)"""
        import shutil
        import uuid
        new = entry is None
        if new:
            path = filedialog.askopenfilename(parent=self.root, title="등록할 부서 양식 고르기",
                                              filetypes=[("한글 문서", "*.hwp *.hwpx"), ("모든 파일", "*.*")])
            if not path:
                return
            ext = os.path.splitext(path)[1].lower() or ".hwp"
            entry = {"id": uuid.uuid4().hex[:10], "name": os.path.splitext(os.path.basename(path))[0],
                     "fields": [], "styles": {}}
            entry["file"] = entry["id"] + ext
            stored = styles.myform_path(entry)
            shutil.copyfile(path, stored)
        else:
            stored = styles.myform_path(entry)
        found = self.call(lambda: self.hwp.myform_preview(stored), "양식 열기")
        if found is None:
            if new and os.path.exists(stored):
                os.remove(stored)
            return
        fields = [dict(f) for f in entry.get("fields", [])]
        if new:
            fields = [{"find": t, "kind": k} for t, k in found]

        w = self.popup("서식 불러오기" if new else "자리 다시 정하기: " + entry["name"])
        nm = self.entry(w, "서식 이름", 0, entry["name"], 30)
        tk.Label(w, text="다음부터 열 때 자동으로 바꿀 자리 (한글에 열린 양식을 보면서 정하세요)", font=FONT_B, fg=NAVY,
                 bg="white").grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 2))
        tv = ttk.Treeview(w, columns=("find", "kind"), show="headings", height=7)
        tv.heading("find", text="양식의 글자")
        tv.heading("kind", text="바꿔 넣을 정보")
        tv.column("find", width=210)
        tv.column("kind", width=170)
        tv.grid(row=2, column=0, columnspan=4, sticky="ew")

        def fill():
            tv.delete(*tv.get_children())
            for i, f in enumerate(fields):
                tv.insert("", "end", iid=str(i), values=(f["find"], logic.FIELD_LABEL.get(f["kind"], f["kind"])))
        fill()

        tk.Label(w, text="빠진 자리는 한글에서 그 글자를 블록으로 잡고 아래 버튼을 누르세요:", font=FONT_S, fg=MUTED,
                 bg="white").grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        kb = tk.Frame(w, bg="white")
        kb.grid(row=4, column=0, columnspan=4, sticky="w")

        def add(kind):
            t = self.call(self.hwp.selection_for_field, "자리 추가", parent=w)
            if not t:
                return
            for f in fields:
                if f["find"] == t:
                    f["kind"] = kind
                    break
            else:
                fields.append({"find": t, "kind": kind})
            fill()

        for i, (kind, lab) in enumerate(logic.FIELD_KINDS):
            short = {"date_kor": "날짜(년월일)", "head_full": "부서장(○○실장)", "head": "부서장(실장)"}.get(kind, lab.split(" (")[0])
            tk.Button(kb, text=short, font=FONT_S,
                      relief="groove", bg="white", command=lambda k=kind: add(k)).grid(row=i // 4, column=i % 4, padx=1, pady=1, sticky="ew")

        def remove():
            for iid in sorted(tv.selection(), key=int, reverse=True):
                fields.pop(int(iid))
            fill()
        tk.Button(w, text="고른 줄 빼기", font=FONT_S, relief="groove", bg="white", command=remove).grid(
            row=5, column=0, sticky="w", pady=(4, 0))

        def save():
            name = nm.get().strip()
            if not name:
                messagebox.showinfo(TITLE, "서식 이름을 넣어 주세요. 예: 경영지원실 업무보고", parent=w)
                return
            others = [e for e in self.myforms() if e is not entry and e["id"] != entry["id"]]
            if any(e["name"] == name for e in others):
                messagebox.showinfo(TITLE, "같은 이름의 서식이 이미 있습니다. 다른 이름을 넣어 주세요.", parent=w)
                return
            w.config(cursor="watch")
            self.set_status("양식의 기호 서식 읽는 중… (긴 문서는 30초~1분)")
            w.update()
            st = self.call(lambda: self.hwp.read_styles("doc"), "기호 서식 읽기", parent=w) if new or not entry.get("styles") else entry["styles"]
            w.config(cursor="")
            entry["name"] = name
            entry["fields"] = fields
            entry["rules"] = logic.FIELD_RULES
            entry["styles"] = {k: styles.clean_spec(v) for k, v in (st or {}).items()}
            if new:
                self.myforms().append(entry)
            styles.save(self.store)
            self.refresh_myforms()
            self.set_status("'{}' 저장 · 자리 {}곳 · 기호 서식 {}가지".format(name, len(fields), len(entry["styles"])))
            w.destroy()

        def cancel():
            if new and os.path.exists(stored):
                try:
                    os.remove(stored)
                except Exception:
                    pass
            w.destroy()

        bb = tk.Frame(w, bg="white")
        bb.grid(row=6, column=0, columnspan=4, sticky="e", pady=(10, 0))
        tk.Button(bb, text="취소", font=FONT, relief="groove", bg="white", width=8, command=cancel).pack(side="left", padx=4)
        tk.Button(bb, text="저장", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=10, command=save).pack(side="left")
        w.protocol("WM_DELETE_WINDOW", cancel)
        return w

    def dlg_myforms(self):
        w = self.popup("내 서식 정리")
        lb = tk.Listbox(w, font=FONT, width=34, height=8, relief="solid", bd=1)
        lb.grid(row=0, column=0, rowspan=4, sticky="ns")

        def fill():
            lb.delete(0, "end")
            for e in self.myforms():
                lb.insert("end", "{}  (자리 {}곳)".format(e["name"], len(e.get("fields", []))))
        fill()

        def cur():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo(TITLE, "목록에서 서식을 먼저 고르세요.", parent=w)
                return None
            return self.myforms()[sel[0]]

        def rename():
            from tkinter import simpledialog
            e = cur()
            if not e:
                return
            n = simpledialog.askstring(TITLE, "새 이름", initialvalue=e["name"], parent=w)
            if n and n.strip():
                e["name"] = n.strip()
                styles.save(self.store)
                fill()
                self.refresh_myforms()

        def refields():
            e = cur()
            if e:
                w.destroy()
                self.dlg_register(e)

        def delete():
            e = cur()
            if e and messagebox.askyesno(TITLE, "'{}' 서식을 지울까요?".format(e["name"]), parent=w):
                self.myforms().remove(e)
                try:
                    os.remove(styles.myform_path(e))
                except Exception:
                    pass
                if self.store.get("current") == e["name"]:
                    self.reset_format()
                styles.save(self.store)
                fill()
                self.refresh_myforms()

        for i, (lab, fn) in enumerate((("이름 바꾸기", rename), ("자리 다시 정하기", refields), ("지우기", delete))):
            tk.Button(w, text=lab, font=FONT, relief="groove", bg="white", width=14, command=fn).grid(row=i, column=1, padx=(6, 0), pady=1, sticky="n")
        self.close_btn(w, 4, cols=2)

    def reset_format(self):
        self.store["current"] = "기본"
        self.hwp.active = {}
        styles.save(self.store)
        self.refresh_sets()
        self.set_status("보고서 공통 서식으로 돌아왔습니다")

    def dlg_report(self):
        w = self.popup("보고서 만들기")
        form = tk.IntVar(value=1)
        top = tk.Frame(w, bg="white")
        top.grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(top, text="양식", font=FONT_B, fg=NAVY, bg="white").pack(side="left", padx=(0, 6))
        tk.Radiobutton(top, text="양식 1 (본문)", variable=form, value=1, bg="white", font=FONT,
                       command=lambda: show2()).pack(side="left")
        tk.Radiobutton(top, text="양식 2 (표지 + 요약 + 본문)", variable=form, value=2, bg="white", font=FONT,
                       command=lambda: show2()).pack(side="left")
        tk.Label(w, text="적은 칸만 들어갑니다. 비워 두면 그 부분은 빠집니다.", font=FONT_S, fg=MUTED, bg="white").grid(
            row=1, column=0, columnspan=4, sticky="w")
        et = self.entry(w, "제목", 2, "", 40)

        # 양식 2 칸 (표지·요약)
        f2 = tk.LabelFrame(w, text=" 표지 · 요약 ", font=FONT_S, fg=NAVY, bg="white", padx=4, pady=2)
        tk.Label(f2, text="사업기간", font=FONT, bg="white").grid(row=0, column=0, sticky="w")
        ep = tk.Entry(f2, font=FONT, width=18, relief="solid", bd=1)
        ep.grid(row=0, column=1, sticky="w", pady=1)
        tk.Label(f2, text="예: 25. 3. ~ 26. 3.", font=FONT_S, fg=MUTED, bg="white").grid(row=0, column=2, sticky="w", padx=4)
        tk.Label(f2, text="보고서 종류", font=FONT, bg="white").grid(row=1, column=0, sticky="w")
        ek = ttk.Combobox(f2, values=["결과보고서", "계획서", "보고서"], font=FONT, width=16)
        ek.set("결과보고서")
        ek.grid(row=1, column=1, sticky="w", pady=1)
        tk.Label(f2, text="요약 소제목\n(한 줄에 하나)", font=FONT, bg="white", justify="left").grid(row=2, column=0, sticky="nw")
        th = tk.Text(f2, font=FONT, width=30, height=3, relief="solid", bd=1)
        th.grid(row=2, column=1, columnspan=2, sticky="w", pady=1)
        th.insert("1.0", "사업내용\n사업추진결과\n집행금액")

        def show2():
            if form.get() == 2:
                f2.grid(row=3, column=0, columnspan=4, sticky="ew", pady=4)
            else:
                f2.grid_remove()

        es = self.entry(w, "요지 (한 줄)", 4, "", 40)
        tk.Label(w, text="큰 제목\n(한 줄에 하나)", font=FONT, bg="white", anchor="w", justify="left").grid(row=5, column=0, sticky="nw", pady=2)
        tx = tk.Text(w, font=FONT, width=40, height=6, relief="solid", bd=1)
        tx.grid(row=5, column=1, columnspan=3, sticky="w", pady=2)
        tx.insert("1.0", "추진 배경\n추진 내용\n향후 계획")
        presets = [("기본", "추진 배경\n추진 내용\n향후 계획"), ("사업계획", "사업개요\n세부 추진계획\n소요예산(안)"),
                   ("결과보고", "사업개요\n사업실적\n세부사업실적 및 추진결과"), ("회의", "회의 개요\n논의 내용\n향후 조치")]
        pf = tk.Frame(w, bg="white")
        pf.grid(row=6, column=1, columnspan=3, sticky="w")
        tk.Label(pf, text="예시:", font=FONT_S, bg="white", fg=MUTED).pack(side="left")
        for lab, val in presets:
            tk.Button(pf, text=lab, font=FONT_S, relief="groove", bg="white",
                      command=lambda v=val: (tx.delete("1.0", "end"), tx.insert("1.0", v))).pack(side="left", padx=1)
        bv = tk.BooleanVar(value=True)
        tk.Checkbutton(w, text="큰 제목마다 □ ○ - · 자리 넣기", variable=bv, bg="white", font=FONT).grid(row=7, column=1, columnspan=3, sticky="w")
        nv = tk.BooleanVar(value=True)
        tk.Checkbutton(w, text="새 문서로 만들기 (끄면 지금 커서 자리에)", variable=nv, bg="white", font=FONT).grid(row=8, column=1, columnspan=3, sticky="w")

        def lines(widget):
            return [l.strip() for l in widget.get("1.0", "end").splitlines() if l.strip()]

        def go():
            title = et.get().strip() or "보고서 제목"
            if form.get() == 2:
                job = lambda: self.hwp.report_build2(title, ek.get().strip(), ep.get().strip(), lines(th),
                                                     es.get().strip(), lines(tx), bullets=bv.get(), new_doc=nv.get()) or True
            else:
                job = lambda: self.hwp.report_build(title, es.get().strip(), lines(tx),
                                                    bullets=bv.get(), new_doc=nv.get()) or True
            r = self.call(job, "보고서 만들기", parent=w)
            if r:
                w.destroy()
                self.set_status("보고서 틀 완성 · 본문 첫 □ 줄에 바로 쓰시면 됩니다")

        tk.Button(w, text="만들기", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=10,
                  command=go).grid(row=9, column=1, sticky="w", pady=(8, 0))
        self.close_btn(w, 9)
        w.form_var = form  # 점검용
        w.show2 = show2
        et.focus_set()
        return w

    # ---------------- 양식 ----------------
    def open_form(self, kind):
        if kind == "report":
            dst = self.hwp.do_open_report(os.path.join(FORMS, "report.hwp"))
        elif kind == "press":
            dst = self.hwp.do_open_press(os.path.join(FORMS, "press.hwp"))
        elif kind == "travel":
            dst = self.hwp.do_open_travel(os.path.join(FORMS, "travel.hwp"))
        elif kind == "weekly":
            dst = self.hwp.do_open_weekly(os.path.join(FORMS, "weekly.hwp"))
        elif kind == "card":
            dst = self.hwp.do_open_card(os.path.join(FORMS, "card.hwp"))
        else:
            return
        self.set_status("저장 위치: " + os.path.basename(dst))
        log("양식 열기: " + dst)

    def open_icn(self, fname, name):
        dst = self.hwp.do_open_plain(os.path.join(FORMS, fname), name)
        log("양식 열기: " + dst)

    def dlg_overtime(self, rows=6):
        """시간외 근로 현황: 일자(시작·끝)·장소·내용은 함께, 사람마다 이름·직위·시작·끝 시간·합계."""
        w = self.popup("시간외 근로")
        me = self.profile_values() or {}
        today = datetime.date.today()
        tk.Label(w, text="근로 내용 (모두 같음)", font=FONT_B, fg=NAVY, bg="white").grid(
            row=0, column=0, columnspan=6, sticky="w")
        common = {}
        tk.Label(w, text="일자", font=FONT_S, fg=MUTED, bg="white").grid(row=1, column=0, sticky="e", padx=(0, 4))
        common["d1"] = tk.Entry(w, font=FONT, width=13)
        common["d1"].insert(0, "{}. {}. {}.".format(today.year, today.month, today.day))
        common["d1"].grid(row=1, column=1, columnspan=2, sticky="w", pady=2, ipady=2)
        tk.Label(w, text="~ 끝일", font=FONT_S, fg=MUTED, bg="white").grid(row=1, column=3, sticky="e", padx=(4, 4))
        common["d2"] = tk.Entry(w, font=FONT, width=13)
        common["d2"].grid(row=1, column=4, columnspan=2, sticky="w", pady=2, ipady=2)
        tk.Label(w, text="하루면 끝일은 비워 두세요 · 11. 3. / 11/3 / 2026-11-03 모두 됨", font=FONT_S, fg=MUTED,
                 bg="white").grid(row=2, column=1, columnspan=5, sticky="w")
        for r, (key, lab) in enumerate([("place", "장소"), ("what", "내용")], start=3):
            tk.Label(w, text=lab, font=FONT_S, fg=MUTED, bg="white").grid(row=r, column=0, sticky="e", padx=(0, 4))
            e = tk.Entry(w, font=FONT, width=40)
            e.grid(row=r, column=1, columnspan=5, sticky="we", pady=2, ipady=2)
            common[key] = e
        tk.Label(w, text="대상자 (적은 사람만 적은 차례대로) · 시간은 07:00, 7, 0730 모두 됨", font=FONT_B, fg=NAVY,
                 bg="white").grid(row=5, column=0, columnspan=6, sticky="w", pady=(8, 0))
        for c, lab in enumerate(["", "이름", "직위", "시작", "끝", "합계"]):
            tk.Label(w, text=lab, font=FONT_S, fg=MUTED, bg="white").grid(row=6, column=c, sticky="w")
        w.rows = []
        for i in range(rows):
            r = 7 + i
            tk.Label(w, text="{}.".format(i + 1), font=FONT_S, fg=MUTED, bg="white").grid(row=r, column=0, sticky="e")
            ents = [tk.Entry(w, font=FONT, width=w_) for w_ in (10, 9, 7, 7, 6)]
            for c, e in enumerate(ents, start=1):
                e.grid(row=r, column=c, padx=2, pady=1, ipady=2, sticky="w")
            if i == 0:
                ents[0].insert(0, me.get("name", ""))
                ents[1].insert(0, me.get("title", ""))
            w.rows.append(ents)
        tk.Label(w, text="합계: 비우면 하루짜리는 시간에서 계산(1h·2.5h), 여러 날은 직접 적어 주세요(6 → 6h)",
                 font=FONT_S, fg=MUTED, bg="white").grid(row=7 + rows, column=1, columnspan=5, sticky="w")

        def go():
            d1 = logic.parse_day(common["d1"].get())
            d2 = logic.parse_day(common["d2"].get()) if common["d2"].get().strip() else None
            if d1 is None or (common["d2"].get().strip() and d2 is None):
                messagebox.showinfo(TITLE, "일자를 읽지 못했습니다. 예) 2026. 11. 1. 또는 11/1", parent=w)
                return
            if d2 and d2 < d1:
                messagebox.showinfo(TITLE, "끝일이 시작일보다 앞입니다.", parent=w)
                return
            people = [{"name": n.get().strip(), "title": t.get().strip(), "start": a.get().strip(),
                       "end": b.get().strip(), "total": tt.get().strip()}
                      for n, t, a, b, tt in w.rows if n.get().strip()]
            if not people:
                messagebox.showinfo(TITLE, "대상자를 한 명 이상 적어 주세요.", parent=w)
                return
            args = (d1, d2, common["place"].get().strip(), common["what"].get().strip(), people)

            def job():
                dst = self.hwp.do_open_overtime(os.path.join(FORMS, "overtime.hwp"), *args)
                self.set_status("저장 위치: " + os.path.basename(dst))
                log("양식 열기: " + dst)
            w.destroy()
            self.call(job, "시간외근로")
        w.go = go  # 점검용
        w.common = common
        r = 8 + rows
        tk.Button(w, text="열기", font=FONT_B, bg=PRIMARY_BG, width=8, command=go).grid(row=r, column=4, sticky="e", pady=(8, 0))
        tk.Button(w, text="닫기", font=FONT, width=8, command=w.destroy).grid(row=r, column=5, sticky="e", pady=(8, 0))
        common["place"].focus_set()
        return w

    def dlg_travel(self, rows=5):
        """여비계산서: 혼자면 그냥 열기, 함께 간 사람이 있으면 이름·직위를 적고 열기."""
        w = self.popup("여비계산서")
        tk.Label(w, text="출장 간 사람 (혼자면 첫 줄 나만 두고 [열기])", font=FONT_B, fg=NAVY, bg="white").grid(
            row=0, column=0, columnspan=4, sticky="w")
        tk.Label(w, text="적은 사람만, 적은 차례대로 영수인 줄과 <붙임> 표에 들어갑니다. 활동비는 직위로 자동(실장 50,000 … 주임 35,000).",
                 font=FONT_S, fg=MUTED, bg="white").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 4))
        for c, lab in enumerate(["", "이름", "직위", "부서"]):
            tk.Label(w, text=lab, font=FONT_S, bg="white").grid(row=2, column=c, sticky="w")
        me = self.profile_values() or {}
        mydept = me.get("dept", "")
        w.rows = []
        for i in range(rows):
            tk.Label(w, text="{}.".format(i + 1), font=FONT_S, fg=MUTED, bg="white").grid(row=3 + i, column=0, sticky="e")
            en = tk.Entry(w, font=FONT, width=10, relief="solid", bd=1)
            et = tk.Entry(w, font=FONT, width=8, relief="solid", bd=1)
            ed = ttk.Combobox(w, values=logic.DEPTS, font=FONT, width=16)
            ed.set(mydept)
            en.grid(row=3 + i, column=1, padx=2, pady=1)
            et.grid(row=3 + i, column=2, padx=2, pady=1)
            ed.grid(row=3 + i, column=3, padx=2, pady=1)
            if i == 0:                                 # 첫 줄은 나 (지우거나 순서를 바꿔도 됨)
                en.insert(0, me.get("name", ""))
                et.insert(0, me.get("title", ""))
            w.rows.append((en, et, ed))

        def go():
            comp = [{"name": en.get().strip(), "title": et.get().strip(), "dept": ed.get().strip()}
                    for en, et, ed in w.rows if en.get().strip()]

            try:
                days = max(1, int(w.days.get().strip() or "1"))
            except ValueError:
                messagebox.showinfo(TITLE, "출장 일수는 숫자로 적어 주세요.", parent=w)
                return

            def job():
                dst = self.hwp.do_open_travel(os.path.join(FORMS, "travel.hwp"), comp, days)
                self.set_status("저장 위치: " + os.path.basename(dst))
                log("양식 열기: " + dst)
            w.destroy()
            self.call(job, "여비계산서")
        w.go = go  # 점검용
        r = 3 + rows
        dayf = tk.Frame(w, bg="white")
        dayf.grid(row=r, column=1, columnspan=2, sticky="w", pady=(8, 0))
        tk.Label(dayf, text="출장 일수", font=FONT_S, fg=MUTED, bg="white").pack(side="left")
        w.days = tk.Entry(dayf, font=FONT, width=4)
        w.days.insert(0, "1")
        w.days.pack(side="left", padx=4, ipady=2)
        tk.Label(dayf, text="일", font=FONT_S, fg=MUTED, bg="white").pack(side="left")
        r += 1
        tk.Button(w, text="열기", font=FONT_B, relief="groove", bg="#e8edf8", width=8, command=go).grid(
            row=r, column=2, sticky="e", pady=(8, 0))
        self.close_btn(w, r)
        w.rows[0][0].focus_set()
        return w

    def dlg_letter(self):
        w = self.popup("공문 양식 선택")
        tk.Label(w, text="어느 공문 양식을 열까요?", font=FONT_B, fg=NAVY, bg="white").grid(row=0, column=0, columnspan=3, pady=(0, 6))

        def go(lang, fname):
            def job():
                dst = self.hwp.do_open_letter(os.path.join(FORMS, fname), lang)
                log("공문 열기: " + dst)
            self.call(job, "공문 열기", parent=w)
            w.destroy()

        for i, (lab, lang, fn) in enumerate([("국문", "ko", "letter_ko.hwp"), ("영문", "en", "letter_en.hwp"),
                                             ("일문", "ja", "letter_ja.hwp")]):
            tk.Button(w, text=lab, font=("맑은 고딕", 11), width=8, relief="groove", bg="white",
                      command=lambda l=lang, f=fn: go(l, f)).grid(row=1, column=i, padx=3, pady=3, ipady=6)
        self.close_btn(w, 2, cols=3)

    # ---------------- 글자 ----------------
    SYMBOL_GROUPS = [
        ("번호", ["ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ", "①②③④⑤⑥⑦⑧⑨⑩", "❶❷❸❹❺❻❼❽❾❿", "⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽", "㉠㉡㉢㉣㉤㉥㉮㉯㉰㉱㉲㉳"]),
        ("개조식", list("□■▣☑○●◎◇◆❖◈▪∘∙·※＊☞★☆✓✔")),
        ("화살표", list("→←↑↓↔↕↗↘⇒⇐⇔⇨➜➪▶▷▸◀◁▲▼△▽")),
        ("단위", list("㈜㈔’₩%㎞㎏㎥㎖㎡℃㎜㎝")),
        ("비교", list("≒±≥≤×÷∼…●◐○△✕☎")),
    ]

    def dlg_special(self):
        w = self.popup("특수문자")
        h = self.hwp
        cols = 12
        big = ("맑은 고딕", 11)

        def put(c):
            h.insert(c)
            rec = [x for x in self.store.get("recent_symbols", []) if x != c]
            self.store["recent_symbols"] = ([c] + rec)[:cols]
            try:
                styles.save(self.store)
            except Exception:
                pass
            draw_recent()

        def buttons(parent, chars):
            # chars: 글자 목록, 또는 줄마다 한 묶음인 글자열 목록 (번호는 종류별로 한 줄씩)
            rows = chars if chars and len(chars[0]) > 1 else [chars[i:i + cols] for i in range(0, len(chars), cols)]
            for r, line in enumerate(rows):
                for c_i, c in enumerate(line):
                    tk.Button(parent, text=c, font=big, width=3,
                              command=lambda c=c: self.call(lambda: put(c), "기호 " + c, parent=w)).grid(
                        row=r, column=c_i, padx=1, pady=1, sticky="ew")

        head = tk.LabelFrame(w, text=" 최근 쓴 기호 ", font=FONT_B, bg="white")
        head.pack(fill="x", pady=(0, 6))
        recent_box = tk.Frame(head, bg="white")
        recent_box.pack(fill="x")

        def draw_recent():
            for x in recent_box.winfo_children():
                x.destroy()
            rec = self.store.get("recent_symbols", [])
            if rec:
                buttons(recent_box, rec)
            else:
                tk.Label(recent_box, text="기호를 누르면 여기에 모입니다", font=FONT_S, fg=MUTED,
                         bg="white").grid(row=0, column=0, sticky="w", pady=4)
        draw_recent()

        nb = ttk.Notebook(w)                 # 묶음은 탭으로 나눠 한 번에 하나만
        nb.pack(fill="x", pady=(0, 6))
        for title, chars in self.SYMBOL_GROUPS:
            f = tk.Frame(nb, bg="white", padx=4, pady=6)
            buttons(f, chars)
            nb.add(f, text=title)

        def wrap(a, b):
            t = h.selected_text()
            h.insert(a + t + b)
        f = tk.LabelFrame(w, text=" 괄호로 감싸기 (선택한 글 앞뒤) ", font=FONT_B, bg="white")
        f.pack(fill="x", pady=(0, 6))
        for i, (a, b) in enumerate(WRAPS):
            tk.Button(f, text="{}…{}".format(a, b), font=FONT, width=5,
                      command=lambda a=a, b=b: self.call(lambda: wrap(a, b), "괄호 감싸기", parent=w)).grid(
                row=i // 8, column=i % 8, padx=1, pady=1, sticky="ew")
        tk.Button(w, text="닫기", font=FONT, width=8, command=w.destroy).pack(anchor="e")
        return w

    # ---------------- 예산코드 ----------------
    BUDGET_FILE = os.path.join(FORMS, "budget_codes.json")

    def _budget_rows(self):
        if getattr(self, "_budget_cache", None) is None:
            try:
                with open(self.BUDGET_FILE, encoding="utf-8") as f:
                    self._budget_cache = json.load(f)
            except Exception as e:
                messagebox.showinfo(TITLE, "예산코드 파일을 읽지 못했습니다.\n{}".format(e), parent=self.root)
                return None
        return self._budget_cache

    def dlg_budget(self):
        data = self._budget_rows()
        if not data:
            return
        rows = data.get("rows", [])
        w = self.popup("예산코드 ({}년)".format(data.get("year", "")))
        mydept = (self.profile_values() or {}).get("dept", "").strip()

        top = tk.Frame(w, bg="white")
        top.pack(fill="x")
        tk.Label(top, text="찾기", font=FONT_B, bg="white").pack(side="left")
        q = tk.StringVar()
        ent = tk.Entry(top, textvariable=q, font=FONT, width=24)
        ent.pack(side="left", padx=(4, 8))
        tk.Label(top, text="출장 · 373 · 경제진흥실 처럼", font=FONT_S, fg=MUTED, bg="white").pack(side="left")

        flt = tk.Frame(w, bg="white")
        flt.pack(fill="x", pady=(6, 4))
        kind = tk.StringVar(value="지출")
        for v in ("지출", "수입", "전체"):
            tk.Radiobutton(flt, text=v, value=v, variable=kind, font=FONT_S, bg="white",
                           command=lambda: fill()).pack(side="left")
        tk.Label(flt, text="  회계", font=FONT_S, bg="white").pack(side="left")
        acct = ttk.Combobox(flt, values=["전체", "일반회계", "검정회계", "수익회계"], width=8, state="readonly", font=FONT_S)
        acct.set("전체")
        acct.pack(side="left", padx=(2, 8))
        acct.bind("<<ComboboxSelected>>", lambda e: fill())
        mine = tk.BooleanVar(value=bool(mydept))
        tk.Checkbutton(flt, text="우리 부서만" + (" ({})".format(mydept) if mydept else ""), variable=mine,
                       font=FONT_S, bg="white", command=lambda: fill(),
                       state="normal" if mydept else "disabled").pack(side="left")

        cols = (("code", "코드", 48, "center"), ("name", "세부예산단위명", 250, "w"),
                ("mok", "항 · 목", 330, "w"), ("dept", "소관부서", 150, "w"), ("acct", "회계", 46, "center"))
        box = tk.Frame(w, bg="white")
        box.pack(fill="both", expand=True)
        tv = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings", height=16, selectmode="browse")
        for key, lab, wd, an in cols:
            tv.heading(key, text=lab)
            tv.column(key, width=wd, anchor=an, stretch=(key == "name"))
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        count = tk.Label(w, text="", font=FONT_S, fg=MUTED, bg="white", anchor="w")
        count.pack(fill="x", pady=(4, 0))

        shown = {}

        def norm(x):
            return re.sub(r"\s+", "", x or "").lower()

        def fill(*_):
            tv.delete(*tv.get_children())
            shown.clear()
            words = [norm(x) for x in q.get().split() if x.strip()]
            k, a = kind.get(), acct.get()
            for i, r in enumerate(rows):
                if k != "전체" and r["kind"] != k:
                    continue
                if a != "전체" and r["acct"] != a:
                    continue
                if mine.get() and mydept and not r["dept"].startswith(mydept):
                    continue
                hay = norm(" ".join([r["code"], r["name"], r["hang"], r["mok"], r.get("sec", ""), r["dept"], r["acct"], r["kind"]]))
                if any(wd not in hay for wd in words):
                    continue
                iid = tv.insert("", "end", values=(r["code"], r["name"], " · ".join(x for x in (r["hang"], r["mok"], r.get("sec")) if x),
                                                    r["dept"], r["acct"].replace("회계", "")))
                shown[iid] = r
            kids = tv.get_children()
            if kids:
                tv.selection_set(kids[0])
                tv.focus(kids[0])
            count.config(text="{}개".format(len(kids)) + ("" if kids else " — 찾는 말을 줄이거나 '우리 부서만'을 풀어 보세요"))

        def current():
            sel = tv.selection()
            return shown.get(sel[0]) if sel else None

        def put(fmt):
            r = current()
            if not r:
                return
            text = fmt.format(**r)
            res = self.call(lambda: (self.hwp.do_insert_text(text), True)[1], "예산코드 넣기", parent=w)
            if res:
                self.set_status("넣음: " + text)

        def copy():
            r = current()
            if not r:
                return
            w.clipboard_clear()
            w.clipboard_append(r["code"])
            self.set_status("복사함: {} ({})".format(r["code"], r["name"]))

        q.trace_add("write", fill)
        tv.bind("<Double-1>", lambda e: put("{kind}예산_{acct}_{mok}_{name}(Code No. {code})"))
        ent.bind("<Return>", lambda e: put("{kind}예산_{acct}_{mok}_{name}(Code No. {code})"))

        btn = tk.Frame(w, bg="white")
        btn.pack(fill="x", pady=(6, 0))
        tk.Button(btn, text="넣기", font=FONT_B, bg=NAVY, fg="white", relief="flat",
                  command=lambda: put("{kind}예산_{acct}_{mok}_{name}(Code No. {code})")).pack(side="left")
        tk.Button(btn, text="코드만 넣기", font=FONT, command=lambda: put("{code}")).pack(side="left", padx=4)
        tk.Button(btn, text="코드 복사", font=FONT, command=copy).pack(side="left")
        tk.Button(btn, text="닫기", font=FONT, width=8, command=w.destroy).pack(side="right")
        tk.Label(w, text="두 번 누르거나 Enter = 넣기 · 한글 커서 자리에 「지출예산_일반회계_회원지원사업비_공공조달 지원사업(Code No. 021)」처럼 들어갑니다",
                 font=FONT_S, fg=MUTED, bg="white").pack(anchor="w", pady=(4, 0))
        fill()
        ent.focus_set()
        return w

    # ---------------- 표 ----------------
    def dlg_table(self):
        w = self.popup("인천상의 표 만들기")
        tk.Label(w, text="머리줄 연파랑 · 좌우 바깥선 없음 · 위아래 굵게", font=FONT_S, fg=MUTED, bg="white").grid(row=0, column=0, columnspan=4, sticky="w")
        er = self.entry(w, "줄(행) 수", 1, "4", 8)
        ec = self.entry(w, "칸(열) 수", 2, "3", 8)

        def make():
            try:
                r, c = int(er.get()), int(ec.get())
            except ValueError:
                messagebox.showinfo(TITLE, "숫자로 넣어 주세요.", parent=w)
                return
            self.call(lambda: self.hwp.do_incham_table(r, c), "표 만들기", parent=w)
            w.destroy()

        tk.Button(w, text="만들기", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=10,
                  command=make).grid(row=3, column=1, sticky="w", pady=(8, 0))
        self.close_btn(w, 3)

    def dlg_border(self):
        w = self.popup("테두리 (선택한 셀)")
        h = self.hwp
        r = 0
        for side, lab in (("top", "위"), ("bottom", "아래"), ("left", "왼쪽"), ("right", "오른쪽")):
            items = [("{} {}".format(lab, sl), (lambda s=side, st=st: h.border_side(s, st)))
                     for st, sl in (("thin", "얇게"), ("thick", "굵게"), ("none", "없애기"), ("dot", "점선"))]
            r = self.pop_buttons(w, items, cols=4, row=r)
        r = self.pop_buttons(w, [("아래 이중선", lambda: h.border_side("bottom", "double")),
                                 ("상좌우 굵게", h.border_top_lr_thick)], cols=4, row=r, title="그 밖에")
        self.close_btn(w, r)

    def dlg_shade(self):
        w = self.popup("배경색 (선택한 셀)")
        h = self.hwp
        items = []
        for bg, fg, name in SHADES:
            hexbg = "#%02x%02x%02x" % bg
            hexfg = "#%02x%02x%02x" % fg
            items.append((name, (lambda bg=bg, fg=fg: h.fill_with_text(bg, fg)), {"bg": hexbg, "fg": hexfg, "width": 7}))
        items.append(("배경 지우기", lambda: h.cell_fill(None), {"width": 7}))
        r = self.pop_buttons(w, items, cols=5)
        self.close_btn(w, r, cols=5)

    def dlg_mass(self):
        w = self.popup("대량 계산 (선택한 셀)")
        e = self.entry(w, "값", 0, "100", 10)
        h = self.hwp

        def op(o):
            try:
                v = float(e.get().replace(",", ""))
            except ValueError:
                v = 0
            return lambda: h.cells_math(o, v)

        r = self.pop_buttons(w, [("더하기", op("+")), ("빼기", op("-")), ("곱하기", op("*")), ("나누기", op("/")),
                                 ("반올림", lambda: h.cells_math("round", 0))], cols=5, row=1)
        self.close_btn(w, r, cols=5)

    def dlg_sort(self):
        w = self.popup("셀 정렬 (선택한 셀)")
        h = self.hwp
        r = self.pop_buttons(w, [("가나다순", lambda: h.cells_sort("asc")), ("가나다 역순", lambda: h.cells_sort("desc")),
                                 ("숫자 작은 순", lambda: h.cells_sort("num_asc")), ("숫자 큰 순", lambda: h.cells_sort("num_desc"))],
                             cols=2)
        self.close_btn(w, r, cols=2)

    def pick_pictures(self, background):
        paths = filedialog.askopenfilenames(parent=self.root, title="사진 고르기",
                                            filetypes=[("사진", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if paths:
            self.call(lambda: self.hwp.pictures(list(paths), background), "사진 넣기")

    # ---------------- 정리 ----------------
    def dlg_around(self):
        w = self.popup("앞뒤 붙이기 (선택한 줄·셀마다)")
        e = self.entry(w, "글자", 0, "", 24)
        h = self.hwp
        r = self.pop_buttons(w, [
            ("앞에 붙이기", lambda: h.transform(lambda l: logic.add_around(l, front=e.get()))),
            ("뒤에 붙이기", lambda: h.transform(lambda l: logic.add_around(l, back=e.get()))),
            ("이 글자 지우기", lambda: h.transform(lambda l: logic.remove_text(l, e.get()))),
        ], cols=3, row=1)
        self.close_btn(w, r, cols=3)

    def dlg_replace(self):
        w = self.popup("바꾸기 (선택 범위 안에서만)")
        tk.Label(w, text="찾을 말", font=FONT_B, bg="white").grid(row=0, column=0)
        tk.Label(w, text="바꿀 말", font=FONT_B, bg="white").grid(row=0, column=1)
        pairs = []
        for i in range(3):
            a = tk.Entry(w, font=FONT, width=16, relief="solid", bd=1)
            b = tk.Entry(w, font=FONT, width=16, relief="solid", bd=1)
            a.grid(row=i + 1, column=0, padx=2, pady=2)
            b.grid(row=i + 1, column=1, padx=2, pady=2)
            pairs.append((a, b))
        h = self.hwp

        def go():
            ps = [(a.get(), b.get()) for a, b in pairs]
            self.call(lambda: h.transform(lambda t: logic.replace_pairs(t, ps), per_line=False), "바꾸기", parent=w)

        tk.Button(w, text="바꾸기", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=10,
                  command=go).grid(row=4, column=0, sticky="w", pady=(8, 0))
        tk.Button(w, text="닫기", font=FONT, relief="groove", bg="white", width=8,
                  command=w.destroy).grid(row=4, column=1, sticky="e", pady=(8, 0))

    def dlg_ratio(self):
        w = self.popup("금액 비율")
        tk.Label(w, text="이름(선택)", font=FONT_B, bg="white").grid(row=0, column=0)
        tk.Label(w, text="금액", font=FONT_B, bg="white").grid(row=0, column=1)
        rows = []
        for i in range(6):
            a = tk.Entry(w, font=FONT, width=12, relief="solid", bd=1)
            b = tk.Entry(w, font=FONT, width=14, relief="solid", bd=1)
            a.grid(row=i + 1, column=0, padx=2, pady=1)
            b.grid(row=i + 1, column=1, padx=2, pady=1)
            rows.append((a, b))
        rows[0][0].insert(0, "국비")
        rows[1][0].insert(0, "시비")

        def go():
            data = [(a.get().strip(), logic.to_number(b.get())) for a, b in rows if b.get().strip()]
            data = [(n, v) for n, v in data if v is not None]
            if not data:
                messagebox.showinfo(TITLE, "금액을 넣어 주세요.", parent=w)
                return
            try:
                ps = logic.percents([v for _, v in data])
            except ValueError as e:
                messagebox.showinfo(TITLE, str(e), parent=w)
                return
            if all(n for n, _ in data):
                text = ", ".join("{} {}".format(n, logic.pct_text(p)) for (n, _), p in zip(data, ps))
            else:
                text = ", ".join(logic.pct_text(p) for p in ps)
            self.call(lambda: self.hwp.insert("({})".format(text)), "금액 비율", parent=w)

        tk.Button(w, text="커서 자리에 넣기", font=FONT_B, bg=NAVY, fg="white", relief="flat",
                  command=go).grid(row=7, column=0, sticky="w", pady=(8, 0))
        tk.Button(w, text="닫기", font=FONT, relief="groove", bg="white", width=8,
                  command=w.destroy).grid(row=7, column=1, sticky="e", pady=(8, 0))

    def dlg_date_insert(self):
        w = self.popup("날짜 넣기")
        h = self.hwp
        today = datetime.date.today()
        days = [("오늘", today), ("내일", today + datetime.timedelta(1)), ("어제", today - datetime.timedelta(1))]
        r = 0
        for name, d in days:
            items = [(logic.date_fmt(d, st), (lambda d=d, st=st: h.insert(logic.date_fmt(d, st))), {"width": 22, "font": FONT_S})
                     for st, _ in logic.DATE_STYLES]
            r = self.pop_buttons(w, items, cols=4, title=name, row=r)
        periods = ["이번 주", "다음 주", "지난주", "이번 달", "다음 달", "지난달", "올해", "내년", "작년"]
        tk.Label(w, text="기간", font=FONT_B, fg=NAVY, bg="white").grid(row=r, column=0, sticky="w", pady=(6, 2))
        r += 1
        for p in periods:
            a, b = logic.named_period(p)
            tk.Label(w, text=p, font=FONT, bg="white").grid(row=r, column=0, sticky="w")
            for j, st in enumerate(("dotw", "dot", "full")):
                txt = logic.period_text(a, b, st)
                tk.Button(w, text=txt, font=FONT_S, relief="groove", bg="white", width=27,
                          command=lambda t=txt: self.call(lambda: h.insert(t), "날짜 넣기", parent=w)
                          ).grid(row=r, column=j + 1, padx=1, pady=1, sticky="ew")
            r += 1
        r = self.pop_buttons(w, [("지금 시각 (분)", lambda: h.insert(logic.now_text())),
                                 ("지금 시각 (초)", lambda: h.insert(logic.now_text(True)))],
                             cols=4, title="지금 시각", row=r)
        self.close_btn(w, r)

    def dlg_date_convert(self):
        w = self.popup("날짜 바꾸기 (선택한 글·셀 속 날짜를 모두)")
        h = self.hwp
        items = [(ex, (lambda st=st: h.do_convert_dates(st)), {"width": 20}) for st, ex in logic.CONVERT_STYLES]
        r = self.pop_buttons(w, items, cols=2)
        self.close_btn(w, r, cols=2)

    def dlg_date_calc(self):
        w = self.popup("날짜 계산기")
        ea = self.entry(w, "시작일", 0, logic.today_text(), 18)
        eb = self.entry(w, "종료일", 1, logic.today_text(), 18)
        out = tk.Label(w, text="", font=FONT_B, fg="#1a7f37", bg="white", justify="left")
        out.grid(row=2, column=0, columnspan=4, sticky="w", pady=4)

        def diff():
            try:
                a, b = logic.parse_date_input(ea.get()), logic.parse_date_input(eb.get())
            except ValueError as e:
                out.config(text=str(e), fg="#c0392b")
                return
            n = (b - a).days
            out.config(text="{} ~ {}\n{}일 차이 (시작일 포함 {}일)".format(logic.date_fmt(a, "dotw"), logic.date_fmt(b, "dotw"),
                                                                    n, n + 1), fg="#1a7f37")

        en = self.entry(w, "며칠 뒤", 3, "30", 8)

        def after():
            try:
                a = logic.parse_date_input(ea.get())
                n = int(en.get())
            except ValueError as e:
                out.config(text=str(e), fg="#c0392b")
                return
            d = a + datetime.timedelta(days=n)
            out.config(text="시작일로부터 {}일 뒤: {}".format(n, logic.date_fmt(d, "dotw")), fg="#1a7f37")

        tk.Button(w, text="일수 계산", font=FONT, relief="groove", bg="white", command=diff).grid(row=4, column=0, sticky="w", pady=4)
        tk.Button(w, text="○일 뒤 날짜", font=FONT, relief="groove", bg="white", command=after).grid(row=4, column=1, sticky="w", pady=4)
        self.close_btn(w, 5)

    # ---------------- 이동 ----------------
    def dlg_page_number(self):
        w = self.popup("쪽번호 이어서")
        e = self.entry(w, "시작 번호", 0, "2", 8)

        def go():
            try:
                n = int(e.get())
            except ValueError:
                return
            self.call(lambda: self.hwp.page_new_number(n), "쪽번호", parent=w)
            w.destroy()

        tk.Button(w, text="적용", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=8,
                  command=go).grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.close_btn(w, 1)

    # ---------------- 편리 ----------------
    def dlg_mailmerge(self):
        w = self.popup("메일머지 필드 넣기")
        tk.Label(w, text="커서 자리에 '필드' 칸을 심습니다. 다 심은 뒤 한글 [도구] → [메일 머지]로 명단을 연결하세요.",
                 font=FONT_S, fg=MUTED, bg="white", wraplength=360, justify="left").grid(row=0, column=0, columnspan=5, sticky="w")
        items = [("필드{}".format(i), (lambda i=i: self.hwp.mailmerge_field(i)), {"width": 6}) for i in range(1, 21)]
        r = self.pop_buttons(w, items, cols=5, row=1)
        self.close_btn(w, r, cols=5)

    def dlg_toc(self):
        w = self.popup("목차 만들기")
        tk.Label(w, text="커서를 목차 넣을 자리에 두고, 기준 크기 이상인 제목 줄을 모읍니다.", font=FONT_S, fg=MUTED,
                 bg="white").grid(row=0, column=0, columnspan=4, sticky="w")
        e = self.entry(w, "기준 크기(pt)", 1, "16", 8)

        def go():
            try:
                s = float(e.get())
            except ValueError:
                s = 16
            n = self.call(lambda: self.hwp.make_toc(s), "목차 만들기", parent=w)
            if n:
                messagebox.showinfo(TITLE, "제목 {}개로 목차를 만들었습니다.".format(n), parent=w)
                w.destroy()

        tk.Button(w, text="만들기", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=8,
                  command=go).grid(row=2, column=1, sticky="w", pady=(8, 0))
        self.close_btn(w, 2)

    def dlg_memo(self):
        w = self.popup("메모")
        h = self.hwp
        r = self.pop_buttons(w, [("메모 넣기", lambda: h.memo("add")), ("선택 글을 메모로", lambda: h.memo("from_sel")),
                                 ("메모 보기/숨기기", lambda: h.memo("view")), ("메모 지우기", lambda: h.memo("del"))],
                             cols=2)
        self.close_btn(w, r, cols=2)

    def dlg_purify(self):
        found = self.call(self.hwp.purify_scan, "공문 언어 순화")
        if found is None:
            return
        if not found:
            messagebox.showinfo(TITLE, "바꿀 만한 행정 용어를 찾지 못했습니다.")
            return
        w = self.popup("공문 언어 순화")
        tk.Label(w, text="문서에서 찾은 행정 용어 {}개 (체크한 것만 바꿉니다)".format(len(found)), font=FONT_B, fg=NAVY,
                 bg="white").grid(row=0, column=0, columnspan=3, sticky="w")
        vars_ = []
        for i, (a, b, c) in enumerate(found):
            v = tk.BooleanVar(value=True)
            tk.Checkbutton(w, variable=v, bg="white").grid(row=i + 1, column=0)
            tk.Label(w, text="{} → {}".format(a, b), font=FONT, bg="white", anchor="w", width=26).grid(row=i + 1, column=1, sticky="w")
            tk.Label(w, text="{}곳".format(c), font=FONT_S, fg=MUTED, bg="white").grid(row=i + 1, column=2)
            vars_.append((v, a, b))

        def go():
            def job():
                for v, a, b in vars_:
                    if v.get():
                        self.hwp.replace_all(a, b)
            self.call(job, "순화어 바꾸기", parent=w)
            w.destroy()

        r = len(found) + 1
        tk.Button(w, text="바꾸기", font=FONT_B, bg=NAVY, fg="white", relief="flat", width=10,
                  command=go).grid(row=r, column=1, sticky="w", pady=(8, 0))
        self.close_btn(w, r, cols=3)

    # ---------------- 수료증 ----------------
    def dlg_cert(self):
        win = self.popup("수료증 만들기")
        pad = {"padx": 2, "pady": 3}
        tk.Label(win, text="① 수강생 명단", font=FONT_B, fg=NAVY, bg="white").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        tk.Label(win, text="엑셀에서 소속 · 직급 · 성명 세 칸을 복사해 아래에 붙여 넣거나 [엑셀 불러오기]를 누르세요 (머리줄은 있어도 됨)",
                 font=FONT_S, fg=MUTED, bg="white").grid(row=1, column=0, columnspan=2, sticky="w")
        txt = tk.Text(win, width=60, height=10, font=FONT, relief="solid", bd=1)
        txt.grid(row=2, column=0, columnspan=2, pady=4)
        count = tk.Label(win, text="인원: 0명", font=FONT_B, bg="white", fg="#1a7f37")
        count.grid(row=3, column=0, sticky="w")
        state = {"people": []}

        def refresh(_e=None):
            state["people"] = logic.parse_roster_text(txt.get("1.0", "end"))
            count.config(text="인원: {}명".format(len(state["people"])))

        txt.bind("<KeyRelease>", refresh)

        def poll():
            if win.winfo_exists():
                refresh()
                win.after(700, poll)

        win.after(700, poll)

        def pick_excel():
            path = filedialog.askopenfilename(parent=win, title="명단 엑셀 불러오기", filetypes=[("엑셀 파일", "*.xlsx *.xlsm")])
            if not path:
                return
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                rows = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
                wb.close()
                people = logic.parse_roster_rows(rows)
                txt.delete("1.0", "end")
                txt.insert("1.0", "\n".join("\t".join(p) for p in people))
                refresh()
            except Exception:
                log("엑셀 읽기 오류\n" + traceback.format_exc())
                messagebox.showerror("수료증 만들기", "엑셀 파일을 읽지 못했습니다. (.xls는 .xlsx로 저장해서 골라주세요)", parent=win)

        tk.Button(win, text="엑셀 불러오기", font=FONT, relief="groove", bg="white",
                  command=pick_excel).grid(row=3, column=1, sticky="e")
        tk.Label(win, text="② 교육 정보 (모두 같은 값)", font=FONT_B, fg=NAVY, bg="white").grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 3))
        entries = {}
        today = datetime.date.today()
        fields = [("과정명", ""), ("수강기간", "{} 14:00~17:00 (3H)".format(logic.date_fmt(today, "dotw"))),
                  ("교육구분", "오프라인 교육"), ("발급일", logic.cert_date_text(today)), ("시작 번호", "{}-001".format(today.year))]
        for i, (label, default) in enumerate(fields):
            tk.Label(win, text=label, font=FONT, bg="white", width=9, anchor="w").grid(row=5 + i, column=0, sticky="w", pady=2)
            e = tk.Entry(win, font=FONT, width=48, relief="solid", bd=1)
            e.insert(0, default)
            e.grid(row=5 + i, column=1, sticky="w", pady=2)
            entries[label] = e
        tk.Label(win, text="시작 번호 예: 2026-303 → 다음 사람부터 2026-304, 2026-305 …", font=FONT_S, fg=MUTED,
                 bg="white").grid(row=10, column=0, columnspan=2, sticky="w")

        def make():
            refresh()
            people = state["people"]
            if not people:
                messagebox.showinfo("수료증 만들기", "명단을 먼저 넣어 주세요.", parent=win)
                return
            vals = {k: e.get().strip() for k, e in entries.items()}
            if not vals["과정명"]:
                messagebox.showinfo("수료증 만들기", "과정명을 입력해 주세요.", parent=win)
                return
            try:
                numbers = logic.cert_numbers(vals["시작 번호"], len(people))
            except ValueError as err:
                messagebox.showinfo("수료증 만들기", str(err), parent=win)
                return
            common = {k: vals[k] for k in ("과정명", "수강기간", "교육구분", "발급일")}
            res = self.call(lambda: self.hwp.do_make_certs(os.path.join(FORMS, "cert.hwp"), people, common, numbers),
                            "수료증 만들기", parent=win)
            if res:
                dst, missing = res
                log("수료증: {}명 → {}".format(len(people), dst))
                msg = "{}명의 수료증을 만들었습니다.\n\n저장 위치: {}".format(len(people), dst)
                if missing:
                    msg += "\n\n※ 양식에서 찾지 못해 채우지 않은 칸: " + ", ".join(missing)
                messagebox.showinfo("수료증 만들기", msg, parent=win)
                win.destroy()

        btns = tk.Frame(win, bg="white")
        btns.grid(row=11, column=0, columnspan=2, sticky="e", pady=10)
        tk.Button(btns, text="닫기", font=FONT, relief="groove", bg="white", width=8, command=win.destroy).pack(side="left", padx=4)
        tk.Button(btns, text="만들기", font=FONT_B, relief="flat", bg=NAVY, fg="white", width=10, command=make).pack(side="left", padx=4)


def main():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Incham.Office.Trial")
    except Exception:
        pass
    log("시작 (버전 {})".format(VERSION))
    make_shortcut()
    root = tk.Tk()
    app = App(root)
    root.after(3000, app.check_update)       # 켜고 3초 뒤 조용히 새 버전 확인
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        fatal("프로그램을 시작하지 못했습니다.\n" + traceback.format_exc())
