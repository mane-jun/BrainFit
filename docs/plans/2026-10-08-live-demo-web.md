# 계획서: 본선용 라이브 데모 웹 (web/)

- 작성: 2026-10-08 · 담당: 담우 (+ 웹 담당 팀원) · 기준 문서: docs/LIVE_DEMO.md
- 이미 있는 것: 실시간 엔진·API·WebSocket·적응형 선택·성향 분류·시뮬레이터/재생 (`brainfit/realtime/`, `server/live.py`), 검증용 화면 `/static/debug.html`, 테스트 `tests/test_realtime.py`
- 만들 것: `web/` 의 정식 화면(React) + 활동 7종 + 결과 화면 + 시연 안정화

## 기술 선택
| 항목 | 선택 | 이유 |
|---|---|---|
| 프레임워크 | React + Vite + TypeScript (`web/`) | 서버 렌더링 불필요, WebSocket·캔버스 위주, 설정 단순 |
| 개발 서버 | Vite proxy: `/api`, `/ws`, `/live-files` → `localhost:8000` | 백엔드 수정 없이 붙음 |
| 실시간 그래프 | `<canvas>` 직접 그리기 (debug.html 로직 이식) | 4채널×128Hz 를 차트 라이브러리로 그리면 끊김 |
| 결과 그래프 | Recharts (레이더·막대·라인) | 정적 그래프는 생산성 우선 |
| 상태 관리 | `useReducer` 기반 화면 상태 기계 + `useLiveSocket` 훅 | 외부 상태 라이브러리 불필요 |
| 테스트 | Vitest (자극 순서 규칙·채점 함수) | 활동 로직이 틀리면 데이터 전체가 틀림 |

## 단계 (PR 단위)

### P1 `feat/web-scaffold` — 골격 + 실시간 패널 (10/8–10/10)
- Vite React TS 생성, proxy, ESLint/Prettier, `npm run dev/build/test`
- `useLiveSocket()` : `/ws/live` 연결·재연결, 최신 snapshot, 파형 버퍼(채널당 5초)
- 컴포넌트: `Waveform`, `QualityGrid`, `HeadMap`(센서 4점, 대역 선택), `BandBars`, `TrendChart`, `StateBadge`
- 레이아웃: 왼쪽 '진행 화면', 오른쪽 '실시간 패널'(항상 보임). 발표용 큰 글씨 모드 토글
- **완료 조건**: `uvicorn server.main:app` + `npm run dev` → 시뮬레이터 시작 시 4개 패널이 0.5초마다 갱신, 빌드 성공

### P2 `feat/web-flow` — 측정 흐름 (10/10–10/13)
- 화면 상태 기계: 시작 → 착용 확인 → 눈 뜬 휴식 → 눈 감은 휴식(비프) → 분석 중 → 성향 카드 → 활동 루프 → 결과
- 착용 확인: 4센서 모두 good 3초 유지 시 '다음' 활성 / poor 면 재착용 안내 문구
- 시연 모드(휴식 30초) / 정식 모드(60초) 선택
- **완료 조건**: 시뮬레이터로 성향 카드까지 끊김 없이 진행, 새로고침 시 '세션 진행 중' 안내

### P3 `feat/activities-1` — 활동 4종 (10/13–10/17)
- `ActivityRunner`(시작 카운트다운 → 활동 → onDone), 공통 입력(키보드/클릭/터치), 150ms 미만 무효
- `gonogo`, `nback`, `oddball`, `pvt` — 타이밍·비율은 docs/LIVE_DEMO.md 4절 / docs/BATTERY.md
- 자극 순서 생성기는 `brainfit/sequences.py` 규칙과 동일하게(TS 로 이식) + Vitest
- **완료 조건**: 각 활동이 `/api/live/trial` 에 올바른 target/resp/correct/rt 를 보냄(서버 events 로 확인), 테스트 통과

### P4 `feat/activities-2` — 활동 3종 (10/17–10/21)
- `stroop`(4지선다, extra.congruent), `arithmetic`(3연속 정답 시 난이도↑), `word_memory`(학습→판정)
- **완료 조건**: 7종 모두 `/api/live/next` 결과로 실행 가능, 시뮬레이터 4활동 세션 완주

### P5 `feat/web-results` — 활동 요약·최종 결과 (10/21–10/26)
- 활동 요약 카드: 뇌파 반응(뚜렷/약함/보류), 몰입·부하 z, 행동 지표, 피드백 문장
- 다음 활동 안내에 **선택 이유** 강조 표시 (적응형 알고리즘이 보이는 지점)
- 최종 화면: 전체 요약 문장, 활동별 카드, 지표 추이(활동 구간 음영), 육각형, 리포트 그림 갤러리, JSON 다운로드
- **완료 조건**: 결과 화면 캡처 1장으로 "어느 활동에서 집중이 떨어졌고 무엇을 제안하는지"가 읽힘

### P6 `feat/live-hardening` — 실기기·시연 안정화 (10/26–11/3)
- 실제 Muse(LSL) 3회 이상 완주, 블루투스 끊김 시 화면 경고, 재생 모드 즉시 전환 버튼
- 본인 녹화 1개를 `scripts/import_recording.py` 로 재생 파일화(동의·익명 ID)
- `record_markers: true` 로 LabRecorder 동시 녹화 → 오프라인 리포트와 라이브 결과 비교
- 백엔드 보정: `RESPONSIVE_Z`(CogWear·파일럿), 성향 `POP_REF`(공개 데이터)
- 리허설 체크리스트(docs/LIVE_DEMO.md 7절) 2회
- **완료 조건**: 기기 연결부터 결과까지 10분 이내, 리허설에서 막힘 없음

## 위험
| 위험 | 대응 |
|---|---|
| 브라우저 타이밍 흔들림 | 대역 파워 분석만 라이브, ERP 는 pygame 녹화로 |
| 뇌파 반응이 작아 적응형이 늘 '보완'만 함 | `RESPONSIVE_Z` 보정, 이유 문장으로 정직하게 표시 |
| 시연장 블루투스 | 재생 모드 + 사전 녹화 리포트 |
| 과대 해석 | docs/LIVE_DEMO.md 6절 표현 규칙을 컴포넌트 문구에 그대로 사용 |
