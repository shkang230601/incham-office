# 인천상의 오피스 — 배포 안내 (Claude용)

인천상공회의소 직원용 한글(HWP) 자동화 프로그램. Python(tkinter) + win32com, Windows 전용.
사용자: 경제진흥실 강신현 주임. 사용자에게는 쉬운 한국어로, 작업 전 ①지시 재구성 ②처리 경로(3단계) ③확인 요청을 먼저 보여 주고 승인받는다.

## 어디에 무엇이 있나
- **원본(작업본)**: 사용자 PC `D:\클로드\인천상의오피스\인천상의오피스\` (app, python, run_IncheonOffice.bat)
  - 사용자가 직접 고친 파일이 있을 수 있으니 **배포 전에는 반드시 PC의 app 폴더를 기준**으로 삼는다 (device 도구로 가져오기).
  - PC app 폴더에는 시험용 파일(prep*, probe*, selftest.py, hwpctl_old.py 등)이 섞여 있음 → 배포에서 자동 제외됨.
- **이 저장소** (공개): `app/` = 마지막 배포본, `release/latest.json` + `release/app_<버전>.zip` = 업데이트 서버.
- **배포판 보관**: 첫 설치용 zip을 매번 사용자 PC `D:\클로드\인천상의오피스\배포판\` 에 저장한다 (사용자 요청).

## 업데이트 동작
- 프로그램이 켜지고 3초 뒤 `https://raw.githubusercontent.com/shkang230601/incham-office/main/release/latest.json` 확인
  → `VERSION.txt`보다 높으면 업데이트 창 → `release/<file>` 받아 app 폴더 덮어씀(같은 파일은 건너뜀, 원본은 app\_backup\<옛 버전>) → 다시 켬.
- GitHub raw 캐시 때문에 올린 뒤 **약 5분** 지나야 보임. zip 이름에 버전을 넣는 이유도 캐시.
- GitHub Releases API는 이 환경에서 막혀 있어 쓰지 않는다. git push 만 사용.

## 배포 순서
1. PC app 폴더를 받아 온다 (device_stage_files 또는 device_bash로 묶어서). 바뀐 파일을 확인하고 사용자에게 알린다.
2. 버전을 올린다 (3.1 → 3.2 …). 업데이트 내용은 notes 파일에 쓴다.
   - 끝이 `:` 인 줄은 굵게, `- ` 로 시작하는 줄은 점 목록으로 보인다.
   - 업데이트 창 글꼴(InchamSans)은 자주 쓰는 한글 2,350자만 있음 → 드문 글자는 피한다.
3. 실행:
   ```
   python tools/release.py --version 3.2 --notes-file notes.txt --app <받아 온 app 폴더> --python <PC의 python 폴더를 받아 온 것>
   git add -A && git commit -m "인천상의 오피스 3.2" && git push
   ```
   - 개인 정보(이름·휴대폰·메일·내선번호)가 남으면 스크립트가 멈춘다. 고친 뒤 다시.
4. `_build/<버전>/인천상의오피스_<버전>.zip` 을 사용자 PC `D:\클로드\인천상의오피스\배포판\` 에 저장하고, PC 작업본의 `app\VERSION.txt`도 새 버전으로 맞춘다.
5. 5분 뒤 latest.json 이 바뀌었는지 확인하고 사용자에게 알린다.

## 주의
- 파이썬 폴더(`python/`)는 저장소에 넣지 않는다(.gitignore). 업데이트는 app 폴더만 바꾼다.
  - 파이썬에 `_ssl.pyd`, `libssl-3-x64.dll`, `libcrypto-3-x64.dll` 이 DLLs 에 있어야 https(업데이트)가 된다.
- 사용자 데이터(내 정보·내 서식·최근 기호)는 `%APPDATA%` 에 있어 업데이트와 무관.
- 3.1 배포 시점에 사용자 PC는 시험 때문에 3.1.1 로 표시됨(내용은 3.1과 같음) → 다음 정식 버전은 3.2 이상.
