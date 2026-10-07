# 라이브 데모 설계 (본선 시연용 로컬호스트 웹)

> 목표 장면: 참가자가 Muse 2 를 쓰고 "뇌파 테스트 시작" → 착용 확인 → 기준선 측정 → "○○형으로 파악되었습니다"
> → 활동 3~5개(뇌파 반응에 따라 다음 활동이 바뀜) → 실시간 그래프·센서 지도 → 활동별 문제점과 제안 → 최종 리포트.

## 1. 구조

```
[Muse 2] → BlueMuse → LSL ─┐
[시뮬레이터 SimSource] ────┼─▶ RealtimeEngine (brainfit/realtime/engine.py)
[녹화 재생 ReplaySource] ──┘      · 인과 필터(60Hz 노치 + 1–40Hz) → 0.5초마다 최근 2초 창 분석
                                  · 지표: 몰입·부하·피로 (오프라인과 같은 features.window_features)
                                  · 기준선(눈 뜸/감음) → 성향 분류(brain_type.py)
                                  · 활동 요약·반응도·다음 활동 선택(adaptive.py)
                                  · 이벤트 기록(엔진 시계) → 끝나면 오프라인 리포트(report.py)
                                         │
                FastAPI (server/main.py + server/live.py)
                 REST /api/live/*   WebSocket /ws/live (0.5초 tick)
                                         │
                웹 화면: web/ (React, 정식 UI), /static/debug.html (기존 검증용)
```

- **입력 소스 3종을 같은 인터페이스로** 둔 이유: 기기 없이도(시뮬레이터) / 실제 뇌파로(녹화 재생) 화면을 만들고, 시연 당일 기기가 말썽이면 재생으로 즉시 전환하기 위해.
- 시뮬레이터는 화면 흐름(눈 감기, 활동 시작)에 맞춰 신호가 바뀌고, 활동별 반응 정도(`SIM_RESPONSE`)를 일부 낮게 둬서 **적응형 선택이 시연되도록** 했다.
- LabRecorder 로 같은 세션을 .xdf 로 남기려면 `start` 에 `record_markers: true` (LSL 마커 송신).

실행:
```bash
cd web && npm install && npm run build
cd .. && uvicorn server.main:app --reload  # http://localhost:8000 → 정식 화면
```

## 2. 화면 흐름 (상태 기계)

| # | 화면 | API | 비고 |
|---|---|---|---|
| 0 | 시작: 입력 소스(시뮬/Muse/재생), 사용자 ID, 활동 수(3–5) | `POST start` | |
| 1 | "뇌파 기기를 착용해 주세요" + 센서 4개 품질 + 파형 | `POST phase{signal_check}` | 4센서 모두 good 3초 유지 시 '다음' 활성 |
| 2 | 눈 뜬 휴식 60초(시연 30초) | `mark rest_eo_start/end` | 응시점 + 진행 링 |
| 3 | 눈 감은 휴식 60초(시연 30초), 끝나면 비프 | `mark rest_ec_start/end` | 응답에 `brain_type` |
| 4 | "분석 중…" → **"○○형으로 파악되었습니다"** 카드 | | 근거 수치는 접기 |
| 5 | 다음 활동 안내: 이름·방법·**선택 이유** | `GET next` | 이유 문장을 꼭 보여 준다(적응형 알고리즘의 '보이는' 부분) |
| 6 | 활동 수행 (아래 4절) | `mark block_start` → `trial`×N → `mark block_end` | 옆 패널에 실시간 상태 |
| 7 | 활동 요약: 뇌파 반응(뚜렷/약함/보류), 행동, 피드백 | `block_end` 응답의 `activity_result` | 5초 휴식 후 5번으로 |
| 8 | 최종 결과: 전체 요약, 활동 카드, 육각형, 지표 추이, 리포트 그림 | `POST finish` | `figures` URL 표시 |

## 3. API·메시지 스키마

**WebSocket `/ws/live` tick (0.5초)**
```jsonc
{ "type": "tick",
  "snapshot": {
    "t": 123.5, "phase": "activity", "activity": "nback2", "block": 2, "t_in_phase": 31.0,
    "source": "lsl|sim|replay", "baseline_ready": true,
    "quality": {"TP9": 0.95, "AF7": 0.7, "AF8": 0.8, "TP10": 1.0}, "quality_status": "good|fair|poor",
    "rel": {"delta": 0.2, "theta": 0.2, "alpha": 0.35, "beta": 0.2},          // 상대 파워
    "bands": {"TP9": {"theta": 12.1, "alpha": 30.2, "beta": 8.1}, ...},      // 절대 파워 µV²
    "z": {"engagement": 1.2, "workload": 0.4, "fatigue": -0.3},             // 휴식 대비, 기준선 전엔 null
    "head": {"TP9": {"theta": 0.3, "alpha": -1.1, "beta": 0.8}, ...},        // 센서별 대역 z
    "state_label": "몰입|보통|이완·저각성|피로|기준선 측정 전",
    "brain_type": { "id": "relaxed", "name": "안정·이완형", "summary": "...", "tip": "...", ... } },
  "wave": { "sfreq": 128, "ch": ["TP9","AF7","AF8","TP10"], "data": [[...],[...],[...],[...]] } }  // 새 샘플(µV)
```

**`GET /api/live/next`**
```json
{"activity":"arithmetic","task":"arithmetic","level":null,"name":"암산","how":"...","sec":90,
 "mode":"explore|compensate|hold","reason":"'단어 기억'에서는 작업 부하 반응이 약했어요(z=0.1). ...",
 "index":3,"total":4}
```
**`POST /api/live/trial`** `{task, block, idx, target(1=반응해야 함/0=참아야 함), resp(1/0), correct(1/0), rt(초, 무응답 -1), extra{}}`

