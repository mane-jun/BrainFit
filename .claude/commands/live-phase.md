---
description: 라이브 데모 웹 계획서의 한 단계(P1~P6)를 계획→구현→검증
---
단계: $ARGUMENTS   (예: P1)

1. docs/plans/2026-10-08-live-demo-web.md 에서 해당 단계와 '완료 조건'을, docs/LIVE_DEMO.md 에서 API·활동 명세·
   시각화 원칙(6절)을 읽어라. 백엔드 계약(server/live.py, brainfit/realtime/)은 바꾸지 않는 것이 원칙이다.
   바꿔야 하면 이유를 먼저 보고하고 승인받아라.
2. 이 단계의 작업 목록(파일, 컴포넌트, 테스트)을 10줄 이내로 제시하고 승인을 기다려라.
3. 승인 후 `feat/…` 브랜치에서 구현. 프런트는 web/ 안에서만 작업한다.
4. 검증: `pytest -q`, `ruff check .`, `cd web && npm run build && npm test`.
   그리고 `uvicorn server.main:app` + `npm run dev` 를 띄워 시뮬레이터로 해당 화면을 끝까지 진행한 결과를 보고하라.
5. 화면 문구는 docs/LIVE_DEMO.md 6절 표현 규칙을 따른다(뇌 부위 단정, 진단 표현 금지).
6. 완료 조건 체크리스트와 남은 문제를 보고하고 PR 본문 초안을 작성하라.
