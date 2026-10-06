# 마커 규약 (팀 공용 계약)

과제 프로그램은 사건이 생길 때마다 **LSL 마커 스트림**(`type=Markers`, 이름 `BrainFitMarkers`)으로 문자열 하나를 보낸다. LabRecorder 가 EEG 와 같은 시계로 저장하므로, 분석 코드는 "몇 초에 무슨 일이 있었는지"를 정확히 안다. 마커가 없으면 휴식/과제 구간을 나눌 수 없어 1번·3번 분석이 모두 불가능하다.

## 형식
```
event|key=value|key=value
```
- `event` 는 소문자 snake_case. 구간은 반드시 `<이름>_start` / `<이름>_end` 쌍.
- 값에 `|` 와 `=` 금지. 숫자는 그대로(`rt=0.532`), 없음은 `-1`.
- 파이썬에서는 `brainfit.io.format_marker()` / `parse_marker()` 를 쓴다. 웹/Unity 등 다른 언어도 같은 문자열을 만들면 된다.

## 이벤트 목록 (v1)
| event | 필수 키 | 시점 | 쓰임 |
|---|---|---|---|
| `session_start` | user, protocol | 세션 시작 | 메타 |
| `rest_eo_start` / `rest_eo_end` | – | 눈 뜬 휴식 | **1번 기준선**, 모든 z 점수의 기준 |
| `rest_ec_start` / `rest_ec_end` | – | 눈 감은 휴식 | **1번** IAF, 알파 반응성 |
| `block_start` / `block_end` | task, block, (n) | 과제 블록 | **3번** 블록별 집중 |
| `stim` | task, block, idx, pos, target | 자극 제시 순간 | (확장) ERP/P300 |
| `response` | task, block, idx, rt | 키 입력 순간 | (확장) 반응 관련 분석 |
| `trial` | task, block, idx, target, resp, correct, rt | 시행 종료 | **3번** 행동 지표(d′, 정확도, RT) |
| `rest_ec_post_start` / `_end` | – | 과제 후 눈 감은 휴식 | **3번** 피로(사전 대비 알파·세타 변화) |
| `session_end` / `session_abort` | – | 종료 | 메타 |

## task 이름 → Brain Profile 축 (docs/BATTERY.md 4절, config.HEX_AXES)
| task | target=1 의 뜻 | 쓰이는 축 |
|---|---|---|
| `pvt` | 모든 자극 | 반응속도(노년층 보조), 지속 주의 |
| `gonogo` | Go(초록 원) | 반응속도, 억제조절, 집중 유지 |
| `nback0`…`nback3` | 일치(0-back 은 가운데 칸) | 작업기억(2-back d′) |
| `oddball` | 타깃(노란 삼각형) | 주의 정확성, 뇌 반응(P300: `stim` 마커 사용) |
| (확장) `verbal_*`, `stroop`, `flanker` … | 과제별 정의 | 2번 담당과 협의 후 축 추가 |

새 과제를 추가하면 ① 이 표 ② `config.HEX_AXES`/`HEX_REFERENCE` ③ 정답 판정 규칙을 같은 PR 에서 추가한다.
`pvt` 의 `trial` 마커에는 `false_start=0|1` 이 추가로 붙는다.

## 웹/앱에서 과제를 만들 때
브라우저는 LSL 을 직접 못 쏜다. 방법은 두 가지다.
1. (권장) 로컬 Python 서버(`server/`)에 WebSocket 으로 이벤트를 보내고, 서버가 `tasks/markers.py::MarkerOutlet` 으로 LSL 마커를 쏜다. 네트워크 지연은 수 ms 수준이라 블록·시행 단위 분석엔 충분하다(ERP 같은 ms 단위 분석엔 부족).
2. Unity 라면 LSL4Unity 로 직접 마커 송신 가능.
