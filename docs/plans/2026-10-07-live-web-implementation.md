# 라이브 웹 과제 구현 실행 계획

기준: `docs/plans/2026-10-08-live-demo-web.md` P1~P5, `docs/LIVE_DEMO.md` 3~6절. 사용자는 계획을 바탕으로 구현을 요청했다.

## 목표

시뮬레이터·Muse LSL·녹화 재생 중 하나로 시작해 착용 확인, EO/EC 기준선, 성향 카드, 적응형 활동 3~5개, 결과까지 브라우저에서 수행한다. 일곱 활동 모두 참가자의 실제 입력을 채점하고 시행마다 `trial` API로 보낸다. 기존 `server/static/debug.html`의 자동 응답은 정식 화면에서 사용하지 않는다.

## 작업 순서

1. `web/`에 Vite·React·TypeScript·Vitest 설정과 `/api`, `/ws`, `/live-files` 프록시를 만든다.
2. 자극 순서·채점·문제 생성의 순수 함수를 테스트부터 작성한다. Go/No-Go와 Oddball 간격, N-back 타깃, 150ms 미만 반응 무효, 객관식 채점, 단어 기억 구성을 검증한다.
3. WebSocket 훅과 파형·품질·센서 위치·대역·상태 패널을 구현한다.
4. 시작→착용→EO/EC→성향→활동→결과 상태 흐름을 API에 연결한다. API 오류, 신호 품질 저하, 연결 끊김을 화면에 표시한다.
5. 일곱 활동을 같은 시행 전송 계약으로 구현한다. 공통 입력은 Space/숫자 키와 터치·클릭이며, 마커는 `block_start`→`trial`×N→`block_end` 순서를 보장한다.
6. 활동별 요약, 선택 이유, 최종 결과, 리포트 그림, JSON 내려받기를 추가한다. 빌드 후 FastAPI `/`에서 정식 화면을 제공한다.
7. Vitest, TypeScript 빌드, 기존 pytest·ruff, 브라우저 시뮬레이터 흐름을 검증한다.

## 위험과 범위

- 실제 Muse 연결·파일럿 보정·LabRecorder 동시 녹화 검증은 장비가 필요한 P6 단계다. 기기 없이 시뮬레이터와 브라우저로 확인한다.
- 브라우저 자극 타이밍은 ERP/P300 분석에 사용하지 않는다.
- 능력 점수는 행동 성과이며, EEG 지표는 본인 EO 휴식 대비 상태라는 문구를 유지한다.
- 화면은 깊은 남색 바탕, 청록 신호 강조, 호박색 응답 강조를 사용한다. 진행 과제를 가장 크게 놓고 실시간 수치는 보조 패널에 둔다.

## 구현 상태 (2026-10-07)

- `feat/realtime`에서 시작한 구현을 `codex/realtime-web-tests` 브랜치에 정리했다.
- P1~P5 웹 흐름 구현: 시작 설정, 신호 품질 확인, EO/EC 기준선, 성향 카드, 적응형 활동 3~5개, 활동별 요약, 결과 화면.
- Go/No-Go, N-back, Oddball, PVT, Stroop, 암산, 단어 기억의 자극·실제 사용자 반응·채점·시행별 API 기록을 구현했다. 브라우저 시행 기록은 `block_start` → `trial` → `block_end` 순서다.
- WebSocket 실시간 파형·대역·품질·상태, 응답 지연/품질 저하 알림, 결과 차트·리포트 이미지·JSON 내려받기를 구현했다.
- FastAPI `/`에서 `web/dist` 빌드 화면을 제공한다. 기존 디버그 화면은 `/static/debug.html`에 유지한다.
- 검증: Vitest 20개, `npm run lint`, `npm run format:check`, `npm run build`, Python pytest 25개, `ruff check .`. 실제 브라우저에서 시뮬레이터 시작 → 신호 품질 통과 → EO/EC 기준선 → Oddball 72시행 → 활동 요약 → 다음 활동 화면까지 확인했다. 결과 화면 렌더링과 WebSocket 재연결 시 품질 게이트 초기화도 테스트했다.
- 로컬 `http://127.0.0.1:8000/`에서 서버 응답을 확인했다. 재시작 및 로컬 개발 방법은 `web/README.md`와 루트 `README.md`에 기록했다.
- P6 Muse 장비 연결, LabRecorder 동시 녹화, 파일럿 보정, 전체 세션의 현장 타이밍 검증은 장비가 있는 환경에서 수행해야 한다.
