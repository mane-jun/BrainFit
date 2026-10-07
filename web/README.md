# BrainFit 라이브 웹

`feat/realtime`의 정식 웹 화면이다. 기존 `/static/debug.html`의 자동 응답 대신 참가자가 일곱 인지 활동을 직접 수행한다. 화면은 `server/live.py`의 REST API와 `/ws/live` WebSocket을 사용한다.

## 실행

저장소 루트에서 Python 의존성을 설치하고 웹을 빌드한다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd web
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

`http://127.0.0.1:8000`을 연다. 개발 중에는 FastAPI를 켜 둔 상태에서 `cd web; npm run dev`를 실행하면 `http://127.0.0.1:5173`에서 빠르게 확인할 수 있다. Vite는 `/api`, `/ws`, `/live-files`를 8000번 포트로 전달한다.

## 측정 흐름

1. 시뮬레이터, Muse 2 LSL, 녹화 재생 중 입력을 선택한다.
2. 센서 네 곳이 모두 70% 이상으로 3초 유지되면 착용 확인을 통과한다.
3. 눈 뜬/감은 휴식으로 기준선을 만든다. 시연 모드는 각 30초, 정식 모드는 각 60초다.
4. 오늘의 뇌파 성향을 본 뒤, 서버가 선택한 활동 3~5개를 실제로 수행한다. 다음 활동의 선택 이유를 매번 표시한다.
5. 각 시행은 `target`, `resp`, `correct`, `rt`와 필요한 추가 정보를 `/api/live/trial`로 전송한다. 서버는 활동별 요약과 최종 결과를 만든다.

활동은 Go/No-Go, 위치 기억(N-back), Oddball, PVT, Stroop, 암산, 단어 기억이다. Go/No-Go·N-back·Oddball·PVT에서는 Space 또는 반응 버튼을 누른다. Stroop·암산에서는 숫자 1~4 또는 선택 버튼을 사용한다. 단어 기억에서는 1(봤어요), 2(처음 봐요)를 선택한다. 150ms 미만 반응은 무효다.

## 검사

```powershell
cd web
npm test
npm run lint
npm run format:check
npm run build
```

브라우저 자극 시각은 P300 분석에 사용하지 않는다. 실제 Muse와 LabRecorder 동시 녹화, 파일럿 임계값 보정은 별도의 장비 검증 단계다.
