# Claude Code 프롬프트 모음 (바이브코딩용)

## 사용 원칙
1. **계획 → 승인 → 구현 → 검증** 순서. 큰 작업은 항상 `/plan` 부터 (Plan 모드: Shift+Tab).
2. 한 번에 PR 하나 분량만 시킨다. "다 만들어줘"는 금지.
3. 실데이터 경로·결과 수치를 프롬프트에 구체적으로 넣는다.
4. 끝나면 `/eeg-review` 로 도메인 함정 점검 → `pytest` → PR.

## 저장소에 들어 있는 슬래시 명령 (.claude/commands/)
| 명령 | 하는 일 |
|---|---|
| `/plan <주제>` | docs/plans/ 에 계획서 작성 후 멈춤 |
| `/implement <계획서 경로>` | 승인된 계획서대로 구현 + 테스트 |
| `/analyze <xdf경로> [user]` | 실데이터 분석 실행 후 결과 해석 |
| `/eeg-review` | 현재 변경분을 EEG 함정 체크리스트로 리뷰 |
| `/pr` | 커밋 정리 + PR 본문 초안 |

---

## 라이브 데모 웹 (본선) — 단계별 프롬프트
계획서: `docs/plans/2026-10-08-live-demo-web.md`, 설계: `docs/LIVE_DEMO.md`. 각 단계는 `/live-phase P1` 처럼 실행해도 된다.

**0. 시작 전 (처음 한 번)**
```
CLAUDE.md, docs/LIVE_DEMO.md, docs/plans/2026-10-08-live-demo-web.md, server/live.py,
brainfit/realtime/*.py, server/static/debug.html 을 읽고, 라이브 데모의 데이터 흐름을 10줄로 요약해줘.
특히 /ws/live tick 메시지와 활동 컴포넌트 계약(ActivityProps)을 정확히 짚어줘. 코드는 아직 수정하지 마.
```

**P1 골격 + 실시간 패널**
```
/live-phase P1
추가 요구: debug.html 의 drawWave/drawTrend/drawHead 로직을 React 컴포넌트(Waveform, TrendChart, HeadMap)로
이식하고, 캔버스는 devicePixelRatio 를 반영해. 오른쪽 실시간 패널은 모든 화면에서 고정으로 보이게 해줘.
```

**P2 측정 흐름**
```
/live-phase P2
화면 문구 예: "뇌파 기기를 착용해 주세요" → "화면 가운데를 편하게 바라보세요" → "눈을 감고 쉬세요" →
"분석 중…" → "○○형으로 파악되었습니다". 성향 카드에는 summary, tip, notes 를 보여 주고 근거 수치는 접어 둬.
```

**P3/P4 활동**
```
/live-phase P3
활동마다 src/activities/<id>.tsx 하나, 순서 생성·채점은 src/activities/logic/<id>.ts 로 분리해서 Vitest 로 테스트해.
Go/No-Go 순서 규칙은 brainfit/sequences.py 의 spaced_rare_sequence 와 같은 결과가 나오도록.
```

**P5 결과**
```
/live-phase P5
최종 화면 맨 위에 overall.message 를 크게, 그 아래 활동 카드(반응 뚜렷/약함/보류 배지 + 피드백),
지표 추이 그래프에는 활동 구간을 음영과 이름으로 표시해줘. 다음 활동 안내 화면의 reason 문장은 강조 상자로.
```

**P6 실기기**
```
/live-phase P6
실제 Muse 로 세션을 진행한 로그(서버 콘솔, quality 변화)를 붙일게. 블루투스 끊김 감지(파형 1초 이상 정지) 시
화면 경고와 '녹화 재생으로 전환' 버튼을 만들어줘. 백엔드 RESPONSIVE_Z 보정은 계획서부터.
```

## 분석 파트 단계별 프롬프트 (복사해서 사용)

### 공개 Muse 데이터로 파이프라인 검증 (기기 측정 전)
```
/analyze 대신 아래 순서로:
1) python scripts/validate_muse_n400.py --inspect <data/external/muse_n400 의 파일 1개>
   출력된 마커 패턴을 보고, 목표 단어의 관련/무관 마커를 고르는 정규식을 제안해줘.
2) 그 정규식으로 전체 검증을 돌리고 loader_check.csv 에서 끊김·샘플링률·시행 수 이상치를 정리해줘.
3) outputs/validation/cogwear/report.md 와 비교해서, 우리 config 임계값(ptp 150 µV 등) 중
   실제 Muse 데이터에서 너무 많이/적게 버리는 값이 있는지 근거와 함께 제안해줘. 수정은 계획서부터.
```

### 배터리 과제 실측 점검
```
/plan tasks/battery.py 를 실제 Muse 로 1회 돌린 XDF 점검
- scripts/check_xdf.py <경로>: 스트림 목록, task 별 stim/trial 개수, 블록 길이, 마커-EEG 시간 범위 겹침 확인
- docs/BATTERY.md 1절 표의 시행 수·시간과 실제 기록이 맞는지 표로 비교
- P300 깨끗한 타깃 에포크 수가 25 미만이면 원인(깜빡임/움직임) 채널별 보고
```