**`block_end` 응답의 `activity_result`**: `z{engagement,workload,fatigue}`, `response`, `response_metric`, `responsive(true|false|null)`, `engagement_slope_per_min`, `behavior{n_trials, accuracy, fa_rate, miss_rate, rt_median, rt_cv}`, `feedback[]`.

## 4. 활동 (웹 구현 명세)

모든 활동은 같은 컴포넌트 계약을 따른다.
```ts
interface ActivityProps {
  task: string; block: number; level?: number; durationSec: number;
  onTrial: (t: {idx:number; target:0|1; resp:0|1; correct:0|1; rt:number; extra?:object}) => void;
  onDone: () => void;
}
```
입력은 키보드(스페이스/숫자)와 클릭·터치 모두 지원. 150 ms 미만 반응은 '예측 반응'으로 무효. 시행 간격은 지터(무작위 폭)를 둔다.

| id | 이름 | 영역 | 자극·규칙 | 타이밍 | target / 채점 | 목표 지표 |
|---|---|---|---|---|---|---|
| `gonogo` | Go/No-Go | 억제조절 | 초록 원=누름, 빨간 사각형=참기(25%), No-Go 앞 Go ≥2 | 자극 300ms, 응답창 800ms, 간격 0.7–1.1s | Go=1, No-Go=0 | 몰입 |
| `nback` | 위치 기억 | 작업기억 | 3×3 격자, N번 전 위치와 같으면 누름(약 30%) | 자극 500ms, 시행 2.5s, 기본 N=2 | 일치=1 | 부하·몰입 |
| `oddball` | 드문 모양 찾기 | 주의 정확성 | 원 80% / 삼각형 20%에만 반응 | 자극 250ms, 간격 1.0–1.3s | 삼각형=1 | 몰입 |
| `stroop` | 색깔 단어 | 선택적 주의 | 색 단어의 '글자 색'을 4지선다로 | 응답까지 최대 2s, 일치 50%/불일치 50% | 모든 시행 target=1, correct=정답 여부, extra.congruent | 몰입·부하 |
| `arithmetic` | 암산 | 계산 | 두 자리 ± 연산, 3지선다, 정답 3연속이면 한 단계 어렵게 | 문제당 최대 6s | target=1, correct | 부하·몰입 |
| `pvt` | 반응 속도 | 각성 | 2–6s 무작위 간격 후 신호, 최대한 빨리 | 최대 1.5s | target=1, 500ms 초과=lapse(extra) | 몰입 |
| `word_memory` | 단어 기억 | 언어 기억 | 단어 8개 학습(각 1.5s) → 16개 섞인 목록에서 본 단어 고르기 | 판정 단계 시행당 최대 3s | 본 단어=1, 새 단어=0 | 부하 |

> P300(ERP)은 브라우저의 화면 표시 시각이 수십 ms 흔들려 라이브에서 쓰지 않는다. P300 은 `tasks/battery.py`(pygame) 녹화로 오프라인 분석한다.

## 5. 적응형 활동 선택 (`brainfit/realtime/adaptive.py`)

1. **탐색(1–2번째)**: 성향 카드의 `start_with` 활동에 가중치 3, 서로 다른 영역에서 무작위.
2. **반응도 판정**: 활동 중 깨끗한 창(시작 5초 제외)의 목표 지표 평균 z(본인 눈 뜬 휴식 대비).
   목표 지표 중 최댓값 ≥ `RESPONSIVE_Z`(임시 0.8) 이면 '반응 뚜렷'. 깨끗한 창 < 6개면 '판단 보류'.
3. **보완(3번째부터)**: 반응이 약했고 아직 보완되지 않은 활동이 있으면, 그 지표를 목표로 하는 남은 활동 중
   자극 강도(`arousal`)가 가장 높은 것을 고른다. 이유 문장을 화면에 표시.
4. 보완에 성공했거나 약한 활동이 없으면 → 아직 측정하지 않은 영역 탐색.
5. 신호 품질이 `poor` 면 반응 없음으로 오판하지 않고 `hold` + 재착용 안내.
6. `RESPONSIVE_Z` 는 CogWear 검증(Stroop 중 사람별 z 분포)과 파일럿으로 보정한다.

## 6. 시각화 원칙 (심사에서 지적받지 않으려면)

| 보여 줄 것 | 표현 | 하지 말 것 |
|---|---|---|
| 센서 지도 | 머리 그림 위 **센서 4개 점**의 색 = 휴식 대비 z. 제목 "센서 위치별 활동" | 4점을 보간한 컬러맵을 '뇌 활성 지도'처럼 보이기. (넣는다면 "참고용 보간" 라벨 필수) |
| 현재 리듬 | "지금 이마 쪽 센서에서 세타가 휴식보다 높아요 (기억 부담이 클 때 자주 보이는 변화)" | "전두엽이 활성화되었습니다" 같은 뇌 부위 단정 |
| 상태 | 몰입 / 보통 / 이완·저각성 / 피로 (본인 휴식 대비) | 절대 점수로 사람끼리 비교 |
| 성향 | "오늘의 뇌파 성향" + 임시 기준 안내 | 성격·능력·진단처럼 표현 |
| 품질 | 센서별 깨끗한 구간 비율, poor 면 결과 대신 재착용 안내 | 품질 나쁜 데이터로 결론 |

## 7. 시연 당일 대비
- 재생 파일(`data/demo/*.npz`)과 미리 녹화한 리포트를 준비. 기기 문제 시 입력을 '녹화 재생'으로 전환.
- `time_scale`(빨리 감기)은 리허설용. 실제 시연에선 1.0.
- 블루투스 혼선 대비: 시연 PC 와 Muse 를 1m 이내, 다른 Muse 앱 종료, 충전기 분리.
