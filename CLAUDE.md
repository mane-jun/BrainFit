# CLAUDE.md — BrainFit

이 파일은 Claude Code 가 이 저장소에서 작업할 때 항상 먼저 읽는 규칙이다. 답변과 주석, 커밋 메시지 본문은 **한국어**로 쓴다.

## 프로젝트 한 줄 요약
Muse 2(4채널 EEG)로 **사용자 기준 뇌파(1번)**를 측정하고, Grid N-back 등 인지 과제 중 뇌파·수행 데이터를 결합해 **집중력·인지 상태(3번)**를 분석, Brain Profile 로 시각화하는 2026 인공지능융합대학 메이커톤 프로젝트. 시연: 2026-11-05.

서비스 흐름: 뇌파 기준 분석 → 인지 기능 측정 → 취약 영역 분석 → 맞춤형 훈련 → 변화 추적

## 하드웨어·데이터 경로 (바꾸지 말 것)
`Muse 2 → BlueMuse(블루투스→LSL) → LabRecorder(.xdf 저장, EEG + BrainFitMarkers 동시 기록) → brainfit.io.load_xdf()`
- 채널: TP9, AF7, AF8, TP10 (+ Right AUX 는 버림), 256 Hz, 기준전극 Fpz
- 과제 앱(tasks/)이 LSL 마커를 쏘고 LabRecorder 가 같은 시계로 저장한다 → 시점 동기화는 이 구조로만 한다.
- 실측 데이터는 `C:/EEGData/` 처럼 **영문 경로**에 둔다(LabRecorder 가 한글 경로에서 실패함).

## 폴더 구조
```
brainfit/datasets/  공개 데이터 로더(registry, cogwear, muse_n400) — docs/DATASETS.md
brainfit/      분석 패키지 (io → preprocess → features → baseline(1번) → cognitive(3번) → erp(P300)
               → profile(육각형) → recommend(4번) → viz → report)
tasks/         측정 세션 앱 (pygame): battery.py = EO/EC → (PVT) → Go/No-Go → Grid N-back → Oddball → 사후 EC
               grid_nback.py = 공통 App 클래스 + N-back 단독 실행, markers.py = LSL 마커
scripts/       CLI: analyze_session.py, make_synthetic.py, live_monitor.py
server/        [예비] FastAPI 뼈대 / dashboard/ [예비] Streamlit 시연 화면 / app/ 앱 미정
docs/          BATTERY(과제·점수 상세 — 최우선 참조), PLAN(전체 계획), PROTOCOL(측정 절차), MARKERS(마커 규약), METRICS(지표 식·근거),
               EEG_PRIMER(배경지식), DATASETS(공개 데이터), GIT_SETUP, PROMPTS
tests/         가짜 데이터로 '알려진 뇌파 현상'을 코드가 잡는지 검증
```

## 자주 쓰는 명령
```bash
pip install -r requirements.txt
pytest -q                                              # 반드시 통과시킨 뒤 커밋
ruff check . --fix
python scripts/analyze_session.py --synthetic          # 기기 없이 전체 파이프라인
python scripts/analyze_session.py --xdf C:/EEGData/exp001/block_Default.xdf --user <id>
python tasks/battery.py --user <id> --mode standard    # 실측 세션 (senior / demo 모드도 있음)
python tasks/battery.py --auto --speed 60 --mode demo  # 화면 없이 과제 앱 테스트
python scripts/analyze_session.py --synthetic --mode senior --age-band senior
python scripts/download_datasets.py --dataset cogwear       # 공개 데이터 → data/external/ (커밋 금지)
python scripts/validate_cogwear.py                           # Muse S 휴식 vs Stroop 검증
python scripts/validate_muse_n400.py --inspect <xdf>         # 실제 Muse .xdf 마커 확인 → 전체 검증
```

## EEG 도메인 규칙 (어기면 결과가 틀린다)
1. **단위**: MNE 내부는 볼트(V). BlueMuse 는 µV 로 보낸다 → `load_xdf` 가 1e-6 변환. 그림·임계값은 µV 로 표시. 새 코드에서 단위를 섞지 말 것.
2. **필터는 연속 신호 전체에 먼저** 적용하고 그다음 창으로 자른다(창마다 필터링 금지: 가장자리 왜곡).
3. **잡음 창은 버린다**: 진폭(ptp) > 150 µV 또는 평탄 신호. 4채널이라 ICA 불가. 버린 비율을 항상 품질 지표로 보고.
4. **사람 간 비교 금지 원칙**: 모든 상태 지표는 같은 세션의 눈 뜬 휴식(EO) 기준 z 점수, 또는 본인 과거 세션 기준. 집단 참고값은 '참고'로만.
5. 비율 지표(engagement, workload, fatigue)는 **로그를 씌운 뒤** 평균·z 점수.
6. **감마(30Hz+)는 해석하지 않는다** (Muse 건식 전극은 근전도 오염이 큼). 4채널 topomap 은 보간 장식에 불과하므로 결론에 쓰지 않는다.
7. AF7/AF8 의 델타·세타는 **눈 깜빡임**에 오염되기 쉽다. 세타 급등(스파이크)은 먼저 잡음을 의심.
8. 겹치는 창은 서로 독립이 아니다 → 창 단위 p-value 를 '유의함'의 근거로 쓰지 않는다. 비교는 블록/세션/사람 단위.
9. 결과 문구에 **진단·치료 표현 금지**(ADHD, 치매, 우울 등). "학습·훈련용 참고 지표" 문구 유지.
10. 능력 점수는 **과제 수행 성과**에서 나온다. 뇌파만으로 언어·기억 능력을 측정한다고 쓰지 말 것.
11. P300 절대 잠복기를 임상 논문(치매·MCI) 값과 비교하지 말 것(블루투스 지연). 본인 이전 기록과만 비교.
12. 점수 기준값(HEX_REFERENCE)은 임시값이다. 화면·보고서에 '임시 기준' 표시를 지우지 말 것.

## 계약(인터페이스) — 바꾸려면 문서부터
- 마커 문자열 규약: `docs/MARKERS.md` (`event|key=value|...`). 2번 담당(과제 설계) 팀원과 공유하는 계약이다.
- 분석 결과 JSON 스키마: `brainfit/report.py::save_report` 의 summary 키. 앱 팀이 이걸 읽는다.
- 지표 정의/임계값: `brainfit/config.py` + `docs/METRICS.md` 를 **같은 PR 에서** 함께 수정.

## 작업 방식
- 큰 작업은 먼저 `docs/plans/<날짜>-<주제>.md` 에 계획(목표, 변경 파일, 테스트, 위험)을 쓰고 사용자 승인 후 구현.
- 브랜치: `feat/…`, `fix/…`, `docs/…`, `exp/…`(실험). main 에 직접 push 금지, PR 로만.
- 커밋: Conventional Commits (`feat(baseline): IAF 무게중심 계산 추가`).
- 새 분석 기능 = 가짜 데이터 테스트 1개 이상 추가. 실제 데이터 파일(.xdf, 참가자 정보)은 **절대 커밋 금지**(공개 저장소).
- 공개 데이터 로더는 '실제 파일 형식'을 흉내 낸 가짜 파일 테스트(tests/fake_datasets.py)를 함께 추가한다.
- 모르는 EEG 사실은 지어내지 말고 "확인 필요"로 표시하고 docs/METRICS.md 참고문헌에 근거를 남긴다.