### PR #2 — 실데이터 로더 검증
```
/plan 실제 Muse 2 녹화 파일로 load_xdf 검증
상황: C:/EEGData/exp001/block_Default.xdf 는 마커 없이 녹화한 파일이다(BlueMuse→LabRecorder).
목표:
1) python scripts/analyze_session.py --xdf <경로> --segments "rest_eo:..,rest_ec:.." 가 끝까지 돌게 할 것
2) meta 에 실제 샘플링률, 끊김(n_gaps), 채널명이 정확히 찍히는지 확인
3) 01_quality.png 기준 품질이 60% 미만이면 원인을 채널별로 보고
제약: 단위 규칙(CLAUDE.md 1번) 준수, 데이터 파일은 커밋하지 말 것.
```

### PR #3 — 과제 앱 마커 연동 확인
```
/plan grid_nback 마커가 LabRecorder XDF 에 기록되는지 검증하는 절차와 점검 스크립트
- scripts/check_xdf.py <경로>: 스트림 목록, 마커 개수, 이벤트별 개수, block 구간 길이, trial 수를 표로 출력
- 마커 시점과 EEG 시점의 정렬 오차를 확인하는 방법도 제안
docs/MARKERS.md 규약을 바꾸지 말 것.
```

### PR #4 — 기준선(1번) 튜닝
```
/plan 기준선 분석 실데이터 튜닝
파일럿 3명(ID: p01~p03)의 xdf 에서 알파 반응성과 IAF 를 뽑아 표로 비교하고,
EC 스펙트럼에 알파 피크가 약한 사람(알파 prominence < 1.5)을 자동 경고하는 기능을 추가해줘.
IAF 기반 개인 맞춤 대역(theta: IAF-6~IAF-4, alpha: IAF-2~IAF+2, Klimesch 1999)을 config 옵션으로.
docs/METRICS.md 의 표와 변경 이력도 함께 수정.
```

### PR #5 — 인지 상태(3번) 튜닝
```
/plan 집중·피로 분석 임계값을 파일럿 데이터로 보정
- 파일럿별 블록 요약(engagement_z, workload_z, d′)을 하나의 CSV 로 모으는 scripts/aggregate.py
- 난이도(N)별 workload_z 평균을 사람 단위로 비교하는 그림(사람마다 선 하나)
- 지속 집중 시간 계산의 drop_z, drop_hold_sec 민감도 분석(값별 결과 표)
통계는 사람 단위로만. 창 단위 p-value 금지.
```

### PR #6 — 2번 담당 과제 연동
```
/plan 언어(verbal)·시공간(spatial) 과제를 마커 규약에 맞춰 연동
2번 담당이 만든 과제는 <설명>. trial 마커에 target/resp/correct/rt 를 넣는 방법,
profile 의 언어·시공간 점수 계산(정확도 또는 d′), 레이더 차트 반영까지.
config.task_domain 과 docs/MARKERS.md 표를 같은 PR 에서 수정.
```

### PR #8 — 공개 데이터 / 분류기
```
/plan Muse 공개 데이터로 상태 분류기 실험 (exp 브랜치)
docs/DATASETS.md 의 원칙(LOSO 교차검증, 사람 단위 분할)을 따를 것.
비교: (a) 교차 피험자 모델 (b) 개인 보정 모델(EO 휴식 vs 2·3-back, 첫 세션 5분 학습).
결과는 docs/plans/ 에 표와 그림으로, 과장 없이.
```

### PR #9 — 실시간 게이지
```
/plan scripts/live_monitor.py 계산부를 brainfit/realtime.py 로 분리하고 server/main.py 의 /live WebSocket 으로 0.5초마다 {"t", "engagement_z", "quality"} 전송
--fake 모드로 기기 없이 테스트 가능하게. 연결 끊김 시 재연결.
```

### 앱 형태가 정해졌을 때
```
/plan BrainFit 앱 1차 화면 설계
입력: server/main.py 의 /sessions/analyze 응답 JSON (outputs/*/summary.json 예시 참고)
화면: 1) 측정 안내 2) 실시간 게이지 3) 결과(Brain Profile 레이더, 지속 집중 시간, 블록별 카드) 4) 변화 추적
모든 결과 화면에 '학습·훈련용 참고 지표' 문구.
```

## 좋은 프롬프트 vs 나쁜 프롬프트
| 나쁨 | 좋음 |
|---|---|
| "뇌파로 집중력 점수 내줘" | "block 구간 창의 z_log_engagement 평균을 0–100 으로 변환하는 함수. 변환식은 docs/BATTERY.md 4절, 테스트는 synthetic 데이터로 nback2 > nback1 확인" |
| "그래프 예쁘게" | "04_engagement.png 에 블록 경계 세로선과 블록 이름, 한글 폰트(맑은 고딕) 적용" |
| "에러 고쳐줘" | "아래 traceback 과 실행 명령, 입력 파일 정보(채널 5개, 256Hz) 를 보고 원인 먼저 설명한 뒤 수정" |
