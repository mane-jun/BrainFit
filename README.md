# BrainFit (뇌피트) 🧠

Muse 2 뇌파와 인지 과제를 결합해 **기준 뇌파 → 인지 측정 → 취약 영역 → 맞춤 훈련 → 변화 추적**을 수행하는 2026 인공지능융합대학 메이커톤 프로젝트.

> 학습·훈련용 참고 지표이며 의학적 진단 도구가 아닙니다.

## 빠른 시작 (기기 없이)
```bash
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python scripts/analyze_session.py --synthetic --user demo      # outputs/ 에 그림 8장 + summary.json
python tasks/battery.py --auto --speed 60 --mode demo          # 과제 앱 자동 실행 테스트
```

## 라이브 데모 (본선용)
```bash
uvicorn server.main:app --reload     # http://localhost:8000 → 입력 '시뮬레이터'로 기기 없이 전체 흐름 확인
```
실제 Muse: BlueMuse Start Streaming 후 입력을 'Muse 2 (LSL)'로. 녹화 재생: `data/demo/synthetic_demo.npz`.
설계는 [LIVE_DEMO](docs/LIVE_DEMO.md), 웹 구현 계획은 [plans/2026-10-08-live-demo-web](docs/plans/2026-10-08-live-demo-web.md).

## 실측
1. Muse 2 → BlueMuse `Start Streaming`
2. `python tasks/battery.py --user p01 --mode standard` (노년층 `senior`, 시연 `demo`)
3. LabRecorder: Study Root `C:\EEGData`, BIDS 해제, Update → **Muse EEG + BrainFitMarkers** 체크 → Start → 과제 창에서 SPACE
4. `python scripts/analyze_session.py --xdf C:/EEGData/exp001/block_Default.xdf --user p01`

## 결과물
| 파일 | 내용 |
|---|---|
| 01_quality | 채널별 신호 품질 |
| 02_baseline_spectrum | 눈 뜸/감음 스펙트럼, IAF, 알파 반응성 (1번) |
| 03_band_timeline | 구간별 θ/α/β 변화 |
| 04_engagement | 집중 곡선, 지속 집중 (3번) |
| 05_blocks | 과제·블록별 집중, 감소 기울기, d′ |
| 06_fatigue | 피로 추세, 사전·사후 비교 |
| 07_profile | 육각형 Brain Profile |
| 08_erp | Oddball P300 |

## 문서
[LIVE_DEMO](docs/LIVE_DEMO.md) · [BATTERY](docs/BATTERY.md) · [PLAN](docs/PLAN.md) · [PROTOCOL](docs/PROTOCOL.md) · [MARKERS](docs/MARKERS.md) · [METRICS](docs/METRICS.md) · [EEG_PRIMER](docs/EEG_PRIMER.md) · [DATASETS](docs/DATASETS.md) · [GIT_SETUP](docs/GIT_SETUP.md) · [PROMPTS](docs/PROMPTS.md) · Claude Code 규칙: [CLAUDE.md](CLAUDE.md)
