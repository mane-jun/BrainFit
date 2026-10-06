# 측정 프로토콜 (실행 절차·품질 체크리스트)

> 과제 구성은 **docs/BATTERY.md** 의 Cognitive Battery(`tasks/battery.py`)가 기준이다.
> 아래 표는 N-back 단독 버전(`tasks/grid_nback.py`)이며, 실행 순서·품질 체크리스트는 두 버전에 공통이다.

## N-back 단독 버전 (약 15분)

목표: 한 번 앉아서 **1번(기준선)과 3번(인지 상태)** 데이터를 모두 얻는다. 시연 날에도 이 순서를 그대로 쓴다.

| 순서 | 단계 | 시간 | 마커 | 얻는 것 |
|---|---|---|---|---|
| 0 | 착용·신호 확인 | 2–3분 | – | BlueMuse 연결, 잡음 확인 |
| 1 | 눈 뜬 휴식(+ 응시) | 60초(가능하면 120초) | `rest_eo` | z 점수 기준, 상대 파워 |
| 2 | 눈 감은 휴식 | 60초(가능하면 120초) | `rest_ec` | IAF, 알파 반응성 |
| 3 | Grid N-back 6블록 (1,2,3,2,3,1) | 블록당 약 65초 + 휴식 15초 | `block`, `trial` | 난이도별 집중·부하, 행동 지표 |
| 4 | 과제 후 눈 감은 휴식 | 60초 | `rest_ec_post` | 피로(알파·세타 변화) |

블록 순서를 1→2→3 으로만 하면 "어려워서"인지 "지쳐서"인지 구분이 안 된다. 그래서 **ABCBCA 처럼 섞는다**(난이도 효과와 시간 효과를 분리). 0-back 을 넣고 싶으면 `--levels 0,2,3,0,3,2` 처럼 사용한다.

## 실행 순서
1. Muse 전원 → BlueMuse 에서 `Start Streaming` (LSL Bridge 에 EEG 스트림 확인)
2. `python tasks/battery.py --user <id> --mode standard` (노년층 `--mode senior`) → 대기 화면
3. LabRecorder: Study Root `C:\EEGData`, BIDS 해제 → `Update` → **Muse EEG + BrainFitMarkers 둘 다 체크** → `Start`
4. 과제 창에서 SPACE → 진행
5. 끝나면 LabRecorder `Stop` → `python scripts/analyze_session.py --xdf C:/EEGData/.../block_Default.xdf --user <id>`

## 신호 품질 체크리스트 (데이터 질의 80%는 여기서 결정)
- [ ] 이마 센서(AF7/AF8)가 머리카락 없이 피부에 닿는가. 건조하면 물티슈로 살짝 적신다.
- [ ] 귀 뒤 센서(TP9/TP10)에 머리카락이 끼지 않았는가 (가장 흔한 실패 원인).
- [ ] 휴대폰 Muse 앱과 동시 연결 금지 (BlueMuse 만 연결).
- [ ] 측정 중 말하기·턱 깨물기·껌 금지 → 근전도가 베타/감마를 오염.
- [ ] 노트북 충전기 분리 권장(60 Hz 잡음), 블루투스 거리 1 m 이내.
- [ ] 분석 결과 `01_quality.png` 에서 채널별 사용 가능 비율 60% 이상인지 확인. 미달이면 재착용 후 재측정.
- [ ] `02_baseline_spectrum.png` 에서 **눈 감은 쪽 곡선이 8–13 Hz 에서 위로 솟아야** 정상. 안 솟으면 TP 센서 접촉 불량을 의심.

## 참가자 윤리
- 측정 전 동의 받기(목적, 저장 기간, 익명 ID 사용, 언제든 중단 가능).
- 파일명·저장소엔 실명 대신 ID. 원본 데이터는 **공개 GitHub 에 올리지 않는다**(팀 드라이브 공유).
- 결과는 "학습·훈련 참고 지표"이며 진단이 아님을 안내.
