# app/ — 앱 (형태 미정, 예비)

분석 엔진(brainfit)과 앱은 **summary.json 계약**으로만 연결한다. 앱이 무엇이 되든 아래 흐름은 같다.

```
[측정] tasks/battery.py (지금은 pygame) ──LSL──> LabRecorder ──> .xdf
[분석] POST /sessions/analyze (server/main.py) ──> summary.json + 그림 PNG
[표시] 앱 화면 ← summary.json
```

## 후보
| 형태 | 장점 | 단점 |
|---|---|---|
| Streamlit (`dashboard/`) | 이미 동작, 하루면 시연 화면 | 모바일·게임성 약함 |
| 웹(Next.js) + FastAPI | 팀 협업 쉬움, 반응형 | 과제를 웹으로 옮기면 마커를 WebSocket→서버→LSL 로 중계 필요 |
| Unity | 게임형 과제·연출에 강함, LSL4Unity 로 마커 직접 송신 | 분석 결과는 여전히 Python 서버 필요 |

## 화면 초안
1. 측정 안내(착용법, 신호 품질 표시) 2. 실시간 집중 게이지 3. 결과: 육각형, 종합 수행, 과제별 카드, 추천 4. 변화 추적(주차별 추세, RCI 기준 '의미 있는 변화')

모든 결과 화면에 "학습·훈련용 참고 지표이며 의학적 진단이 아닙니다" 표시.
